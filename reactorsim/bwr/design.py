"""Design definition for a boiling water reactor: every number the BWR plant model needs."""

from __future__ import annotations

from dataclasses import dataclass

from reactorsim.physics.kinetics import DelayedNeutronData


@dataclass(frozen=True)
class BWRSetpoints:
    """Protection, isolation and ECCS actuation set points. Levels are inches above instrument zero."""
    aprm_high_percent: float  # fixed neutron flux scram, % of rated
    aprm_flow_bias_slope: float  # flow-biased scram line: slope (% power per % core flow) ...
    aprm_flow_bias_intercept: float  # ... and intercept (% power)
    aprm_setdown_percent: float  # flux scram with the mode switch out of Run
    dome_pressure_high_psig: float
    level3_scram_in: float
    level8_trip_in: float  # turbine and feed pump trip
    level4_alarm_in: float  # low level alarm
    level7_alarm_in: float  # high level alarm
    level2_in: float  # HPCI/RCIC start, recirculation pump trip
    level1_in: float  # core spray and LPCI start, MSIV closure, ADS arm
    tsv_closure_bypass_percent: float  # stop/control valve scrams armed above this power
    msl_pressure_low_psig: float  # MSIV closure in Run
    msl_flow_high_percent: float  # MSIV closure
    atws_rpt_psig: float  # recirculation pump trip on high pressure (ATWS mitigation)
    ads_delay_s: float
    scram_delay_s: float
    scram_stroke_s: float  # full insertion time after release


@dataclass(frozen=True)
class ECCS:
    hpci_flow_kg_s: float
    hpci_min_pressure_pa: float  # turbine stalls below this
    hpci_start_s: float
    rcic_flow_kg_s: float
    rcic_min_pressure_pa: float
    rcic_start_s: float
    core_spray_loops: int
    core_spray_flow_kg_s: float  # per loop at rated
    core_spray_shutoff_pa: float  # pump shutoff head above containment pressure
    lpci_pumps: int
    lpci_flow_kg_s: float  # per pump
    lpci_shutoff_pa: float
    lp_start_s: float  # diesel start plus pump run-up
    ads_valves: int


@dataclass(frozen=True)
class BWRDesign:
    key: str
    name: str
    description: str
    kind: str = "bwr"
    # --- power and kinetics
    rated_power: float = 0.0  # W
    licensed_power: float = 0.0
    delayed: DelayedNeutronData | None = None
    generation_time: float = 40e-6
    excess_reactivity: float = 0.0  # cold, clean, all rods out, dk/k
    fuel_coefficient: float = 0.0  # dk/k per C of average fuel temperature (Doppler)
    moderator_coefficient: float = 0.0  # dk/k per C of liquid temperature
    alpha_void: float = 0.0  # dk/k per percent core-average void
    reference_temp: float = 20.0
    void_time_constant: float = 1.0  # s, lag of the core void behind its steady value
    # --- rods
    n_rods: int = 0
    notches: int = 48
    notch_cm: float = 15.24
    rod_bank_worth: float = 0.0  # dk/k, all rods full in to full out
    rod_speed_cm_s: float = 7.62
    scram_reactivity_shape: float = 2.0  # S-curve steepness for the scram insertion
    # --- core thermal
    fuel_heat_capacity: float = 0.0  # J/K
    fuel_conductance: float = 0.0  # W/K, fuel average to coolant
    gamma_fraction: float = 0.04  # fission heat deposited directly in the coolant
    core_coolant_volume: float = 0.0  # m3
    separator_volume: float = 0.0  # m3 of two-phase mixture above the core that swells the level
    slip_ratio: float = 2.0
    hot_channel_factor: float = 1.4  # peak to average bundle power
    # --- vessel
    steam_volume: float = 0.0  # m3, dome plus steam lines to the valves
    condensing_mass: float = 0.0  # kg of saturated liquid that follows the dome pressure
    condensing_time_constant: float = 3.0  # s, how fast that liquid follows a pressure change
    liquid_mass: float = 0.0  # kg in the vessel at normal level
    downcomer_area: float = 0.0  # m2
    normal_level_in: float = 0.0
    taf_level_in: float = 0.0  # top of active fuel, inches above instrument zero
    baf_level_in: float = 0.0  # bottom of active fuel
    # --- recirculation
    rated_core_flow: float = 0.0  # kg/s
    natural_circulation_fraction: float = 0.3  # of rated flow at rated power with pumps tripped
    pump_time_constant: float = 2.0  # s, speed follows demand
    pump_coastdown: float = 4.0  # s
    min_pump_speed: float = 0.28
    # --- steam and feed
    dome_pressure_setpoint_pa: float = 0.0
    steam_lines: int = 4
    msiv_stroke_s: float = 4.0
    tsv_stroke_s: float = 0.1
    bypass_fraction: float = 0.25  # of rated steam flow
    bypass_stroke_s: float = 0.3
    srv_setpoints_psig: tuple[float, ...] = ()
    srv_reseat_psi: float = 40.0
    srv_capacity_kg_s: float = 0.0  # each, at its set point
    feedwater_temp_c: float = 0.0
    feedwater_max_fraction: float = 1.15  # of rated steam flow
    feedwater_time_constant: float = 3.0
    level_gain: float = 0.02  # fraction of rated steam flow per inch of level error
    downcomer_transit_s: float = 8.0
    # --- containment
    torus_water_mass: float = 0.0  # kg
    torus_initial_temp: float = 30.0
    # --- poisons and burnup
    flux_per_watt: float = 0.0
    sigma_f: float = 0.0
    sigma_a: float = 0.0
    u235_mass_g: float = 0.0
    burnup_reactivity_per_fraction: float = 0.0
    decay_heat_at_shutdown: float | None = None
    intrinsic_source: float = 0.0  # W/s
    fuel_limits: dict | None = None
    setpoints: BWRSetpoints | None = None
    eccs: ECCS | None = None
