"""Area and process radiation monitors and fuel-failure source term.

Dose rates scale with the core gamma source (fission plus decay heat) and with
the water shielding above the core. A cladding failure releases fission
products into the pool water, which shows up first on the water process
monitor and then in the air. Magnitudes are illustrative and are scaled so that
full power with a normal pool sits well below the scram setpoints.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RadiationParams:
    rated_power: float
    pool_top_full_power: float  # mR/h at rated power, normal level
    console_full_power: float
    water_full_power: float
    normal_level_m: float
    attenuation_per_m: float  # effective water attenuation for core gammas
    release_mr_per_damage: float  # water monitor mR/h per unit fuel-damage fraction
    release_half_life_s: float  # effective decay plus cleanup of released activity
    air_fraction: float  # fraction of released water activity seen by the air monitor


class RadiationModel:
    def __init__(self, p: RadiationParams):
        self.p = p
        self.released = 0.0  # water activity from failed fuel, in water-monitor mR/h

    def add_release(self, damage_increase: float) -> None:
        self.released += damage_increase * self.p.release_mr_per_damage

    def step(self, h: float) -> None:
        self.released *= math.exp(-math.log(2) * h / self.p.release_half_life_s)

    def dose_rates(self, gamma_power_w: float, level_m: float) -> dict[str, float]:
        p = self.p
        rel = gamma_power_w / p.rated_power
        shielding = math.exp(min(p.attenuation_per_m * (p.normal_level_m - level_m), 30.0))
        return {
            "pool_top": p.pool_top_full_power * rel * shielding + 0.3 * self.released,
            "console": p.console_full_power * rel * shielding + 0.02 * self.released + 0.01,
            "water": p.water_full_power * rel + self.released + 0.02,
            "air": p.air_fraction * self.released,
        }
