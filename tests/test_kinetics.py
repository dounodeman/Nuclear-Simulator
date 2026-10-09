import math

import numpy as np
import pytest

from reactorsim.physics.kinetics import DelayedNeutronData, PointKinetics
from reactorsim.simulator import Simulator

BETA = 0.0076
LAMBDA = 5.4e-5


@pytest.fixture
def pk():
    return PointKinetics(DelayedNeutronData.u235_thermal(BETA), LAMBDA)


def test_equilibrium_is_steady(pk):
    c = pk.equilibrium_precursors(1000.0)
    p, c2 = pk.step(1000.0, c, 0.0, 0.0, 100.0)
    assert p == pytest.approx(1000.0, rel=1e-9)
    assert np.allclose(c, c2)


def test_prompt_jump(pk):
    rho = -0.5 * BETA
    c = pk.equilibrium_precursors(1.0)
    p, _ = pk.step(1.0, c, rho, 0.0, 0.05)  # ten prompt time constants, little delayed decay
    assert p == pytest.approx(BETA / (BETA - rho), rel=0.03)


@pytest.mark.parametrize("rho", [0.0005, 0.001, 0.002, -0.002])
def test_simulated_period_matches_inhour(pk, rho):
    c = pk.equilibrium_precursors(1.0)
    p, t = 1.0, 0.0
    samples = []
    while t < 1000:  # negative periods converge slowly, so run long
        p, c = pk.step(p, c, rho, 0.0, 1.0)
        t += 1.0
        samples.append(p)
    measured = 50.0 / math.log(samples[-1] / samples[-51])
    assert measured == pytest.approx(pk.stable_period(rho), rel=0.02)


def test_negative_period_limit_is_longest_group(pk):
    # A large negative insertion approaches the -1/lambda_1 = -80.6 s limit.
    assert pk.stable_period(-0.05) == pytest.approx(-1 / 0.0124, rel=0.05)


def test_scram_period_is_set_by_longest_lived_group():
    sim = Simulator()
    longest = -1 / sim.design.delayed.lam.min()  # about -75 s for the PUR-1 group data
    sim.initialize_at_power(10_000.0)
    sim.scram()
    sim.run(300, dt=0.5)
    p0, t0 = sim.power, sim.t
    sim.run(200, dt=0.5)
    period = (sim.t - t0) / math.log(sim.power / p0)
    assert period == pytest.approx(longest, rel=0.05)
