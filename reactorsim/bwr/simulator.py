"""Boiling water reactor simulator: one BWR, its vessel and plant systems, and an operator interface.

The reactor core is point kinetics with Doppler, moderator and void feedback, xenon and
samarium, decay heat and burnup, shared with the pool-reactor engine. Around it sits a
lumped plant model:

* fuel         - one heat-capacity node for the fuel, conducting to boiling coolant
* core         - inlet subcooling, boiling boundary, exit quality and a core-average void
                 that lags its steady value (the void sweep time); void swell in the
                 separators raises the downcomer level
* vessel       - one dome pressure, driven by steam made in the core less steam leaving,
                 with the saturated liquid condensing or flashing as pressure moves
* recirculation- two pumps driving jet pumps, plus natural circulation, giving core flow
* steam lines  - MSIVs, turbine stop and control valves under a pressure regulator,
                 bypass valves to the condenser, safety/relief valves to the torus
* feedwater    - three-element level control, feed pump trips, heater loss on a trip
* ECCS         - HPCI, RCIC, core spray, LPCI and automatic depressurization at their
                 level and pressure permissives
* protection   - the reactor protection system scrams, isolation and ECCS initiation
                 signals at the design's set points

Time advances in control cycles (default 50 ms) exactly like the pool simulator: logic
first, then physics in adaptive sub-steps, then a record.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy.optimize import brentq

from reactorsim.bwr.design import BWRDesign
from reactorsim.physics import steam
from reactorsim.physics.burnup import Burnup
from reactorsim.physics.decay_heat import DecayHeat
from reactorsim.physics.kinetics import PointKinetics
from reactorsim.physics.poisons import Poisons, PoisonState
from reactorsim.reactors import get_design

IN = 0.0254
WATER_CP = 4800.0  # J/kg-K for hot liquid
ECCS_WATER_C = 40.0
RCIC_STEAM_KG_S = 6.0  # turbine steam draw while running
HPCI_STEAM_KG_S = 45.0


@dataclass
class Event:
    time: float
    kind: str  # "scram", "trip", "alarm", "operator", "limit", "eccs"
    message: str


@dataclass
class RodBank:
    """All control rods moved as one bank. ``withdrawn_cm`` runs 0 (full in) to the full stroke."""
    stroke_cm: float
    speed_cm_s: float
    withdrawn_cm: float = 0.0
    command: int = 0  # +1 withdraw, -1 insert, 0 hold
    target_cm: float | None = None
    scram_fraction: float = 0.0  # extra insertion by the scram, 0..1 of the remaining travel
    scram_time: float | None = None  # time the scram insertion started

    @property
    def notch(self) -> float:
        return self.withdrawn_cm / self.stroke_cm

    def inserted_fraction(self) -> float:
        f = 1.0 - self.withdrawn_cm / self.stroke_cm
        return f + (1.0 - f) * self.scram_fraction


def _s_curve(f: float) -> float:
    """Integral rod worth as a fraction of the total for an inserted fraction ``f``."""
    f = min(max(f, 0.0), 1.0)
    return f - math.sin(2 * math.pi * f) / (2 * math.pi)


@dataclass
class Pump:
    speed: float = 0.0  # fraction of rated
    demand: float = 0.0
    tripped: bool = False


@dataclass
class Injection:
    """One ECCS pump or turbine-driven injection system."""
    name: str
    available: bool = True
    running: bool = False
    start_time: float | None = None
    manual: bool = False  # operator start overrides the auto logic
    flow: float = 0.0  # kg/s delivered last step


@dataclass
class _Snapshot:
    t: float
    power: float
    thermal_power: float
    pressure: float
    level_in: float
    core_flow: float
    void: float
    fuel_temp: float
    peak_fuel_temp: float
    steam_flow: float
    feed_flow: float
    eccs_flow: float
    rods: float
    reactivity: dict
    torus_temp: float
    scrammed: bool


class BWRSimulator:
    def __init__(self, design: BWRDesign | str = "peach_bottom_2", seed: int | None = None,
                 control_dt: float = 0.05, max_substep: float = 0.05):
        d = get_design(design) if isinstance(design, str) else design
        if getattr(d, "kind", None) != "bwr":
            raise TypeError(f"{d.key!r} is not a BWR design; use reactorsim.Simulator")
        self.design: BWRDesign = d
        self.control_dt = control_dt
        self.max_substep = max_substep
        self.rng = np.random.default_rng(seed) if seed is not None else None
        self.kinetics = PointKinetics(d.delayed, d.generation_time)
        self.decay = DecayHeat(d.decay_heat_at_shutdown)
        self.poison_model = Poisons(d.sigma_f, d.sigma_a)
        self.burnup_model = Burnup(d.u235_mass_g, d.burnup_reactivity_per_fraction)
        sp = d.setpoints
        p0 = d.dome_pressure_setpoint_pa

        self.t = 0.0
        self.power = 1e-3
        self.precursors = self.kinetics.equilibrium_precursors(self.power)
        self.decay_groups = np.zeros_like(self.decay.frac)
        self.poisons = PoisonState()
        self.u235_g = d.u235_mass_g
        self.external_reactivity = 0.0

        self.rods = RodBank(d.notches * d.notch_cm, d.rod_speed_cm_s)
        self.fuel_temp = steam.t_sat(p0)
        self.pressure = p0
        self.void = 0.0
        self.exit_void = 0.0
        self.liquid_mass = d.liquid_mass
        self.inlet_enthalpy = steam.h_f(p0)
        self.downcomer_enthalpy = self.inlet_enthalpy
        self.condensing_temp = steam.t_sat(p0)  # saturated liquid that follows the dome pressure, lagged
        self.core_flow = 0.0
        self.steam_generation = 0.0
        self.steam_out = 0.0
        self.boiling_boundary = 1.0
        self._void_volume0 = 0.0
        self.core_cover = 1.0
        self._void_at_rated = 0.3

        self.pumps = [Pump(), Pump()]
        self.mode = "run"  # mode switch: "run" or "startup"
        self.msiv = 1.0
        self.msiv_closing = False
        self.tsv = 1.0
        self.tcv = 0.0
        self.bypass = 0.0
        self.bypass_available = True
        self.turbine_tripped = False
        self.pressure_regulator_pa = p0
        self.regulator_band_pa = 20.0 * steam.PSI
        self.srv_open = [False] * len(d.srv_setpoints_psig)
        self.srv_manual = [False] * len(d.srv_setpoints_psig)
        self.srv_flow = 0.0
        self.feed_flow = 0.0
        self.feed_demand = 0.0
        self.feed_tripped = False
        self.feed_available = True
        self.level_setpoint_in = d.normal_level_in
        self.level_in = d.normal_level_in
        self.feed_temp = d.feedwater_temp_c
        self.condenser_available = True
        self.torus_temp = d.torus_initial_temp

        e = d.eccs
        self.hpci = Injection("HPCI")
        self.rcic = Injection("RCIC")
        self.core_spray = Injection("Core spray")
        self.lpci = Injection("LPCI")
        self.ads_armed_at: float | None = None
        self.ads_inhibited = False
        self.ads_open = False
        self.eccs_flow = 0.0
        self.level2_latched = False
        self.level1_latched = False

        self.rps_enabled = True
        self.tsv_scram_enabled = True  # the 1977 tests ran with this direct scram bypassed
        self.scrammed = False
        self.scram_causes: list[str] = []
        self._pending_release: float | None = None
        self.events: list[Event] = []
        self._active_alarms: set[str] = set()
        self.fuel_damage = 0.0
        self.max_peak_fuel_temp = self.fuel_temp
        self.energy_j = 0.0
        self.history: list[_Snapshot] = []
        self._h = control_dt
        self._update_level()

    # ------------------------------------------------------------------ reactivity

    def rod_worth_inserted(self) -> float:
        return self.design.rod_bank_worth * _s_curve(self.rods.inserted_fraction())

    def reactivity(self) -> dict[str, float]:
        d = self.design
        t_liq = steam.t_sat(self.pressure) - (steam.h_f(self.pressure) - self.inlet_enthalpy) / WATER_CP
        void_pct = 100.0 * (self.void * self.core_cover + (1.0 - self.core_cover))
        parts = {
            "excess": d.excess_reactivity,
            "rods": -self.rod_worth_inserted(),
            "fuel_temp": d.fuel_coefficient * (self.fuel_temp - d.reference_temp),
            "moderator_temp": d.moderator_coefficient * (t_liq - d.reference_temp),
            "void": d.alpha_void * void_pct,
            "xenon": self.poison_model.xenon_worth(self.poisons),
            "samarium": self.poison_model.samarium_worth(self.poisons),
            "burnup": self.burnup_model.worth(self.u235_g),
            "experiments": self.external_reactivity,
        }
        parts["total"] = sum(parts.values())
        return parts

    def thermal_power(self) -> float:
        return (1.0 - self.decay.total_fraction) * self.power + float(self.decay_groups.sum())

    # ------------------------------------------------------------------ plant helpers

    def _core_flow(self) -> float:
        d = self.design
        # Natural circulation is driven by the void head in the core and risers, so it follows
        # the (lagged) void rather than the power; single-phase convection keeps a trickle going.
        void_ref = self._void_at_rated
        nat = d.natural_circulation_fraction * (0.15 + 0.85 * math.sqrt(min(self.void / void_ref, 2.0)))
        pump = (1.0 - d.natural_circulation_fraction) * 0.5 * sum(p.speed for p in self.pumps)
        return d.rated_core_flow * (nat + pump)

    def _void_profile(self, heat: float, flow: float, p: float) -> tuple[float, float, float]:
        """Steady core-average void, exit void and boiling boundary for a given heat and flow."""
        d = self.design
        hf, hfg = steam.h_f(p), steam.h_fg(p)
        rg_rf = steam.rho_g(p) / steam.rho_f(p)
        q_sub = flow * max(hf - self.inlet_enthalpy, 0.0)
        if heat <= 0 or flow <= 0:
            return 0.0, 0.0, 1.0
        zb = min(q_sub / heat, 1.0)
        x_exit = max(heat - q_sub, 0.0) / (flow * hfg)
        if x_exit <= 0:
            return 0.0, 0.0, zb
        z = np.linspace(0.0, 1.0, 21)
        x = np.clip((z - zb) / max(1.0 - zb, 1e-9), 0.0, None) * x_exit
        alpha = x / (x + (1.0 - x) * d.slip_ratio * rg_rf)
        return float(np.mean(0.5 * (alpha[1:] + alpha[:-1]))), float(alpha[-1]), zb

    def _void_at(self, heat: float, flow: float, p: float, h_fw: float) -> tuple[float, float, float]:
        """Steady void for a power and flow with the feed matched to the steam (for references)."""
        saved = self.inlet_enthalpy
        gen = heat / (steam.h_g(p) - h_fw)
        self.inlet_enthalpy = steam.h_f(p) - gen * (steam.h_f(p) - h_fw) / flow
        out = self._void_profile(heat, flow, p)
        self.inlet_enthalpy = saved
        return out

    def _update_level(self) -> None:
        d = self.design
        swell = d.core_coolant_volume * self.void + d.separator_volume * self.exit_void
        dv = (self.liquid_mass - d.liquid_mass) / steam.rho_f(self.pressure) + swell - self._void_volume0
        self.level_in = d.normal_level_in + dv / d.downcomer_area / IN
        self.core_cover = min(max((self.level_in - d.baf_level_in) / (d.taf_level_in - d.baf_level_in), 0.0), 1.0)

    def _steam_flows(self, p: float) -> tuple[float, float, float, float]:
        """Steam leaving the vessel (kg/s): turbine, bypass, SRVs, ECCS turbines."""
        d = self.design
        rated = self._rated_steam_flow()
        turbine = 1.05 * rated * (p / d.dome_pressure_setpoint_pa) * self.tcv * self.tsv * self.msiv
        bypass = d.bypass_fraction * rated * (p / d.dome_pressure_setpoint_pa) * self.bypass * self.msiv
        srv = 0.0
        for i, sp in enumerate(d.srv_setpoints_psig):
            if self.srv_open[i]:
                srv += d.srv_capacity_kg_s * p / steam.from_psig(sp)
        eccs = (RCIC_STEAM_KG_S if self.rcic.running else 0.0) + (HPCI_STEAM_KG_S if self.hpci.running else 0.0)
        return turbine, bypass, srv, eccs

    def _rated_steam_flow(self) -> float:
        d = self.design
        p = d.dome_pressure_setpoint_pa
        return d.rated_power / (steam.h_g(p) - steam.h_liquid(d.feedwater_temp_c, p))

    def peak_fuel_temp(self) -> float:
        d = self.design
        t_cool = steam.t_sat(self.pressure)
        return t_cool + (self.fuel_temp - t_cool) * d.hot_channel_factor

    # ------------------------------------------------------------------ physics

    def _physics(self, dt: float) -> None:
        d = self.design
        t_left = dt
        while t_left > 1e-12:
            h = min(self._h, t_left, self.max_substep)
            rods_before = (self.rods.withdrawn_cm, self.rods.scram_fraction)
            rho0 = self.reactivity()["total"]
            self._advance_rods(h)
            rho1 = self.reactivity()["total"]
            rho = 0.5 * (rho0 + rho1)
            p1, c1 = self.kinetics.step(self.power, self.precursors, rho, d.intrinsic_source, h)
            ratio = p1 / self.power if self.power > 0 else 1.0
            if (ratio > 1.1 or ratio < 1 / 1.1) and h > 1e-5:
                self.rods.withdrawn_cm, self.rods.scram_fraction = rods_before
                self._h = h / 4
                continue
            p_avg = 0.5 * (self.power + p1)
            self.power, self.precursors = p1, c1
            self.decay_groups = self.decay.step(self.decay_groups, p_avg, h)
            heat = (1.0 - self.decay.total_fraction) * p_avg + float(self.decay_groups.sum())
            self._plant(heat, h)
            flux = d.flux_per_watt * p_avg
            self.poisons = self.poison_model.step(self.poisons, flux, h)
            self.u235_g -= self.burnup_model.consumption_rate_g_per_s(p_avg) * h
            self.energy_j += p_avg * h
            self._fuel_damage(h)
            self.t += h
            t_left -= h
            self._h = min(h * 1.5, self.max_substep)

    def _advance_rods(self, h: float) -> None:
        r = self.rods
        if r.scram_time is not None:
            r.scram_fraction = min((self.t - r.scram_time + h) / self.design.setpoints.scram_stroke_s, 1.0)
            return
        if r.target is not None:
            step = min(abs(r.target - r.withdrawn_cm), r.speed_cm_s * h)
            r.withdrawn_cm += math.copysign(step, r.target - r.withdrawn_cm)
            if abs(r.target - r.withdrawn_cm) < 1e-9:
                r.target = None
        elif r.command:
            r.withdrawn_cm = min(max(r.withdrawn_cm + r.command * r.speed_cm_s * h, 0.0), r.stroke_cm)

    def _plant(self, heat: float, h: float) -> None:
        d = self.design
        p = self.pressure
        tsat = steam.t_sat(p)
        hf, hg, hfg = steam.h_f(p), steam.h_g(p), steam.h_fg(p)

        # Recirculation pumps and core flow.
        for pump in self.pumps:
            if pump.tripped:
                pump.speed *= math.exp(-h / d.pump_coastdown)
            else:
                pump.speed += (pump.demand - pump.speed) * (1 - math.exp(-h / d.pump_time_constant))
        self.core_flow = self._core_flow()

        # Fuel node: implicit in the fuel temperature, conducting to the coolant at saturation.
        cover = self.core_cover
        ua = d.fuel_conductance * (cover + 0.004 * (1 - cover))  # steam cooling of uncovered fuel
        q_direct = d.gamma_fraction * heat * cover
        tf = (self.fuel_temp + h / d.fuel_heat_capacity * ((1 - d.gamma_fraction) * heat + ua * tsat)) \
            / (1 + h * ua / d.fuel_heat_capacity)
        q_fc = ua * (tf - tsat)
        self.fuel_temp = tf
        q_cool = max(q_fc + q_direct, 0.0)

        # Feedwater and ECCS injection set the inlet enthalpy after a downcomer transit.
        self.feed_flow += (self.feed_demand - self.feed_flow) * (1 - math.exp(-h / d.feedwater_time_constant))
        inj = self.feed_flow * steam.h_liquid(self.feed_temp, p) + self.eccs_flow * steam.h_liquid(ECCS_WATER_C, p)
        w_in = self.feed_flow + self.eccs_flow
        flow = self.core_flow
        h_in_ss = hf - (w_in * hf - inj) / max(flow, w_in, 1.0) if w_in > 0 else hf
        h_in_ss = min(h_in_ss, hf)
        # Feed and injection mix into the downcomer, then the lower plenum, before the core sees them.
        k_t = 1 - math.exp(-h / (0.5 * d.downcomer_transit_s))
        self.downcomer_enthalpy += (h_in_ss - self.downcomer_enthalpy) * k_t
        self.inlet_enthalpy += (self.downcomer_enthalpy - self.inlet_enthalpy) * k_t
        self.inlet_enthalpy = min(self.inlet_enthalpy, hf)

        # Core boiling: steam generation, void profile (lagged), level swell.
        q_sub = flow * max(hf - self.inlet_enthalpy, 0.0)
        gen = max(q_cool - q_sub, 0.0) / hfg
        alpha_ss, exit_ss, zb = self._void_profile(q_cool, flow, p)
        # The void lags its steady value by about half the core transit time, which grows as the
        # flow falls.
        tau = d.void_time_constant * math.sqrt(d.rated_core_flow / max(flow, 0.05 * d.rated_core_flow))
        k = 1 - math.exp(-h / tau)
        self.void += (alpha_ss - self.void) * k
        self.exit_void += (exit_ss - self.exit_void) * k
        self.boiling_boundary = zb
        self.steam_generation = gen

        # Vessel pressure: steam made less steam leaving, buffered by the dome volume and by the
        # saturated liquid that must warm (or flash) as the saturation temperature moves.
        turbine, bypass, srv, eccs_steam = self._steam_flows(p)
        out = turbine + bypass + srv + eccs_steam
        self.steam_out = out
        self.srv_flow = srv
        # The liquid warms (condensing steam) or cools (flashing) toward saturation over a few
        # seconds, so a fast pressure wave sees only the steam space while a slow pressurization
        # is buffered by the whole saturated inventory.
        k_c = 1 - math.exp(-h / d.condensing_time_constant)
        dt_c = (tsat - self.condensing_temp) * k_c
        self.condensing_temp += dt_c
        w_cond = d.condensing_mass * WATER_CP * dt_c / hfg / h
        self.pressure = max(p + (gen - out - w_cond) / (d.steam_volume * steam.drho_g_dp(p)) * h, 1.2e5)

        # Inventory and level.
        self.liquid_mass += (w_in - out) * h
        self._update_level()

        # Torus heats up with every kilogram the SRVs dump into it.
        if srv > 0:
            h_pool = 4186.0 * self.torus_temp  # enthalpy of the pool water above 0 C
            self.torus_temp += srv * (hg - h_pool) / (d.torus_water_mass * 4186.0) * h

        # Feedwater heaters follow the turbine: without extraction steam the feed cools toward the condensate.
        target = d.feedwater_temp_c if (not self.turbine_tripped and self.tsv > 0.5) else 110.0
        self.feed_temp += (target - self.feed_temp) * (1 - math.exp(-h / 400.0))

        # Valves move toward their demands.
        self._advance_valves(h)

    def _advance_valves(self, h: float) -> None:
        d = self.design
        if self.turbine_tripped:
            self.tsv = max(self.tsv - h / d.tsv_stroke_s, 0.0)
        if self.msiv_closing:
            self.msiv = max(self.msiv - h / d.msiv_stroke_s, 0.0)
        # Pressure regulator: steam demand rises with pressure above the regulator set point;
        # the turbine takes it first, the bypass takes what the turbine cannot.
        demand = (self.pressure - self.pressure_regulator_pa) / self.regulator_band_pa
        demand = min(max(demand, 0.0), 1.0 + d.bypass_fraction)
        tcv_cap = 0.0 if self.turbine_tripped else 1.0
        tcv_target = min(demand, tcv_cap)
        bypass_target = min(max(demand - tcv_target, 0.0) / d.bypass_fraction, 1.0) \
            if (self.bypass_available and self.condenser_available) else 0.0
        self.tcv += (tcv_target - self.tcv) * (1 - math.exp(-h / 0.2))
        self.bypass += (bypass_target - self.bypass) * (1 - math.exp(-h / d.bypass_stroke_s))
        p = steam.psig(self.pressure)
        for i, sp in enumerate(d.srv_setpoints_psig):
            if self.srv_manual[i] or (self.ads_open and i < d.eccs.ads_valves):
                self.srv_open[i] = True
            elif not self.srv_open[i] and p >= sp:
                self.srv_open[i] = True
                self._event("trip", f"SRV {i + 1} lifted at {sp:.0f} psig")
            elif self.srv_open[i] and p <= sp - d.srv_reseat_psi:
                self.srv_open[i] = False

    def _fuel_damage(self, h: float) -> None:
        limits = self.design.fuel_limits
        peak = self.peak_fuel_temp()
        if peak > self.max_peak_fuel_temp:
            if self.max_peak_fuel_temp <= limits["safety_limit"] < peak:
                self._event("limit", f"Peak fuel temperature limit {limits['safety_limit']:.0f} C exceeded")
            self.max_peak_fuel_temp = peak
        over = peak - limits["blister"]
        if over > 0:
            rate = 2e-5 * over + (0.05 if peak > limits["melt"] else 0.0)
            inc = min(rate * h, 1.0 - self.fuel_damage)
            if self.fuel_damage == 0 and inc > 0:
                self._event("limit", "Cladding failure: fission products entering the coolant")
            self.fuel_damage += inc

    # ------------------------------------------------------------------ control cycle

    def _event(self, kind: str, message: str) -> None:
        self.events.append(Event(self.t, kind, message))

    def _alarm(self, active: bool, msg: str) -> None:
        if active and msg not in self._active_alarms:
            self._event("alarm", msg)
            self._active_alarms.add(msg)
        elif not active:
            self._active_alarms.discard(msg)

    def _control(self) -> None:
        d, sp, e = self.design, self.design.setpoints, self.design.eccs
        pct = 100.0 * self.power / d.rated_power
        flow_pct = 100.0 * self.core_flow / d.rated_core_flow
        p_psig = steam.psig(self.pressure)
        L = self.level_in

        # Reactor protection system.
        causes = []
        if self.mode == "run":
            if pct >= sp.aprm_high_percent:
                causes.append("APRM neutron flux high")
            if pct >= sp.aprm_flow_bias_slope * flow_pct + sp.aprm_flow_bias_intercept:
                causes.append("APRM flow-biased neutron flux high")
        elif pct >= sp.aprm_setdown_percent:
            causes.append("APRM neutron flux high (startup setdown)")
        if p_psig >= sp.dome_pressure_high_psig:
            causes.append("Reactor pressure high")
        if L <= sp.level3_scram_in:
            causes.append("Reactor water level low (Level 3)")
        if self.tsv_scram_enabled and pct >= sp.tsv_closure_bypass_percent and self.tsv < 0.9:
            causes.append("Turbine stop valve closure")
        if self.msiv < 0.9:
            causes.append("Main steam isolation valve closure")
        if self.rps_enabled and causes and not self.scrammed:
            self.scram(causes)
        elif self.scrammed:
            for c in causes:
                if c not in self.scram_causes:
                    self.scram_causes.append(c)

        # Level 8: turbine and feed pump trip, HPCI/RCIC injection stops.
        if L >= sp.level8_trip_in:
            if not self.turbine_tripped:
                self.trip_turbine("Reactor water level high (Level 8)")
            if not self.feed_tripped:
                self.feed_tripped = True
                self._event("trip", "Feed pumps tripped on Level 8")
            for s in (self.hpci, self.rcic):
                if s.running and not s.manual:
                    s.running = False
                    s.start_time = None
                    self._event("eccs", f"{s.name} injection stopped on Level 8")

        # ATWS recirculation pump trip on high pressure (Level 2 trips them too, below).
        if p_psig >= sp.atws_rpt_psig and not all(pump.tripped for pump in self.pumps):
            self.trip_recirc_pumps(quiet=True)
            self._event("trip", "Recirculation pump trip on high reactor pressure (ATWS-RPT)")

        # Level 2: HPCI and RCIC start, recirculation pump trip.
        if L <= sp.level2_in and not self.level2_latched:
            self.level2_latched = True
            self._event("eccs", "Level 2: HPCI and RCIC initiation, recirculation pump trip")
            self._start(self.hpci)
            self._start(self.rcic)
            self.trip_recirc_pumps(quiet=True)
        if L > sp.level2_in + 10 and self.level2_latched and not self.hpci.running and not self.rcic.running:
            self.level2_latched = False

        # Level 1: low-pressure ECCS start, MSIV closure, ADS timer.
        if L <= sp.level1_in and not self.level1_latched:
            self.level1_latched = True
            self._event("eccs", "Level 1: core spray and LPCI initiation, MSIV closure, ADS timer started")
            self._start(self.core_spray)
            self._start(self.lpci)
            self.close_msivs(quiet=True)
            self.ads_armed_at = self.t
        if self.ads_armed_at is not None and not self.ads_open and not self.ads_inhibited:
            lp_running = (self.core_spray.running or self.lpci.running)
            if lp_running and self.t - self.ads_armed_at >= sp.ads_delay_s and L <= sp.level1_in + 20:
                self.ads_open = True
                self._event("eccs", f"ADS: {e.ads_valves} relief valves opened")
        if self.level1_latched and L > sp.level1_in + 30 and self.ads_open:
            pass  # ADS valves stay open once blown; the operator closes them

        # MSIV isolation on low steam line pressure in Run.
        if self.mode == "run" and p_psig <= sp.msl_pressure_low_psig and not self.msiv_closing and self.msiv > 0:
            self.close_msivs(reason="Main steam line pressure low")

        # ECCS flows for the coming physics step.
        self.eccs_flow = sum(self._inject(s) for s in (self.hpci, self.rcic, self.core_spray, self.lpci))

        # Feedwater: three-element level control, unless tripped.
        if self.feed_tripped or not self.feed_available:
            self.feed_demand = 0.0
        else:
            rated = self._rated_steam_flow()
            err = self.level_setpoint_in - L
            self.feed_demand = min(max(self.steam_out + d.level_gain * rated * err, 0.0),
                                   d.feedwater_max_fraction * rated)

        # Alarms.
        self._alarm(L <= sp.level4_alarm_in, "Reactor water level low")
        self._alarm(L >= sp.level7_alarm_in, "Reactor water level high")
        self._alarm(p_psig >= sp.dome_pressure_high_psig - 30, "Reactor pressure high")
        self._alarm(any(self.srv_open), "Safety/relief valve open")
        self._alarm(self.torus_temp > 35.0, "Suppression pool temperature high")
        self._alarm(self.level_in <= d.taf_level_in, "Core uncovered")
        self._alarm(self.mode == "run" and pct > 0 and self._in_exclusion_region(pct, flow_pct),
                    "Operating in the instability exclusion region")

    def _in_exclusion_region(self, pct: float, flow_pct: float) -> bool:
        return flow_pct < 45.0 and pct > 0.6 * flow_pct + 10.0 and pct > 25.0

    def _start(self, s: Injection) -> None:
        if s.available and not s.running and s.start_time is None:
            s.start_time = self.t

    def _inject(self, s: Injection) -> float:
        d, e = self.design, self.design.eccs
        p = self.pressure
        if s.start_time is not None and not s.running:
            delay = {"HPCI": e.hpci_start_s, "RCIC": e.rcic_start_s}.get(s.name, e.lp_start_s)
            if self.t - s.start_time >= delay:
                s.running = True
                self._event("eccs", f"{s.name} injecting")
        if not s.running:
            s.flow = 0.0
            return 0.0
        if s.name == "HPCI":
            s.flow = e.hpci_flow_kg_s if p > e.hpci_min_pressure_pa else 0.0
        elif s.name == "RCIC":
            s.flow = e.rcic_flow_kg_s if p > e.rcic_min_pressure_pa else 0.0
        elif s.name == "Core spray":
            head = e.core_spray_shutoff_pa
            s.flow = e.core_spray_loops * e.core_spray_flow_kg_s * math.sqrt(max(1 - (p - 1e5) / head, 0.0))
        else:
            head = e.lpci_shutoff_pa
            s.flow = e.lpci_pumps * e.lpci_flow_kg_s * math.sqrt(max(1 - (p - 1e5) / head, 0.0))
        return s.flow

    def step(self, dt: float | None = None) -> None:
        dt = self.control_dt if dt is None else dt
        self._control()
        if self._pending_release is not None and self._pending_release < self.t + dt:
            first = max(self._pending_release - self.t, 0.0)
            if first > 0:
                self._physics(first)
            self._pending_release = None
            self.rods.scram_time = self.t
            self._physics(dt - first)
        else:
            self._physics(dt)

    def run(self, duration: float, dt: float | None = None, record_every: float | None = None,
            until: Callable[["BWRSimulator"], bool] | None = None,
            each_step: Callable[["BWRSimulator"], None] | None = None) -> None:
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

    def withdraw_rods(self, notches: float = 1.0) -> None:
        self.rods.target = min(self.rods.withdrawn_cm + notches * self.design.notch_cm, self.rods.stroke_cm)

    def insert_rods(self, notches: float = 1.0) -> None:
        self.rods.target = max(self.rods.withdrawn_cm - notches * self.design.notch_cm, 0.0)

    def drive_rods(self, direction: str) -> None:
        """Hold the bank switch: 'out', 'in' or 'stop'."""
        self.rods.target = None
        self.rods.command = {"out": 1, "in": -1, "stop": 0}[direction]

    def set_recirc_speed(self, fraction: float) -> None:
        f = min(max(fraction, self.design.min_pump_speed), 1.0)
        for p in self.pumps:
            if not p.tripped:
                p.demand = f

    def trip_recirc_pumps(self, which: str = "both", quiet: bool = False) -> None:
        idx = [0, 1] if which == "both" else [0] if which == "A" else [1]
        for i in idx:
            self.pumps[i].tripped = True
        if not quiet:
            self._event("trip", f"Recirculation pump{'s' if len(idx) > 1 else ' ' + which} tripped")

    def restart_recirc_pumps(self) -> None:
        for p in self.pumps:
            p.tripped = False
            p.demand = max(p.demand, self.design.min_pump_speed)

    def trip_turbine(self, reason: str = "Manual turbine trip") -> None:
        if not self.turbine_tripped:
            self.turbine_tripped = True
            self._event("trip", f"Turbine trip: {reason}")

    def close_msivs(self, reason: str | None = None, quiet: bool = False) -> None:
        if not self.msiv_closing:
            self.msiv_closing = True
            if not quiet:
                self._event("trip", "MSIV closure" + (f": {reason}" if reason else ""))

    def open_msivs(self) -> None:
        self.msiv_closing = False
        self.msiv = 1.0

    def scram(self, cause: str | list[str] = "Manual scram") -> None:
        causes = [cause] if isinstance(cause, str) else list(cause)
        first = not self.scrammed
        self.scrammed = True
        self.scram_causes = causes
        self.rods.command = 0
        self.rods.target = None
        if first:
            self._event("scram", "SCRAM: " + "; ".join(causes))
            self._pending_release = self.t + self.design.setpoints.scram_delay_s

    def reset_scram(self) -> bool:
        if self.scrammed and self.rods.scram_fraction < 1.0:
            return False
        self.scrammed = False
        self.scram_causes = []
        self.rods.scram_time = None
        self.rods.withdrawn_cm = 0.0
        self.rods.scram_fraction = 0.0
        self._event("operator", "Scram reset")
        return True

    def trip_feedwater(self) -> None:
        if not self.feed_tripped:
            self.feed_tripped = True
            self._event("trip", "Loss of feedwater")

    def restore_feedwater(self) -> None:
        self.feed_tripped = False

    def set_level_setpoint(self, inches: float) -> None:
        self.level_setpoint_in = inches

    def set_pressure_setpoint(self, psig: float) -> None:
        self.pressure_regulator_pa = steam.from_psig(psig)

    def start_system(self, name: str) -> None:
        s = self._system(name)
        s.manual = True
        self._start(s)

    def stop_system(self, name: str) -> None:
        s = self._system(name)
        s.running = False
        s.start_time = None
        s.manual = False

    def set_available(self, name: str, available: bool) -> None:
        if name.lower() == "bypass":
            self.bypass_available = available
        elif name.lower() == "condenser":
            self.condenser_available = available
        elif name.lower() == "feedwater":
            self.feed_available = available
        else:
            s = self._system(name)
            s.available = available
            if not available:
                s.running = False
                s.start_time = None

    def _system(self, name: str) -> Injection:
        return {"hpci": self.hpci, "rcic": self.rcic, "core_spray": self.core_spray, "lpci": self.lpci}[name.lower()]

    def open_srv(self, valve: int, open: bool = True) -> None:
        self.srv_manual[valve - 1] = open
        if not open:
            self.srv_open[valve - 1] = False
        self._event("operator", f"SRV {valve} {'opened' if open else 'closed'} by hand")

    def inhibit_ads(self, inhibit: bool = True) -> None:
        self.ads_inhibited = inhibit

    def station_blackout(self) -> None:
        """Loss of all AC power: feed pumps, recirculation pumps and condenser lost, MSIVs shut.
        HPCI and RCIC run on steam and DC power; the low-pressure ECCS has no diesels."""
        self._event("trip", "Station blackout: loss of all AC power")
        self.trip_feedwater()
        self.feed_available = False
        self.trip_recirc_pumps(quiet=True)
        self.condenser_available = False
        self.close_msivs(quiet=True)
        self.trip_turbine("loss of AC power")
        self.core_spray.available = False
        self.lpci.available = False

    def insert_reactivity(self, amount: float) -> None:
        self.external_reactivity += amount

    # ------------------------------------------------------------------ setup

    def initialize_at_power(self, power_w: float, core_flow_fraction: float = 1.0, xenon: str = "equilibrium",
                            history_hours: float = 100.0) -> None:
        """Put the plant at steady power: pressure at the regulator set point, level at its
        set point, feed matching steam, fuel and void at their steady values, and the rod bank
        at the critical position."""
        d = self.design
        self.mode = "run"
        self.power = power_w
        self.precursors = self.kinetics.equilibrium_precursors(power_w)
        self.decay_groups = self.decay.frac * power_w * (1 - np.exp(-self.decay.lam * history_hours * 3600.0))
        heat = self.thermal_power()
        flux = d.flux_per_watt * power_w
        self.poisons = self.poison_model.equilibrium(flux) if xenon == "equilibrium" else PoisonState()
        if xenon == "equilibrium":
            self.poisons.samarium = 0.0

        p = d.dome_pressure_setpoint_pa
        self.pressure = p
        hf, hfg, tsat = steam.h_f(p), steam.h_fg(p), steam.t_sat(p)
        self.condensing_temp = tsat
        self.fuel_temp = tsat + (1 - d.gamma_fraction) * heat / d.fuel_conductance
        self.feed_temp = d.feedwater_temp_c
        # Fixed point: feed flow equals steam made, which depends on the inlet subcooling the feed
        # sets, and the core void (which drives natural circulation) depends on both.
        self.core_flow = core_flow_fraction * d.rated_core_flow
        h_fw = steam.h_liquid(self.feed_temp, p)
        gen = heat / (steam.h_g(p) - h_fw)
        self.inlet_enthalpy = hf - gen * (hf - h_fw) / self.core_flow
        self.void, self.exit_void, self.boiling_boundary = self._void_profile(heat, self.core_flow, p)
        # Rated-condition void is the natural-circulation reference, so work it out once.
        self._void_at_rated = self._void_at(d.rated_power, d.rated_core_flow, p, h_fw)[0]
        nat = d.natural_circulation_fraction * (0.15 + 0.85 * math.sqrt(min(self.void / self._void_at_rated, 2.0)))
        speed = (core_flow_fraction - nat) / (1 - d.natural_circulation_fraction)
        for pump in self.pumps:
            pump.tripped = False
            pump.demand = pump.speed = min(max(speed, 0.0), 1.0)
        if abs(self._core_flow() - self.core_flow) > 0.01 * d.rated_core_flow:
            raise ValueError(f"core flow fraction {core_flow_fraction} is not reachable at this power "
                             f"(natural circulation alone gives {nat:.2f})")
        self.core_flow = self._core_flow()
        self.downcomer_enthalpy = self.inlet_enthalpy
        self.feed_flow = self.feed_demand = gen
        self.steam_generation = self.steam_out = gen
        self._void_volume0 = d.core_coolant_volume * self.void + d.separator_volume * self.exit_void
        self.liquid_mass = d.liquid_mass
        self.level_setpoint_in = d.normal_level_in
        self._update_level()
        rated = self._rated_steam_flow()
        self.tcv = gen / (1.05 * rated)
        self.tsv = 1.0
        self.turbine_tripped = False
        self.pressure_regulator_pa = p - self.tcv * self.regulator_band_pa
        self.torus_temp = d.torus_initial_temp

        # Rod bank to criticality.
        r = self.rods
        r.scram_time, r.scram_fraction, r.target, r.command = None, 0.0, None, 0
        self.scrammed, self.scram_causes, self._pending_release = False, [], None

        def rho_at(x):
            r.withdrawn_cm = x
            return self.reactivity()["total"]

        if rho_at(r.stroke_cm) < 0:
            raise ValueError("core cannot be made critical at this power and xenon state")
        rho_at(brentq(rho_at, 0.0, r.stroke_cm, xtol=1e-9))

    # ------------------------------------------------------------------ reporting

    def record(self) -> None:
        self.history.append(_Snapshot(
            t=self.t, power=self.power, thermal_power=self.thermal_power(), pressure=self.pressure,
            level_in=self.level_in, core_flow=self.core_flow, void=self.void, fuel_temp=self.fuel_temp,
            peak_fuel_temp=self.peak_fuel_temp(), steam_flow=self.steam_out, feed_flow=self.feed_flow,
            eccs_flow=self.eccs_flow, rods=self.rods.withdrawn_cm, reactivity=self.reactivity(),
            torus_temp=self.torus_temp, scrammed=self.scrammed,
        ))

    def history_arrays(self) -> dict[str, np.ndarray]:
        h = self.history
        keys = ["t", "power", "thermal_power", "pressure", "level_in", "core_flow", "void", "fuel_temp",
                "peak_fuel_temp", "steam_flow", "feed_flow", "eccs_flow", "rods", "torus_temp", "scrammed"]
        out = {k: np.array([getattr(s, k) for s in h], dtype=float) for k in keys}
        if h:
            for k in h[0].reactivity:
                out[f"rho_{k}"] = np.array([s.reactivity[k] for s in h])
        return out

    def status(self) -> dict:
        d = self.design
        rho = self.reactivity()
        return {
            "time_s": self.t,
            "power_w": self.power,
            "power_percent": 100.0 * self.power / d.rated_power,
            "thermal_power_w": self.thermal_power(),
            "reactivity_dollars": rho["total"] / d.delayed.beta_total,
            "pressure_psig": steam.psig(self.pressure),
            "level_in": self.level_in,
            "core_flow_percent": 100.0 * self.core_flow / d.rated_core_flow,
            "void_percent": 100.0 * self.void,
            "fuel_temp_c": self.fuel_temp,
            "peak_fuel_temp_c": self.peak_fuel_temp(),
            "steam_flow_kg_s": self.steam_out,
            "feed_flow_kg_s": self.feed_flow,
            "eccs_flow_kg_s": self.eccs_flow,
            "rod_notch": round(self.rods.notch * d.notches, 1),
            "srv_open": sum(self.srv_open),
            "torus_temp_c": self.torus_temp,
            "scrammed": self.scrammed,
            "scram_causes": list(self.scram_causes),
            "alarms": sorted(self._active_alarms),
            "fuel_damage": self.fuel_damage,
        }
