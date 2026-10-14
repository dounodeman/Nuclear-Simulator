"""Peach Bottom Atomic Power Station Unit 2: a General Electric BWR/4 in a Mark I containment.

The numbers describe the plant as it ran its April 1977 turbine trip tests at the end of
Cycle 2, the state the OECD/NEA BWR Turbine Trip benchmark (NEA/NSC/DOC(2001)1) documents,
with the original licensed power of 3,293 MWt. Where a value is a typical BWR/4 figure
rather than a Peach Bottom one, docs/peach_bottom_2_reference.md says so.
"""

from __future__ import annotations

from reactorsim.bwr.design import ECCS, BWRDesign, BWRSetpoints
from reactorsim.physics.kinetics import DelayedNeutronData
from reactorsim.physics.steam import from_psig

RATED_W = 3293e6
GPM = 6.309e-5 * 740.0  # kg/s per gpm of hot water (about)
LB_H = 0.4536 / 3600.0

DESIGN = BWRDesign(
    key="peach_bottom_2",
    name="Peach Bottom Unit 2",
    description="GE BWR/4, Mark I containment, 3,293 MWt as tested in 1977 (4,016 MWt today)",
    rated_power=RATED_W,
    licensed_power=RATED_W,
    # Mid-cycle beta-effective; Keepin U-235 group split. The benchmark gives its own six-group
    # set per cycle state, which drops toward 0.0050 at end of cycle as plutonium builds in.
    delayed=DelayedNeutronData.u235_thermal(0.0053),
    generation_time=40e-6,
    excess_reactivity=0.12,  # cold, clean, all rods out; held down by the rods and gadolinia
    fuel_coefficient=-2.0e-5,  # Doppler, per C of average fuel temperature
    moderator_coefficient=-2.0e-5,  # per C of liquid temperature (hot, small; void dominates)
    alpha_void=-1.6e-3,  # per percent core-average void (tuned to the 1977 turbine trip, see docs)
    reference_temp=20.0,
    void_time_constant=0.4,
    n_rods=185,
    notches=48,
    notch_cm=15.24,  # 6 in
    rod_bank_worth=0.18,
    rod_speed_cm_s=7.62,  # 3 in/s
    fuel_heat_capacity=4.6e7,  # about 153 t of UO2 at 300 J/kg-K
    fuel_conductance=1.0e7,  # average fuel about 600 C at rated power
    gamma_fraction=0.04,
    core_coolant_volume=27.0,
    separator_volume=10.0,
    slip_ratio=2.0,
    hot_channel_factor=1.4,
    steam_volume=160.0,
    condensing_mass=150_000.0,
    condensing_time_constant=3.0,
    liquid_mass=250_000.0,
    downcomer_area=12.3,  # annulus between a 251 in vessel and the core shroud
    normal_level_in=35.0,
    taf_level_in=-160.0,
    baf_level_in=-304.0,
    rated_core_flow=102.5e6 * LB_H,  # 102.5 Mlb/h
    natural_circulation_fraction=0.35,
    pump_time_constant=2.0,
    pump_coastdown=4.5,
    min_pump_speed=0.28,
    dome_pressure_setpoint_pa=from_psig(1020.0),
    steam_lines=4,
    msiv_stroke_s=4.0,
    tsv_stroke_s=0.1,
    bypass_fraction=0.25,
    bypass_stroke_s=0.3,
    srv_setpoints_psig=(1135, 1135, 1135, 1145, 1145, 1145, 1145, 1155, 1155, 1155, 1155),
    srv_reseat_psi=40.0,
    srv_capacity_kg_s=870_000 * LB_H,  # about 110 kg/s each at the set point
    feedwater_temp_c=191.0,  # about 376 F
    feedwater_max_fraction=1.15,
    feedwater_time_constant=5.0,
    level_gain=0.01,
    downcomer_transit_s=8.0,
    torus_water_mass=3.48e6,  # about 123,000 ft3
    torus_initial_temp=30.0,
    flux_per_watt=9.1e3,  # about 3e13 n/cm2-s core average thermal flux at rated power
    sigma_f=0.0027,
    sigma_a=0.0060,
    u235_mass_g=3.4e6,  # about 3.4 t of U-235 in 764 assemblies at 2.2% average enrichment
    burnup_reactivity_per_fraction=0.9,
    decay_heat_at_shutdown=0.066,
    intrinsic_source=50.0,
    fuel_limits={"safety_limit": 2200.0, "blister": 1200.0, "melt": 2840.0},  # peak fuel C
    setpoints=BWRSetpoints(
        aprm_high_percent=120.0,
        aprm_flow_bias_slope=0.66,
        aprm_flow_bias_intercept=54.0,
        aprm_setdown_percent=15.0,
        dome_pressure_high_psig=1085.0,
        level3_scram_in=1.0,
        level8_trip_in=54.0,
        level4_alarm_in=27.0,
        level7_alarm_in=45.0,
        level2_in=-48.0,
        level1_in=-160.0,
        tsv_closure_bypass_percent=30.0,
        msl_pressure_low_psig=850.0,
        msl_flow_high_percent=140.0,
        atws_rpt_psig=1135.0,
        ads_delay_s=120.0,
        scram_delay_s=0.1,
        scram_stroke_s=3.5,
    ),
    eccs=ECCS(
        hpci_flow_kg_s=5000 * GPM,
        hpci_min_pressure_pa=from_psig(150.0),
        hpci_start_s=30.0,
        rcic_flow_kg_s=600 * GPM,
        rcic_min_pressure_pa=from_psig(150.0),
        rcic_start_s=30.0,
        core_spray_loops=2,
        core_spray_flow_kg_s=6250 * GPM,
        core_spray_shutoff_pa=from_psig(290.0),
        lpci_pumps=4,
        lpci_flow_kg_s=10_000 * GPM,
        lpci_shutoff_pa=from_psig(220.0),
        lp_start_s=40.0,
        ads_valves=5,
    ),
)
