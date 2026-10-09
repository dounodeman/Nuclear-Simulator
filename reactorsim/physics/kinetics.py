"""Point reactor kinetics with six delayed-neutron groups and an external source.

Power ``P`` is in watts and precursor concentrations ``C_i`` are expressed in the
same "power-equivalent" units, so that at steady state ``C_i = beta_i * P / (Lambda * lambda_i)``.

    dP/dt   = (rho - beta) / Lambda * P + sum(lambda_i * C_i) + S
    dC_i/dt = beta_i / Lambda * P - lambda_i * C_i

For a reactivity held constant over a step the system is linear, so it is
advanced exactly with a matrix exponential. That is unconditionally stable for the
stiff prompt-neutron time scale and exact for step insertions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm
from scipy.optimize import brentq

# Keepin six-group data for thermal fission of U-235: relative abundances and decay constants (1/s).
KEEPIN_U235_RELATIVE = np.array([0.033, 0.219, 0.196, 0.395, 0.115, 0.042])
KEEPIN_U235_LAMBDA = np.array([0.0124, 0.0305, 0.111, 0.301, 1.14, 3.01])


@dataclass(frozen=True)
class DelayedNeutronData:
    beta: np.ndarray  # effective delayed fraction per group
    lam: np.ndarray  # decay constant per group, 1/s

    @property
    def beta_total(self) -> float:
        return float(self.beta.sum())

    @classmethod
    def u235_thermal(cls, beta_eff: float) -> "DelayedNeutronData":
        rel = KEEPIN_U235_RELATIVE / KEEPIN_U235_RELATIVE.sum()
        return cls(beta=beta_eff * rel, lam=KEEPIN_U235_LAMBDA.copy())


class PointKinetics:
    def __init__(self, delayed: DelayedNeutronData, generation_time: float):
        self.d = delayed
        self.Lambda = generation_time
        n = len(delayed.beta)
        self._n = n
        # Constant part of the augmented system matrix; the [0, 0] entry depends on rho.
        A = np.zeros((n + 2, n + 2))
        A[0, 1 : n + 1] = delayed.lam
        A[1 : n + 1, 0] = delayed.beta / generation_time
        A[1 : n + 1, 1 : n + 1] = -np.diag(delayed.lam)
        self._A0 = A

    def equilibrium_precursors(self, power: float) -> np.ndarray:
        return self.d.beta * power / (self.Lambda * self.d.lam)

    def step(self, power: float, precursors: np.ndarray, rho: float, source: float, h: float):
        """Advance (P, C) by ``h`` seconds with constant ``rho`` and source ``S`` (W/s)."""
        A = self._A0.copy()
        A[0, 0] = (rho - self.d.beta_total) / self.Lambda
        A[0, -1] = source  # source enters through the constant augmented state
        x = np.empty(self._n + 2)
        x[0] = power
        x[1 : self._n + 1] = precursors
        x[-1] = 1.0
        y = expm(A * h) @ x
        return max(float(y[0]), 0.0), np.maximum(y[1 : self._n + 1], 0.0)

    # --- analytic helpers used for validation and for the operator's period readout ---

    def inhour_rho(self, omega: float) -> float:
        """Reactivity that gives asymptotic inverse period ``omega`` (1/s)."""
        return omega * self.Lambda + float(np.sum(self.d.beta * omega / (omega + self.d.lam)))

    def stable_period(self, rho: float) -> float:
        """Asymptotic (stable) period in seconds for a step reactivity ``rho``.

        Returns +inf for rho == 0. Negative reactivity gives a negative period, which
        is bounded by the longest-lived precursor group (about -80 s).
        """
        if rho == 0:
            return float("inf")
        if rho > 0:
            hi = 1.0
            while self.inhour_rho(hi) < rho:
                hi *= 2
            omega = brentq(lambda w: self.inhour_rho(w) - rho, 0.0, hi, xtol=1e-14)
        else:
            lo = -float(self.d.lam.min())
            omega = brentq(lambda w: self.inhour_rho(w) - rho, lo + 1e-12, 0.0, xtol=1e-14)
        return 1.0 / omega
