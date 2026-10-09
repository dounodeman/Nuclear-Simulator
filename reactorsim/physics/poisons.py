"""Xenon-135 and samarium-149 fission-product poisoning.

Chains (number densities per cm^3, averaged over the core):

    I-135  -> Xe-135 (beta decay),     Xe-135 burns out by absorption or decays
    Pm-149 -> Sm-149 (beta decay),     Sm-149 is stable and only burns out

Worth is ``rho = -sigma * N / Sigma_a`` with ``Sigma_a`` the core-average
macroscopic absorption cross section, which is the usual one-group estimate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Standard thermal data for U-235 fission.
GAMMA_I = 0.0639
GAMMA_XE = 0.00237
GAMMA_PM = 0.0113
LAMBDA_I = 2.87e-5  # 1/s (6.7 h)
LAMBDA_XE = 2.09e-5  # 1/s (9.2 h)
LAMBDA_PM = 3.63e-6  # 1/s (53.1 h)
SIGMA_XE = 2.65e-18  # cm^2 (2.65 Mb)
SIGMA_SM = 4.1e-20  # cm^2 (41 kb)


@dataclass
class PoisonState:
    iodine: float = 0.0
    xenon: float = 0.0
    promethium: float = 0.0
    samarium: float = 0.0


class Poisons:
    def __init__(self, sigma_f: float, sigma_a: float):
        self.sigma_f = sigma_f  # core-average macroscopic fission cross section, 1/cm
        self.sigma_a = sigma_a  # core-average macroscopic absorption cross section, 1/cm

    def equilibrium(self, flux: float) -> PoisonState:
        F = self.sigma_f * flux
        i = GAMMA_I * F / LAMBDA_I
        xe = (GAMMA_I + GAMMA_XE) * F / (LAMBDA_XE + SIGMA_XE * flux)
        pm = GAMMA_PM * F / LAMBDA_PM
        sm = GAMMA_PM * F / (SIGMA_SM * flux) if flux > 0 else 0.0
        return PoisonState(i, xe, pm, sm)

    def step(self, s: PoisonState, flux: float, h: float) -> PoisonState:
        """Implicit (backward Euler) update, stable for any step length."""
        F = self.sigma_f * flux
        i = (s.iodine + h * GAMMA_I * F) / (1 + h * LAMBDA_I)
        xe = (s.xenon + h * (GAMMA_XE * F + LAMBDA_I * i)) / (1 + h * (LAMBDA_XE + SIGMA_XE * flux))
        pm = (s.promethium + h * GAMMA_PM * F) / (1 + h * LAMBDA_PM)
        sm = (s.samarium + h * LAMBDA_PM * pm) / (1 + h * SIGMA_SM * flux)
        return PoisonState(i, xe, pm, sm)

    def xenon_worth(self, s: PoisonState) -> float:
        return -SIGMA_XE * s.xenon / self.sigma_a

    def samarium_worth(self, s: PoisonState) -> float:
        return -SIGMA_SM * s.samarium / self.sigma_a
