"""Lumped thermal-hydraulics for an open pool reactor cooled by natural convection.

Three heat-capacity nodes:

* fuel   - the fuel plates (meat and cladding)
* core   - the water in the core coolant channels
* pool   - the bulk pool water

Heat flows fuel -> core water through a plate-to-water conductance, core water
-> pool through natural-circulation flow, and pool -> chiller / room. Subcooled
and bulk boiling are represented by an enhanced conductance and a core void
fraction that feeds back on reactivity. If the pool level drops below the top of
the core, the uncovered fraction of the plates loses water cooling and moderation.

The three temperatures are advanced implicitly (backward Euler) each sub-step,
with flow, conductance and chiller duty evaluated at the start of the step.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

WATER_CP = 4186.0  # J/kg-K
G = 9.81
ATM_PA = 101325.0
WATER_DENSITY = 998.0


def saturation_temperature_c(pressure_pa: float) -> float:
    """Water saturation temperature from the Antoine equation (valid 99-374 C)."""
    mmhg = pressure_pa / 133.322
    return 1810.94 / (8.14019 - math.log10(mmhg)) - 244.485


@dataclass(frozen=True)
class ThermalParams:
    fuel_heat_capacity: float  # J/K
    core_water_mass: float  # kg in the core channels
    pool_water_mass: float  # kg
    plate_conductance: float  # W/K, single-phase natural convection
    natcirc_flow_rated: float  # kg/s at rated power
    rated_power: float  # W
    natcirc_min_flow: float  # kg/s floor at zero power (pool mixing)
    gamma_heat_fraction: float  # fraction of fission heat deposited directly in the water
    hot_spot_factor: float  # peak-to-average plate temperature rise
    core_height_m: float
    pool_loss_ua: float  # W/K pool to room (evaporation and conduction lumped)
    pool_loss_ref_temp: float  # C
    chiller_capacity: float  # W
    air_conductance: float  # W/K for plates in air
    void_time_constant: float  # s
    void_per_degree_superheat: float  # void fraction per C of wall superheat
    max_void: float
    subcool_scale: float = 40.0  # C of bulk subcooling that cuts subcooled-boiling void by 1/e
    chf_superheat: float = 30.0  # wall superheat (C) at critical heat flux
    film_conductance_factor: float = 0.3  # film boiling conductance relative to single phase


@dataclass
class ThermalState:
    fuel_temp: float
    core_temp: float
    pool_temp: float
    void: float = 0.0  # core void fraction from boiling, 0..1
    chiller_on: bool = False
    chiller_duty: float = 0.0  # W, last value


class PoolThermal:
    def __init__(self, p: ThermalParams):
        self.p = p

    # --- correlations ---

    def natcirc_flow(self, heat_to_water: float) -> float:
        p = self.p
        q = max(heat_to_water, 0.0) / p.rated_power
        return max(p.natcirc_flow_rated * q ** (1.0 / 3.0), p.natcirc_min_flow)

    def saturation_temp(self, level_above_core_m: float) -> float:
        depth = max(level_above_core_m, 0.0) + self.p.core_height_m / 2
        return saturation_temperature_c(ATM_PA + WATER_DENSITY * G * depth)

    def boiling_regime(self, s: ThermalState, t_sat: float) -> str:
        wall = self.peak_fuel_temp(s)
        if wall <= t_sat:
            return "single-phase"
        if wall - t_sat <= self.p.chf_superheat:
            return "nucleate"
        return "film"

    def plate_conductance(self, s: ThermalState, t_sat: float) -> float:
        """Plate-to-water conductance along a simple boiling curve keyed to the hot-spot wall superheat.

        Single phase below saturation; nucleate boiling raises it steeply up to critical
        heat flux; past CHF a vapor film blankets the plate and conductance collapses.
        """
        p = self.p
        superheat = self.peak_fuel_temp(s) - t_sat
        if superheat <= 0:
            return p.plate_conductance
        if superheat <= p.chf_superheat:
            return p.plate_conductance * (1.0 + (superheat / 8.0) ** 2)
        return p.plate_conductance * p.film_conductance_factor

    def peak_fuel_temp(self, s: ThermalState) -> float:
        return s.core_temp + self.p.hot_spot_factor * (s.fuel_temp - s.core_temp)

    # --- integration ---

    def step(
        self,
        s: ThermalState,
        heat_power: float,
        h: float,
        level_above_core_m: float,
        chiller_available: bool,
        chiller_setpoints: tuple[float, float],
    ) -> ThermalState:
        p = self.p
        covered = min(max((level_above_core_m + p.core_height_m) / p.core_height_m, 0.0), 1.0)
        t_sat = self.saturation_temp(level_above_core_m)

        q_fuel = heat_power * (1.0 - p.gamma_heat_fraction)
        q_water = heat_power * p.gamma_heat_fraction * covered
        g = self.plate_conductance(s, t_sat) * covered + p.air_conductance * (1.0 - covered)
        w_cp = self.natcirc_flow(q_fuel + q_water) * WATER_CP * covered
        c_f = p.fuel_heat_capacity
        c_c = max(p.core_water_mass * covered, 1.0) * WATER_CP
        c_p = p.pool_water_mass * WATER_CP

        # Thermostatic chiller with hysteresis (on above the high setpoint, off below the low one).
        lo, hi = chiller_setpoints
        on = s.chiller_on
        if not chiller_available:
            on = False
        elif s.pool_temp > hi:
            on = True
        elif s.pool_temp < lo:
            on = False
        q_chill = p.chiller_capacity if on else 0.0

        a = np.array([
            [c_f / h + g, -g, 0.0],
            [-g, c_c / h + g + w_cp, -w_cp],
            [0.0, -w_cp, c_p / h + w_cp + p.pool_loss_ua],
        ])
        b = np.array([
            c_f / h * s.fuel_temp + q_fuel,
            c_c / h * s.core_temp + q_water,
            c_p / h * s.pool_temp - q_chill + p.pool_loss_ua * p.pool_loss_ref_temp,
        ])
        tf, tc, tp = np.linalg.solve(a, b)

        # Boiling: the water cannot exceed saturation; surplus energy makes steam that leaves.
        if covered > 0 and tc > t_sat:
            tc = t_sat

        # Void relaxes toward a value set by wall superheat. Subcooled boiling still makes steam at
        # the plate surface (the mechanism that shuts down plate-fuel power bursts) but bulk
        # subcooling condenses much of it, so the void shrinks as the channel water gets colder.
        wall = tc + p.hot_spot_factor * (tf - tc)
        subcool = max(t_sat - tc, 0.0)
        void_eq = p.void_per_degree_superheat * max(wall - t_sat, 0.0) * math.exp(-subcool / p.subcool_scale)
        void_eq = min(void_eq, p.max_void)
        k = h / p.void_time_constant
        void = (s.void + k * void_eq) / (1.0 + k)

        return replace(s, fuel_temp=float(tf), core_temp=float(tc), pool_temp=float(tp), void=float(void),
                       chiller_on=on, chiller_duty=q_chill)
