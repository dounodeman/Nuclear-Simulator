import pytest

from reactorsim.physics.decay_heat import DecayHeat
from reactorsim.simulator import Simulator


def test_tech_spec_reactivity_limits():
    sim = Simulator("pur1")
    d = sim.design
    assert d.excess_reactivity <= 0.006  # TS maximum excess reactivity
    assert sim.shutdown_margin() >= 0.010  # TS minimum shutdown margin
    assert sum(r.worth for r in d.rods if r.name in d.shim_rods) == pytest.approx(0.058)


def test_shutdown_state_is_subcritical_with_source_counts():
    sim = Simulator("pur1")
    sim.run(5)
    assert sim.reactivity()["total"] < -0.05
    assert sim.instruments.readings.ch1_cps > 2  # above the rod withdrawal interlock


def test_initialize_at_power_is_steady():
    sim = Simulator("pur1")
    sim.initialize_at_power(10_000.0)
    shim = sim.rods["SS1"].position
    assert 40 < shim < 61
    sim.run(60)
    assert sim.power == pytest.approx(10_000.0, rel=0.02)
    assert sim.thermal.fuel_temp < 30  # a few degrees above a 21 C pool


def test_decay_heat_curve():
    dh = DecayHeat()
    assert dh.total_fraction == pytest.approx(0.066, rel=0.01)
    groups = dh.equilibrium(1.0)
    after_hour = dh.step(groups, 0.0, 3600.0).sum()
    assert after_hour == pytest.approx(0.066 * 3601 ** -0.2, rel=0.01)


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
