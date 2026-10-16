"""Balance-of-plant and auxiliary systems behind the Peach Bottom 2 side and back panels.

The plant model (``reactorsim.bwr``) carries the reactor, the steam lines, the ECCS and the torus.
The equipment on the auxiliary panels is modelled here, simply, so that every switch on those
panels does what it does in the plant and every meter moves for a reason:

* condensate pumps (the feed pumps' suction) and the three feedwater heater strings; a BWR has
  no deaerator, the condenser hotwell deaerates the condensate under vacuum and the steam jet
  air ejectors carry the gases off to the offgas system;
* circulating water pumps and air ejectors, which hold condenser vacuum: low vacuum trips the
  turbine, then closes the MSIVs and takes the bypass valves away;
* reactor water cleanup, which isolates on Level 2 and on standby liquid control;
* CRD hydraulic pumps, without which the rods cannot be driven;
* instrument air compressors: low header pressure bleeds the scram air header (a scram) and
  lets the MSIVs drift shut;
* high pressure service water and RHR torus cooling, which take heat out of the torus;
* reactor building ventilation and standby gas treatment (secondary containment);
* the four emergency diesel generators and their 4 kV emergency buses, which bring core spray
  and LPCI back after a loss of offsite power;
* the process and area radiation monitors.

Numbers are typical BWR/4 values (tagged *Typical* or *Assumed* in the panel docs), not
Peach Bottom's measured ones.
"""

from __future__ import annotations

import math

from reactorsim.app.session import CommandError
from reactorsim.physics import steam

UNITS = {
    "cond_pump": "ABC", "heater": "ABC", "circ_pump": "ABC", "sjae": "AB", "rwcu_pump": "AB", "crd_pump": "AB",
    "air_comp": "ABC", "hpsw_pump": "ABCD", "torus_cool": "AB", "sgts": "AB", "rb_hvac": "A", "diesel": "1234",
}
NAMES = {
    "cond_pump": "Condensate pump", "heater": "Feedwater heater string", "circ_pump": "Circulating water pump",
    "sjae": "Steam jet air ejector", "rwcu_pump": "RWCU pump", "crd_pump": "CRD pump", "air_comp": "Instrument air compressor",
    "hpsw_pump": "HPSW pump", "torus_cool": "RHR torus cooling loop", "sgts": "Standby gas treatment train",
    "rb_hvac": "Reactor building ventilation", "diesel": "Diesel generator E",
}
# Motor ammeters over the pump switches: rated current of each motor, A (Assumed).
MOTOR_AMPS = {"cond_pump": 380.0, "circ_pump": 480.0, "rwcu_pump": 90.0, "crd_pump": 40.0, "hpsw_pump": 160.0, "air_comp": 120.0}
# Offsite power only (non-safety buses); the rest also run from the diesel-backed emergency buses.
NON_SAFETY = {"cond_pump", "circ_pump", "rwcu_pump", "air_comp", "rb_hvac"}

SW_TEMP_C = 29.4           # river water, 85 F
TORUS_HX_W_PER_K = 1.0e6   # one RHR heat exchanger loop on HPSW, about 33 MW at 60 C torus water
VACUUM_TRIP_INHG = 22.5    # turbine trip on low condenser vacuum
VACUUM_ISOL_INHG = 7.0     # MSIV closure and bypass valves lost
AIR_SCRAM_PSIG = 60.0      # scram air header bled down
AIR_MSIV_PSIG = 50.0       # MSIVs drift shut
DIESEL_START_S = 10.0


def _tsat_f_of_inhg(inhg_abs: float) -> float:
    """Condensing temperature at an absolute back pressure (Antoine equation for water)."""
    mmhg = max(inhg_abs, 0.3) * 25.4
    c = 1730.63 / (8.07131 - math.log10(mmhg)) - 233.426
    return c * 9 / 5 + 32


