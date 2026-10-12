"""Reactor physics experiments: the classic research-reactor laboratory measurements.

Each experiment drives the simulator the way a student crew at the console would and
analyses only what the instruments show: count rates, log and linear power, rod
positions and pool temperature. Nothing in the analysis reads the model's internal
reactivity. The result reports each measured value next to the value built into the
model, so the measurement technique itself (its assumptions, noise and systematic
errors) can be judged, exactly as in a reactor physics lab report.

    python -m reactorsim experiments
    python -m reactorsim experiment rod_calibration --plot rr_worth.png
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy.optimize import brentq

from reactorsim.physics.kinetics import PointKinetics
from reactorsim.physics.thermal import WATER_CP, ThermalState
from reactorsim.reactors.base import ReactorDesign, temperature_reactivity
from reactorsim.simulator import Simulator


@dataclass(frozen=True)
class Experiment:
    key: str
    title: str
    objective: str
    run: Callable[..., tuple[Simulator, dict]]
    plot: Callable[[Simulator, dict, str], None] | None = None


@dataclass
class Recorder:
    """Logs instrument readings every control cycle, the way the console's data logger does."""

    t: list[float] = field(default_factory=list)
    log_w: list[float] = field(default_factory=list)  # Ch2 log power, converted to watts
    linear_w: list[float] = field(default_factory=list)  # Ch3 linear power
    cps: list[float] = field(default_factory=list)  # Ch1 count rate
    pool_c: list[float] = field(default_factory=list)
    rods: dict[str, list[float]] = field(default_factory=dict)

    def __call__(self, sim: Simulator) -> None:
        r = sim.instruments.readings
        self.t.append(sim.t)
        self.log_w.append(r.ch2_percent * sim.design.rated_power / 100.0)
        self.linear_w.append(r.ch3_power_w)
        self.cps.append(r.ch1_cps)
        self.pool_c.append(r.pool_temp)
        for name, rod in sim.rods.items():
            self.rods.setdefault(name, []).append(rod.position)

    def arrays(self, t0: float = -math.inf, t1: float = math.inf) -> dict[str, np.ndarray]:
        t = np.array(self.t)
        m = (t >= t0) & (t <= t1)
        out = {"t": t[m], "log_w": np.array(self.log_w)[m], "linear_w": np.array(self.linear_w)[m],
               "cps": np.array(self.cps)[m], "pool_c": np.array(self.pool_c)[m]}
        for name, v in self.rods.items():
            out[f"rod_{name}"] = np.array(v)[m]
        return out


# ---------------------------------------------------------------------------- analysis tools

def fit_period(t: np.ndarray, signal: np.ndarray) -> float:
    """Reactor period (s) from a least-squares fit of ln(signal) against time."""
    y = np.log(np.maximum(signal, 1e-30))
    slope = np.polyfit(t - t[0], y, 1)[0]
    return math.inf if slope == 0 else 1.0 / slope


def inhour_reactivity(design: ReactorDesign, period_s: float) -> float:
    """Reactivity (dk/k) that gives a stable period, from the inhour equation with the core's
    own delayed-neutron data and prompt generation time."""
    if not math.isfinite(period_s) or abs(period_s) > 1e7:
        return 0.0
    kin = PointKinetics(design.delayed, design.generation_time)
    omega = 1.0 / period_s
    lam_min = float(design.delayed.lam.min())
    if omega <= -lam_min:  # faster than the longest-lived group allows: the period is not stable yet
        omega = -lam_min * 0.999
    return kin.inhour_rho(omega)


def inverse_kinetics(design: ReactorDesign, t: np.ndarray, power: np.ndarray) -> np.ndarray:
    """Reactivity history (dk/k) from a measured power history: the reactivity computer.

    Starts from equilibrium precursors (a critical reactor at the first sample) and integrates
    the precursor equations exactly for power varying linearly between samples."""
    d = design.delayed
    lam, beta = d.lam, d.beta
    gen = design.generation_time
    p = np.maximum(np.asarray(power, dtype=float), 1e-30)
    c = beta * p[0] / (gen * lam)
    rho = np.zeros_like(p)
    for i in range(1, len(p)):
        h = t[i] - t[i - 1]
        e = np.exp(-lam * h)
        # Exact for P(t) linear over the interval.
        a0 = (1 - e) / lam
        a1 = (h - a0) / (lam * h) if h > 0 else 0.0
        c = c * e + beta / gen * (p[i - 1] * a0 + (p[i] - p[i - 1]) * a1)
        dpdt = (p[i] - p[i - 1]) / h if h > 0 else 0.0
        rho[i] = d.beta_total + gen * dpdt / p[i] - gen * float(np.sum(lam * c)) / p[i]
    rho[0] = rho[1] if len(rho) > 1 else 0.0
    return rho


def _cents(design: ReactorDesign, rho: float) -> float:
    return 100.0 * rho / design.delayed.beta_total


def _r(x: float, n: int = 4) -> float:
    return float(round(x, n)) if math.isfinite(x) else x


# ---------------------------------------------------------------------------- operator helpers

def _move(sim: Simulator, rod: str, position_cm: float, record=None, dt: float = 0.25,
          timeout_s: float = 900.0, attempts: int = 30) -> None:
    """Drive one rod to a position and wait for it to stop. A withdrawal interlock (a noisy short
    period on the startup channel, say) stops the drive; like an operator, wait a few seconds and
    try again, and fail loudly only if it never clears."""
    r = sim.rods[rod]
    goal = min(max(position_cm, 0.0), r.spec.length_cm)
    causes: list[str] = []
    for _ in range(attempts):
        sim.drive_to(rod, goal)
        sim.run(timeout_s, dt=dt, each_step=record, until=lambda s: r.target is None)
        if abs(r.drive_position - goal) <= 0.05:
            return
        prot = sim.last_protection
        causes = list(prot.interlock_causes) + list(prot.setback_causes) or causes
        sim.run(5.0, dt=dt, each_step=record)
    raise RuntimeError(f"{rod} stopped at {r.drive_position:.2f} cm short of {goal:.2f} cm "
                       f"(interlock: {'; '.join(causes) or 'unknown'})")


