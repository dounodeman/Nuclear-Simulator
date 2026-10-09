"""A live simulator session: the reactor advancing in real time under operator commands.

The session owns one ``Simulator`` and a background thread that steps it in
digital control cycles paced to the wall clock (times a speed factor). The
control-room page reads ``state()`` and sends ``command()`` calls; both take
the same lock as the stepping thread, so every command lands between cycles,
the way an operator's switch is read by the real digital control system.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque

import numpy as np

from reactorsim.simulator import Simulator

TICK_S = 0.05  # wall-clock pacing of the stepping loop
TREND_EVERY_S = 0.5  # simulated seconds between trend samples
TREND_LEN = 7200  # one simulated hour at TREND_EVERY_S
SPEEDS = (0.0, 1.0, 2.0, 5.0, 10.0, 30.0, 100.0)

INITIAL_STATES = {
    "cold": "Cold shutdown: rods in, source in, 22 C pool",
    "critical_1kw": "Critical at 1 kW, rods banked, servo off",
    "power_10kw": "Steady at 10 kW on the servo",
}


def _num(v):
    """JSON-safe number: infinities and NaN become None."""
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        v = float(v)
        return v if math.isfinite(v) else None
    return v


class CommandError(ValueError):
    pass


class SimSession:
    def __init__(self, initial: str = "cold", design: str = "pur1", seed: int | None = None):
        self.design_key = design
        self._seed = seed
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.speed = 1.0
        self.reset(initial)

    # ------------------------------------------------------------------ lifecycle

    def reset(self, initial: str = "cold") -> None:
        if initial not in INITIAL_STATES:
            raise CommandError(f"unknown initial state {initial!r}")
        seed = self._seed if self._seed is not None else int(time.time() * 1e3) % 2**31
        sim = Simulator(self.design_key, seed=seed)
        if initial == "critical_1kw":
            sim.initialize_at_power(1_000.0)
        elif initial == "power_10kw":
            sim.initialize_at_power(10_000.0, reg_position_cm=30.0)
            sim.set_servo(True, 10_000.0)
        # Range the linear channel to the starting power and let the count-rate and period
        # meters settle (instruments only, plant time does not advance), so a noisy first
        # reading cannot trip the period scram the moment the session starts.
        sim.instruments.auto_range(sim.power)
        for _ in range(int(60.0 / sim.control_dt)):
            sim._sample_instruments(sim.control_dt)
        with self._lock:
            self.sim = sim
            self.initial = initial
            self.trend: deque[tuple] = deque(maxlen=TREND_LEN)
            self._next_trend = 0.0
            self._sample_trend()
            self.sim._event("operator", f"Session started: {INITIAL_STATES[initial]}")

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="reactorsim-session", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _loop(self) -> None:
        next_tick = time.monotonic()
        while not self._stop.is_set():
            next_tick += TICK_S
            self.advance(self.speed * TICK_S)
            delay = next_tick - time.monotonic()
            if delay > 0:
                self._stop.wait(delay)
            else:
                next_tick = time.monotonic()  # fell behind (slow machine or high speed): don't spiral

    def advance(self, sim_seconds: float) -> None:
        """Step the simulator by ``sim_seconds`` of plant time in control cycles."""
        with self._lock:
            sim = self.sim
            end = sim.t + sim_seconds
            while sim.t < end - 1e-9:
                sim.step(min(sim.control_dt, end - sim.t))
                if sim.t >= self._next_trend - 1e-9:
                    self._sample_trend()

    def _sample_trend(self) -> None:
        s = self.sim
        r = s.instruments.readings
        self.trend.append((round(s.t, 3), s.power, r.ch2_percent, r.ch4_percent,
                           s.peak_fuel_temp(), s.thermal.pool_temp))
        self._next_trend = s.t + TREND_EVERY_S

    # ------------------------------------------------------------------ state for the page

    def state(self, events_after: int = 0, trend_after: float = -1.0) -> dict:
        with self._lock:
            s = self.sim
            d = s.design
            r = s.instruments.readings
            rho = s.reactivity()
            beta = d.delayed.beta_total
            prot = s.last_protection
            rods = {}
            for name, rod in s.rods.items():
                rods[name] = {
                    "position_cm": rod.position,
                    "drive_cm": rod.drive_position,
                    "travel_cm": rod.spec.length_cm,
                    "latched": rod.latched,
                    "falling": rod.falling,
                    "moving": rod.command != 0 or rod.target is not None or rod.runaway,
                    "command": rod.command,
                    "stuck": rod.stuck,
                    "runaway": rod.runaway,
                    "worth_dollars": rod.inserted_worth() / beta,
                    "scrammable": rod.spec.scrammable,
                }
            events = [{"i": i, "t": e.time, "kind": e.kind, "message": e.message}
                      for i, e in enumerate(s.events) if i >= events_after]
            trend = [t for t in self.trend if t[0] > trend_after]
            out = {
                "reactor": {"key": d.key, "name": d.name, "rated_w": d.rated_power,
                            "licensed_w": d.licensed_power},
                "initial": self.initial,
                "time_s": s.t,
                "speed": self.speed,
                "true": {
                    "power_w": s.power,
                    "thermal_power_w": s.thermal_power(),
                    "fuel_temp_c": s.thermal.fuel_temp,
                    "peak_fuel_temp_c": s.peak_fuel_temp(),
                    "core_temp_c": s.thermal.core_temp,
                    "pool_temp_c": s.thermal.pool_temp,
                    "void_fraction": s.thermal.void,
                    "level_m": s.level_m,
                    "fuel_damage": s.fuel_damage,
                    "energy_kwh": s.energy_j / 3.6e6,
                    "xenon_dollars": rho["xenon"] / beta,
                },
                "reactivity_dollars": {k: v / beta for k, v in rho.items()},
                "channels": {
                    "ch1_cps": r.ch1_cps, "ch1_period_s": r.ch1_period, "ch1_saturated": r.ch1_saturated,
                    "ch2_percent": r.ch2_percent, "ch2_period_s": r.ch2_period, "ch2_hv_ok": r.ch2_hv_ok,
                    "ch3_range": r.ch3_range, "ch3_range_w": r.ch3_range_w,
                    "ch3_percent_of_range": r.ch3_percent_of_range, "ch3_power_w": r.ch3_power_w,
                    "ch4_percent": r.ch4_percent,
                    "auto_range": s.auto_range,
                    "faults": {c: f.mode for c, f in s.instruments.faults.items()},
                },
                "process": {
                    "pool_temp_c": r.pool_temp, "pool_level_m": r.pool_level_m,
                    "chiller_available": s.chiller_available,
                    "leak_m_per_hour": s.leak_rate_m_s * 3600.0,
                },
                "radiation_mr_h": {"pool_top": r.rad_pool_top, "console": r.rad_console,
                                   "water": r.rad_water, "air": r.rad_air},
                "rods": rods,
                "regulating_rod": d.regulating_rod,
                "shim_rods": list(d.shim_rods),
                "servo": {"enabled": s.servo.enabled, "setpoint_w": s.servo.setpoint_w,
                          "error": s.servo.error},
                "source_inserted": s.source_inserted,
                "scrammed": s.scrammed,
                "scram_causes": list(s.scram_causes),
                "setback": s.setback_active,
                "interlocks": list(prot.interlock_causes),
                "alarms": sorted(s._active_alarms),
                "protection": {"enabled": s.protection.enabled,
                               "failed_trips": sorted(s.protection.failed_trips)},
                "events": events,
                "event_count": len(s.events),
                "trend": trend,
            }
        return _clean(out)

    # ------------------------------------------------------------------ operator and instructor commands

    def command(self, action: str, **a) -> dict:
        if action == "reset":
            self.reset(a.get("initial", "cold"))
            return {"ok": True}
        with self._lock:
            s = self.sim
            rods = s.rods
            if action == "speed":
                speed = float(a["speed"])
                if speed not in SPEEDS:
                    raise CommandError(f"speed must be one of {SPEEDS}")
                self.speed = speed
            elif action == "drive":
                self._rod(a["rod"])
                if a["direction"] not in ("out", "in", "stop"):
                    raise CommandError("direction must be out, in or stop")
                if s.servo_drives(a["rod"]) and a["direction"] != "stop":
                    raise CommandError("The servo is driving the regulating rod; switch it to manual first")
                s.drive(a["rod"], a["direction"])
            elif action == "drive_to":
                self._rod(a["rod"])
                s.drive_to(a["rod"], float(a["position_cm"]))
            elif action == "stop_all":
                s.stop_all()
            elif action == "scram":
                s.scram("Manual scram (console)")
            elif action == "reset_scram":
                if not s.reset_scram():
                    raise CommandError("Scram cannot be reset while a trip condition remains: "
                                       + "; ".join(s.last_protection.scram_causes))
            elif action == "source":
                s.insert_source() if a["inserted"] else s.withdraw_source()
                s._event("operator", "Source inserted" if a["inserted"] else "Source withdrawn")
            elif action == "servo":
                setpoint = a.get("setpoint_w")
                if setpoint is not None and not 0 < float(setpoint) <= s.design.licensed_power:
                    raise CommandError("Servo setpoint must be above 0 and at most the licensed power")
                if a["enabled"] and s.scrammed:
                    raise CommandError("Reset the scram before engaging the servo")
                s.set_servo(bool(a["enabled"]), None if setpoint is None else float(setpoint))
                s._event("operator", f"Servo {'on' if a['enabled'] else 'off'}, setpoint "
                                     f"{s.servo.setpoint_w:.4g} W")
            elif action == "range":
                step = a["step"]
                if step == "up":
                    s.instruments.range_up()
                elif step == "down":
                    s.instruments.range_down()
                elif step == "auto":
                    s.auto_range = bool(a.get("enabled", not s.auto_range))
                else:
                    raise CommandError("step must be up, down or auto")
                if step != "auto":
                    s.auto_range = False
            # ---- instructor: experiments, faults and equipment failures ----
            elif action == "experiment":
                dollars = float(a["dollars"])
                if abs(dollars) > 5:
                    raise CommandError("Experiment worth is limited to +/- $5 in the simulator")
                ramp = float(a.get("ramp_s", 0.0))
                s.insert_reactivity(dollars * s.design.delayed.beta_total, ramp)
                s._event("operator", f"Experiment {dollars:+.2f} $ inserted"
                                     + (f" over {ramp:g} s" if ramp > 0 else ""))
            elif action == "chiller":
                s.chiller_available = bool(a["available"])
                s._event("operator", "Chiller " + ("restored" if s.chiller_available else "tripped"))
            elif action == "leak":
                rate = float(a["m_per_hour"])
                if not 0 <= rate <= 20:
                    raise CommandError("Leak rate must be 0 to 20 m/h")
                s.start_leak(rate)
                s._event("operator", f"Pool leak {rate:g} m/h" if rate else "Pool leak stopped")
            elif action == "channel_fault":
                try:
                    s.set_channel_fault(a["channel"], a["mode"], float(a.get("value", 1.0)))
                except ValueError as e:
                    raise CommandError(str(e)) from None
            elif action == "rod_fault":
                rod = self._rod(a["rod"])
                fault = a["fault"]
                if fault not in ("none", "stuck", "runaway"):
                    raise CommandError("fault must be none, stuck or runaway")
                rod.stuck = fault == "stuck"
                rod.runaway = fault == "runaway"
                s._event("operator", f"Fault: {a['rod']} drive " + ("cleared" if fault == "none" else fault))
            elif action == "protection":
                if "enabled" in a:
                    s.protection.enabled = bool(a["enabled"])
                if "failed_trips" in a:
                    trips = set(a["failed_trips"])
                    if not trips <= {"period", "radiation"}:
                        raise CommandError("failed trips must be period or radiation")
                    s.protection.failed_trips = trips
                s._event("operator", "Protection system " + ("in service" if s.protection.enabled
                                                             else "FAILED (no protective action)"))
            else:
                raise CommandError(f"unknown action {action!r}")
        return {"ok": True}

    def _rod(self, name: str):
        try:
            return self.sim.rods[name]
        except KeyError:
            raise CommandError(f"unknown rod {name!r}") from None


def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    return _num(obj)
