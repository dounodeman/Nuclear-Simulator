"""A live Peach Bottom 2 session: the BWR plant advancing in real time under the control-room
switches, with the readings the analog benchboards show.

Same shape as ``SimSession`` (lock, stepping thread, ``state()`` and ``command()``), but the
state is a flat dict of *instrument readings* in the units engraved on the panel meters (psig,
inches, Mlb/h, gpm, degrees F) plus the lamp and switch states, and an annunciator model with
acknowledge/reset like the real window boxes: a new alarm flashes until acknowledged, stays lit
while the condition holds, and clears on reset once it is gone.
"""

from __future__ import annotations

import math
import threading
import time

from reactorsim.app.session import SPEEDS, TICK_S, CommandError, _clean
from reactorsim.physics import steam
from reactorsim.reactors import simulator_for

INITIAL_STATES = {
    "full_power": "Full power, 3,293 MWt, rated core flow",
    "power_60": "61.6% power, 80.9% core flow (the 1977 turbine trip test state)",
    "low_power": "25% power, minimum pump speed",
}

LB_H = 0.4536 / 3600.0
GPM = 6.309e-5 * 740.0
MLB_H = 1e6 * LB_H
SRV_SW = ("CLOSE", "AUTO", "OPEN")


def f_of_c(c: float) -> float:
    return c * 9 / 5 + 32