def _settle_instruments(sim: Simulator) -> None:
    """Let the count-rate and period meters settle on the present state (instrument time only),
    as the crew does before starting, so a noisy first reading cannot trip a period setback."""
    sim.instruments.auto_range(sim.power)
    for _ in range(int(60.0 / sim.control_dt)):
        sim._sample_instruments(sim.control_dt)


def _place_at_power(sim: Simulator, power_w: float, **kw) -> None:
    """Put the core at steady critical power (a start-up compressed to an instant)."""
    sim.initialize_at_power(power_w, **kw)
    sim._stop_positions.clear()  # the rods were placed, not driven: no drive drift
    _settle_instruments(sim)


def _wait(sim: Simulator, seconds: float, record=None, dt: float | None = None) -> None:
    sim.run(seconds, dt=dt, each_step=record)


def _rod_integral(design: ReactorDesign, rod: str):
    """The facility's existing worth curve for a rod (dk/k withdrawn at a position)."""
    spec = next(s for s in design.rods if s.name == rod)
    return lambda x: spec.worth * spec.worth_fraction_removed(x)


def _curve_from_points(points: list[tuple[float, float]]):
    xs = np.array([p[0] for p in points])
    ys = np.array([p[1] for p in points])
    return lambda x: float(np.interp(x, xs, ys))


def _servo_rod_position(sim: Simulator, settle_s: float, average_s: float, rec: Recorder) -> float:
    """Let the servo hold power, then read the regulating rod's average position."""
    _wait(sim, settle_s, rec, dt=0.1)
    t0 = sim.t
    _wait(sim, average_s, rec, dt=0.1)
    a = rec.arrays(t0)
    return float(a[f"rod_{sim.design.regulating_rod}"].mean())


# ---------------------------------------------------------------------------- 1. approach to critical

def approach_to_critical(seed: int | None = 1, reg_cm: float = 30.0, first_steps_cm: tuple = (20.0, 35.0),
                         max_step_cm: float = 5.0, count_s: float = 60.0):
    """Inverse multiplication (1/M) approach to critical with the startup source in.

    The regulating rod is set at ``reg_cm``; the two shim-safety rods are withdrawn as a bank
    (one at a time, as the interlock requires). After each step the crew waits for the count
    rate to settle, counts, plots 1/M = C0/C against bank height and extrapolates the last two
    points to predict the critical height. Each new step goes at most halfway to the prediction
    and never more than ``max_step_cm``: early predictions run long because the rods' worth per
    centimetre grows as they come out toward the middle of the core.
    """
    sim = Simulator(seed=seed, max_substep=0.5)
    d = sim.design
    rec = Recorder()
    sim.chiller_available = False  # keep the pool temperature (and so the critical height) steady
    sim.auto_range = True  # the crew ranges the linear channel up as the count rate climbs
    _settle_instruments(sim)
    _move(sim, d.regulating_rod, reg_cm, rec)

    def settle_and_count() -> float:
        # Wait in 30 s blocks until the count rate stops rising, then count. A rise that keeps
        # its pace instead of levelling off is a positive period: the bank has passed critical.
        means: list[float] = []
        for _ in range(40):
            t0 = sim.t
            _wait(sim, 30.0, rec, dt=0.25)
            means.append(float(rec.arrays(t0)["cps"].mean()))
            if len(means) < 2:
                continue
            ratios = [b / a for a, b in zip(means[:-1], means[1:])]
            if abs(ratios[-1] - 1) < 0.02:
                break
            if len(ratios) >= 4 and ratios[-1] >= ratios[-2] >= ratios[-3] > 1.02:
                raise _Supercritical()
        t0 = sim.t
        _wait(sim, count_s, rec, dt=0.25)
        return float(rec.arrays(t0)["cps"].mean())

    def set_bank(x: float) -> None:
        for name in d.shim_rods:
            _move(sim, name, x, rec)

    c0 = settle_and_count()
    rows = [(0.0, c0, 1.0, None)]
    x = 0.0
    predicted = None
    steps = list(first_steps_cm)
    supercritical = False
    for _ in range(25):
        if steps:
            nxt = steps.pop(0)
        else:
            nxt = x + min(0.5 * (predicted - x), max_step_cm)
        if predicted is not None and predicted - x < 0.25:
            break
        set_bank(nxt)
        x = nxt
        try:
            c = settle_and_count()
        except _Supercritical:
            supercritical = True
            break
        inv_m = c0 / c
        (x1, _, m1, _) = rows[-1]
        slope = (inv_m - m1) / (x - x1)
        predicted = x - inv_m / slope if slope < 0 else None
        rows.append((x, c, inv_m, predicted))
        if predicted is None:
            steps = steps or [x + max_step_cm]
        if inv_m < 0.02:
            break

    true_cm = _critical_bank(d, reg_cm, sim.thermal.pool_temp)
    est = rows[-1][3] if rows[-1][3] is not None else x
    result = {
        "measured": {"critical_bank_cm": _r(est, 2), "last_inverse_multiplication": _r(rows[-1][2], 4),
                     "source_count_rate_cps": _r(c0, 1), "steps": len(rows) - 1},
        "reference": {"critical_bank_cm": _r(true_cm, 2)},
        "error": {"critical_bank_cm": _r(est - true_cm, 2)},
        "table": {"columns": ["bank_cm", "count_rate_cps", "inverse_M", "predicted_critical_cm"],
                  "rows": [[_r(a, 2), _r(b, 1), _r(c, 4), None if p is None else _r(p, 2)]
                           for a, b, c, p in rows]},
        "notes": [f"Regulating rod held at {reg_cm:g} cm; startup source inserted throughout.",
                  "Prediction from a straight line through the last two 1/M points."
                  + (" The count rate showed a positive period, so the last step passed critical."
                     if supercritical else "")],
    }
    sim.recorder = rec
    return sim, result


class _Supercritical(Exception):
    pass


def _critical_bank(design: ReactorDesign, reg_cm: float, pool_temp: float) -> float:
    """Shim bank height that is exactly critical (source out) with the regulating rod at ``reg_cm``."""
    ref = Simulator(design)
    ref.thermal = ThermalState(pool_temp, pool_temp, pool_temp)
    ref.rods[design.regulating_rod].position = reg_cm

    def rho(x):
        for n in design.shim_rods:
            ref.rods[n].position = x
        return ref.reactivity()["total"]

    return brentq(rho, 0.0, min(ref.rods[n].spec.length_cm for n in design.shim_rods), xtol=1e-6)


