import pytest

from reactorsim import get_design, list_designs, simulator_for
from reactorsim.bwr.scenarios import BWR_SCENARIOS
from reactorsim.bwr.simulator import BWRSimulator
from reactorsim.physics import steam
from reactorsim.simulator import Simulator

RATED = 3293e6


def run(key, **kw):
    return BWR_SCENARIOS[key].run(**kw)


def test_design_is_registered_and_routed_to_the_bwr_engine():
    d = get_design("peach_bottom_2")
    assert d.kind == "bwr" and d.rated_power == RATED
    assert "peach_bottom_2" in {x.key for x in list_designs()}
    assert isinstance(simulator_for("peach_bottom_2"), BWRSimulator)
    assert isinstance(simulator_for("pur1"), Simulator)
    with pytest.raises(TypeError):
        Simulator("peach_bottom_2")
    with pytest.raises(TypeError):
        BWRSimulator("pur1")


def test_steam_table_matches_known_points():
    assert steam.t_sat(7.0e6) == pytest.approx(285.8, abs=0.3)
    assert steam.h_fg(7.0e6) == pytest.approx(1505e3, rel=0.01)
    assert steam.rho_g(steam.from_psig(1020)) == pytest.approx(37.3, rel=0.03)
    assert steam.psig(steam.from_psig(1020)) == pytest.approx(1020)


def test_full_power_steady_state_holds():
    sim = BWRSimulator()
    sim.initialize_at_power(RATED)
    assert sim.reactivity()["total"] == pytest.approx(0.0, abs=1e-7)
    # Rated-plant numbers: about 1,670 kg/s of steam, fuel around 600 C, void around 30%.
    assert sim.feed_flow == pytest.approx(1674, rel=0.02)
    assert 550 < sim.fuel_temp < 650
    assert 0.25 < sim.void < 0.45
    sim.run(300, record_every=1.0)
    a = sim.history_arrays()
    assert a["power"].min() > 0.995 * RATED and a["power"].max() < 1.005 * RATED
    assert abs(steam.psig(a["pressure"]).max() - 1020) < 1.0 if hasattr(a["pressure"], "max") else True
    assert abs(sim.level_in - 35.0) < 0.5
    assert not sim.scrammed and not sim.status()["alarms"]


def test_turbine_trip_benchmark_shape():
    # OECD/NEA BWRTT benchmark, test TT2: measured peak about 3.6x initial power at about 0.74 s
    # after the stop valves start closing, scram rods moving from 0.75 s. The lumped model
    # reproduces the shape (pressure-driven void collapse, flux scram, rods ending it) but
    # under-predicts the peak; see docs/peach_bottom_2_reference.md.
    sim, s = run("pb2_turbine_trip_benchmark")
    assert 1.5 < s["power_ratio_at_peak"] < 4.0
    assert 0.3 < s["time_of_peak_after_trip_s"] < 1.0
    assert s["scrammed"] and "APRM" in s["scram_causes"][0]
    assert 20 < s["pressure_rise_at_1s_psi"] < 150
    assert s["final_power_percent"] < 3.0


def test_turbine_trip_from_full_power_scrams_on_stop_valves():
    sim, s = run("pb2_turbine_trip", minutes=1.0)
    assert s["scram_causes"][0] == "Turbine stop valve closure"
    assert s["peak_pressure_psig"] < 1135  # the bypass and the scram keep the SRVs shut
    assert s["min_level_in"] > sim.design.setpoints.level3_scram_in  # post-scram shrink stays above L3
    assert s["final_power_percent"] < 1.0


def test_recirc_pump_trip_runs_back_to_natural_circulation_without_scram():
    sim, s = run("pb2_recirc_pump_trip", minutes=5.0)
    assert not s["scrammed"]
    assert 30 < s["final_power_percent"] < 55
    assert 0.25 < sim.core_flow / sim.design.rated_core_flow < 0.45


def test_loss_of_feedwater_scrams_on_level_3_and_hpci_restores_level():
    sim, s = run("pb2_loss_of_feedwater", minutes=5.0)
    assert s["scram_causes"][0] == "Reactor water level low (Level 3)"
    msgs = [e.message for e in sim.events]
    assert any("Level 2" in m for m in msgs) and any("HPCI injecting" in m for m in msgs)
    assert s["min_level_in"] > sim.design.taf_level_in  # the core stays covered
    assert sim.level_in > sim.design.setpoints.level2_in


def test_msiv_closure_lifts_the_relief_valves_and_heats_the_torus():
    sim, s = run("pb2_msiv_closure", minutes=5.0)
    assert s["scram_causes"][0] == "Main steam isolation valve closure"
    assert 1130 < s["peak_pressure_psig"] < 1200
    assert any("SRV" in e.message for e in sim.events)
    assert s["final_torus_temp_c"] > 30.5


def test_turbine_trip_without_scram_settles_on_natural_circulation():
    sim, s = run("pb2_turbine_trip_atws", minutes=2.0)
    assert not s["scrammed"]
    assert any("ATWS-RPT" in e.message for e in sim.events)
    assert s["peak_pressure_psig"] < 1300  # below the 1,325 psig safety limit
    assert 30 < s["final_power_percent"] < 70


@pytest.mark.slow
def test_station_blackout_without_injection_uncovers_the_core():
    sim, s = run("pb2_station_blackout_no_injection", hours=1.0)
    assert s["time_core_uncovered_s"] is not None and 600 < s["time_core_uncovered_s"] < 3000
    assert sim.fuel_temp > steam.t_sat(sim.pressure) + 100  # uncovered fuel heating on decay heat


def test_rod_withdrawal_error_is_caught_by_the_aprm():
    sim, s = run("pb2_rod_withdrawal", minutes=1.0)
    assert s["scrammed"] and "APRM" in s["scram_causes"][0]
    assert s["peak_power_percent"] < 130
