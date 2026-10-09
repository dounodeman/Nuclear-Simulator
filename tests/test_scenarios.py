import pytest

from reactorsim.scenarios import SCENARIOS


def run(key, **kw):
    return SCENARIOS[key].run(**kw)


def test_experiment_at_tech_spec_limit_scrams_without_damage():
    sim, s = run("experiment")
    assert s["scrammed"]
    assert s["fuel_damage_fraction"] == 0


def test_moderate_excursion_is_self_limiting():
    sim, s = run("reactivity_accident")
    assert s["peak_power_w"] > 1e7
    assert s["peak_fuel_temp_c"] < 530
    assert s["fuel_damage_fraction"] == 0


def test_large_excursion_damages_fuel():
    # SPERT-I's destructive test ($3.3) melted plates; $4 here must exceed the fuel limits.
    sim, s = run("reactivity_accident_large")
    assert s["peak_fuel_temp_c"] > 582
    assert s["fuel_damage_fraction"] > 0


def test_calibration_error_runs_past_license_limit():
    sim, s = run("calibration_error")
    assert s["true_power_w"] > 2.5 * s["indicated_power_w"]
    assert s["true_power_w"] > s["licensed_power_w"]


def test_servo_channel_failure_is_caught_by_safety_channel():
    sim, s = run("linear_channel_failure")
    assert any("Ch4" in e.message for e in sim.events if e.kind == "setback")
    assert s["peak_power_w"] < 12_000


@pytest.mark.slow
def test_startup_reaches_full_power():
    sim, s = run("startup")
    assert not s["scrammed"]
    assert s["final_power_w"] == pytest.approx(10_000, rel=0.03)
    assert s["startup_time_s"] < 3600


@pytest.mark.slow
def test_loss_of_chiller_heatup_rate():
    sim, s = run("loss_of_chiller", hours=3.0)
    assert s["heatup_rate_c_per_h"] == pytest.approx(0.33, abs=0.05)


@pytest.mark.slow
def test_pool_leak_scrams_on_radiation():
    sim, s = run("loss_of_pool_water", hours=1.0)
    assert s["scrammed"]
    assert any("radiation" in c.lower() for c in s["scram_causes"])
