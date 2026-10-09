"""Scripted scenarios: normal operations, transients and accidents.

Each scenario builds a simulator, drives it like an operator (or a fault)
would, and returns a summary dict. The full time history stays on the returned
simulator for plotting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from reactorsim.simulator import Simulator


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    description: str
    run: Callable[..., tuple[Simulator, dict]]


def _summary(sim: Simulator, **extra) -> dict:
    a = sim.history_arrays()
    out = {
        "end_time_s": sim.t,
        "peak_power_w": float(a["power"].max()),
        "final_power_w": sim.power,
        "peak_fuel_temp_c": float(a["peak_fuel_temp"].max()),
        "peak_pool_temp_c": float(a["pool_temp"].max()),
        "fuel_damage_fraction": sim.fuel_damage,
        "scrammed": sim.scrammed,
        "scram_causes": list(sim.scram_causes),
        "events": [f"{e.time:9.1f} s  {e.kind:8s} {e.message}" for e in sim.events],
    }
    out.update(extra)
    return out


# ---------------------------------------------------------------------------- operator scripts

class StartupOperator:
    """Follows a PUR-1-style startup: shims to the shim range, regulating rod to 30 cm,
    then shims out in small steps to a stable positive period of 30-60 s, source out above 5 W,
    linear channel ranged up by hand, and the servo engaged near the target power."""

    def __init__(self, target_w: float = 10_000.0, shim_range_cm: float = 40.0, min_period_s: float = 30.0):
        self.target_w = target_w
        self.shim_range_cm = shim_range_cm
        self.min_period_s = min_period_s
        self.phase = "shims_to_range"
        self.wait_until = 0.0
        self.done = False

    def __call__(self, sim: Simulator) -> None:
        d = sim.design
        r = sim.instruments.readings
        shims = [sim.rods[n] for n in d.shim_rods]
        reg = sim.rods[d.regulating_rod]
        period = r.ch2_period if r.ch1_saturated else r.ch1_period

        # Range the linear channel like an operator: up at 80% of scale, down below 20%.
        if r.ch3_percent_of_range > 80:
            sim.instruments.range_up()
        elif r.ch3_percent_of_range < 20 and sim.instruments.ch3_range > 0 and self.phase != "shims_to_range":
            sim.instruments.range_down()
        if sim.source_inserted and sim.power > 5.0:
            sim.withdraw_source()
            sim._event("operator", "Source withdrawn above 5 W")

        if self.phase == "shims_to_range":
            for rod in shims:
                if rod.target is None and rod.drive_position < self.shim_range_cm - 1e-6:
                    sim.drive_to(rod.name, self.shim_range_cm)
            if all(rod.drive_position >= self.shim_range_cm - 1e-6 for rod in shims):
                sim.drive_to(reg.name, 30.0)
                self.phase = "reg_to_30"
        elif self.phase == "reg_to_30":
            if reg.target is None:
                self.phase = "approach"
                self.wait_until = sim.t + 30.0
        elif self.phase == "approach":
            if sim.t < self.wait_until:
                return
            if 0 < period < 120 and math.isfinite(period):
                self.phase = "ascend"
            else:
                for rod in shims:
                    sim.drive_to(rod.name, rod.drive_position + 0.5)
                self.wait_until = sim.t + 45.0
        elif self.phase == "ascend":
            if 0 < period < self.min_period_s:
                for rod in shims:
                    sim.drive_to(rod.name, rod.drive_position - 0.2)
            elif r.ch3_power_w >= 0.7 * self.target_w:
                sim.set_servo(True, self.target_w)
                sim._event("operator", f"Servo engaged at {self.target_w:g} W")
                self.phase = "hold"
            elif (period > 90 or period < 0) and sim.t >= self.wait_until:
                for rod in shims:
                    sim.drive_to(rod.name, rod.drive_position + 0.2)
                self.wait_until = sim.t + 20.0
        elif self.phase == "hold":
            if abs(sim.servo.error) < 0.01:
                self.done = True


# ---------------------------------------------------------------------------- scenarios

def startup(seed: int | None = None, target_w: float = 10_000.0, hold_s: float = 300.0):
    sim = Simulator(seed=seed)
    op = StartupOperator(target_w)
    sim.run(5400, record_every=1.0, each_step=op, until=lambda s: op.done)
    sim.run(hold_s, record_every=1.0)
    return sim, _summary(sim, startup_time_s=sim.t - hold_s,
                         critical_shim_cm=round(sim.rods["SS1"].position, 2),
                         reg_rod_cm=round(sim.rods["RR"].position, 2))


def scram_from_power(seed: int | None = None):
    sim = Simulator(seed=seed)
    sim.initialize_at_power(10_000.0)
    sim.run(20, record_every=0.05)
    sim.scram("Manual scram (console)")
    sim.run(30, record_every=0.05)
    sim.run(570, record_every=1.0)
    a = sim.history_arrays()
    # Stable negative period measured 300-550 s after the scram, once the shorter groups have died out.
    t, p = a["t"], a["power"]
    m = (t > 320) & (t < 570)
    slope = (math.log(p[m][-1]) - math.log(p[m][0])) / (t[m][-1] - t[m][0])
    i = int((t >= 21.0).argmax())
    return sim, _summary(sim, power_1s_after_scram_fraction=p[i] / 10_000.0,
                         stable_period_after_scram_s=1 / slope)


def xenon_transient(seed: int | None = None, run_hours: float = 40.0, shutdown_hours: float = 50.0):
    sim = Simulator(seed=seed, max_substep=2.0)
    sim.initialize_at_power(10_000.0, xenon="clean")
    sim.set_servo(True, 10_000.0)
    sim.run(run_hours * 3600, dt=1.0, record_every=300.0)
    eq = sim.reactivity()["xenon"]
    sim.scram("Planned shutdown")
    sim.run(shutdown_hours * 3600, dt=1.0, record_every=300.0)
    a = sim.history_arrays()
    after = a["t"] > run_hours * 3600
    k = int(a["rho_xenon"][after].argmin())
    beta = sim.design.delayed.beta_total
    return sim, _summary(sim, xenon_at_power_cents=100 * eq / beta,
                         peak_xenon_after_shutdown_cents=100 * a["rho_xenon"][after][k] / beta,
                         hours_to_xenon_peak=(a["t"][after][k] / 3600 - run_hours))


def experiment_insertion(seed: int | None = None, reactivity: float = 0.003, rps: bool = True):
    """An experiment worth the technical-specification limit (0.003 dk/k) is suddenly inserted at full power."""
    sim = Simulator(seed=seed)
    sim.initialize_at_power(10_000.0)
    sim.set_servo(True, 10_000.0)
    sim.protection.enabled = rps
    sim.run(10, record_every=0.05)
    sim.insert_reactivity(reactivity)
    sim._event("operator", f"Experiment inserted: {reactivity:+.4f} dk/k")
    sim.run(120, record_every=0.05)
    return sim, _summary(sim, inserted_dollars=reactivity / sim.design.delayed.beta_total)


def rod_withdrawal(seed: int | None = None, rps: bool = True, servo: bool = True, minutes: float = 30.0,
                   operator_scram: bool = True):
    """A shim-safety drive runs away (withdraws on its own) at full power."""
    sim = Simulator(seed=seed, max_substep=0.5)
    sim.initialize_at_power(10_000.0)
    sim.set_servo(servo, 10_000.0)
    sim.protection.enabled = rps
    sim.run(10, record_every=0.5)
    sim.rods["SS1"].runaway = True
    sim._event("operator", "Fault: SS1 drive runaway (continuous withdrawal)")
    first_alert: list[float] = []

    def operator(s: Simulator):
        # The operator responds to the first setback or alarm and scrams by hand after a 20 s delay.
        if not first_alert and (s.setback_active or s.events[-1].kind == "alarm"):
            first_alert.append(s.t)
        if operator_scram and first_alert and not s.scrammed and s.t > first_alert[0] + 20:
            s.scram("Manual scram (operator response to runaway rod)")

    sim.run(minutes * 60, record_every=0.5, each_step=operator)
    return sim, _summary(sim)


def reactivity_accident(seed: int | None = None, dollars: float = 1.5, rps: bool = False):
    """Hypothetical step insertion beyond prompt critical with the protection system failed.
    Shows the self-limiting power burst from temperature and void feedback."""
    sim = Simulator(seed=seed, max_substep=0.01)
    sim.initialize_at_power(100.0)
    sim.protection.enabled = rps
    sim.run(1, dt=0.005, record_every=0.005)
    sim.insert_reactivity(dollars * sim.design.delayed.beta_total)
    sim._event("operator", f"Step insertion of ${dollars:.2f}")
    sim.run(5, dt=0.001, record_every=0.001)
    sim.run(115, dt=0.05, record_every=0.1)
    a = sim.history_arrays()
    i = int(a["power"].argmax())
    half = a["power"] >= a["power"][i] / 2
    fwhm = float(a["t"][half].max() - a["t"][half].min()) if half.any() else 0.0
    burst_energy_j = float(((a["power"][1:] + a["power"][:-1]) / 2 * (a["t"][1:] - a["t"][:-1]))[a["t"][1:] < 7].sum())
    return sim, _summary(sim, dollars=dollars, burst_peak_time_s=float(a["t"][i]),
                         burst_fwhm_ms=1000 * fwhm, burst_energy_mj=burst_energy_j / 1e6)


def loss_of_chiller(seed: int | None = None, hours: float = 30.0):
    sim = Simulator(seed=seed, max_substep=2.0)
    sim.initialize_at_power(10_000.0)
    sim.set_servo(True, 10_000.0)
    sim.chiller_available = False
    sim._event("operator", "Chiller tripped")
    sim.run(hours * 3600, dt=1.0, record_every=60.0)
    alarm = next((e.time for e in sim.events if e.message == "Pool temperature high"), None)
    return sim, _summary(sim, hours_to_pool_temp_alarm=None if alarm is None else alarm / 3600,
                         heatup_rate_c_per_h=(sim.history[-1].pool_temp - sim.history[0].pool_temp)
                         / ((sim.history[-1].t - sim.history[0].t) / 3600))


def loss_of_pool_water(seed: int | None = None, leak_m_per_hour: float = 2.0, hours: float = 4.0):
    """A pool leak at full power. Radiation monitors see the shielding thin and scram the reactor;
    the drain continues below the top of the core."""
    sim = Simulator(seed=seed, max_substep=1.0)
    sim.initialize_at_power(10_000.0, history_hours=8.0)
    sim.set_servo(True, 10_000.0)
    sim.start_leak(leak_m_per_hour)
    sim._event("operator", f"Pool leak {leak_m_per_hour:g} m/h")

    def stop_leak_at_floor(s: Simulator):
        if s.level_m <= -s.design.thermal.core_height_m and s.leak_rate_m_s > 0:
            s.leak_rate_m_s = 0.0
            s._event("operator", "Pool drained below core")

    sim.run(hours * 3600, dt=0.5, record_every=10.0, each_step=stop_leak_at_floor)
    a = sim.history_arrays()
    return sim, _summary(sim, peak_pool_top_mr_h=float(a["ind_rad_pool_top"].max()),
                         level_at_scram_m=next((s.level for s in sim.history if s.scrammed), None))


def calibration_error(seed: int | None = None, gain: float = 1 / 3, minutes: float = 20.0):
    """Recreates the 2019-2020 PUR-1 event: new nuclear instruments read about 3x low,
    so holding an indicated 10 kW actually runs the core near 30 kW, past the 12 kW license limit."""
    sim = Simulator(seed=seed)
    sim.initialize_at_power(1_000.0)
    for ch in ("ch2", "ch3", "ch4"):
        sim.instruments.set_fault(ch, "gain", gain)
    sim._event("operator", f"Power channels miscalibrated: read {gain:.2f} x true")
    sim.instruments.auto_range(1000 * gain)
    sim.auto_range = True
    sim.set_servo(True, 10_000.0)
    sim.run(minutes * 60, record_every=1.0)
    return sim, _summary(sim, indicated_power_w=sim.instruments.readings.ch3_power_w,
                         true_power_w=sim.power, licensed_power_w=sim.design.licensed_power)


def linear_channel_failure(seed: int | None = None):
    """The linear channel feeding the servo fails low at full power. The servo sees power vanish
    and withdraws the regulating rod; the independent channels have to catch it."""
    sim = Simulator(seed=seed)
    sim.initialize_at_power(10_000.0)
    sim.set_servo(True, 10_000.0)
    sim.run(10, record_every=0.1)
    sim.set_channel_fault("ch3", "stuck")
    sim.instruments._last["ch3"] = 0.0
    sim.run(300, record_every=0.1)
    return sim, _summary(sim)


SCENARIOS: dict[str, Scenario] = {s.key: s for s in [
    Scenario("startup", "Normal startup to 10 kW",
             "Cold shutdown to 10 kW on the servo, following the startup procedure.", startup),
    Scenario("scram", "Scram from full power",
             "Manual scram at 10 kW: prompt drop then the -80 s stable period.", scram_from_power),
    Scenario("xenon", "Xenon transient",
             "40 h at 10 kW then shutdown: xenon build-up and post-shutdown peak.", xenon_transient),
    Scenario("experiment", "Experiment insertion",
             "A 0.003 dk/k experiment (tech spec limit) inserted at full power.", experiment_insertion),
    Scenario("rod_withdrawal", "Uncontrolled rod withdrawal",
             "A shim-safety drive runs away at full power.", rod_withdrawal),
    Scenario("rod_withdrawal_atws", "Rod withdrawal without scram",
             "Same runaway with the servo off and the protection system failed.",
             lambda seed=None: rod_withdrawal(seed, rps=False, servo=False, operator_scram=False)),
    Scenario("reactivity_accident", "Prompt-critical excursion (hypothetical)",
             "$1.50 step insertion with the protection system failed.", reactivity_accident),
    Scenario("reactivity_accident_large", "Large excursion (hypothetical)",
             "$4.00 step insertion with the protection system failed.",
             lambda seed=None: reactivity_accident(seed, dollars=4.0)),
    Scenario("loss_of_chiller", "Loss of pool cooling",
             "Chiller trips at 10 kW and the reactor keeps running.", loss_of_chiller),
    Scenario("loss_of_pool_water", "Loss of pool water",
             "Pool leak at full power, draining below the core.", loss_of_pool_water),
    Scenario("calibration_error", "Instrument miscalibration (2019-2020 event)",
             "Power channels read 3x low; servo holds indicated 10 kW.", calibration_error),
    Scenario("linear_channel_failure", "Servo channel failure",
             "Linear channel feeding the servo fails low at full power.", linear_channel_failure),
]}