class BWRSession:
    def __init__(self, initial: str = "full_power", design: str = "peach_bottom_2", seed: int | None = None):
        self.design_key = design
        self._seed = seed
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.speed = 1.0
        self.run = 0
        self.reset(initial)

    # ------------------------------------------------------------------ lifecycle

    def reset(self, initial: str = "full_power") -> None:
        if initial not in INITIAL_STATES:
            raise CommandError(f"unknown initial state {initial!r}")
        seed = self._seed if self._seed is not None else int(time.time() * 1e3) % 2**31
        sim = simulator_for(self.design_key, seed=seed)
        rated = sim.design.rated_power
        if initial == "full_power":
            sim.initialize_at_power(rated)
        elif initial == "power_60":
            sim.initialize_at_power(0.617 * rated, 0.809)
        else:
            sim.initialize_at_power(0.25 * rated, 0.45)
        with self._lock:
            self.sim = sim
            self.initial = initial
            self.run += 1
            self.speed = 1.0
            self.turbine_speed = 1800.0
            self.gen_breaker = True
            self.slc_running = False
            self.slc_injected = 0.0
            self.rod_selected = "26-27"
            self.srv_switch = [1] * len(sim.srv_open)   # AUTO
            self.ann: dict[str, dict] = {}              # key -> {"active", "acked"}
            self.ann_test_until = 0.0
            self._prev_power = sim.power
            self.period_s = math.inf
            self.sim._event("operator", f"Session started: {INITIAL_STATES[initial]}")

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="reactorsim-bwr-session", daemon=True)
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
                next_tick = time.monotonic()

    def advance(self, sim_seconds: float) -> None:
        with self._lock:
            sim = self.sim
            end = sim.t + sim_seconds
            while sim.t < end - 1e-9:
                h = min(sim.control_dt, end - sim.t)
                p0 = sim.power
                sim.step(h)
                self._plant_extras(h, p0)
            self._update_annunciators()

    def _plant_extras(self, h: float, p0: float) -> None:
        """Things the plant model does not carry: turbine speed, SLC boron, the period meter."""
        sim = self.sim
        # Turbine: holds 1800 rpm on the grid, coasts down after a trip, and the breaker opens.
        if sim.turbine_tripped or sim.msiv < 0.5:
            self.turbine_speed = max(0.0, self.turbine_speed - h * 1800.0 / 900.0)
            self.gen_breaker = False
        else:
            self.turbine_speed = min(1800.0, self.turbine_speed + h * 1800.0 / 120.0)
            if self.turbine_speed >= 1799.0:
                self.gen_breaker = True
        # Standby liquid control: 43 gpm of sodium pentaborate, worth about -0.05 dk/k in 20 min.
        if self.slc_running and self.slc_injected < 0.05:
            d = min(0.05 / 1200.0 * h, 0.05 - self.slc_injected)
            self.slc_injected += d
            sim.insert_reactivity(-d)
        # Period meter with a 2 s filter, as the analog meter responds.
        if p0 > 0 and sim.power > 0 and h > 0:
            raw = h / math.log(sim.power / p0) if abs(sim.power - p0) > 1e-12 * p0 else math.inf
            inv = 0.0 if math.isinf(raw) else 1.0 / raw
            prev = 0.0 if math.isinf(self.period_s) else 1.0 / self.period_s
            f = min(1.0, h / 2.0)
            filt = prev + f * (inv - prev)
            self.period_s = math.inf if abs(filt) < 1e-4 else 1.0 / filt

    # ------------------------------------------------------------------ readings

    def _conditions(self) -> dict[str, bool]:
        """Alarm and lamp conditions from the plant state, by annunciator key."""
        s = self.sim
        d = s.design
        sp = d.setpoints
        pct = 100.0 * s.power / d.rated_power
        flow_pct = 100.0 * s.core_flow / d.rated_core_flow
        p = steam.psig(s.pressure)
        L = s.level_in
        causes = set(s.scram_causes)
        alarms = s._active_alarms
        c = {
            "aprm_high": "APRM neutron flux high" in causes or (s.mode == "run" and pct >= sp.aprm_high_percent),
            "aprm_flow": "APRM flow-biased neutron flux high" in causes
                         or (s.mode == "run" and pct >= sp.aprm_flow_bias_slope * flow_pct + sp.aprm_flow_bias_intercept),
            "aprm_setdown": "APRM neutron flux high (startup setdown)" in causes,
            "irm_high": s.mode != "run" and pct > 10.0,
            "rod_block": s.scrammed or L >= sp.level8_trip_in,
            "rod_drift": False,
            "select_error": False,
            "scram": s.scrammed,
            "half_scram": False,
            "rps_trouble": not s.rps_enabled,
            "level_low_l4": L <= sp.level4_alarm_in,
            "level_low_l3": L <= sp.level3_scram_in or "Reactor water level low (Level 3)" in causes,
            "level_high_l7": L >= sp.level7_alarm_in,
            "level_high_l8": L >= sp.level8_trip_in,
            "pressure_high": p >= sp.dome_pressure_high_psig - 30 or "Reactor pressure high" in causes,
            "msl_low": s.mode == "run" and p <= sp.msl_pressure_low_psig,
            "tsv_closure": s.tsv < 0.9,
            "msiv_closure": s.msiv < 0.9,
            "mode_startup": s.mode != "run",
            "exclusion": "Operating in the instability exclusion region" in alarms,
            "recirc_a_trip": s.pumps[0].tripped,
            "recirc_b_trip": s.pumps[1].tripped,
            "atws_rpt": any("ATWS-RPT" in e.message for e in s.events[-50:]) and all(pp.tripped for pp in s.pumps),
            "feed_trip": s.feed_tripped or not s.feed_available,
            "level_l2": s.level2_latched or L <= sp.level2_in,
            "level_l1": s.level1_latched or L <= sp.level1_in,
            "core_uncovered": L <= d.taf_level_in,
            "fuel_damage": s.fuel_damage > 0,
            "srv_open": any(s.srv_open) or s.ads_open,
            "hpci_init": s.hpci.start_time is not None or s.hpci.running,
            "hpci_run": s.hpci.running,
            "rcic_init": s.rcic.start_time is not None or s.rcic.running,
            "rcic_run": s.rcic.running,
            "cs_init": s.core_spray.start_time is not None or s.core_spray.running,
            "cs_run": s.core_spray.running,
            "lpci_init": s.lpci.start_time is not None or s.lpci.running,
            "lpci_run": s.lpci.running,
            "ads_timer": s.ads_armed_at is not None and not s.ads_open,
            "ads_open": s.ads_open,
            "ads_inhibit": s.ads_inhibited,
            "torus_temp": s.torus_temp > 35.0,
            "torus_level": False,
            "drywell_press": s.ads_open or any(s.srv_open) and s.torus_temp > 60,
            "hpci_unavail": not s.hpci.available,
            "rcic_unavail": not s.rcic.available,
            "cs_unavail": not s.core_spray.available,
            "lpci_unavail": not s.lpci.available,
            "turbine_trip": s.turbine_tripped,
            "gen_breaker": not self.gen_breaker,
            "tcv_fast": s.turbine_tripped and s.tsv > 0.5,
            "bypass_open": s.bypass > 0.02,
            "bypass_unavail": not s.bypass_available,
            "condenser_low": not s.condenser_available,
            "ehc_trouble": False,
            "feed_a_trip": s.feed_tripped, "feed_b_trip": s.feed_tripped, "feed_c_trip": s.feed_tripped,
            "station_blackout": not s.feed_available and not s.condenser_available,
            "diesel_start": not s.feed_available and not s.condenser_available,
        }
        return c

    def _update_annunciators(self) -> None:
        for key, active in self._conditions().items():
            a = self.ann.get(key)
            if active:
                if a is None:
                    self.ann[key] = {"active": True, "acked": False}
                else:
                    a["active"] = True
            elif a is not None:
                a["active"] = False
                if a["acked"]:
                    pass  # stays lit (steady) until reset, as a real window does
        # windows whose condition cleared and were acknowledged go out on the next reset

    def state(self, events_after: int = 0) -> dict:
        with self._lock:
            s = self.sim
            d = s.design
            sp = d.setpoints
            rated = d.rated_power
            pct = 100.0 * s.power / rated
            flow_mlb = s.core_flow / MLB_H
            flow_pct = 100.0 * s.core_flow / d.rated_core_flow
            rated_steam = s._rated_steam_flow()
            p_psig = steam.psig(s.pressure)
            rho = s.reactivity()
            beta = d.delayed.beta_total
            speeds = [pp.speed for pp in s.pumps]
            mean_speed = sum(speeds) / 2
            loops = [flow_mlb / 2 * (sp_ / mean_speed if mean_speed > 0.05 else 0.0) for sp_ in speeds]
            running_feed = not s.feed_tripped and s.feed_available
            cond = self._conditions()
            gen_mw = 0.0
            if self.gen_breaker and not s.turbine_tripped:
                gen_mw = 0.33 * s.thermal_power() / 1e6 * min(1.0, s.tcv + 0.02) * (s.msiv if s.msiv > 0.5 else 0.0)
            hpci_flow = s.hpci.flow / GPM
            rcic_flow = s.rcic.flow / GPM
            cs_flow = s.core_spray.flow / GPM
            lpci_flow = s.lpci.flow / GPM
            irm = min(125.0, pct / 40.0 * 125.0)
            srm = min(6.0, max(-1.0, math.log10(max(pct, 1e-9) * 1e5)))
            ann = {k: ("flash" if a["active"] and not a["acked"] else "on" if a["active"] or (a["acked"] and not a["active"]) else "off")
                   for k, a in self.ann.items()}
            if time.monotonic() < self.ann_test_until:
                ann = {"__test__": "on"}
            r = {
                "reactor": {"key": d.key, "name": d.name, "rated_w": rated},
                "initial": self.initial,
                "run": self.run,
                "time_s": s.t,
                "speed": self.speed,
                "readings": {
                    "aprm": pct, "aprm_flow_setpoint": min(125.0, sp.aprm_flow_bias_slope * flow_pct + sp.aprm_flow_bias_intercept),
                    "irm": irm, "srm": srm, "period": self.period_s if math.isfinite(self.period_s) else None,
                    "thermal_power": 100.0 * s.thermal_power() / rated,
                    "pressure": p_psig, "pressure_setpoint": steam.psig(s.pressure_regulator_pa),
                    "level": s.level_in, "level_setpoint": s.level_setpoint_in,
                    "core_flow": flow_mlb, "core_flow_pct": flow_pct, "recirc_flow_a": loops[0], "recirc_flow_b": loops[1],
                    "recirc_speed_a": 100 * speeds[0], "recirc_speed_b": 100 * speeds[1],
                    "recirc_demand": 100 * max(pp.demand for pp in s.pumps),
                    "core_dp": 2.0 + 18.0 * (s.core_flow / d.rated_core_flow) ** 2,
                    "steam_flow": s.steam_out / MLB_H, "feed_flow": s.feed_flow / MLB_H,
                    "feed_demand": 100 * s.feed_demand / rated_steam if rated_steam else 0.0,
                    "feed_temp": f_of_c(s.feed_temp), "msl_flow": s.steam_out / MLB_H / 4,
                    "fuel_temp": f_of_c(s.fuel_temp), "void": 100 * s.void,
                    "xenon": rho["xenon"] / beta, "reactivity": rho["total"] / beta,
                    "burnup": 100.0 * (1.0 - s.u235_g / d.u235_mass_g) * 20.0,
                    "rod_notch": s.rods.notch * d.notches, "rod_selected": self.rod_selected,
                    "time_since_scram": (s.t - s.rods.scram_time) if s.scrammed and s.rods.scram_time is not None else 0.0,
                    "hpci_flow": hpci_flow, "hpci_speed": 4100.0 if s.hpci.running else 0.0,
                    "hpci_disch": p_psig + 250 if s.hpci.running else 0.0,
                    "rcic_flow": rcic_flow, "rcic_speed": 4500.0 if s.rcic.running else 0.0,
                    "cs_flow_a": cs_flow / 2, "cs_flow_b": cs_flow / 2,
                    "lpci_flow_a": lpci_flow / 4, "lpci_flow_b": lpci_flow / 4, "lpci_flow_c": lpci_flow / 4, "lpci_flow_d": lpci_flow / 4,
                    "eccs_flow": s.eccs_flow / GPM, "rhr_hx": 0.0,
                    "torus_temp": f_of_c(s.torus_temp), "torus_level": 0.0,
                    "drywell_pressure": 0.9 + (12.0 if s.ads_open else 0.0), "drywell_temp": 135.0 + 0.5 * (f_of_c(s.torus_temp) - 86),
                    "torus_pressure": 0.4 + (8.0 if s.ads_open else 0.0), "drywell_h2": 0.0,
                    "srv_flow": s.srv_flow / MLB_H, "srv_tail_temp": 140.0 + (300.0 if (any(s.srv_open) or s.ads_open) else 0.0),
                    "turbine_inlet": p_psig - 30.0 if s.msiv > 0.5 else 0.0,
                    "first_stage": 0.6 * p_psig * min(1.0, s.tcv) * (1.0 if not s.turbine_tripped else 0.0),
                    "turbine_speed": self.turbine_speed, "tcv": 100 * s.tcv, "bypass": 100 * s.bypass,
                    "vacuum": 28.5 if s.condenser_available else 8.0, "hotwell_temp": 101.0 if s.condenser_available else 160.0,
                    "gen_mw": gen_mw, "gen_mvar": 0.25 * gen_mw if gen_mw else 0.0, "gen_kv": 22.0 if self.gen_breaker else 0.0,
                    "gen_hz": 60.0 if self.gen_breaker else self.turbine_speed / 30.0, "gen_amps": gen_mw / 22.0 / math.sqrt(3) if gen_mw else 0.0,
                    "gen_h2": 60.0,
                    "rfpt_speed": 5200.0 * (s.feed_flow / rated_steam) ** 0.5 if running_feed and rated_steam else 0.0,
                    "rfp_flow": s.feed_flow / MLB_H / 3, "hotwell_level": 30.0, "cond_pump": 450.0 if s.condenser_available else 0.0,
                    "msl_rad": 3.0 * pct / 100, "bus_4kv": 4.16, "diesel_kw": 2800.0 if cond["diesel_start"] else 0.0,
                    "dc_bus": 128.0, "grid_kv": 525.0,
                    "mode": 3 if s.mode == "run" else 2,
                    "three_element": 2, "irm_range": 2, "slc": 1 if self.slc_running else 0,
                    "srv_sw": list(self.srv_switch),
                },
                "lamps": {
                    **cond,
                    "not_scrammed": not s.scrammed, "scram_pilot": not s.scrammed,
                    "recirc_a_run": speeds[0] > 0.05 and not s.pumps[0].tripped, "recirc_a_stopped": s.pumps[0].tripped or speeds[0] <= 0.05,
                    "recirc_b_run": speeds[1] > 0.05 and not s.pumps[1].tripped, "recirc_b_stopped": s.pumps[1].tripped or speeds[1] <= 0.05,
                    "recirc_demand_auto": False, "recirc_demand_manual": True,
                    "feed_run": running_feed, "feed_stopped": not running_feed,
                    "feed_demand_auto": running_feed, "feed_demand_manual": not running_feed,
                    "pressure_auto": True, "pressure_manual": False,
                    "hpci_stopped": not s.hpci.running, "hpci_avail": s.hpci.available,
                    "rcic_stopped": not s.rcic.running, "rcic_avail": s.rcic.available,
                    "cs_stopped": not s.core_spray.running, "lpci_stopped": not s.lpci.running,
                    "msiv_open": s.msiv > 0.9, "msiv_closed": s.msiv < 0.1,
                    "tsv_open": s.tsv > 0.9, "tsv_closed": s.tsv < 0.1,
                    "turbine_tripped": s.turbine_tripped, "turbine_latched": not s.turbine_tripped,
                    "gen_breaker": self.gen_breaker, "gen_breaker_open": not self.gen_breaker,
                    "bypass_avail": s.bypass_available, "condenser_avail": s.condenser_available,
                    "jet_pump_mismatch": abs(speeds[0] - speeds[1]) > 0.1,
                    "rod_out_permit": not s.scrammed and s.rods.scram_fraction == 0.0,
                    "rod_moving": s.rods.command != 0 or s.rods.target is not None,
                    "slc_run": self.slc_running,
                    **{f"srv_{i + 1}": bool(o) or (s.ads_open and i < d.eccs.ads_valves) for i, o in enumerate(s.srv_open)},
                    **{f"srv_{i + 1}_closed": not (bool(o) or (s.ads_open and i < d.eccs.ads_valves)) for i, o in enumerate(s.srv_open)},
                },
                "annunciators": ann,
                "scrammed": s.scrammed,
                "scram_causes": list(s.scram_causes),
                "alarms": sorted(s._active_alarms),
                "mode": s.mode,
                "events": [{"i": i, "t": e.time, "kind": e.kind, "message": e.message}
                           for i, e in enumerate(s.events) if i >= events_after],
                "event_count": len(s.events),
                "true": {"power_w": s.power, "fuel_damage": s.fuel_damage, "peak_fuel_temp_c": s.peak_fuel_temp(),
                         "torus_temp_c": s.torus_temp, "void": s.void},
            }
            for i in range(len(s.srv_open)):
                r["readings"][f"srv_{i + 1}_sw"] = self.srv_switch[i]
        return _clean(r)

    # ------------------------------------------------------------------ commands

    def command(self, action: str, **a) -> dict:
        if action == "reset":
            self.reset(a.get("initial", "full_power"))
            return {"ok": True}
        with self._lock:
            s = self.sim
            d = s.design
            ev = s._event
            if action == "speed":
                speed = float(a["speed"])
                if speed not in SPEEDS:
                    raise CommandError(f"speed must be one of {SPEEDS}")
                self.speed = speed
            elif action == "scram":
                s.scram("Manual scram (P603 pushbuttons)")
            elif action == "scram_reset":
                if not s.reset_scram():
                    raise CommandError("Scram cannot be reset until the rods are fully inserted")
            elif action == "rod_drive":
                direction = a["direction"]
                if direction not in ("in", "out", "stop"):
                    raise CommandError("direction must be in, out or stop")
                if s.scrammed and direction != "stop":
                    raise CommandError("Rod block: reactor scrammed")
                s.drive_rods(direction)
            elif action == "rod_notch":
                if s.scrammed:
                    raise CommandError("Rod block: reactor scrammed")
                n = float(a.get("notches", 1.0))
                (s.withdraw_rods if n > 0 else s.insert_rods)(abs(n))
                ev("operator", f"Rod {self.rod_selected} {'withdrawn' if n > 0 else 'inserted'} {abs(n):g} notch")
            elif action == "rod_select":
                self.rod_selected = str(a.get("rod", self.rod_selected))[:5]
            elif action == "recirc_pump":
                i = {"a": 0, "b": 1}[a["pump"].lower()]
                pump = s.pumps[i]
                if pump.tripped or pump.speed < 0.05:
                    pump.tripped = False
                    pump.demand = max(pump.demand, d.min_pump_speed)
                    ev("operator", f"Recirculation pump {a['pump'].upper()} started")
                else:
                    s.trip_recirc_pumps(a["pump"].upper())
            elif action == "recirc_speed":
                demand = max(pp.demand for pp in s.pumps) + float(a["delta"]) / 100.0
                s.set_recirc_speed(demand)
                ev("operator", f"Recirc speed demand {100 * max(pp.demand for pp in s.pumps):.0f}%")
            elif action == "level_setpoint":
                sp_ = min(max(s.level_setpoint_in + float(a["delta"]), 0.0), 55.0)
                s.set_level_setpoint(sp_)
                ev("operator", f"Level set point {sp_:.0f} in")
            elif action == "feed_pump":
                if s.feed_tripped:
                    s.restore_feedwater()
                    ev("operator", "Feed pumps restarted")
                else:
                    s.trip_feedwater()
            elif action in ("hpci", "rcic", "core_spray", "lpci"):
                sysm = s._system(action)
                if sysm.running or sysm.start_time is not None:
                    s.stop_system(action)
                    ev("operator", f"{sysm.name} stopped by hand")
                else:
                    if not sysm.available:
                        raise CommandError(f"{sysm.name} is out of service")
                    s.start_system(action)
                    ev("operator", f"{sysm.name} started by hand")
            elif action == "available":
                name = a["system"]
                on = bool(a["available"])
                s.set_available(name, on)
                ev("operator", f"{name.upper()} {'returned to service' if on else 'out of service'}")
            elif action == "ads_inhibit":
                s.inhibit_ads(not s.ads_inhibited)
                ev("operator", "ADS " + ("inhibited" if s.ads_inhibited else "armed"))
            elif action == "ads_manual":
                s.ads_open = True
                ev("operator", f"ADS manual initiation: {d.eccs.ads_valves} valves opened")
            elif action == "srv":
                i = int(a["valve"]) - 1
                pos = (self.srv_switch[i] + 1) % 3
                self.srv_switch[i] = pos
                if pos == 2:
                    s.open_srv(i + 1, True)
                elif pos == 0:
                    s.open_srv(i + 1, False)
                else:
                    s.srv_manual[i] = False
                    ev("operator", f"SRV {i + 1} in automatic")
            elif action == "msiv":
                if s.msiv > 0.5 and not s.msiv_closing:
                    s.close_msivs("operator")
                else:
                    if steam.psig(s.pressure) <= d.setpoints.msl_pressure_low_psig and s.mode == "run":
                        raise CommandError("MSIVs cannot be opened: low steam line pressure isolation in Run")
                    s.open_msivs()
                    ev("operator", "MSIVs opened")
            elif action == "turbine_trip":
                s.trip_turbine("manual trip, P653")
            elif action == "turbine_reset":
                if s.msiv < 0.5:
                    raise CommandError("Turbine cannot be reset with the MSIVs closed")
                s.turbine_tripped = False
                s.tsv = 1.0
                ev("operator", "Turbine trip reset, stop valves open")
            elif action == "pressure_setpoint":
                p = min(max(steam.psig(s.pressure_regulator_pa) + float(a["delta"]), 900.0), 1100.0)
                s.set_pressure_setpoint(p)
                ev("operator", f"Pressure regulator set point {p:.0f} psig")
            elif action == "mode_switch":
                s.mode = "startup" if s.mode == "run" else "run"
                ev("operator", f"Mode switch to {s.mode.upper()}")
            elif action == "slc":
                self.slc_running = not self.slc_running
                ev("operator", "Standby liquid control " + ("started: boron injection" if self.slc_running else "stopped"))
            elif action == "gen_breaker":
                self.gen_breaker = not self.gen_breaker
                if not self.gen_breaker:
                    s.trip_turbine("generator breaker opened")
                ev("operator", "Generator breaker " + ("closed" if self.gen_breaker else "opened"))
            elif action == "station_blackout":
                s.station_blackout()
            elif action == "ann_ack":
                for v in self.ann.values():
                    v["acked"] = True
            elif action == "ann_reset":
                for k in [k for k, v in self.ann.items() if not v["active"] and v["acked"]]:
                    del self.ann[k]
            elif action == "ann_test":
                self.ann_test_until = time.monotonic() + 3.0
            elif action == "fault":
                which = a["which"]
                if which == "rps":
                    s.rps_enabled = bool(a.get("enabled", not s.rps_enabled))
                    ev("operator", "RPS " + ("in service" if s.rps_enabled else "FAILED (no automatic scram)"))
                elif which == "tsv_scram":
                    s.tsv_scram_enabled = bool(a.get("enabled", not s.tsv_scram_enabled))
                else:
                    raise CommandError("fault must be rps or tsv_scram")
            else:
                raise CommandError(f"unknown action {action!r}")
        return {"ok": True}