# ---------------------------------------------------------------------------- 2. rod calibration

def rod_calibration(seed: int | None = 1, rod: str = "RR", step_cm: float = 8.0, power_w: float = 1.0,
                    compensating_rod: str = "SS1", wait_s: float = 60.0, fit_s: float = 90.0,
                    settle_s: float = 300.0):
    """Positive-period calibration of a control rod.

    Start critical at low power with the rod under test fully inserted. Each step withdraws it
    by ``step_cm``; once the transient has died away the stable period is fitted from the log
    power channel and converted to reactivity with the inhour equation. The reactor is then
    brought back down with a shim-safety rod and made critical again for the next step. The
    step worths give the differential worth curve, and their running sum the integral curve.
    """
    sim = Simulator(seed=seed, max_substep=0.5)
    d = design = sim.design
    if rod != d.regulating_rod:
        raise ValueError("the positive-period method here calibrates the regulating rod")
    _place_at_power(sim, power_w, reg_position_cm=0.0)
    sim.auto_range = True
    sim.chiller_available = False
    rec = Recorder()
    test = sim.rods[rod]
    comp = sim.rods[compensating_rod]
    comp_curve = _rod_integral(design, compensating_rod)  # the shim's curve from earlier calibrations
    beta = design.delayed.beta_total

    def measure_rho(seconds: float) -> tuple[float, float]:
        t0 = sim.t
        _wait(sim, seconds, rec, dt=0.1)
        a = rec.arrays(t0)
        period = fit_period(a["t"], a["log_w"])
        return inhour_reactivity(design, period), period

    def shim_to_add(rho: float) -> float:
        """Shim position change that adds ``rho`` according to the shim's worth curve."""
        x0 = comp.drive_position
        target = comp_curve(x0) + rho
        lo, hi = 0.0, comp.spec.length_cm
        if not comp_curve(lo) <= target <= comp_curve(hi):
            raise RuntimeError("compensating rod is out of range")
        return brentq(lambda x: comp_curve(x) - target, lo, hi, xtol=1e-4) - x0

    def trim() -> None:
        for _ in range(4):
            rho, _ = measure_rho(40.0)
            if abs(rho) < 0.002 * beta:
                return
            _move(sim, compensating_rod, comp.drive_position + shim_to_add(-rho), rec)

    positions = list(np.arange(0.0, test.spec.length_cm, step_cm)) + [test.spec.length_cm]
    if positions[-1] - positions[-2] < 1.0:
        positions.pop(-2)
    true_curve = _rod_integral(design, rod)
    rows = []
    _wait(sim, 30.0, rec, dt=0.1)
    trim()
    for x0, x1 in zip(positions[:-1], positions[1:]):
        rho_before, _ = measure_rho(60.0)
        _move(sim, rod, x1, rec, dt=0.1)
        _wait(sim, wait_s, rec, dt=0.1)
        rho_after, period = measure_rho(fit_s)
        step = rho_after - rho_before
        rows.append((x0, x1, period, step, true_curve(x1) - true_curve(x0)))
        # Insert the shim past critical (about -30 cents), let power fall back, then restore and trim.
        extra = -0.30 * beta
        _move(sim, compensating_rod, comp.drive_position + shim_to_add(-rho_after + extra), rec)
        sim.run(1800, dt=0.1, each_step=rec,
                until=lambda s: s.instruments.readings.ch2_percent * d.rated_power / 100 <= power_w)
        _move(sim, compensating_rod, comp.drive_position + shim_to_add(-extra), rec)
        # The power descent left the precursors out of balance with the new level; let the
        # longest-lived group (about 75 s mean life) settle before the next baseline.
        _wait(sim, settle_s, rec, dt=0.1)
        trim()

    integral = np.cumsum([r[3] for r in rows])
    points = [(positions[0], 0.0)] + [(r[1], float(v)) for r, v in zip(rows, integral)]
    total = float(integral[-1])
    result = {
        "measured": {"total_worth_dollars": _r(total / beta, 4), "total_worth_dk_k": _r(total, 6),
                     "max_differential_cents_per_cm": _r(max(_cents(d, r[3]) / (r[1] - r[0]) for r in rows), 3)},
        "reference": {"total_worth_dollars": _r(test.spec.worth / beta, 4), "total_worth_dk_k": test.spec.worth},
        "error": {"total_worth_percent": _r(100 * (total - test.spec.worth) / test.spec.worth, 2)},
        "table": {"columns": ["from_cm", "to_cm", "stable_period_s", "step_worth_cents", "model_step_cents",
                              "differential_cents_per_cm"],
                  "rows": [[_r(a, 2), _r(b, 2), _r(p, 1), _r(_cents(d, s), 3), _r(_cents(d, m), 3),
                            _r(_cents(d, s) / (b - a), 3)] for a, b, p, s, m in rows]},
        "integral_curve": [[_r(x, 2), _r(v, 7)] for x, v in points],
        "notes": [f"Started critical at {power_w:g} W with {rod} fully in; {compensating_rod} compensates.",
                  "Period fitted to Ch2 log power over "
                  f"{fit_s:g} s after a {wait_s:g} s wait; reactivity from the inhour equation."],
    }
    sim.recorder = rec
    return sim, result


# ---------------------------------------------------------------------------- 3. rod drop

