"""Reactor design definition: every number the engine needs to simulate one reactor."""

from __future__ import annotations

from dataclasses import dataclass

from reactorsim.physics.kinetics import DelayedNeutronData
from reactorsim.physics.thermal import ThermalParams
from reactorsim.plant.instruments import InstrumentParams
from reactorsim.plant.protection import ProtectionSetpoints
from reactorsim.plant.radiation import RadiationParams
from reactorsim.plant.rods import RodSpec


@dataclass(frozen=True)
class ReactorDesign:
    key: str
    name: str
    description: str
    rated_power: float  # W
    licensed_power: float  # W
    delayed: DelayedNeutronData
    generation_time: float  # s
    excess_reactivity: float  # dk/k, all rods out, cold clean core at reference temperature
    rods: tuple[RodSpec, ...]
    shim_rods: tuple[str, ...]  # rods driven in by a setback
    regulating_rod: str
    fuel_coefficient: tuple[tuple[float, float], ...]  # (upper temperature C, dk/k per C) bands
    moderator_coefficient: tuple[tuple[float, float], ...]  # same, for core water temperature
    alpha_void: float  # dk/k per percent void
    reference_temp: float  # C
    thermal: ThermalParams
    flux_per_watt: float  # core-average thermal flux per watt, n/cm2-s/W
    sigma_f: float  # 1/cm
    sigma_a: float  # 1/cm
    u235_mass_g: float
    burnup_reactivity_per_fraction: float
    source_strength: float  # W/s equivalent with the startup source inserted
    intrinsic_source: float  # W/s equivalent with the source withdrawn
    instruments: InstrumentParams
    protection: ProtectionSetpoints
    radiation: RadiationParams
    chiller_setpoints: tuple[float, float]  # C, (off below, on above)
    initial_pool_temp: float
    normal_level_m: float  # water above the top of the core
    fuel_limits: dict  # name -> peak plate temperature, C
    decay_heat_at_shutdown: float | None = None  # fraction of power just after shutdown
    scram_delay_s: float = 0.0  # signal-to-magnet-release delay
    one_rod_withdrawal: bool = False  # interlock: only one rod may be withdrawn at a time
    setback_drives_all_rods: bool = False  # setback = gang lower of every rod
    scram_drives_regulating_rod_in: bool = True


def temperature_reactivity(temp: float, ref: float, bands: tuple[tuple[float, float], ...]) -> float:
    """Integral of a piecewise-constant temperature coefficient from ``ref`` to ``temp``.

    ``bands`` is a sequence of (upper bound C, coefficient) in increasing order; the last
    coefficient applies above every bound.
    """
    if temp == ref:
        return 0.0
    lo, hi, sign = (ref, temp, 1.0) if temp > ref else (temp, ref, -1.0)
    total = 0.0
    start = -1e9
    for i, (upper, coef) in enumerate(bands):
        end = 1e9 if i == len(bands) - 1 else upper
        a, b = max(lo, start), min(hi, end)
        if b > a:
            total += coef * (b - a)
        start = end
    return sign * total
