import pytest

from reactorsim.physics.decay_heat import DecayHeat
from reactorsim.simulator import Simulator


def test_tech_spec_reactivity_limits():
    sim = Simulator("pur1")
    d = sim.design
    assert d.excess_reactivity <= 0.006  # TS maximum excess reactivity
    assert sim.shutdown_margin() >= 0.010  # TS minimum shutdown margin
    assert sim.shutdown_margin() == pytest.approx(0.018)  # measured, SAR 2008


def test_banked_critical_height_and_rod_rates():
    sim = Simulator("pur1")
    sim.initialize_at_power(1.0)
    assert sim.rods["SS1"].position == pytest.approx(53.5, abs=1.0)  # SAR 2008 fresh LEU core
    # Maximum reactivity insertion rates (SAR 2008 measured): SS1 2.31e-4, SS2 1.42e-4, RR 5.39e-5 /s.
    for name, measured in (("SS1", 2.31e-4), ("SS2", 1.42e-4), ("RR", 5.39e-5)):
        rod = sim.rods[name]
        span = rod.spec.active_cm
        rate = rod.spec.worth * 2 / span * rod.spec.speed_cm_s
        assert rate == pytest.approx(measured, rel=0.2)


def test_shutdown_state_is_subcritical_with_source_counts():
    sim = Simulator("pur1")
    sim.run(5)
    assert sim.reactivity()["total"] < -0.05
    assert sim.instruments.readings.ch1_cps > 2  # above the rod withdrawal interlock


def test_initialize_at_power_is_steady():
    sim = Simulator("pur1")
    sim.initialize_at_power(10_000.0)
    shim = sim.rods["SS1"].position
    assert 45 < shim < 64
    sim.run(60)
    assert sim.power == pytest.approx(10_000.0, rel=0.02)
    assert sim.thermal.fuel_temp < 30  # a few degrees above a 22 C pool


def test_decay_heat_curve():
    dh = DecayHeat()
    assert dh.total_fraction == pytest.approx(0.066, rel=0.01)
    groups = dh.equilibrium(1.0)
    after_hour = dh.step(groups, 0.0, 3600.0).sum()
    assert after_hour == pytest.approx(0.066 * 3601 ** -0.2, rel=0.01)
    assert DecayHeat(0.063).total_fraction == pytest.approx(0.063)  # PUR-1 SAR value


def test_hot_clad_temperature_matches_natcon():
    # SAR/NATCON: about 43 C peak clad at 18 kW steady state with a 27 C pool.
    sim = Simulator("pur1")
    sim.thermal.pool_temp = 27.0
    sim.initialize_at_power(18_000.0)
    assert sim.peak_fuel_temp() == pytest.approx(43.0, abs=3.0)


def test_equilibrium_xenon_is_a_few_cents_at_10_kw():
    sim = Simulator("pur1")
    sim.initialize_at_power(10_000.0, xenon="equilibrium")
    cents = 100 * sim.reactivity()["xenon"] / sim.design.delayed.beta_total
    assert -10 < cents < -3


def test_rod_drop_time_under_one_second():
    sim = Simulator("pur1")
    sim.initialize_at_power(10_000.0)
    sim.scram()
    sim.run(1.0, dt=0.01)
    for name in sim.design.shim_rods:
        assert sim.rods[name].position == 0.0
