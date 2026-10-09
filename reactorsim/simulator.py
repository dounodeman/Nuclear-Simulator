"""The simulator: one reactor, its plant systems and an operator interface.

Time advances in digital control cycles (default 50 ms). Each cycle the
protection system and controllers act on the latest instrument readings, then
the physics is integrated across the cycle in adaptive sub-steps, then the
instruments sample the new plant state.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy.optimize import brentq

from reactorsim.physics.burnup import Burnup
from reactorsim.physics.decay_heat import DecayHeat
from reactorsim.physics.kinetics import PointKinetics
from reactorsim.physics.poisons import Poisons, PoisonState
from reactorsim.physics.thermal import WATER_CP, PoolThermal, ThermalState
from reactorsim.plant.control import PowerServo
from reactorsim.plant.instruments import Instruments
from reactorsim.plant.protection import ProtectionOutput, ProtectionSystem
from reactorsim.plant.radiation import RadiationModel
from reactorsim.plant.rods import Rod
from reactorsim.reactors import get_design
from reactorsim.reactors.base import ReactorDesign


@dataclass
class Event:
    time: float
    kind: str  # "scram", "setback", "alarm", "operator", "limit"
    message: str


@dataclass
class _Ramp:
    remaining: float  # dk/k still to add
    rate: float  # dk/k per s


@dataclass
class _Snapshot:
    t: float
    power: float
    rods: dict
    reactivity: dict
    fuel_temp: float
    peak_fuel_temp: float
    core_temp: float
    pool_temp: float
    void: float
    level: float
    readings: dict
    scrammed: bool
    setback: bool


class Simulator:
    def __init__(self, design: ReactorDesign | str = "pur1", seed: int | None = None,
                 control_dt: float = 0.05, max_substep: float = 1.0):
        self.design = get_design(design) if isinstance(design, str) else design
        d = self.design
        self.control_dt = control_dt
        self.max_substep = max_substep
        self.kinetics = PointKinetics(d.delayed, d.generation_time)
        self.decay = DecayHeat()
        self.thermal_model = PoolThermal(d.thermal)
        self.poison_model = Poisons(d.sigma_f, d.sigma_a)
        self.burnup_model = Burnup(d.u235_mass_g, d.burnup_reactivity_per_fraction)
        self.rng = np.random.default_rng(seed) if seed is not None else None
        self.instruments = Instruments(d.instruments, self.rng)
        self.protection = ProtectionSystem(d.protection, d.rated_power)
        self.radiation = RadiationModel(d.radiation)
        self.servo = PowerServo()

        self.t = 0.0
        self.rods: dict[str, Rod] = {s.name: Rod(s) for s in d.rods}
        self.source_inserted = True
        self.thermal = ThermalState(d.initial_pool_temp, d.initial_pool_temp, d.initial_pool_temp)
        self.poisons = PoisonState()
        self.u235_g = d.u235_mass_g
        self.level_m = d.normal_level_m
        self.leak_rate_m_s = 0.0
        self.chiller_available = True
        self.external_reactivity = 0.0
        self._ramps: list[_Ramp] = []
        self.fuel_damage = 0.0
        self.max_peak_fuel_temp = self.thermal.fuel_temp
        self.energy_j = 0.0
        self.auto_range = False

        rho = self.reactivity()["total"]
        self.power = self._subcritical_power(rho)
        self.precursors = self.kinetics.equilibrium_precursors(self.power)
        self.decay_groups = np.zeros_like(self.decay.frac)

        self.scrammed = False
        self.scram_causes: list[str] = []
        self.setback_active = False
        self.setback_count = 0
        self.last_protection = ProtectionOutput()
        self.events: list[Event] = []
        self._active_alarms: set[str] = set()
        self._latched_alarms: set[str] = set()  # condition alarms raised by the simulator itself
        self._stop_positions: dict[str, float] = {}
        self._h = control_dt
        self.history: list[_Snapshot] = []
        self._sample_instruments(0.0)

    # ------------------------------------------------------------------ physics helpers

    def _source(self) -> float:
        d = self.design
        return d.source_strength if self.source_inserted else d.intrinsic_source

    def _subcritical_power(self, rho: float) -> float:
        if rho >= 0:
            return 1e-3
        return -self._source() * self.design.generation_time / rho

    def reactivity(self) -> dict[str, float]:
        """Breakdown of core reactivity (dk/k) at the current state."""
        d = self.design
        th = self.thermal
        covered = min(max((self.level_m + d.thermal.core_height_m) / d.thermal.core_height_m, 0.0), 1.0)
        void_pct = 100.0 * (th.void * covered + (1.0 - covered))
        parts = {
            "excess": d.excess_reactivity,
            "rods": -sum(r.inserted_worth() for r in self.rods.values()),
            "fuel_temp": d.alpha_fuel * (th.fuel_temp - d.reference_temp),
            "moderator_temp": d.alpha_moderator * (th.core_temp - d.reference_temp),
            "void": d.alpha_void * void_pct,
            "xenon": self.poison_model.xenon_worth(self.poisons),
            "samarium": self.poison_model.samarium_worth(self.poisons),
            "burnup": self.burnup_model.worth(self.u235_g),
            "experiments": self.external_reactivity,
        }
        parts["total"] = sum(parts.values())
        return parts

    def thermal_power(self) -> float:
        """Heat being deposited in the core: prompt fission heat plus decay heat (W)."""
        return (1.0 - self.decay.total_fraction) * self.power + float(self.decay_groups.sum())

    def peak_fuel_temp(self) -> float:
        return self.thermal_model.peak_fuel_temp(self.thermal)

    def _physics(self, dt: float) -> None:
        d = self.design
        t_left = dt
        h_min = 1e-6
        while t_left > 1e-12:
            h = min(self._h, t_left, self.max_substep)
            rods_before = copy.deepcopy(self.rods)
            ext_before = (self.external_reactivity, copy.deepcopy(self._ramps))
            rho0 = self.reactivity()["total"]
            for r in self.rods.values():
                r.advance(h)
            self._advance_ramps(h)
            rho1 = self.reactivity()["total"]
            rho = 0.5 * (rho0 + rho1)
            p1, c1 = self.kinetics.step(self.power, self.precursors, rho, self._source(), h)
            ratio = p1 / self.power if self.power > 0 else 1.0
            if (ratio > 1.1 or ratio < 1 / 1.1) and h > h_min:
                self.rods = rods_before
                self.external_reactivity, self._ramps = ext_before
                self._h = h / 4
                continue

            p_avg = 0.5 * (self.power + p1)
            self.power, self.precursors = p1, c1
            self.decay_groups = self.decay.step(self.decay_groups, p_avg, h)
            heat = (1.0 - self.decay.total_fraction) * p_avg + float(self.decay_groups.sum())
            self.level_m -= self.leak_rate_m_s * h
            self.thermal = self.thermal_model.step(self.thermal, heat, h, self.level_m,
                                                   self.chiller_available, d.chiller_setpoints)
            flux = d.flux_per_watt * p_avg
            self.poisons = self.poison_model.step(self.poisons, flux, h)
            self.u235_g -= self.burnup_model.consumption_rate_g_per_s(p_avg) * h
            self.energy_j += p_avg * h
            self._fuel_damage(h)
            self.radiation.step(h)

            self.t += h
            t_left -= h
            self._h = min(h * 1.5, self.max_substep)

    def _advance_ramps(self, h: float) -> None:
        for ramp in self._ramps:
            add = math.copysign(min(abs(ramp.rate) * h, abs(ramp.remaining)), ramp.remaining)
            self.external_reactivity += add
            ramp.remaining -= add
        self._ramps = [r for r in self._ramps if abs(r.remaining) > 1e-15]

    def _fuel_damage(self, h: float) -> None:
        limits = self.design.fuel_limits
        peak = self.peak_fuel_temp()
        if peak > self.max_peak_fuel_temp:
            if self.max_peak_fuel_temp <= limits["safety_limit"] < peak:
                self._event("limit", f"Fuel safety limit {limits['safety_limit']:.0f} C exceeded")
            self.max_peak_fuel_temp = peak
        over = peak - limits["blister"]
        if over > 0:
            rate = 0.002 * over + (0.05 if peak > limits["melt"] else 0.0)
            inc = min(rate * h, 1.0 - self.fuel_damage)
            if self.fuel_damage == 0 and inc > 0:
                self._event("limit", "Cladding blistering: fission products entering pool water")
            self.fuel_damage += inc
            self.radiation.add_release(inc)

    # ------------------------------------------------------------------ control cycle

    def _sample_instruments(self, dt: float) -> None:
        rad = self.radiation.dose_rates(self.thermal_power(), self.level_m)
        self.instruments.update(dt, self.power, self.thermal.pool_temp, self.level_m, rad)

    def _event(self, kind: str, message: str) -> None:
        self.events.append(Event(self.t, kind, message))

    def _rod_drift(self) -> float:
        worst = 0.0
        for name, rod in self.rods.items():
            moving = (rod.command != 0) or (rod.target is not None) or self.servo_drives(name)
            if moving or not rod.latched:
                self._stop_positions.pop(name, None)
                continue
            ref = self._stop_positions.setdefault(name, rod.drive_position)
            worst = max(worst, abs(rod.drive_position - ref))
        return worst

    def servo_drives(self, name: str) -> bool:
        return self.servo.enabled and name == self.design.regulating_rod

    def _control(self) -> None:
        d = self.design
        r = self.instruments.readings
        shutdown = self.power < 1e-3 * d.rated_power
        servo_err = self.servo.deviation
        out = self.protection.evaluate(r, self._rod_drift(), servo_err, shutdown)
        self.last_protection = out

        if out.scram_causes and not self.scrammed:
            self.scram(cause=out.scram_causes)
        elif out.scram_causes:
            for c in out.scram_causes:
                if c not in self.scram_causes:
                    self.scram_causes.append(c)

        setback = (bool(out.setback_causes) or (self.setback_active and not out.setback_clear)) \
            and not self.scrammed
        if setback and not self.setback_active:
            self._event("setback", "Setback: " + "; ".join(out.setback_causes))
            self.setback_count += 1
            self.servo.enabled = False
        if setback:
            for name in d.shim_rods:
                self.rods[name].target = None
                self.rods[name].command = -1
            self.rods[d.regulating_rod].target = None
            self.rods[d.regulating_rod].command = 0

        if self.setback_active and not setback:
            for name in d.shim_rods:
                self.rods[name].command = 0
        self.setback_active = setback

        new_alarms = set(out.alarms)
        for a in sorted(new_alarms - self._active_alarms):
            self._event("alarm", a)
        self._active_alarms = new_alarms | self._latched_alarms
        self._latched_alarms = set()

        # Servo on the regulating rod.
        reg = self.rods[d.regulating_rod]
        if self.servo.enabled and not self.scrammed:
            log_rate = 0.0 if not math.isfinite(r.ch2_period) else 1.0 / r.ch2_period
            reg.target = None
            reg.command = self.servo.command(r.ch3_power_w, log_rate)
            if reg.command == 1 and reg.drive_position >= reg.spec.length_cm - 1e-6:
                self._alarm_once("Regulating rod at upper limit")
            if reg.command == -1 and reg.drive_position <= 1e-6:
                self._alarm_once("Regulating rod at lower limit")

        # Rod withdrawal interlocks.
        blocked = bool(out.interlock_causes) or self.scrammed
        for name, rod in self.rods.items():
            wants_out = rod.command == 1 or (rod.target is not None and rod.target > rod.drive_position)
            if not wants_out:
                continue
            shim_limit = (name in d.shim_rods and not out.channels_operable
                          and rod.drive_position >= d.protection.shim_interlock_height_cm)
            if blocked or shim_limit:
                rod.command = 0
                rod.target = None

        if self.auto_range:
            indicated = r.ch3_power_w if r.ch3_percent_of_range < 100 else r.ch2_percent * d.rated_power / 100
            self.instruments.auto_range(indicated)

    def _alarm_once(self, msg: str) -> None:
        """Raise a simulator-generated alarm; it stays active while re-raised every cycle."""
        if msg not in self._active_alarms:
            self._event("alarm", msg)
        self._active_alarms.add(msg)
        self._latched_alarms.add(msg)

    def step(self, dt: float | None = None) -> None:
        """Advance one control cycle (or ``dt`` seconds, treated as one cycle)."""
        dt = self.control_dt if dt is None else dt
        self._control()
        self._physics(dt)
        self._sample_instruments(dt)

    def run(self, duration: float, dt: float | None = None, record_every: float | None = None,
            until: Callable[["Simulator"], bool] | None = None,
            each_step: Callable[["Simulator"], None] | None = None) -> None:
        """Run for ``duration`` seconds, optionally stopping early when ``until(sim)`` is true."""
        dt = self.control_dt if dt is None else dt
        record_every = dt if record_every is None else record_every
        end = self.t + duration
        next_record = self.t
        while self.t < end - 1e-9:
            if each_step is not None:
                each_step(self)
            self.step(min(dt, end - self.t))
            if self.t >= next_record - 1e-9:
                self.record()
                next_record = self.t + record_every
            if until is not None and until(self):
                self.record()
                break

    # ------------------------------------------------------------------ operator actions

    def drive(self, rod: str, direction: str) -> None:
        """Hold a rod drive switch: 'out', 'in' or 'stop'."""
        r = self.rods[rod]
        r.target = None
        r.command = {"out": 1, "in": -1, "stop": 0}[direction]

    def drive_to(self, rod: str, position_cm: float) -> None:
        r = self.rods[rod]
        r.command = 0
        r.target = min(max(position_cm, 0.0), r.spec.length_cm)

    def stop_all(self) -> None:
        for r in self.rods.values():
            r.command = 0
            r.target = None

    def scram(self, cause: str | list[str] = "Manual scram") -> None:
        causes = [cause] if isinstance(cause, str) else list(cause)
        if not self.scrammed:
            self._event("scram", "SCRAM: " + "; ".join(causes))
        self.scrammed = True
        self.scram_causes = causes
        self.servo.enabled = False
        for r in self.rods.values():
            r.target = None
            r.command = 0
            r.release()
        self.rods[self.design.regulating_rod].command = -1

    def reset_scram(self) -> bool:
        """Clear a scram if no trip condition remains. Drives must then be run in to re-latch."""
        if self.last_protection.scram_causes:
            return False
        self.scrammed = False
        self.scram_causes = []
        for r in self.rods.values():
            r.magnet_power = True
        self._event("operator", "Scram reset")
        return True

    def insert_source(self) -> None:
        self.source_inserted = True

    def withdraw_source(self) -> None:
        self.source_inserted = False

    def set_servo(self, enabled: bool, setpoint_w: float | None = None) -> None:
        if setpoint_w is not None and setpoint_w != self.servo.setpoint_w:
            self.servo.setpoint_w = setpoint_w
            self.servo.captured = False
        if enabled and not self.servo.enabled:
            self.servo.captured = False
        self.servo.enabled = enabled and not self.scrammed
        if not enabled:
            self.rods[self.design.regulating_rod].command = 0

    def insert_reactivity(self, amount: float, ramp_seconds: float = 0.0) -> None:
        """Add reactivity from an experiment (positive or negative), as a step or a linear ramp."""
        if ramp_seconds <= 0:
            self.external_reactivity += amount
        else:
            self._ramps.append(_Ramp(amount, amount / ramp_seconds))

    def set_channel_fault(self, channel: str, mode: str, value: float = 1.0) -> None:
        self.instruments.set_fault(channel, mode, value)
        self._event("operator", f"Fault injected: {channel} {mode}")

    def start_leak(self, rate_m_per_hour: float) -> None:
        self.leak_rate_m_s = rate_m_per_hour / 3600.0

    # ------------------------------------------------------------------ setup helpers

    def initialize_at_power(self, power_w: float, reg_position_cm: float | None = None,
                            xenon: str = "clean", history_hours: float = 4.0) -> None:
        """Put the reactor at steady critical power with rods at their critical heights.

        ``xenon`` is "clean" (no poisons) or "equilibrium" (long run at this power).
        The shims are moved together to the height that makes the core critical.
        """
        d = self.design
        self.source_inserted = False
        self.power = power_w
        self.precursors = self.kinetics.equilibrium_precursors(power_w)
        hist = history_hours * 3600.0
        self.decay_groups = self.decay.frac * power_w * (1 - np.exp(-self.decay.lam * hist))
        flux = d.flux_per_watt * power_w
        self.poisons = self.poison_model.equilibrium(flux) if xenon == "equilibrium" else PoisonState()
        if xenon == "equilibrium":
            self.poisons.samarium = 0.0  # samarium is part of the measured excess reactivity

        tp = self.thermal.pool_temp
        heat = power_w
        p = d.thermal
        w = self.thermal_model.natcirc_flow(heat)
        tc = tp + heat / (w * WATER_CP)
        tf = tc + heat * (1 - p.gamma_heat_fraction) / p.plate_conductance
        self.thermal = ThermalState(tf, tc, tp)

        reg = self.rods[d.regulating_rod]
        reg_pos = reg.spec.length_cm / 2 if reg_position_cm is None else reg_position_cm
        reg.position = reg.drive_position = reg_pos

        def rho_at(x):
            for n in d.shim_rods:
                self.rods[n].position = self.rods[n].drive_position = x
            return self.reactivity()["total"]

        L = self.rods[d.shim_rods[0]].spec.length_cm
        if rho_at(L) < 0:
            raise ValueError("core cannot be made critical at this power and xenon state")
        rho_at(brentq(rho_at, 0.0, L, xtol=1e-9))
        self.servo.setpoint_w = power_w
        self.instruments.auto_range(power_w)
        for _ in range(3):
            self._sample_instruments(self.control_dt)
        self.instruments.ch1_period.rate = 0.0
        self.instruments.ch2_period.rate = 0.0
        self._sample_instruments(0.0)

    # ------------------------------------------------------------------ reporting

    def record(self) -> None:
        r = self.instruments.readings
        self.history.append(_Snapshot(
            t=self.t,
            power=self.power,
            rods={n: rod.position for n, rod in self.rods.items()},
            reactivity=self.reactivity(),
            fuel_temp=self.thermal.fuel_temp,
            peak_fuel_temp=self.peak_fuel_temp(),
            core_temp=self.thermal.core_temp,
            pool_temp=self.thermal.pool_temp,
            void=self.thermal.void,
            level=self.level_m,
            readings={k: v for k, v in vars(r).items() if k != "downscale"},
            scrammed=self.scrammed,
            setback=self.setback_active,
        ))

    def history_arrays(self) -> dict[str, np.ndarray]:
        h = self.history
        out = {
            "t": np.array([s.t for s in h]),
            "power": np.array([s.power for s in h]),
            "fuel_temp": np.array([s.fuel_temp for s in h]),
            "peak_fuel_temp": np.array([s.peak_fuel_temp for s in h]),
            "core_temp": np.array([s.core_temp for s in h]),
            "pool_temp": np.array([s.pool_temp for s in h]),
            "void": np.array([s.void for s in h]),
            "level": np.array([s.level for s in h]),
            "scrammed": np.array([s.scrammed for s in h]),
        }
        if h:
            for k in h[0].reactivity:
                out[f"rho_{k}"] = np.array([s.reactivity[k] for s in h])
            for k in h[0].rods:
                out[f"rod_{k}"] = np.array([s.rods[k] for s in h])
            for k, v in h[0].readings.items():
                if isinstance(v, (int, float, bool)):
                    out[f"ind_{k}"] = np.array([s.readings[k] for s in h], dtype=float)
        return out

    def status(self) -> dict:
        rho = self.reactivity()
        r = self.instruments.readings
        return {
            "time_s": self.t,
            "power_w": self.power,
            "thermal_power_w": self.thermal_power(),
            "reactivity_dollars": rho["total"] / self.design.delayed.beta_total,
            "rods_cm": {n: round(rod.position, 2) for n, rod in self.rods.items()},
            "fuel_temp_c": self.thermal.fuel_temp,
            "peak_fuel_temp_c": self.peak_fuel_temp(),
            "pool_temp_c": self.thermal.pool_temp,
            "level_m": self.level_m,
            "scrammed": self.scrammed,
            "scram_causes": list(self.scram_causes),
            "setback": self.setback_active,
            "alarms": sorted(self._active_alarms),
            "ch2_period_s": r.ch2_period,
            "fuel_damage": self.fuel_damage,
        }

    # ------------------------------------------------------------------ technical specification checks

    def shutdown_margin(self) -> float:
        """Shutdown margin (dk/k) with the most reactive shim and the regulating rod fully withdrawn,
        evaluated for the cold clean core as the technical specifications define it."""
        d = self.design
        worths = sorted((self.rods[n].spec.worth for n in d.shim_rods), reverse=True)
        remaining = sum(worths[1:])
        return -(d.excess_reactivity - remaining)
