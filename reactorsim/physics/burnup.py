"""U-235 depletion and its reactivity effect."""

from __future__ import annotations

AVOGADRO = 6.02214076e23
ENERGY_PER_FISSION_J = 3.204e-11  # about 200 MeV recoverable
U235_CAPTURE_TO_FISSION = 0.169  # alpha for thermal U-235


class Burnup:
    def __init__(self, initial_u235_g: float, reactivity_per_fraction: float):
        self.m0 = initial_u235_g
        self.k = reactivity_per_fraction  # d(rho) / d(fractional U-235 loss), positive number

    def consumption_rate_g_per_s(self, fission_power_w: float) -> float:
        fissions = fission_power_w / ENERGY_PER_FISSION_J
        return fissions * (1 + U235_CAPTURE_TO_FISSION) * 235.0439 / AVOGADRO

    def worth(self, mass_g: float) -> float:
        return -self.k * (self.m0 - mass_g) / self.m0
