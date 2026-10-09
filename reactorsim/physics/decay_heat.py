"""Fission-product decay heat as a set of exponential groups.

The 17 groups were fitted (non-negative least squares) to the curve
``P_d/P_0 = 0.066 (t + 1 s)^-0.2`` for U-235 after long operation, which follows
the Way-Wigner shape and gives 6.6% just after shutdown. The fit is within 0.05%
of that curve from 0.1 s to 10^7 s. Because the groups are tracked as states, a
finite operating history is handled naturally.

Each group heat ``H_i`` (W) obeys ``dH_i/dt = lambda_i (a_i P - H_i)``, so at steady
state ``H_i = a_i P`` and the prompt fission heat is ``(1 - sum a_i) P``.
"""

from __future__ import annotations

import numpy as np

DECAY_LAMBDA = np.array([
    3.16227766e+00, 1.0e+00, 3.16227766e-01, 1.0e-01, 3.16227766e-02, 1.0e-02,
    3.16227766e-03, 1.0e-03, 3.16227766e-04, 1.0e-04, 3.16227766e-05, 1.0e-05,
    3.16227766e-06, 1.0e-06, 3.16227766e-07, 1.0e-07, 1.0e-08,
])
DECAY_FRACTION = np.array([
    0.00092879, 0.00604645, 0.0096067, 0.00943751, 0.00804335, 0.00652012,
    0.00522013, 0.00415088, 0.00330435, 0.00261917, 0.00208884, 0.00164761,
    0.00132715, 0.00101683, 0.00091656, 0.00046593, 0.0026704,
])


class DecayHeat:
    def __init__(self, fraction_at_shutdown: float | None = None):
        """``fraction_at_shutdown`` rescales the curve (e.g. 0.063 from a reactor's safety analysis)."""
        self.lam = DECAY_LAMBDA
        scale = 1.0 if fraction_at_shutdown is None else fraction_at_shutdown / DECAY_FRACTION.sum()
        self.frac = DECAY_FRACTION * scale
        self.total_fraction = float(self.frac.sum())

    def equilibrium(self, power: float) -> np.ndarray:
        return self.frac * power

    def step(self, groups: np.ndarray, fission_power: float, h: float) -> np.ndarray:
        # Exact for a constant fission power over the step.
        e = np.exp(-self.lam * h)
        return groups * e + self.frac * fission_power * (1.0 - e)
