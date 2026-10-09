"""PUR-1, Purdue University Reactor Number One.

A 10 kW (12 kW licensed) light-water pool reactor with MTR-type 19.75% U3Si2-Al
plate fuel, graphite reflector, two borated-steel shim-safety blades, one
stainless regulating rod and an all-digital safety and control system.

Sources and the status of every value (sourced, derived or assumed) are listed
in docs/pur1_reference.md.
"""

from __future__ import annotations

from reactorsim.physics.kinetics import DelayedNeutronData
from reactorsim.physics.thermal import ThermalParams
from reactorsim.plant.instruments import InstrumentParams
from reactorsim.plant.protection import ProtectionSetpoints
from reactorsim.plant.radiation import RadiationParams
from reactorsim.plant.rods import RodSpec
from reactorsim.reactors.base import ReactorDesign

RATED_W = 10_000.0
CORE_HEIGHT_CM = 61.0

# Half-decade linear ranges, 1 mW to 31.6 kW full scale (16 ranges).
LINEAR_RANGES = tuple(1e-3 * 10 ** (k / 2) for k in range(16))

# Core-average flux and cross sections. 1.2e10 n/cm2-s average thermal flux at 1 kW (sourced),
# core volume about 30 x 30 x 61 cm. Sigma_f follows from P = E_f * Sigma_f * phi * V.
CORE_VOLUME_CM3 = 30.5 * 30.5 * CORE_HEIGHT_CM
FLUX_PER_WATT = 1.2e10 / 1000.0
SIGMA_F = 1.0 / (3.204e-11 * FLUX_PER_WATT * CORE_VOLUME_CM3)
SIGMA_A = 2.43 * SIGMA_F / 1.4  # nu * Sigma_f / k_inf, k_inf about 1.4 for a small MTR core

DESIGN = ReactorDesign(
    key="pur1",
    name="PUR-1 (Purdue University Reactor Number One)",
    description="10 kW open-pool MTR research reactor with all-digital I&C",
    rated_power=RATED_W,
    licensed_power=12_000.0,
    delayed=DelayedNeutronData.u235_thermal(beta_eff=0.0076),
    generation_time=5.4e-5,
    excess_reactivity=0.0055,
    rods=(
        RodSpec("SS1", worth=0.029, length_cm=CORE_HEIGHT_CM, speed_cm_s=11.0 / 60, scrammable=True, drop_time_s=0.6),
        RodSpec("SS2", worth=0.029, length_cm=CORE_HEIGHT_CM, speed_cm_s=11.0 / 60, scrammable=True, drop_time_s=0.6),
        RodSpec("RR", worth=0.0047, length_cm=CORE_HEIGHT_CM, speed_cm_s=43.5 / 60, scrammable=False),
    ),
    shim_rods=("SS1", "SS2"),
    regulating_rod="RR",
    alpha_fuel=-0.2e-4,
    alpha_moderator=-1.7e-4,
    alpha_void=-2.0e-3,
    reference_temp=20.0,
    thermal=ThermalParams(
        fuel_heat_capacity=31_500.0,
        core_water_mass=33.0,
        pool_water_mass=24_200.0,
        plate_conductance=8_700.0,
        natcirc_flow_rated=1.0,
        rated_power=RATED_W,
        natcirc_min_flow=0.05,
        gamma_heat_fraction=0.03,
        hot_spot_factor=2.0,
        core_height_m=CORE_HEIGHT_CM / 100,
        pool_loss_ua=35.0,
        pool_loss_ref_temp=5.0,
        chiller_capacity=10_550.0,
        air_conductance=60.0,
        void_time_constant=0.02,
        void_per_degree_superheat=0.01,
        max_void=0.6,
    ),
    flux_per_watt=FLUX_PER_WATT,
    sigma_f=SIGMA_F,
    sigma_a=SIGMA_A,
    u235_mass_g=2650.0,
    burnup_reactivity_per_fraction=0.3,
    source_strength=1.05,
    intrinsic_source=1e-4,
    instruments=InstrumentParams(
        rated_power=RATED_W,
        startup_cps_per_watt=2e4,
        startup_background_cps=0.3,
        startup_max_cps=1e5,
        log_min_percent=1e-5,
        log_max_percent=300.0,
        linear_ranges_w=LINEAR_RANGES,
        safety_max_percent=150.0,
        period_filter_s=1.5,
        ion_chamber_noise=0.003,
    ),
    protection=ProtectionSetpoints(
        period_scram_s=7.0,
        period_setback_s=12.0,
        period_interlock_s=15.0,
        startup_min_cps=2.0,
        power_scram_percent=120.0,
        power_setback_percent=110.0,
        linear_scram_percent=120.0,
        linear_setback_percent=110.0,
        pool_top_scram=50.0,
        console_scram=7.5,
        water_scram=7.5,
        air_alarm=1.0,
        pool_temp_alarm=29.7,
        pool_level_alarm_m=3.96,  # 13 ft minimum above the core
        servo_deviation_alarm=0.05,
        rod_drift_setback_cm=3.0,
        shim_interlock_height_cm=6.0,
    ),
    radiation=RadiationParams(
        rated_power=RATED_W,
        pool_top_full_power=10.0,
        console_full_power=0.5,
        water_full_power=1.0,
        normal_level_m=4.3,
        attenuation_per_m=3.0,
        release_mr_per_damage=5_000.0,
        release_half_life_s=8 * 3600.0,
        air_fraction=0.01,
    ),
    chiller_setpoints=(18.3, 23.9),
    initial_pool_temp=21.0,
    normal_level_m=4.3,
    fuel_limits={"safety_limit": 530.0, "blister": 550.0, "melt": 582.0},
)