def rod_drop(seed: int | None = 1, rod: str = "SS2", power_w: float = 50.0, reg_cm: float = 30.0):
    """Rod-drop measurement of a shim-safety rod's worth, and its drop time.

    From steady critical power one rod's magnet is de-energized. Its worth follows from the power
    history two ways: the prompt-jump estimate (rho in dollars = 1 - P0/P1, with P1 the level
    just after the prompt drop) and the inverse-kinetics reactivity computer. The rod-bottom time
    checks the technical specification (under 1 s from release).
    """
    sim = Simulator(seed=seed, max_substep=0.05)
    d = sim.design
    _place_at_power(sim, power_w, reg_position_cm=reg_cm)
    sim.auto_range = True
    rec = Recorder()
    _wait(sim, 20.0, rec, dt=0.05)
    r = sim.rods[rod]
    true_worth = r.spec.worth - r.inserted_worth()  # worth currently withdrawn, which the drop inserts
    t_drop = sim.t
    start_pos = r.position
    sim.drop_rod(rod)
    bottom = []

    def watch(s: Simulator):
        rec(s)
        if not bottom and s.rods[rod].position <= 0.0:
            bottom.append(s.t)

    sim.run(3.0, dt=0.005, each_step=watch)
    sim.run(120.0, dt=0.05, each_step=watch)
    a = rec.arrays()
    t, p = a["t"], a["log_w"]
    p0 = float(p[(t > t_drop - 10) & (t < t_drop)].mean())
    # Prompt-jump level: the power just after the rod reaches the bottom (0.8-1.2 s after release).
    p1 = float(p[(t > t_drop + 0.8) & (t < t_drop + 1.2)].mean())
    rho_pj = -(p0 / p1 - 1.0) * d.delayed.beta_total
    # Integral count method: rho($) = -P0 * sum(a_i / lambda_i) / integral of P after the drop,
    # with the tail past the record extrapolated on the final stable negative period.
    after = t >= t_drop
    tail = (t > t[-1] - 30)
    tau = -fit_period(t[tail], p[tail])
    area = float(np.sum((p[after][1:] + p[after][:-1]) / 2 * np.diff(t[after]))) + float(p[-1]) * tau
    dl = d.delayed
    rho_ic = -p0 * float(np.sum(dl.beta / dl.lam)) / area
    rho_ik_hist = inverse_kinetics(d, t[t > t_drop - 10], p[t > t_drop - 10])
    tk = t[t > t_drop - 10]
    window = (tk > t_drop + 5) & (tk < t_drop + 40)
    rho_ik = float(rho_ik_hist[window].mean())
    drop_time = (bottom[0] - t_drop) if bottom else math.inf
    beta = d.delayed.beta_total
    result = {
        "measured": {"worth_inverse_kinetics_dollars": _r(-rho_ik / beta, 4),
                     "worth_integral_count_dollars": _r(-rho_ic / beta, 4),
                     "worth_prompt_jump_dollars": _r(-rho_pj / beta, 4),
                     "drop_time_s": _r(drop_time, 3)},
        "reference": {"worth_dollars": _r(true_worth / beta, 4), "drop_time_limit_s": 1.0},
        "error": {"inverse_kinetics_percent": _r(100 * (-rho_ik - true_worth) / true_worth, 2),
                  "integral_count_percent": _r(100 * (-rho_ic - true_worth) / true_worth, 2),
                  "prompt_jump_percent": _r(100 * (-rho_pj - true_worth) / true_worth, 2)},
        "table": {"columns": ["time_after_drop_s", "log_power_w", "inverse_kinetics_cents"],
                  "rows": [[_r(tt - t_drop, 2), _r(pp, 4), _r(_cents(d, rr), 2)]
                           for tt, pp, rr in zip(tk[::40], p[t > t_drop - 10][::40], rho_ik_hist[::40])]},
        "notes": [f"{rod} dropped from {start_pos:.2f} cm at {power_w:g} W; the other rods stay latched.",
                  "Inverse kinetics averaged 5-40 s after the drop, from Ch2 log power.",
                  "The integral-count estimate reads a few percent low because the rod takes about half "
                  "a second to fall rather than entering as a step.",
                  "The prompt-jump estimate reads high: the shortest-lived precursor groups have already "
                  "decayed part way by the time the rod is on the bottom."],
    }
    sim.relatch_rod(rod)
    sim.recorder = rec
    sim._ik = (tk - t_drop, rho_ik_hist)
    return sim, result


# ---------------------------------------------------------------------------- 4. sample worth

def sample_worth(seed: int | None = 1, sample_dollars: float = -0.10, power_w: float = 1.0,
                 calibration: list | None = None):
    """Reactivity worth of an experiment sample by regulating-rod compensation.

    The servo holds the reactor at low power. The sample is lowered into the core; the servo
    moves the regulating rod to stay critical, and the sample worth is read off the rod's
    integral worth curve between the before and after positions. A negative ``sample_dollars``
    is an absorber (a cadmium or boron sample); a positive one is fissile material.
    ``calibration`` is an integral curve from ``rod_calibration`` ([cm, dk/k] points); without
    one the facility's existing curve is used.
    """
    sim = Simulator(seed=seed, max_substep=0.5)
    d = sim.design
    reg = d.regulating_rod
    start = 30.0 if sample_dollars < 0 else 48.0
    _place_at_power(sim, power_w, reg_position_cm=start)
    sim.set_servo(True, power_w)
    sim.auto_range = True
    sim.chiller_available = False
    rec = Recorder()
    curve = _curve_from_points(calibration) if calibration else _rod_integral(d, reg)
    x_before = _servo_rod_position(sim, 120.0, 60.0, rec)
    rho = sample_dollars * d.delayed.beta_total
    sim.insert_reactivity(rho, ramp_seconds=20.0)
    sim._event("operator", f"Sample lowered into the core ({sample_dollars:+.3f} $ in the model)")
    x_after = _servo_rod_position(sim, 300.0, 60.0, rec)
    measured = -(curve(x_after) - curve(x_before))
    beta = d.delayed.beta_total
    limit = 0.003  # PUR-1 technical specification: a single experiment worth under 0.3% dk/k
    result = {
        "measured": {"sample_worth_dollars": _r(measured / beta, 4), "sample_worth_dk_k": _r(measured, 6),
                     "rr_before_cm": _r(x_before, 2), "rr_after_cm": _r(x_after, 2),
                     "within_tech_spec": abs(measured) < limit},
        "reference": {"sample_worth_dollars": _r(sample_dollars, 4), "tech_spec_limit_dk_k": limit},
        "error": {"percent": _r(100 * (measured - rho) / rho, 2)},
        "notes": [f"Servo holding {power_w:g} W on Ch3; regulating rod start {start:g} cm.",
                  "Rod worth curve: " + ("from the supplied calibration" if calibration
                                         else "the facility's existing regulating-rod curve") + "."],
    }
    sim.recorder = rec
    return sim, result


