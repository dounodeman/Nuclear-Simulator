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
    alpha_fuel: float  # dk/k per C
    alpha_moderator: float  # dk/k per C
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