class Auxiliaries:
    def __init__(self) -> None:
        self.on = {
            "cond_pump": [True, True, True], "heater": [True, True, True], "circ_pump": [True, True, True],
            "sjae": [True, False], "rwcu_pump": [True, True], "crd_pump": [True, False],
            "air_comp": [True, True, False], "hpsw_pump": [False] * 4, "torus_cool": [False, False],
            "sgts": [False, False], "rb_hvac": [True], "diesel": [False] * 4,
        }
        self.offsite = True
        self.sbo_t: float | None = None
        self.diesel_t = [0.0] * 4         # time each diesel has been cranking/running
        self.diesel_auto = [False] * 4    # started by an automatic signal (runs unloaded on the grid)
        self.diesels_failed = False       # station blackout: the diesels do not start on their own
        self.locked_out = {k: [False] * len(v) for k, v in self.on.items()}   # stopped by hand: no auto start
        self._sequencer: dict[str, list[bool]] = {}
        self.vacuum = 28.5
        self.cond_o2 = 15.0
        self.conductivity = 0.08
        self.crd_charging = 1450.0
        self.air = 105.0
        self.rb_dp = -0.25
        self.rwcu_isolated = False
        self.rb_isolated = False
        self._vacuum_isolated = False     # condenser taken away by low vacuum (not by the instructor)
        self._eccs_lost = False           # core spray / LPCI lost with the AC buses

    # ------------------------------------------------------------------ power

    def diesel_running(self, i: int) -> bool:
        return self.on["diesel"][i] and self.diesel_t[i] >= DIESEL_START_S

    def emergency_buses(self) -> int:
        return 4 if self.offsite else sum(self.diesel_running(i) for i in range(4))

    def powered(self, equip: str, i: int = 0) -> bool:
        if self.offsite:
            return True
        if equip in NON_SAFETY:
            return False
        if equip in ("hpsw_pump", "torus_cool", "sgts", "crd_pump"):
            return self.diesel_running(i % 4) or self.diesel_running((i + 2) % 4)
        return True

    def running(self, equip: str) -> list[bool]:
        return [on and self.powered(equip, i) for i, on in enumerate(self.on[equip])]

    def count(self, equip: str) -> int:
        return sum(self.running(equip))

    def lose_offsite(self, t: float, diesels_fail: bool = True) -> None:
        """Loss of all offsite power. In a station blackout the diesels also fail to start on
        their own; on a plain loss of offsite power they start, close onto their emergency buses
        after about ten seconds and pick up the safety loads."""
        self.offsite = False
        self.sbo_t = t
        self.diesels_failed = diesels_fail
        for k in NON_SAFETY:
            self.on[k] = [False] * len(self.on[k])
        # the safety loads drop off with the buses; the load sequencer restarts the running ones
        restart = {k: list(self.on[k]) for k in ("crd_pump", "hpsw_pump", "torus_cool", "sgts")}
        for k in restart:
            self.on[k] = [False] * len(self.on[k])
        self._sequencer = {} if diesels_fail else restart
        self._eccs_lost = True
        if diesels_fail:
            self.on["diesel"] = [False] * 4
            self.diesel_t = [0.0] * 4
        else:
            for i in range(4):
                if not self.on["diesel"][i]:
                    self.on["diesel"][i] = True
                    self.diesel_t[i] = 0.0
                self.diesel_auto[i] = True

    def restore_offsite(self) -> None:
        self.offsite = True
        self.sbo_t = None
        self.diesels_failed = False
        for k in ("cond_pump", "circ_pump", "rwcu_pump", "air_comp", "rb_hvac"):
            self.on[k] = [not lock and i < (2 if k == "air_comp" else 3) for i, lock in enumerate(self.locked_out[k])]
        self.on["rwcu_pump"] = [not self.rwcu_isolated and not l for l in self.locked_out["rwcu_pump"]]
        self.on["rb_hvac"] = [not self.rb_isolated]

    # ------------------------------------------------------------------ dynamics

    def crd_ok(self) -> bool:
        return self.count("crd_pump") > 0

    def sjae_ok(self, s) -> bool:
        return self.count("sjae") > 0 and s.msiv > 0.5 and steam.psig(s.pressure) > 150.0

    def rwcu_signal(self, s, slc_running: bool) -> bool:
        return s.level2_latched or s.level_in <= s.design.setpoints.level2_in or slc_running

    def rb_signal(self, s, cond: dict) -> bool:
        return cond.get("level_l2", False) or cond.get("drywell_press", False) or self.rad("rb_vent", s) > 16.0

    def _auto_start(self, s, equip: str, i: int, why: str) -> None:
        if self.on[equip][i] or self.locked_out[equip][i] or not self.powered(equip, i):
            return
        self.on[equip][i] = True
        s._event("trip", f"{NAMES[equip]}{'' if equip == 'diesel' else ' '}{UNITS[equip][i]} auto-started: {why}")

    def step(self, s, h: float, slc_running: bool, cond: dict) -> None:
        ev = s._event
        # Diesels start on a LOCA signal (Level 1 or high drywell pressure) and run unloaded,
        # ready for a loss of offsite power.
        if (cond.get("level_l1") or cond.get("drywell_press")) and not self.diesels_failed:
            for i in range(4):
                if not self.on["diesel"][i] and not self.locked_out["diesel"][i]:
                    self.on["diesel"][i] = True
                    self.diesel_t[i] = 0.0
                    self.diesel_auto[i] = True
                    ev("eccs", f"Diesel generator E{i + 1} auto-start on LOCA signal")
        # Diesels crank for ten seconds before the output breaker closes on the dead bus.
        for i in range(4):
            if self.on["diesel"][i]:
                before = self.diesel_running(i)
                self.diesel_t[i] += h
                if not before and self.diesel_running(i):
                    ev("operator", f"Diesel generator E{i + 1} up to speed, " +
                       ("paralleled to the grid" if self.offsite else f"emergency bus E{i + 1}2 energized"))
            else:
                self.diesel_t[i] = 0.0
        if self._eccs_lost and self.emergency_buses() > 0:
            s.core_spray.available = True
            s.lpci.available = True
            self._eccs_lost = False
            ev("operator", "Emergency buses energized: core spray and LPCI available")
        # load sequencer: the safety loads that were running come back on their buses
        for k, was in list(getattr(self, "_sequencer", {}).items()):
            for i, on in enumerate(was):
                if on and not self.on[k][i] and self.powered(k, i):
                    self.on[k][i] = True
                    was[i] = False
                    ev("operator", f"{NAMES[k]} {UNITS[k][i]} restarted by the load sequencer")

        # Condensate pumps feed the reactor feed pumps' suction.
        if self.count("cond_pump") == 0 and not s.feed_tripped and s.feed_available:
            s.trip_feedwater()
            ev("trip", "Reactor feed pumps tripped on low suction pressure (no condensate pumps)")
        s.heater_fraction = self.count("heater") / 3.0

        # Condenser vacuum: circulating water carries the heat away, the air ejectors the air.
        load = min(1.0, max(0.0, s.steam_out / max(s._rated_steam_flow(), 1.0)))
        circ = self.count("circ_pump")
        if not s.condenser_available and not self._vacuum_isolated:
            target, tau = 8.0, 20.0                           # instructor: condenser lost
        elif circ == 0:
            target, tau = 0.0, 40.0
        else:
            target, tau = 28.5 - (3 - circ) * 2.0 * load, 30.0
        follow = self.vacuum + (target - self.vacuum) * (1 - math.exp(-h / tau))
        follow = max(follow, self.vacuum - 0.1 * h)           # the condenser shell fills over minutes
        if not self.sjae_ok(s):
            # air in-leakage builds up with nothing pulling it out: about 2 inHg a minute
            follow = min(follow, self.vacuum - 0.035 * h)
        self.vacuum = max(0.0, follow)
        if self.vacuum < VACUUM_TRIP_INHG and not s.turbine_tripped and s.tsv > 0.5:
            s.trip_turbine("condenser vacuum low")
        if self.vacuum < VACUUM_ISOL_INHG and s.condenser_available:
            s.condenser_available = False
            self._vacuum_isolated = True
            ev("trip", "Condenser vacuum low: bypass valves unavailable")
            if s.msiv > 0.5:
                s.close_msivs("Condenser vacuum low")
        elif self._vacuum_isolated and self.vacuum > VACUUM_ISOL_INHG + 3.0:
            s.condenser_available = True
            self._vacuum_isolated = False
            ev("operator", "Condenser vacuum restored")
        # Dissolved oxygen in the condensate: the hotwell is the deaerator.
        o2 = 15.0 + max(0.0, 25.0 - self.vacuum) * 25.0 + (0.0 if self.sjae_ok(s) else 150.0)
        self.cond_o2 += (min(o2, 600.0) - self.cond_o2) * (1 - math.exp(-h / 120.0))

        # Reactor water cleanup isolates on Level 2 and on SLC (it would take the boron out).
        if self.rwcu_signal(s, slc_running) and not self.rwcu_isolated:
            self.rwcu_isolated = True
            self.on["rwcu_pump"] = [False, False]
            ev("trip", "RWCU isolation" + (": standby liquid control initiated" if slc_running else ": reactor level low (Level 2)"))
        cond_target = 0.08 if self.count("rwcu_pump") else 1.2
        rate = 1 / 300.0 if self.count("rwcu_pump") else 1 / 3600.0
        self.conductivity += (cond_target - self.conductivity) * (1 - math.exp(-h * rate))

        # CRD hydraulics: no pump, no drive water and no accumulator charging.
        if self.crd_ok():
            self.crd_charging += (1450.0 - self.crd_charging) * (1 - math.exp(-h / 5.0))
        else:
            self.crd_charging += (steam.psig(s.pressure) * 0.5 - self.crd_charging) * (1 - math.exp(-h / 60.0))
            if s.rods.command != 0 or s.rods.target is not None:
                s.drive_rods("stop")

        # Instrument air: the standby compressor starts on low header pressure.
        if self.air < 95.0:
            for i in range(3):
                if not self.on["air_comp"][i] and not self.locked_out["air_comp"][i]:
                    self._auto_start(s, "air_comp", i, "instrument air header pressure low")
                    break
        if self.count("air_comp"):
            self.air = min(105.0, self.air + 1.0 * h)
        else:
            self.air = max(0.0, self.air - 0.25 * h)
        if self.air < AIR_SCRAM_PSIG and not s.scrammed:
            s.scram("Scram air header pressure low (instrument air)")
        if self.air < AIR_MSIV_PSIG and s.msiv > 0.5 and not s.msiv_closing:
            s.close_msivs("Instrument air pressure low (MSIVs drift shut)")

        # RHR torus cooling on high pressure service water.
        loops = self.cooling_loops(s)
        if loops and s.torus_temp > SW_TEMP_C:
            s.torus_temp -= loops * TORUS_HX_W_PER_K * (s.torus_temp - SW_TEMP_C) * h / (s.design.torus_water_mass * 4186.0)

        # Secondary containment: Level 2, high drywell pressure or high reactor building
        # exhaust radiation isolate the building ventilation and start standby gas treatment.
        if self.rb_signal(s, cond) and not self.rb_isolated:
            self.rb_isolated = True
            self.on["rb_hvac"] = [False]
            self.on["sgts"] = [True, True]
            ev("trip", "Reactor building ventilation isolated, standby gas treatment started")
        sgts = self.count("sgts")
        hvac = self.count("rb_hvac")
        dp = 0.05 - 0.30 * hvac - (0.32 if sgts == 2 else 0.25 if sgts else 0.0)
        self.rb_dp += (dp - self.rb_dp) * (1 - math.exp(-h / 20.0))

    def cooling_loops(self, s) -> int:
        if not s.lpci.available:
            return 0
        hpsw = self.running("hpsw_pump")
        return sum(1 for i, on in enumerate(self.running("torus_cool")) if on and (hpsw[2 * i] or hpsw[2 * i + 1]))

    # ------------------------------------------------------------------ operator

    def command(self, s, t: float, equip: str, unit: str, slc_running: bool, cond: dict) -> None:
        if equip not in UNITS:
            raise CommandError(f"unknown equipment {equip!r}")
        units = UNITS[equip]
        unit = (unit or units[0]).upper()
        if unit not in units:
            raise CommandError(f"{NAMES[equip]} {unit} does not exist")
        i = units.index(unit)
        name = f"{NAMES[equip]} {unit}" if equip != "diesel" else f"{NAMES[equip]}{unit}"
        if equip == "rb_hvac":
            name = NAMES[equip]
        if self.on[equip][i]:
            self.on[equip][i] = False
            self.locked_out[equip][i] = True
            if equip == "diesel":
                self.diesel_auto[i] = False
            s._event("operator", f"{name} {'out of service' if equip == 'heater' else 'stopped'}")
            return
        if not self.powered(equip, i):
            raise CommandError(f"{name}: no power on its bus" + ("" if equip in NON_SAFETY else " (start a diesel generator)"))
        if equip == "rwcu_pump" and self.rwcu_isolated:
            if self.rwcu_signal(s, slc_running):
                raise CommandError("RWCU isolation signal present (Level 2 or SLC): cannot reset")
            self.rwcu_isolated = False
            s._event("operator", "RWCU isolation reset")
        if equip == "rb_hvac" and self.rb_isolated:
            if self.rb_signal(s, cond):
                raise CommandError("Secondary containment isolation signal present: cannot reset")
            self.rb_isolated = False
            s._event("operator", "Reactor building isolation reset")
        if equip == "torus_cool" and not s.lpci.available:
            raise CommandError("RHR pumps unavailable: torus cooling cannot start")
        self.on[equip][i] = True
        self.locked_out[equip][i] = False
        s._event("operator", f"{name} {'in service' if equip == 'heater' else 'starting' if equip == 'diesel' else 'started'}")

    # ------------------------------------------------------------------ readings

    def rad(self, which: str, s) -> float:
        pct = 100.0 * s.power / s.design.rated_power
        dmg = s.fuel_damage
        return {
            "offgas": (300.0 * pct / 100.0 * (1.0 + 200.0 * dmg)) if self.sjae_ok(s) else 0.0,  # mR/h, pretreatment
            "stack": 0.02 + 0.01 * pct / 100.0 + 40.0 * dmg,           # mR/h equivalent at the monitor
            "rb_vent": 0.4 + 400.0 * dmg,                                # mR/h
            "refuel": 0.3 + 100.0 * dmg,
            "cr_vent": 0.02 + 2.0 * dmg,
        }[which]

    def readings(self, s, gen_mw: float) -> dict:
        load = min(1.0, max(0.0, s.steam_out / max(s._rated_steam_flow(), 1.0)))
        circ = self.count("circ_pump")
        cond = self.count("cond_pump")
        hotwell = _tsat_f_of_inhg(29.92 - self.vacuum)
        fw_hot = s.design.feedwater_temp_c * 9 / 5 + 32
        dt_circ = (22.0 * load * 3 / circ) if circ else 0.0
        diesel_kw = []
        for i in range(4):
            if not self.diesel_running(i):
                diesel_kw.append(400.0 * min(1.0, self.diesel_t[i] / DIESEL_START_S) if self.on["diesel"][i] else 0.0)
            elif self.offsite:
                diesel_kw.append(0.0 if self.diesel_auto[i] else 2600.0)   # LOCA start: unloaded; surveillance run: loaded
            else:
                kw = 900.0 + 700.0 * self.running("hpsw_pump")[i] + 500.0 * self.running("crd_pump")[i % 2]
                kw += 1200.0 * (s.lpci.running or self.running("torus_cool")[i % 2]) + 800.0 * s.core_spray.running
                diesel_kw.append(min(kw, 3800.0))
        sbo_s = 0.0 if self.sbo_t is None else s.t - self.sbo_t
        dc = 130.0 if self.emergency_buses() else max(105.0, 128.0 - 23.0 * sbo_s / 14400.0)
        loops = self.cooling_loops(s)
        tt = s.torus_temp * 9 / 5 + 32
        return {
            "cond_header": (300.0 + 40.0 * cond) if cond else 0.0, "cond_o2": self.cond_o2, "hotwell_temp": hotwell,
            "cond_pump": (300.0 + 40.0 * cond) if cond else 0.0,
            **{f"fw_string_{u.lower()}": (fw_hot if on and s.heater_fraction > 0 and not s.turbine_tripped else hotwell + 8.0)
               for u, on in zip("ABC", self.on["heater"])},
            "vacuum": self.vacuum, "circ_in_temp": 85.0, "circ_out_temp": 85.0 + dt_circ,
            "circ_flow": 160.0 * circ, "sjae_steam": 120.0 if self.sjae_ok(s) else 0.0,
            "offgas_flow": (18.0 + 10.0 * load) if self.sjae_ok(s) else 0.0, "offgas_h2": 0.3 if self.sjae_ok(s) else 0.0,
            "rwcu_flow": 200.0 * self.count("rwcu_pump"), "conductivity": self.conductivity,
            "rwcu_inlet_temp": steam.t_sat(s.pressure) * 9 / 5 + 32 if self.count("rwcu_pump") else 120.0,
            "crd_charging": self.crd_charging, "crd_flow": 63.0 if self.crd_ok() else 0.0,
            "crd_drive_dp": 260.0 if (self.crd_ok() and (s.rods.command != 0 or s.rods.target is not None)) else (20.0 if self.crd_ok() else 0.0),
            "air_header": self.air,
            "hpsw_flow": 4500.0 * self.count("hpsw_pump"), "rhr_hx": 10000.0 * loops,
            "rhr_hx_out": (tt - 0.55 * (tt - 85.0)) if loops else tt,
            "rb_dp": self.rb_dp, "sgts_flow": 6000.0 * self.count("sgts"),
            "offgas_rad": self.rad("offgas", s), "stack_rad": self.rad("stack", s), "rb_vent_rad": self.rad("rb_vent", s),
            "refuel_rad": self.rad("refuel", s), "cr_vent_rad": self.rad("cr_vent", s),
            **{f"diesel_kw_{i + 1}": kw for i, kw in enumerate(diesel_kw)},
            **{f"e_bus_{i + 1}": 4.16 if (self.offsite or self.diesel_running(i)) else 0.0 for i in range(4)},
            "diesel_kw": sum(diesel_kw), "bus_4kv": 4.16 if self.offsite else 0.0, "dc_bus": dc,
            "grid_kv": 525.0 if self.offsite else 0.0,
            **{f"{k}_log": math.log10(max(self.rad(k, s), 1e-3)) for k in ("offgas", "stack", "rb_vent", "refuel", "cr_vent")},
            **{f"{equip}_{u.lower()}_amps": amps * (0.75 + 0.2 * load if equip in ("cond_pump", "circ_pump") else 0.9) if on else 0.0
               for equip, amps in MOTOR_AMPS.items() for u, on in zip(UNITS[equip], self.running(equip))},
        }

    def lamps(self) -> dict:
        out = {}
        for equip, units in UNITS.items():
            run = self.running(equip)
            for i, u in enumerate(units):
                key = f"{equip}_{u.lower()}"
                if equip == "diesel":
                    out[f"{key}_run"] = self.diesel_running(i)
                    out[f"{key}_stopped"] = not self.on["diesel"][i]
                else:
                    out[f"{key}_run"] = run[i]
                    out[f"{key}_stopped"] = not run[i]
        out["offsite_power"] = self.offsite
        out["rwcu_isolated"] = self.rwcu_isolated
        out["rb_isolated"] = self.rb_isolated
        return out

    def conditions(self, s) -> dict:
        at_power = s.power > 0.3 * s.design.rated_power
        return {
            "cond_pump_trip": self.count("cond_pump") < (2 if at_power else 1),
            "cond_o2_high": self.cond_o2 > 100.0,
            "fw_heater_out": self.count("heater") < 3,
            "vacuum_low": self.vacuum < 25.0,
            "circ_pump_trip": self.count("circ_pump") < 3,
            "sjae_trouble": not self.sjae_ok(s) and s.msiv > 0.5,
            "offgas_rad_high": self.rad("offgas", s) > 1000.0,
            "rwcu_isolated": self.rwcu_isolated,
            "conductivity_high": self.conductivity > 0.3,
            "crd_pump_trip": not self.crd_ok(),
            "crd_accum": self.crd_charging < 940.0,
            "air_low": self.air < 85.0,
            "scram_air_low": self.air < AIR_SCRAM_PSIG,
            "torus_cooling": self.cooling_loops(s) > 0,
            "rb_isolated": self.rb_isolated,
            "sgts_run": self.count("sgts") > 0,
            "rb_dp_low": self.rb_dp > -0.10,
            "rad_high": self.rad("rb_vent", s) > 16.0 or self.rad("stack", s) > 5.0,
            "diesel_run": any(self.diesel_running(i) for i in range(4)),
            "diesel_fail": not self.offsite and self.diesels_failed and not any(self.on["diesel"]),
            "dc_low": not self.emergency_buses() and self.sbo_t is not None and s.t - self.sbo_t > 1800.0,
            "loop": not self.offsite,
        }