# ---------------------------------------------------------------------------- 5. temperature coefficient

def temperature_coefficient(seed: int | None = 1, temps_c: tuple = (18.0, 21.0, 24.0, 27.0),
                            power_w: float = 1.0, calibration: list | None = None):
    """Isothermal temperature coefficient of reactivity.

    At low power (no nuclear heating) the pool, core water and fuel share the pool temperature.
    The pool is brought to each temperature in turn (in the plant, by running with the chiller
    off or on over hours; here the instructor sets it); at each one the servo finds the critical
    regulating-rod position, and the rod's worth curve turns the position changes into reactivity.
    The slope of reactivity against temperature is the isothermal coefficient.
    """
    sim = Simulator(seed=seed, max_substep=0.5)
    d = sim.design
    reg = d.regulating_rod
    sim.thermal = ThermalState(temps_c[0], temps_c[0], temps_c[0])
    _place_at_power(sim, power_w, reg_position_cm=20.0)
    sim.set_servo(True, power_w)
    sim.auto_range = True
    sim.chiller_available = False
    rec = Recorder()
    curve = _curve_from_points(calibration) if calibration else _rod_integral(d, reg)
    rows = []
    for T in temps_c:
        sim.thermal = ThermalState(T, T, T)
        sim._event("operator", f"Pool at {T:g} C")
        x = _servo_rod_position(sim, 300.0, 60.0, rec)
        rows.append((T, float(np.mean(rec.arrays(sim.t - 60)["pool_c"])), x, curve(x)))
    temps = np.array([r[1] for r in rows])
    # Reactivity the rod has added relative to the first point balances the temperature defect.
    defect = -(np.array([r[3] for r in rows]) - rows[0][3])
    alpha = float(np.polyfit(temps, defect, 1)[0])
    mid = float(np.mean(temps))
    ref = (temperature_reactivity(mid + 0.5, d.reference_temp, d.moderator_coefficient)
           - temperature_reactivity(mid - 0.5, d.reference_temp, d.moderator_coefficient)
           + temperature_reactivity(mid + 0.5, d.reference_temp, d.fuel_coefficient)
           - temperature_reactivity(mid - 0.5, d.reference_temp, d.fuel_coefficient))
    result = {
        "measured": {"alpha_dk_k_per_c": _r(alpha, 8), "alpha_cents_per_c": _r(_cents(d, alpha), 4)},
        "reference": {"alpha_dk_k_per_c": _r(ref, 8), "alpha_cents_per_c": _r(_cents(d, ref), 4)},
        "error": {"percent": _r(100 * (alpha - ref) / ref, 2)},
        "table": {"columns": ["pool_c", "rr_critical_cm", "temperature_defect_cents"],
                  "rows": [[_r(r[1], 2), _r(r[2], 2), _r(_cents(d, v), 3)] for r, v in zip(rows, defect)]},
        "notes": [f"Servo holding {power_w:g} W; chiller off; shim-safety rods fixed.",
                  "Model reference is the fuel plus moderator coefficient at the mean temperature."],
    }
    sim.recorder = rec
    return sim, result


# ---------------------------------------------------------------------------- 6. calorimetric power calibration

def power_calibration(seed: int | None = 1, indicated_w: float = 10_000.0, channel_gain: float = 1.0,
                      baseline_min: float = 30.0, settle_min: float = 10.0, heat_min: float = 40.0):
    """Calorimetric (heat balance) calibration of the power channels.

    With the chiller off, the pool's heat-up rate at power, less the drift rate measured with
    the reactor shut down (losses to the room), times the heat capacity of the pool water gives
    the thermal power. Comparing it with the indicated power gives the calibration factor for the
    nuclear channels. ``channel_gain`` miscalibrates channels 2-4 (1/3 recreates the 2019 PUR-1
    event), which this measurement is meant to catch.
    """
    sim = Simulator(seed=seed, max_substep=2.0)
    d = sim.design
    if channel_gain != 1.0:
        for ch in ("ch2", "ch3", "ch4"):
            sim.instruments.set_fault(ch, "gain", channel_gain)
    sim.chiller_available = False
    _settle_instruments(sim)
    rec = Recorder()
    # Baseline drift with the reactor shut down.
    _wait(sim, baseline_min * 60, rec, dt=1.0)
    base = rec.arrays()
    off_rate = float(np.polyfit(base["t"], base["pool_c"], 1)[0])
    # At power on the servo (start-up compressed: the core is placed at power directly).
    true_w = indicated_w / channel_gain
    _place_at_power(sim, true_w, reg_position_cm=30.0)
    sim.set_servo(True, indicated_w)
    sim.auto_range = True
    sim._event("operator", f"At {indicated_w:g} W indicated on the servo")
    _wait(sim, settle_min * 60, rec, dt=0.5)
    t0 = sim.t
    thermal = []
    sim.run(heat_min * 60, dt=0.5, each_step=lambda s: (rec(s), thermal.append(s.thermal_power())))
    a = rec.arrays(t0)
    on_rate = float(np.polyfit(a["t"], a["pool_c"], 1)[0])
    heat_capacity = (d.thermal.pool_water_mass + d.thermal.core_water_mass) * WATER_CP
    p_cal = heat_capacity * (on_rate - off_rate)
    ind = float(a["linear_w"].mean())
    true_thermal = float(np.mean(thermal))
    result = {
        "measured": {"calorimetric_power_w": _r(p_cal, 1), "indicated_power_w": _r(ind, 1),
                     "calibration_factor": _r(p_cal / ind, 4),
                     "heatup_rate_c_per_h": _r(on_rate * 3600, 4), "drift_rate_c_per_h": _r(off_rate * 3600, 4)},
        "reference": {"thermal_power_w": _r(true_thermal, 1), "true_factor": _r(true_thermal / ind, 4)},
        "error": {"percent": _r(100 * (p_cal - true_thermal) / true_thermal, 2)},
        "notes": [f"Heat capacity of pool and core water: {heat_capacity / 1e6:.2f} MJ/C.",
                  f"Drift measured over {baseline_min:g} min shut down; heat-up fitted over {heat_min:g} min "
                  f"after {settle_min:g} min at power."
                  + (f" Channels 2-4 miscalibrated to read {channel_gain:g} x true." if channel_gain != 1 else "")],
    }
    sim.recorder = rec
    return sim, result


