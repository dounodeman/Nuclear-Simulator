import math

import pytest

from reactorsim import Simulator
from reactorsim.cli import main
from reactorsim.experiments import EXPERIMENTS, fit_period, inhour_reactivity, inverse_kinetics


def run(key, **kw):
    return EXPERIMENTS[key].run(**kw)


def test_inhour_matches_the_kinetics_model():
    sim = Simulator()
    d = sim.design
    rho = 0.1 * d.delayed.beta_total
    period = sim.kinetics.stable_period(rho)
    assert inhour_reactivity(d, period) == pytest.approx(rho, rel=1e-9)
    assert inhour_reactivity(d, math.inf) == 0.0


def test_period_fit_and_inverse_kinetics_on_a_step():
    sim = Simulator()
    sim.initialize_at_power(1.0, reg_position_cm=30.0)
    sim.protection.enabled = False
    sim.run(5, dt=0.05)
    rho = 0.15 * sim.design.delayed.beta_total
    sim.insert_reactivity(rho)
    sim.run(200, dt=0.05)
    a = sim.history_arrays()
    late = a["t"] > 120
    assert fit_period(a["t"][late], a["power"][late]) == pytest.approx(sim.kinetics.stable_period(rho), rel=0.01)
    ik = inverse_kinetics(sim.design, a["t"], a["power"])
    assert ik[a["t"] > 10].mean() == pytest.approx(rho, rel=0.01)


def test_approach_to_critical_predicts_the_critical_bank():
    sim, r = run("approach_to_critical")
    assert abs(r["error"]["critical_bank_cm"]) < 0.5
    assert not sim.scrammed


@pytest.mark.slow
def test_rod_calibration_recovers_regulating_rod_worth():
    sim, r = run("rod_calibration")
    assert abs(r["error"]["total_worth_percent"]) < 3
    assert len(r["integral_curve"]) == len(r["table"]["rows"]) + 1


def test_rod_drop_worth_and_drop_time():
    sim, r = run("rod_drop")
    assert abs(r["error"]["inverse_kinetics_percent"]) < 2
    assert abs(r["error"]["integral_count_percent"]) < 8
    assert r["measured"]["drop_time_s"] < r["reference"]["drop_time_limit_s"]
    assert sim.rods["SS1"].latched  # only the tested rod was dropped
    assert not sim.scrammed


def test_sample_worth_by_rod_compensation():
    sim, r = run("sample_worth", sample_dollars=-0.12)
    assert abs(r["error"]["percent"]) < 3
    assert r["measured"]["within_tech_spec"]


def test_temperature_coefficient_is_negative_and_close():
    sim, r = run("temperature_coefficient")
    assert r["measured"]["alpha_dk_k_per_c"] < 0
    assert abs(r["error"]["percent"]) < 5


def test_power_calibration_catches_miscalibrated_channels():
    sim, r = run("power_calibration", channel_gain=0.8, heat_min=30.0)
    assert r["measured"]["calibration_factor"] == pytest.approx(1 / 0.8, rel=0.03)
    assert abs(r["error"]["percent"]) < 2


def test_cli_runs_an_experiment(tmp_path, capsys):
    assert main(["experiment", "rod_drop", "--plot", str(tmp_path / "drop.png"),
                 "--json", str(tmp_path / "drop.json")]) == 0
    out = capsys.readouterr().out
    assert "worth_inverse_kinetics_dollars" in out
    assert (tmp_path / "drop.png").stat().st_size > 0
    assert (tmp_path / "drop.json").stat().st_size > 0