# ---------------------------------------------------------------------------- plots

def _fig(n: int, title: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(n, 1, figsize=(9, 3.6 * n), constrained_layout=True, squeeze=False)
    fig.suptitle(title, fontsize=12)
    return plt, fig, [a[0] for a in ax]


def _save(plt, fig, ax, path):
    for a in ax:
        a.grid(alpha=0.25)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_approach(sim, res, path):
    plt, fig, ax = _fig(2, "Approach to critical: inverse multiplication")
    rows = res["table"]["rows"]
    x = [r[0] for r in rows]
    ax[0].plot(x, [r[2] for r in rows], "o-", color="#1f4e79", label="1/M measured")
    for r in rows:
        if r[3] is not None:
            ax[0].plot([r[0], r[3]], [r[2], 0], ":", color="#999", lw=0.8)
    ax[0].axvline(res["reference"]["critical_bank_cm"], color="#c00000", lw=1, label="true critical bank")
    ax[0].set_xlabel("Shim bank height (cm)")
    ax[0].set_ylabel("1/M")
    ax[0].set_ylim(bottom=0)
    ax[0].set_xlim(0, max(r.spec.length_cm for r in sim.rods.values()))
    ax[0].legend(frameon=False)
    a = sim.recorder.arrays()
    ax[1].semilogy(a["t"] / 60, a["cps"], color="#c55a11", lw=0.8)
    ax[1].set_xlabel("Time (min)")
    ax[1].set_ylabel("Ch1 count rate (cps)")
    _save(plt, fig, ax, path)


def _plot_calibration(sim, res, path):
    plt, fig, ax = _fig(3, "Regulating rod calibration (positive period)")
    rows = res["table"]["rows"]
    mid = [(r[0] + r[1]) / 2 for r in rows]
    ax[0].bar(mid, [r[5] for r in rows], width=[r[1] - r[0] for r in rows], alpha=0.5, edgecolor="#1f4e79",
              label="measured")
    ax[0].plot(mid, [r[4] / (r[1] - r[0]) for r in rows], "o", color="#c00000", label="model")
    ax[0].set_ylabel("Differential worth (cents/cm)")
    ax[0].legend(frameon=False)
    beta = sim.design.delayed.beta_total
    xs, ys = zip(*res["integral_curve"])
    ax[1].plot(xs, [100 * y / beta for y in ys], "o-", color="#1f4e79", label="measured")
    f = _rod_integral(sim.design, sim.design.regulating_rod)
    fine = np.linspace(0, xs[-1], 200)
    ax[1].plot(fine, [100 * f(v) / beta for v in fine], color="#c00000", lw=1, label="model")
    ax[1].set_xlabel("Rod position (cm withdrawn)")
    ax[1].set_ylabel("Integral worth (cents)")
    ax[1].legend(frameon=False)
    a = sim.recorder.arrays()
    ax[2].semilogy(a["t"] / 60, a["log_w"], color="#c55a11", lw=0.8)
    ax[2].set_xlabel("Time (min)")
    ax[2].set_ylabel("Ch2 log power (W)")
    _save(plt, fig, ax, path)


def _plot_drop(sim, res, path):
    plt, fig, ax = _fig(2, "Rod drop")
    t, rho = sim._ik
    a = sim.recorder.arrays()
    ax[0].semilogy(t, a["log_w"][-len(t):], color="#1f4e79", lw=1)
    ax[0].set_ylabel("Ch2 log power (W)")
    beta = sim.design.delayed.beta_total
    ax[1].plot(t, 100 * rho / beta, color="#c55a11", lw=0.8, label="inverse kinetics")
    ax[1].axhline(-100 * res["reference"]["worth_dollars"], color="#c00000", lw=1, ls="--", label="model")
    ax[1].set_ylabel("Reactivity (cents)")
    ax[1].set_xlabel("Time after drop (s)")
    ax[1].legend(frameon=False)
    _save(plt, fig, ax, path)


def _plot_rod_trace(title):
    def plot(sim, res, path):
        plt, fig, ax = _fig(2, title)
        a = sim.recorder.arrays()
        ax[0].plot(a["t"] / 60, a[f"rod_{sim.design.regulating_rod}"], color="#1f4e79")
        ax[0].set_ylabel("Regulating rod (cm)")
        ax[1].plot(a["t"] / 60, a["pool_c"], color="#548235")
        ax[1].set_ylabel("Pool temperature (C)")
        ax[1].set_xlabel("Time (min)")
        _save(plt, fig, ax, path)
    return plot


def _plot_power_cal(sim, res, path):
    plt, fig, ax = _fig(2, "Calorimetric power calibration")
    a = sim.recorder.arrays()
    ax[0].plot(a["t"] / 60, a["pool_c"], color="#548235")
    ax[0].set_ylabel("Pool temperature (C)")
    ax[1].plot(a["t"] / 60, a["linear_w"], color="#c55a11", lw=0.8, label="Ch3 indicated")
    ax[1].axhline(res["measured"]["calorimetric_power_w"], color="#1f4e79", ls="--", label="calorimetric")
    ax[1].set_ylabel("Power (W)")
    ax[1].set_xlabel("Time (min)")
    ax[1].legend(frameon=False)
    _save(plt, fig, ax, path)


# ---------------------------------------------------------------------------- materials science

class _LabBench:
    """The reactor and the materials lab run together, as in the control room session."""

    def __init__(self, seed: int | None, power_w: float, unknown_seed: int = 0):
        from reactorsim.materials import MaterialsLab
        self.sim = Simulator(seed=seed, max_substep=2.0)
        d = self.sim.design
        _place_at_power(self.sim, power_w, reg_position_cm=30.0)
        self.sim.set_servo(True, power_w)
        self.sim.auto_range = True
        self.lab = MaterialsLab(d.flux_per_watt, d.delayed.beta_total,
                                np.random.default_rng(None if seed is None else seed + 1), unknown_seed)
        self.sim.recorder = Recorder()

    @property
    def t(self) -> float:
        return self.sim.t

    def run(self, seconds: float, step: float = 1.0) -> None:
        end = self.sim.t + seconds
        while self.sim.t < end - 1e-9:
            h = min(step, end - self.sim.t)
            t0, e0 = self.sim.t, self.sim.energy_j
            self.sim.run(h, dt=min(h, 0.5), record_every=60.0, each_step=self.sim.recorder)
            self.lab.advance(self.sim.t - t0, (self.sim.energy_j - e0) / (self.sim.t - t0), t0)

    def irradiate(self, samples, position: str, seconds: float) -> None:
        for smp in samples:
            self.sim.insert_reactivity(self.lab.insert(smp.id, position, self.t), ramp_seconds=5.0)
        self.run(seconds, step=5.0)
        for smp in samples:
            self.sim.insert_reactivity(self.lab.remove(smp.id, self.t), ramp_seconds=5.0)

    def count(self, smp, live_s: float, shelf_cm: float = 10.0) -> dict:
        c = self.lab.start_count(smp.id, live_s, shelf_cm, self.t)
        step = max(min(live_s / 40, 30.0), 0.5)
        while not c.done:
            self.run(step, step=step)
        return smp.counts[-1]


def _flux_pair(bench: _LabBench, position: str, seconds: float, shelf_cm: float = 25.0, live_s: float = 300.0):
    bare = bench.lab.prepare("gold_foil")
    cov = bench.lab.prepare("gold_foil", cadmium=True)
    bench.irradiate([bare, cov], position, seconds)
    bench.run(60)
    bench.count(bare, live_s, shelf_cm)
    bench.count(cov, live_s, shelf_cm)
    return bare, cov


def foil_activation(seed: int | None = 1, position: str = "core_center", power_w: float = 1000.0,
                    minutes: float = 15.0):
    """Thermal and epithermal neutron flux and the cadmium ratio from bare and cadmium-covered gold foils."""
    bench = _LabBench(seed, power_w)
    bare, cov = _flux_pair(bench, position, minutes * 60)
    f = bench.lab.results(bench.t)["flux"][position]
    th, epi, _ = bench.lab.flux(position, 1000.0)
    from reactorsim.materials import REACTIONS
    au = REACTIONS["Au-198"][1]
    true_cr = (au.sigma_b * th + au.ri_b * epi) / (au.ri_b * epi)
    result = {
        "measured": {"thermal_flux_per_kw": _r(f["thermal_per_kw"], -1), "epithermal_flux_per_kw": _r(f["epithermal_per_kw"], -1),
                     "cadmium_ratio": _r(f["cadmium_ratio"], 3),
                     "dead_time_bare": _r(bare.counts[-1]["dead_time"], 3)},
        "reference": {"thermal_flux_per_kw": _r(th, -1), "epithermal_flux_per_kw": _r(epi, -1), "cadmium_ratio": _r(true_cr, 3)},
        "error": {"thermal_percent": _r(100 * (f["thermal_per_kw"] - th) / th, 2),
                  "epithermal_percent": _r(100 * (f["epithermal_per_kw"] - epi) / epi, 2)},
        "notes": [f"10 mg gold foils, {minutes:g} min at {power_w:g} W in {position}; counted 300 s at 25 cm."],
    }
    return bench.sim, result


def activation_analysis(seed: int | None = 1, material: str = "unknown_ore", unknown_seed: int = 0,
                        power_w: float = 10_000.0, minutes: float = 30.0):
    """Neutron activation analysis of an unknown: element identification and concentrations (absolute
    method) from gamma spectra, with the flux measured by gold foils at the same position."""
    bench = _LabBench(seed, power_w, unknown_seed)
    _flux_pair(bench, "core_center", 600, shelf_cm=50.0, live_s=120.0)
    smp = bench.lab.prepare(material)
    bench.irradiate([smp], "core_center", minutes * 60)
    bench.run(120)
    bench.count(smp, 900, shelf_cm=25.0)   # short-lived products (Al-28, Cl-38, Mn-56)
    bench.run(12 * 3600, step=60.0)
    bench.count(smp, 3600, shelf_cm=10.0)  # long-lived ones once the short ones are gone (Na-24, K-42, Fe-59)
    masses = bench.lab.results(bench.t)["analyses"][smp.id].get("element_masses_g", {})
    rows = []
    for el, frac in sorted(smp.composition.items(), key=lambda kv: -kv[1]):
        m = masses.get(el)
        rows.append([el, _r(frac * 1e6, 1), None if m is None else _r(m / smp.mass_g * 1e6, 1),
                     None if m is None else _r(100 * (m / smp.mass_g - frac) / frac, 1)])
    found = [r for r in rows if r[2] is not None]
    result = {
        "measured": {"elements_found": [r[0] for r in found],
                     "worst_error_percent": _r(max(abs(r[3]) for r in found), 2) if found else None},
        "reference": {"elements_present": [r[0] for r in rows]},
        "table": {"columns": ["element", "true_ppm", "measured_ppm", "error_percent"], "rows": rows},
        "notes": [f"{smp.mass_g * 1000:g} mg {smp.name}, {minutes:g} min at {power_w:g} W in the centre position.",
                  "Counted 15 min at 25 cm after 2 min, then 1 h at 10 cm after 12 h.",
                  "Si, O and Zn make no usable gamma emitters, so NAA does not see them."],
    }
    return bench.sim, result


def half_life(seed: int | None = 1, material: str = "indium_foil", counts: int = 6, live_s: float = 300.0,
              gap_s: float = 300.0, power_w: float = 100.0, minutes: float = 5.0):
    """Half-life from repeated counts of a short-lived activation product."""
    from reactorsim.materials import REACTIONS
    bench = _LabBench(seed, power_w)
    smp = bench.lab.prepare(material)
    bench.irradiate([smp], "core_center", minutes * 60)
    bench.run(60)
    rows = []
    for _ in range(counts):
        res = bench.count(smp, live_s, shelf_cm=10.0)
        pk = max(res["peaks"], key=lambda p: p["net"])
        rows.append([_r(res["start_t"] - smp.time_out, 1), pk["nuclide"], _r(pk["net"], 0), _r(res["dead_time"], 3)])
        bench.run(gap_s)
    product = rows[0][1]
    hl = bench.lab.half_life(smp, product)
    ref = REACTIONS[product][1].half_life_s
    result = {
        "measured": {"nuclide": product, "half_life_s": _r(hl["half_life_s"], 1)},
        "reference": {"half_life_s": ref},
        "error": {"percent": _r(100 * (hl["half_life_s"] - ref) / ref, 2)},
        "table": {"columns": ["since_eoi_s", "nuclide", "net_counts", "dead_time"], "rows": rows},
        "notes": [f"{smp.name}, {minutes:g} min at {power_w:g} W; {counts} counts of {live_s:g} s."],
    }
    return bench.sim, result


def silicon_doping(seed: int | None = 1, target_ohm_cm: float = 2000.0, power_w: float = 10_000.0):
    """Neutron transmutation doping: irradiate a float-zone silicon wafer to a target resistivity using
    the measured flux, then check it against the phosphorus actually made."""
    from reactorsim.materials import MaterialsLab
    bench = _LabBench(seed, power_w)
    _flux_pair(bench, "core_center", 600, shelf_cm=50.0, live_s=120.0)
    f = bench.lab.results(bench.t)["flux"]["core_center"]
    probe = MaterialsLab.ntd(None, 1.0)
    n0 = 1.0 / (1.602e-19 * 1350.0 * probe["initial_resistivity_ohm_cm"])
    donors_needed = 1.0 / (1.602e-19 * 1350.0 * target_ohm_cm) - n0
    per_fluence = probe["phosphorus_per_cm3"]
    seconds = donors_needed / per_fluence / (f["thermal_per_kw"] * power_w / 1000)
    wafer = bench.lab.prepare("silicon_wafer")
    bench.irradiate([wafer], "core_center", seconds)
    predicted = bench.lab.results(bench.t)["ntd"][wafer.id]["resistivity_ohm_cm"]
    actual = MaterialsLab.ntd(wafer, wafer.fluence_thermal)["resistivity_ohm_cm"]
    result = {
        "measured": {"irradiation_h": _r(seconds / 3600, 3), "predicted_resistivity_ohm_cm": _r(predicted, 1)},
        "reference": {"target_ohm_cm": target_ohm_cm, "actual_resistivity_ohm_cm": _r(actual, 1)},
        "error": {"percent_from_target": _r(100 * (actual - target_ohm_cm) / target_ohm_cm, 2)},
        "notes": ["Irradiation time from the gold-foil flux; the actual resistivity uses the wafer's true fluence."],
    }
    return bench.sim, result


def radiation_damage(seed: int | None = 1, power_w: float = 10_000.0, hours: float = 1.0, cool_h: float = 8.0):
    """Fast flux from Ni-58(n,p)Co-58 in a steel coupon, displacement damage (dpa) and the activation of the steel."""
    bench = _LabBench(seed, power_w)
    smp = bench.lab.prepare("steel_304")
    bench.irradiate([smp], "core_center", hours * 3600)
    dose_out = smp.dose_rate_mr_h()
    bench.run(cool_h * 3600, step=60.0)
    res = bench.count(smp, 3600, shelf_cm=10.0)
    dmg = bench.lab.results(bench.t)["damage"][smp.id]
    true_fast = bench.lab.flux("core_center", power_w)[2]
    result = {
        "measured": {"fast_flux": _r(dmg["fast_flux"], -1), "dpa": dmg["dpa"], "hardening_mpa": _r(dmg["hardening_mpa"], 3),
                     "dose_at_removal_mr_h_30cm": _r(dose_out, 2), "nuclides": sorted({p["nuclide"] for p in res["peaks"]})},
        "reference": {"fast_flux": _r(true_fast, -1), "dpa": bench.lab.damage(smp.fluence_fast)["dpa"]},
        "error": {"fast_flux_percent": _r(100 * (dmg["fast_flux"] - true_fast) / true_fast, 2)},
        "notes": [f"{hours:g} h at {power_w:g} W in the centre position, {cool_h:g} h cooling, 1 h count at 10 cm."],
    }
    return bench.sim, result


EXPERIMENTS: dict[str, Experiment] = {e.key: e for e in [
    Experiment("approach_to_critical", "Approach to critical (1/M)",
               "Predict the critical shim bank height from the source multiplication.",
               approach_to_critical, _plot_approach),
    Experiment("rod_calibration", "Regulating rod calibration (positive period)",
               "Measure the regulating rod's differential and integral worth curves.",
               rod_calibration, _plot_calibration),
    Experiment("rod_drop", "Rod drop: shim-safety rod worth and drop time",
               "Measure SS2's worth by prompt jump and inverse kinetics, and its drop time.",
               rod_drop, _plot_drop),
    Experiment("sample_worth", "Experiment sample worth",
               "Measure an absorber sample's reactivity by regulating-rod compensation.",
               sample_worth, _plot_rod_trace("Sample worth by rod compensation")),
    Experiment("temperature_coefficient", "Isothermal temperature coefficient",
               "Measure the reactivity change per degree of pool temperature.",
               temperature_coefficient, _plot_rod_trace("Isothermal temperature coefficient")),
    Experiment("power_calibration", "Calorimetric power calibration",
               "Calibrate the power channels against the pool heat-up rate.",
               power_calibration, _plot_power_cal),
    Experiment("foil_activation", "Neutron flux and cadmium ratio (gold foils)",
               "Measure thermal and epithermal flux with bare and cadmium-covered gold foils.", foil_activation),
    Experiment("activation_analysis", "Neutron activation analysis of an unknown",
               "Identify and quantify the elements in an unknown sample from its gamma spectrum.",
               activation_analysis),
    Experiment("half_life", "Half-life measurement",
               "Fit the decay of In-116m over repeated counts.", half_life),
    Experiment("silicon_doping", "Silicon neutron transmutation doping",
               "Dope a silicon wafer to 2000 ohm-cm with thermal neutrons.", silicon_doping),
    Experiment("radiation_damage", "Radiation damage and activation of steel",
               "Measure fast flux with Ni-58(n,p)Co-58 and work out the displacement damage.", radiation_damage),
]}
