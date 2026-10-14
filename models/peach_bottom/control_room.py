"""Peach Bottom Units 2/3 main control room, Unit 2 side, in its analog (pre-2025) state.

Layout after the GE BWR/4 arrangement described in the project's "Peach Bottom Unit 2 Visual
Reference" (Drive) and the NRC BWR/4 technology manual chapters it cites: a horseshoe of
benchboards the operator stands inside, open to the south, with the reactor control benchboard
(P603) across the north, the core cooling benchboard (P601) on the operator's left and the
turbine-generator benchboard (P653) on the right, joined by angled corner panels (P602 RHR and
containment, P652 electrical). Vertical back panels for recorders and relays stand behind the
horseshoe, and the shift supervisor's desk faces the boards from the open end.

Panel numbers follow the GE pattern (the visual reference says to check them against the
Peach Bottom UFSAR Chapter 7); the proportions (benchboard 0.95 m bench, 2.3 m vertical
section, annunciator boxes above) are typical GE benchboards, not measured. The finish follows
the project's reference photos of the Unit 2 boards: cream panels with black trim, maroon
carpet, a white luminous ceiling, red doors, annunciator boxes of tall windows in lettered
columns and five numbered rows with numbered title plates (301 F/W, 302 RFPT, 303 COND,
305/306 TURBINE, 310/311 REACTOR, 313/314 RECIRC, 321 HPCI, 322 RCIC, 323 RHR/CS ...), the
full core display with its green readout, stencilled panel-number plates and yellow-tabbed
document pockets on the console fronts, and a map-style mimic desk of laminated drawings.
Everything the operator can read or use is named ``ui_...`` and tagged for the page, see panels.py.
"""
from __future__ import annotations

import math

from models.pur1.common import MeshBuilder, box, empty, flat_text
from models.peach_bottom import panels as P
from models.peach_bottom.panels import (ANN_COL_W, annunciator_box, control_switch, core_display, digital,
                                        document_pocket, face_frame, flat_screen, keypad_display, keyswitch, lamp,
                                        ma_station, meter, nameplate, pushbutton, recorder, rod_select_matrix,
                                        square_button, stencil_plate, thumbwheel)

ROOM_X = (-10.0, 10.0)
ROOM_Y = (-7.5, 7.5)
CEILING = 3.2
BENCH_DEPTH, BENCH_LOW, BENCH_HIGH = 0.72, 0.82, 0.95   # the sloped bench section
PANEL_DEPTH, PANEL_H = 0.55, 2.30                        # the vertical section behind it
SPAWN = (0.0, -1.2, 0.0)                                 # inside the horseshoe, facing the reactor benchboard

# Annunciator boxes by panel number, as the title plates in the reference photos read them.
# Each is a 10-column (A to J) by 5-row box; the keys fill it row by row and the rest stay blank.
ANN_P603 = [
    ("301 F/W", [
        "level_low_l4", "level_low_l3", "level_high_l7", "level_high_l8", "feed_trip", "feed_a_trip", "feed_b_trip", "feed_c_trip", "level_l2", "level_l1"]),
    ("310 REACTOR", [
        "aprm_high", "aprm_flow", "aprm_setdown", "irm_high", "rod_block", "rod_drift", "select_error", "scram", "half_scram", "rps_trouble",
        "pressure_high", "msl_low", "tsv_closure", "msiv_closure", "mode_startup", "exclusion", "core_uncovered", "fuel_damage", "srv_open", "spare"]),
    ("311 REACTOR", [
        "level_low_l3", "level_l2", "level_l1", "pressure_high", "scram", "atws_rpt", "half_scram", "rps_trouble", "msiv_closure", "spare"]),
    ("313 RECIRC", ["recirc_a_trip", "exclusion", "atws_rpt", "aprm_flow"]),
    ("314 RECIRC", ["recirc_b_trip", "exclusion", "atws_rpt", "aprm_flow"]),
]
ANN_P601 = [
    ("321 HPCI", ["hpci_init", "hpci_run", "hpci_unavail", "level_l2", "ads_timer", "ads_open", "ads_inhibit", "srv_open", "msiv_closure", "spare"]),
    ("322 RCIC", ["rcic_init", "rcic_run", "rcic_unavail", "level_l2", "torus_temp", "torus_level", "drywell_press", "spare"]),
    ("323 RHR/CS", ["cs_init", "cs_run", "cs_unavail", "lpci_init", "lpci_run", "lpci_unavail", "level_l1", "core_uncovered", "torus_temp", "drywell_press"]),
]
ANN_P653 = [
    ("302 RFPT", ["feed_a_trip", "feed_b_trip", "feed_c_trip", "feed_trip", "level_high_l8"]),
    ("303 COND", ["condenser_low", "bypass_open", "bypass_unavail", "spare"]),
    ("305 TURBINE", ["turbine_trip", "tsv_closure", "tcv_fast", "ehc_trouble", "pressure_high", "msl_low", "msiv_closure"]),
    ("306 TURBINE", ["gen_breaker", "station_blackout", "diesel_start", "spare"]),
]
ANN_P602 = [("307/308 ACDT MON", ["torus_temp", "torus_level", "drywell_press", "core_uncovered", "fuel_damage"])]
ANN_P652 = [("309 DRS/DC PWR", ["station_blackout", "diesel_start", "gen_breaker"]), ("304 CIRC WTR", ["condenser_low"])]


def benchboard(parent, name, origin, yaw, width, with_bench=True, ann=None, ann_cols=10, title=None, front=(), pockets=()):
    """One GE benchboard: a sloped bench section with the vertical panel behind it and the
    annunciator boxes on top, built with the operator at local -X and turned by ``yaw``.
    ``ann`` lists (title, keys) boxes set side by side along the top; ``front`` lists
    (text, r) stencilled number plates and ``pockets`` the r of document pockets on the
    console front below the bench."""
    m = P.mats()
    root = empty(name, origin, parent)
    root.rotation_euler = (0, 0, yaw)
    W = width
    body = MeshBuilder().box((PANEL_DEPTH / 2, 0, PANEL_H / 2), (PANEL_DEPTH, W, PANEL_H))
    body.build(f"{name}_Vertical", m["panel"], root, bevel=0.004)
    # Thin trim strips frame the panel faces as the GE boards are built in bolted sections.
    trim = MeshBuilder()
    for y in (-W / 2, W / 2):
        trim.box((-0.004, y, PANEL_H / 2 + 0.02), (0.008, 0.03, PANEL_H + 0.04))
    trim.box((-0.004, 0, PANEL_H + 0.015), (0.008, W + 0.03, 0.03))
    trim.build(f"{name}_Trim", m["panel_dark"], root)
    frames = {"root": root, "vert": face_frame(f"{name}_VertFrame", root, (0, 0, 0))}
    if with_bench:
        x0, x1 = -BENCH_DEPTH, 0.0
        v = [(x0, -W / 2, 0), (x1, -W / 2, 0), (x1, W / 2, 0), (x0, W / 2, 0),
             (x0, -W / 2, BENCH_LOW), (x1, -W / 2, BENCH_HIGH), (x1, W / 2, BENCH_HIGH), (x0, W / 2, BENCH_LOW)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        wedge = MeshBuilder()
        wedge._add(v, f)
        wedge.build(f"{name}_Bench", m["bench_top"], root, bevel=0.004)
        # kick plate and the writing ledge along the operator's edge
        box(f"{name}_Kick", (x0 + 0.06, 0, 0.05), (0.12, W, 0.10), m["panel_dark"], root)
        box(f"{name}_Ledge", (x0 + 0.03, 0, BENCH_LOW + 0.012), (0.09, W, 0.024), m["panel_dark"], root)
        theta = math.atan2(BENCH_DEPTH, BENCH_HIGH - BENCH_LOW)        # tip of the bench frame
        frames["bench"] = face_frame(f"{name}_BenchFrame", root, ((x0 + x1) / 2, 0, (BENCH_LOW + BENCH_HIGH) / 2 + 0.002), pitch=theta)
        # the console front under the bench: stencilled panel numbers and document pockets
        front_frame = face_frame(f"{name}_FrontFrame", root, (x0, 0, 0))
        frames["front"] = front_frame
        for text, r in front:
            stencil_plate(front_frame, text, r, 0.62)
        for r in pockets:
            document_pocket(front_frame, r, 0.36)
    if ann:
        n = len(ann)
        bw = ann_cols * ANN_COL_W + 0.03
        gap = max(0.06, (W - n * bw) / (n + 1))
        total = n * bw + (n - 1) * gap
        for i, (ttl, keys) in enumerate(ann):
            r = -total / 2 + bw / 2 + i * (bw + gap)
            frames[f"ann{i}"] = annunciator_box(root, f"Ann_{name}_{ttl.split()[0].replace('/', '_')}", r, PANEL_H + 0.33, bw,
                                                5, ann_cols, keys=keys, title=ttl)
    if title:
        nameplate(frames["vert"], title, 0.0, PANEL_H - 0.13 if ann else PANEL_H - 0.06, size=0.03, width=len(title) * 0.024 + 0.08)
    return frames


# ----------------------------------------------------------------------------- P603 reactor control
def build_p603(parent):
    fr = benchboard(parent, "P603", (0.0, 4.0, 0.0), math.pi / 2, 7.2, ann=ANN_P603,
                    title="P603  REACTOR CONTROL", front=[("318  301  302", -2.4), ("303  304", 0.0), ("305  306", 2.4)],
                    pockets=[-3.3, -1.3, 1.1, 3.2])
    v, b = fr["vert"], fr["bench"]

    # --- Recirculation (operator's far left)
    nameplate(v, "RECIRCULATION", -2.75, 2.12, size=0.016)
    meter(v, "RecircFlowA", -3.15, 1.92, tag="recirc_flow_a", lo=0, hi=50, unit="Mlb/h", legend="LOOP A FLOW")
    meter(v, "RecircFlowB", -3.05, 1.92, tag="recirc_flow_b", lo=0, hi=50, unit="Mlb/h", legend="LOOP B FLOW")
    meter(v, "CoreFlow", -2.90, 1.92, w=0.10, h=0.20, tag="core_flow", lo=0, hi=150, unit="Mlb/h", legend="TOTAL CORE FLOW", red=102.5)
    meter(v, "PumpSpeedA", -2.72, 1.92, tag="recirc_speed_a", lo=0, hi=100, unit="%", legend="PUMP A SPEED")
    meter(v, "PumpSpeedB", -2.62, 1.92, tag="recirc_speed_b", lo=0, hi=100, unit="%", legend="PUMP B SPEED")
    meter(v, "CoreDP", -2.47, 1.92, tag="core_dp", lo=0, hi=30, unit="psid", legend="CORE PLATE dP")
    recorder(v, "RecCoreFlow", -2.85, 1.38, tags=["core_flow", "recirc_flow_a", "recirc_flow_b"], lo=0, hi=150, unit="Mlb/h",
             legend="CORE FLOW / LOOP FLOW")
    lamp(v, "JetPumpHi", -2.42, 1.55, "amber", tag="jet_pump_mismatch", label="Jet pump flow mismatch")
    nameplate(v, "RECIRC PUMP A", -3.0, 1.05, size=0.010)
    nameplate(v, "RECIRC PUMP B", -2.55, 1.05, size=0.010)
    control_switch(b, "RecircPumpA", -3.05, 0.12, role="recirc_pump_a", label="Recirculation pump A: start / stop",
                   positions=["STOP", "", "START"], tag="recirc_a_run", light_tags=("recirc_a_run", "recirc_a_stopped"))
    control_switch(b, "RecircPumpB", -2.45, 0.12, role="recirc_pump_b", label="Recirculation pump B: start / stop",
                   positions=["STOP", "", "START"], tag="recirc_b_run", light_tags=("recirc_b_run", "recirc_b_stopped"))
    ma_station(b, "RecircSpeed", -2.75, 0.02, tag="recirc_demand", setpoint_tag="recirc_demand", lo=0, hi=100, unit="%",
               legend="RECIRC MG SET SPEED", role_up="recirc_raise", role_down="recirc_lower", role_auto="recirc_auto",
               label="Recirculation flow control: pump speed demand")
    nameplate(b, "RECIRC FLOW CONTROL", -2.75, -0.25, size=0.010)
    for i, pump in enumerate("AB"):
        square_button(b, f"RecircMG{pump}_Run", -3.30 + i * 0.07, -0.16, "red", role=f"recirc_pump_{pump.lower()}",
                      label=f"Recirc MG set {pump}: running (press to stop)", lamp_tag=f"recirc_{pump.lower()}_run")
        square_button(b, f"RecircMG{pump}_Stop", -3.30 + i * 0.07, -0.23, "green", role=f"recirc_pump_{pump.lower()}",
                      label=f"Recirc MG set {pump}: stopped (press to start)", lamp_tag=f"recirc_{pump.lower()}_stopped")
    nameplate(b, "MG SET  A   B", -3.27, -0.30, size=0.007)

    # --- Feedwater and level
    nameplate(v, "FEEDWATER / REACTOR LEVEL", -1.75, 2.12, size=0.016)
    meter(v, "LevelWR", -2.22, 1.92, w=0.09, h=0.22, tag="level", lo=-150, hi=60, unit="in", legend="RX LEVEL WIDE RANGE", red=1)
    meter(v, "LevelNR_A", -2.08, 1.92, tag="level", lo=0, hi=60, unit="in", legend="LEVEL NR A", red=1)
    meter(v, "LevelNR_B", -1.98, 1.92, tag="level", lo=0, hi=60, unit="in", legend="LEVEL NR B", red=1)
    meter(v, "PressA", -1.84, 1.92, tag="pressure", lo=0, hi=1500, unit="psig", legend="RX PRESSURE A", red=1085)
    meter(v, "PressB", -1.74, 1.92, tag="pressure", lo=0, hi=1500, unit="psig", legend="RX PRESSURE B", red=1085)
    meter(v, "SteamFlow", -1.58, 1.92, w=0.09, h=0.22, tag="steam_flow", lo=0, hi=20, unit="Mlb/h", legend="TOTAL STEAM FLOW")
    meter(v, "FeedFlow", -1.44, 1.92, w=0.09, h=0.22, tag="feed_flow", lo=0, hi=20, unit="Mlb/h", legend="TOTAL FEED FLOW")
    meter(v, "FeedTemp", -1.30, 1.92, tag="feed_temp", lo=0, hi=500, unit="F", legend="FEEDWATER TEMP")
    recorder(v, "RecLevelPress", -2.05, 1.38, tags=["level", "pressure"], lo=0, hi=100, unit="%",
             legend="RX LEVEL (0-60 in) / PRESSURE (0-1500 psig)")
    recorder(v, "RecSteamFeed", -1.55, 1.38, tags=["steam_flow", "feed_flow"], lo=0, hi=20, unit="Mlb/h",
             legend="STEAM FLOW / FEED FLOW")
    lamp(v, "LevelL8", -1.30, 1.65, "red", tag="level_high_l8", label="Level 8: turbine and feed pump trip")
    lamp(v, "LevelL7", -1.30, 1.60, "amber", tag="level_high_l7", label="Level 7 high level alarm")
    lamp(v, "LevelL4", -1.30, 1.55, "amber", tag="level_low_l4", label="Level 4 low level alarm")
    lamp(v, "LevelL3", -1.30, 1.50, "red", tag="level_low_l3", label="Level 3 scram")
    lamp(v, "LevelL2", -1.30, 1.45, "red", tag="level_l2", label="Level 2: HPCI / RCIC initiation")
    lamp(v, "LevelL1", -1.30, 1.40, "red", tag="level_l1", label="Level 1: low pressure ECCS initiation")
    thumbwheel(b, "LevelSetpoint", -2.15, 0.20, tag="level_setpoint", digits=3, legend="LEVEL SETPOINT (in)",
               role_up="level_sp_raise", role_down="level_sp_lower", label="Reactor water level set point")
    ma_station(b, "LevelControl", -1.95, 0.0, tag="feed_demand", setpoint_tag="level_setpoint", lo=0, hi=120, unit="%",
               legend="FW LEVEL CONTROL", role_up="feed_raise", role_down="feed_lower", role_auto="feed_auto",
               label="Feedwater level control station (3-element)")
    control_switch(b, "ElementSel", -1.75, 0.18, role="info", label="Level control: 3-element / 1-element selector",
                   positions=["1 ELEM", "", "3 ELEM"], tag="three_element", lights=(), spring=False, radius=0.022)
    for i, pump in enumerate("ABC"):
        control_switch(b, f"FeedPump{pump}", -1.70 + i * 0.16, -0.14, role=f"feed_pump_{pump.lower()}",
                       label=f"Reactor feed pump {pump}: trip / reset", positions=["TRIP", "", "RUN"], tag="feed_run",
                       light_tags=("feed_run", "feed_stopped"), radius=0.022)
    nameplate(b, "REACTOR FEED PUMPS  A   B   C", -1.54, -0.30, size=0.009)
    for i, pump in enumerate("ABC"):
        square_button(b, f"FeedPump{pump}_Run", -1.24 + i * 0.07, -0.10, "red", role=f"feed_pump_{pump.lower()}",
                      label=f"Reactor feed pump {pump}: running (press to trip)", lamp_tag="feed_run")
        square_button(b, f"FeedPump{pump}_Stop", -1.24 + i * 0.07, -0.16, "green", role=f"feed_pump_{pump.lower()}",
                      label=f"Reactor feed pump {pump}: stopped (press to start)", lamp_tag="feed_stopped")
    nameplate(b, "RFP  A    B    C", -1.17, -0.23, size=0.007)

    # --- Neutron monitoring (centre): full core display over the APRM meters
    nameplate(v, "NEUTRON MONITORING", 0.0, 2.12, size=0.016)
    core_display(v, "FullCoreDisplay", 0.0, 1.73, size=0.60)
    for i, ch in enumerate("ABCDEF"):
        meter(v, f"APRM_{ch}", -0.45 + i * 0.09, 1.21, w=0.075, h=0.21, tag="aprm", lo=0, hi=125, unit="%",
              legend=f"APRM {ch}", red=120)
    meter(v, "APRM_FlowBias", 0.52, 1.21, w=0.075, h=0.21, tag="aprm_flow_setpoint", lo=0, hi=125, unit="%",
          legend="FLOW BIAS TRIP", red=None)
    nameplate(v, "APRM  A    B    C    D    E    F", -0.22, 1.05, size=0.009)
    rod_select_matrix(b, "RodSelect", -0.62, 0.02, size=0.40)
    nameplate(b, "ROD SELECT", -0.62, -0.25, size=0.010)
    digital(b, "RodSelected", -0.26, 0.25, w=0.10, h=0.04, tag="rod_selected", digits=4, legend="SELECTED ROD")
    digital(b, "RodPosition", -0.12, 0.25, w=0.10, h=0.04, tag="rod_notch", digits=2, legend="ROD POSITION")
    keypad_display(b, "RWM", 0.62, 0.22, tag="rod_notch", digits=4, legend="ROD WORTH MINIMIZER",
                   label="Rod worth minimizer display (rod position)")
    nameplate(b, "ROD MOVEMENT CONTROL", -0.12, 0.16, size=0.009)
    pushbutton(b, "RodInsert", -0.26, 0.05, "black", role="rod_in", label="Rod in (hold)")
    pushbutton(b, "RodNotchOut", -0.12, 0.05, "black", role="rod_notch_out", label="Rod out notch")
    pushbutton(b, "RodContOut", 0.02, 0.05, "black", role="rod_out", label="Continuous rod out (hold)")
    nameplate(b, "IN       NOTCH OUT      CONT OUT", -0.12, -0.02, size=0.007)
    control_switch(b, "NotchOverride", -0.12, -0.16, role="info", label="Rod out notch override switch",
                   positions=["", "NORMAL", "OVERRIDE"], tag="", lights=(), radius=0.022)
    lamp(b, "RodOutPermit", 0.12, 0.25, "green", tag="rod_out_permit", label="Rod out permissive")
    lamp(b, "RodBlock", 0.12, 0.20, "amber", tag="rod_block", label="Rod block")
    lamp(b, "RodDrift", 0.12, 0.15, "amber", tag="rod_drift", label="Rod drift")
    lamp(b, "RodMoving", 0.12, 0.10, "white", tag="rod_moving", label="Rod motion")
    keyswitch(b, "ModeSwitch", 0.38, 0.12, role="mode_switch", label="Reactor mode switch (SHUTDOWN / REFUEL / STARTUP / RUN)",
              positions=["SHUTDOWN", "REFUEL", "STARTUP", "RUN"], tag="mode")
    nameplate(b, "REACTOR MODE SWITCH", 0.38, -0.02, size=0.009)
    nameplate(b, "SHUTDOWN  REFUEL  STARTUP  RUN", 0.38, 0.22, size=0.007)
    pushbutton(b, "ScramA", 0.72, -0.08, "red", role="scram", label="Manual SCRAM, channel A", radius=0.022,
               collar="collar_yellow", mushroom=True)
    pushbutton(b, "ScramB", 0.86, -0.08, "red", role="scram", label="Manual SCRAM, channel B", radius=0.022,
               collar="collar_yellow", mushroom=True)
    nameplate(b, "MANUAL SCRAM   A      B", 0.79, -0.24, size=0.009)
    control_switch(b, "ScramReset", 0.79, 0.14, role="scram_reset", label="Scram reset switch",
                   positions=["", "NORMAL", "RESET"], tag="", lights=(), radius=0.022)
    nameplate(b, "SCRAM RESET", 0.79, 0.26, size=0.008)
    keyswitch(b, "SLC", 1.08, 0.12, role="slc", label="Standby liquid control: inject boron (keylock)",
              positions=["STOP", "PUMP A", "PUMP B"], tag="slc")
    nameplate(b, "STANDBY LIQUID CONTROL", 1.08, -0.02, size=0.008)
    lamp(b, "SLC_Run", 1.08, 0.25, "red", tag="slc_run", label="SLC pump running")

    # --- IRM / SRM (right of centre)
    nameplate(v, "IRM / SRM", 1.70, 2.12, size=0.016)
    for i, ch in enumerate("ABCDEFGH"):
        meter(v, f"IRM_{ch}", 1.22 + i * 0.085, 1.92, w=0.072, h=0.19, tag="irm", lo=0, hi=125, unit="%", legend=f"IRM {ch}", red=120)
    for i, ch in enumerate("ABCD"):
        meter(v, f"SRM_{ch}", 1.95 + i * 0.085, 1.92, w=0.072, h=0.19, tag="srm", lo=-1, hi=6, unit="cps", legend=f"SRM {ch}", log=1)
    meter(v, "Period", 2.30, 1.92, w=0.09, h=0.19, tag="period", lo=-100, hi=100, unit="s", legend="RX PERIOD", kind="round")
    recorder(v, "RecAPRM", 1.45, 1.38, tags=["aprm", "core_flow"], lo=0, hi=125, unit="%", legend="APRM / CORE FLOW")
    recorder(v, "RecIRM", 1.95, 1.38, tags=["irm", "srm"], lo=0, hi=125, unit="%", legend="IRM / SRM")
    nameplate(b, "IRM RANGE  A  B  C  D  E  F  G  H", 1.45, 0.26, size=0.008)
    for i, ch in enumerate("ABCDEFGH"):
        control_switch(b, f"IRMRange_{ch}", 1.22 + i * 0.075, 0.12, role="info", label=f"IRM {ch} range switch (1-10)",
                       positions=["1", "5", "10"], tag="irm_range", lights=(), spring=False, radius=0.018)
    control_switch(b, "IRMBypass", 1.35, -0.12, role="info", label="IRM bypass joystick", positions=["A", "", "H"],
                   tag="", lights=(), spring=False, radius=0.024)
    control_switch(b, "APRMBypass", 1.70, -0.12, role="info", label="APRM bypass joystick", positions=["A", "", "F"],
                   tag="", lights=(), spring=False, radius=0.024)
    nameplate(b, "IRM BYPASS     APRM BYPASS", 1.52, -0.27, size=0.008)

    # --- RPS and rod control status (far right)
    nameplate(v, "REACTOR PROTECTION", 2.95, 2.12, size=0.016)
    for i, trip in enumerate(["A1", "A2", "B1", "B2"]):
        lamp(v, f"RPS_{trip}", 2.65 + i * 0.09, 1.98, "red", tag="scram", label=f"RPS trip system {trip} tripped")
        lamp(v, f"RPS_{trip}_ok", 2.65 + i * 0.09, 1.93, "green", tag="not_scrammed", label=f"RPS trip system {trip} reset")
    nameplate(v, "TRIP   A1    A2    B1    B2", 2.78, 2.05, size=0.007)
    lamp(v, "ScramLamp", 3.15, 1.98, "red", tag="scram", radius=0.016, label="SCRAM")
    nameplate(v, "SCRAM", 3.15, 2.05, size=0.008)
    lamp(v, "ScramAir", 3.15, 1.90, "white", tag="scram_pilot", label="Scram pilot valve air header")
    for i, (key, lbl, col) in enumerate([("aprm_high", "APRM HI", "red"), ("aprm_flow", "APRM FLOW BIAS", "red"),
                                         ("level_low_l3", "LEVEL 3", "red"), ("pressure_high", "RX PRESS HI", "red"),
                                         ("tsv_closure", "TSV CLOSURE", "red"), ("msiv_closure", "MSIV CLOSURE", "red"),
                                         ("mode_startup", "MODE SW NOT RUN", "amber"), ("half_scram", "HALF SCRAM", "amber")]):
        lamp(v, f"Trip_{key}", 2.62 + (i % 4) * 0.14, 1.76 - (i // 4) * 0.08, col, tag=key, label=f"Trip: {lbl}")
    nameplate(v, "SCRAM TRIP SIGNALS", 2.83, 1.63, size=0.009)
    digital(v, "ScramTimer", 2.95, 1.45, w=0.12, h=0.045, tag="time_since_scram", digits=5, legend="TIME SINCE SCRAM (s)")
    digital(v, "Reactivity", 2.95, 1.33, w=0.12, h=0.045, tag="reactivity", digits=5, legend="REACTIVITY ($)")
    meter(v, "ThermalPower", 2.70, 1.15, w=0.09, h=0.20, tag="thermal_power", lo=0, hi=125, unit="%", legend="CORE THERMAL POWER", red=100)
    meter(v, "FuelTemp", 2.85, 1.15, w=0.09, h=0.20, tag="fuel_temp", lo=0, hi=3000, unit="F", legend="AVG FUEL TEMP (CALC)")
    meter(v, "Void", 3.00, 1.15, w=0.09, h=0.20, tag="void", lo=0, hi=100, unit="%", legend="CORE VOID (CALC)")
    meter(v, "Xenon", 3.15, 1.15, w=0.09, h=0.20, tag="xenon", lo=-5, hi=0, unit="$", legend="XENON WORTH (CALC)")
    pushbutton(b, "AnnAck", 2.90, 0.12, "black", role="ann_ack", label="Annunciator acknowledge", radius=0.012)
    pushbutton(b, "AnnReset", 3.02, 0.12, "black", role="ann_reset", label="Annunciator reset", radius=0.012)
    pushbutton(b, "AnnTest", 3.14, 0.12, "black", role="ann_test", label="Annunciator lamp test", radius=0.012)
    nameplate(b, "ACK    RESET    TEST", 3.02, 0.02, size=0.008)
    control_switch(b, "RPSReset", 2.60, 0.10, role="scram_reset", label="RPS trip reset (both channels)",
                   positions=["", "NORMAL", "RESET"], tag="", lights=(), radius=0.022)
    nameplate(b, "RPS RESET", 2.60, -0.06, size=0.008)
    control_switch(b, "Historian", 2.85, -0.18, role="info", label="Sequence of events recorder: run / hold",
                   positions=["HOLD", "", "RUN"], tag="", lights=(), spring=False, radius=0.018)
    return fr


# ----------------------------------------------------------------------------- P601 core cooling
def build_p601(parent):
    fr = benchboard(parent, "P601", (-5.16, -0.06, 0.0), math.pi, 5.0, ann=ANN_P601,
                    title="P601  CORE COOLING SYSTEMS", front=[("321  322", -1.6), ("323  324", 1.0)], pockets=[-0.4, 2.0])
    v, b = fr["vert"], fr["bench"]
    nameplate(v, "HPCI", -2.05, 2.12, size=0.016)
    meter(v, "HPCIFlow", -2.25, 1.90, w=0.09, h=0.20, tag="hpci_flow", lo=0, hi=6000, unit="gpm", legend="HPCI FLOW")
    meter(v, "HPCISpeed", -2.10, 1.90, w=0.09, h=0.20, tag="hpci_speed", lo=0, hi=5000, unit="rpm", legend="HPCI TURBINE SPEED")
    meter(v, "HPCIDischP", -1.95, 1.90, w=0.09, h=0.20, tag="hpci_disch", lo=0, hi=1500, unit="psig", legend="HPCI PUMP DISCH")
    nameplate(v, "RCIC", -1.55, 2.12, size=0.016)
    meter(v, "RCICFlow", -1.65, 1.90, w=0.09, h=0.20, tag="rcic_flow", lo=0, hi=800, unit="gpm", legend="RCIC FLOW")
    meter(v, "RCICSpeed", -1.50, 1.90, w=0.09, h=0.20, tag="rcic_speed", lo=0, hi=5000, unit="rpm", legend="RCIC TURBINE SPEED")
    nameplate(v, "CORE SPRAY", -1.05, 2.12, size=0.016)
    meter(v, "CSFlowA", -1.15, 1.90, w=0.09, h=0.20, tag="cs_flow_a", lo=0, hi=8000, unit="gpm", legend="CS LOOP A FLOW")
    meter(v, "CSFlowB", -1.00, 1.90, w=0.09, h=0.20, tag="cs_flow_b", lo=0, hi=8000, unit="gpm", legend="CS LOOP B FLOW")
    nameplate(v, "RHR / LPCI", -0.40, 2.12, size=0.016)
    for i, loop in enumerate("ABCD"):
        meter(v, f"LPCIFlow{loop}", -0.65 + i * 0.15, 1.90, w=0.09, h=0.20, tag=f"lpci_flow_{loop.lower()}", lo=0, hi=12000,
              unit="gpm", legend=f"RHR PUMP {loop} FLOW")
    nameplate(v, "REACTOR", 0.35, 2.12, size=0.016)
    meter(v, "ECCS_Level", 0.20, 1.90, w=0.09, h=0.22, tag="level", lo=-300, hi=60, unit="in", legend="LEVEL FUEL ZONE", red=-160)
    meter(v, "ECCS_Press", 0.35, 1.90, w=0.09, h=0.22, tag="pressure", lo=0, hi=1500, unit="psig", legend="RX PRESSURE", red=1085)
    meter(v, "ECCS_Flow", 0.50, 1.90, w=0.09, h=0.22, tag="eccs_flow", lo=0, hi=50000, unit="gpm", legend="TOTAL ECCS FLOW")
    nameplate(v, "CONTAINMENT", 1.20, 2.12, size=0.016)
    meter(v, "TorusTemp", 0.95, 1.90, w=0.09, h=0.20, tag="torus_temp", lo=0, hi=250, unit="F", legend="TORUS WATER TEMP", red=95)
    meter(v, "TorusLevel", 1.10, 1.90, w=0.09, h=0.20, tag="torus_level", lo=-10, hi=10, unit="in", legend="TORUS LEVEL")
    meter(v, "DrywellP", 1.25, 1.90, w=0.09, h=0.20, tag="drywell_pressure", lo=-5, hi=80, unit="psig", legend="DRYWELL PRESSURE", red=2)
    meter(v, "DrywellT", 1.40, 1.90, w=0.09, h=0.20, tag="drywell_temp", lo=0, hi=350, unit="F", legend="DRYWELL TEMP")
    meter(v, "TorusP", 1.55, 1.90, w=0.09, h=0.20, tag="torus_pressure", lo=-5, hi=80, unit="psig", legend="TORUS PRESSURE")
    recorder(v, "RecECCS", -1.65, 1.35, tags=["hpci_flow", "rcic_flow"], lo=0, hi=6000, unit="gpm", legend="HPCI / RCIC FLOW")
    recorder(v, "RecLPECCS", -0.95, 1.35, tags=["cs_flow_a", "lpci_flow_a"], lo=0, hi=12000, unit="gpm", legend="CORE SPRAY / LPCI FLOW")
    recorder(v, "RecTorus", 1.10, 1.35, tags=["torus_temp", "level"], lo=0, hi=250, unit="F", legend="TORUS TEMP / RX LEVEL")
    recorder(v, "RecLevelFZ", 0.35, 1.35, tags=["level", "pressure"], lo=-300, hi=60, unit="in", legend="FUEL ZONE LEVEL / PRESSURE")
    nameplate(v, "SAFETY / RELIEF VALVES", 2.05, 2.12, size=0.016)
    for i in range(11):
        lamp(v, f"SRV{i + 1}_Open", 1.80 + (i % 6) * 0.09, 1.98 - (i // 6) * 0.10, "red", tag=f"srv_{i + 1}",
             label=f"SRV {i + 1} open")
    nameplate(v, "OPEN  1   2   3   4   5   6", 2.02, 2.05, size=0.007)
    nameplate(v, "7   8   9   10  11", 1.98, 1.95, size=0.007)
    lamp(v, "ADSTimer", 1.85, 1.72, "amber", tag="ads_timer", label="ADS timer running")
    lamp(v, "ADSOpen", 1.95, 1.72, "red", tag="ads_open", label="ADS valves open")
    lamp(v, "ADSInhibit", 2.05, 1.72, "white", tag="ads_inhibit", label="ADS inhibited")
    nameplate(v, "ADS  TIMER   OPEN   INHIBIT", 1.95, 1.65, size=0.007)
    meter(v, "SRVFlow", 2.30, 1.80, w=0.09, h=0.22, tag="srv_flow", lo=0, hi=10, unit="Mlb/h", legend="SRV DISCHARGE FLOW")
    meter(v, "SRVTailT", 2.42, 1.80, w=0.09, h=0.22, tag="srv_tail_temp", lo=0, hi=500, unit="F", legend="SRV TAILPIPE TEMP")

    # bench: system control switches with their lights
    nameplate(b, "HPCI", -2.10, 0.30, size=0.011)
    control_switch(b, "HPCI", -2.25, 0.12, role="hpci", label="HPCI: start / stop", positions=["STOP", "", "START"],
                   tag="hpci_run", light_tags=("hpci_run", "hpci_stopped"))
    control_switch(b, "HPCIInj", -2.05, 0.12, role="info", label="HPCI injection valve", positions=["CLOSE", "", "OPEN"],
                   tag="hpci_run", light_tags=("hpci_run", "hpci_stopped"), radius=0.022)
    control_switch(b, "HPCIAvail", -2.15, -0.16, role="hpci_avail", label="HPCI: in service / out of service (instructor)",
                   positions=["OOS", "", "SERVICE"], tag="hpci_avail", lights=("white",), light_tags=("hpci_avail",),
                   spring=False, radius=0.018)
    nameplate(b, "RCIC", -1.60, 0.30, size=0.011)
    control_switch(b, "RCIC", -1.70, 0.12, role="rcic", label="RCIC: start / stop", positions=["STOP", "", "START"],
                   tag="rcic_run", light_tags=("rcic_run", "rcic_stopped"))
    control_switch(b, "RCICAvail", -1.55, -0.16, role="rcic_avail", label="RCIC: in service / out of service (instructor)",
                   positions=["OOS", "", "SERVICE"], tag="rcic_avail", lights=("white",), light_tags=("rcic_avail",),
                   spring=False, radius=0.018)
    nameplate(b, "CORE SPRAY  A   B", -1.05, 0.30, size=0.011)
    control_switch(b, "CSPumpA", -1.15, 0.12, role="core_spray", label="Core spray pump A: start / stop",
                   positions=["STOP", "", "START"], tag="cs_run", light_tags=("cs_run", "cs_stopped"))
    control_switch(b, "CSPumpB", -0.95, 0.12, role="core_spray", label="Core spray pump B: start / stop",
                   positions=["STOP", "", "START"], tag="cs_run", light_tags=("cs_run", "cs_stopped"))
    nameplate(b, "RHR PUMPS  A   B   C   D", -0.35, 0.30, size=0.011)
    for i, loop in enumerate("ABCD"):
        control_switch(b, f"RHRPump{loop}", -0.65 + i * 0.2, 0.12, role="lpci", label=f"RHR pump {loop} (LPCI): start / stop",
                       positions=["STOP", "", "START"], tag="lpci_run", light_tags=("lpci_run", "lpci_stopped"))
    control_switch(b, "RHRMode", -0.35, -0.16, role="info", label="RHR mode: LPCI / suppression pool cooling / shutdown cooling",
                   positions=["SP COOL", "LPCI", "SDC"], tag="", lights=(), spring=False, radius=0.022)
    # RHR and core spray injection valves: square red (open) / green (closed) pushbuttons in a row
    for i, vlv in enumerate(["RHR INJ A", "RHR INJ B", "RHR INJ C", "RHR INJ D", "CS INJ A", "CS INJ B"]):
        square_button(b, f"Valve{i}_Open", -1.0 + i * 0.07, -0.22, "red", role="info", label=f"{vlv} valve: open",
                      lamp_tag="lpci_run" if vlv.startswith("RHR") else "cs_run")
        square_button(b, f"Valve{i}_Close", -1.0 + i * 0.07, -0.29, "green", role="info", label=f"{vlv} valve: closed",
                      lamp_tag="lpci_stopped" if vlv.startswith("RHR") else "cs_stopped")
    nameplate(b, "INJECTION VALVES   RHR A  B  C  D   CS A  B", -0.82, -0.35, size=0.007)
    keypad_display(b, "ECCSFlow", 0.80, -0.20, tag="eccs_flow", digits=5, legend="TOTAL ECCS FLOW GPM",
                   label="ECCS flow digital display")
    nameplate(b, "ADS", 0.35, 0.30, size=0.011)
    keyswitch(b, "ADSInhibit", 0.35, 0.12, role="ads_inhibit", label="ADS inhibit keylock switch",
              positions=["NORMAL", "INHIBIT"], tag="ads_inhibit")
    pushbutton(b, "ADSManual", 0.60, 0.12, "red", role="ads_manual", label="ADS manual initiation (opens the five ADS valves)",
               radius=0.016, collar="collar_yellow")
    nameplate(b, "ADS MANUAL INITIATION", 0.60, -0.02, size=0.007)
    nameplate(b, "SAFETY / RELIEF VALVES   OPEN - AUTO - CLOSE", 1.65, 0.32, size=0.009)
    for i in range(11):
        control_switch(b, f"SRV{i + 1}", 1.05 + (i % 6) * 0.16, 0.14 - (i // 6) * 0.30, role=f"srv_{i + 1}",
                       label=f"SRV {i + 1} control switch: open / auto / close", positions=["CLOSE", "AUTO", "OPEN"],
                       tag=f"srv_{i + 1}_sw", light_tags=(f"srv_{i + 1}", f"srv_{i + 1}_closed"), spring=False, radius=0.020)
    nameplate(b, "MSIV  INBD A  B  C  D", 2.10, -0.02, size=0.008)
    for i in range(4):
        control_switch(b, f"MSIV_IB_{'ABCD'[i]}", 1.95 + i * 0.11, -0.16, role="msiv", label=f"Inboard MSIV {'ABCD'[i]}: open / close",
                       positions=["CLOSE", "", "OPEN"], tag="msiv_open", light_tags=("msiv_open", "msiv_closed"), radius=0.016)
    return fr


# ----------------------------------------------------------------------------- P653 turbine generator
def build_p653(parent):
    fr = benchboard(parent, "P653", (5.16, -0.06, 0.0), 0.0, 5.0, ann=ANN_P653,
                    title="P653  TURBINE GENERATOR", front=[("302  303", -1.6), ("305  306", 1.0)], pockets=[-0.4, 2.0])
    v, b = fr["vert"], fr["bench"]
    flat_screen(v, "TurbineScreen", 2.05, 1.30, w=0.40, h=0.28, tag="gen_mw", legend="TURBINE SUPERVISORY")
    nameplate(v, "MAIN STEAM", -1.90, 2.12, size=0.016)
    for i, line in enumerate("ABCD"):
        meter(v, f"MSLFlow{line}", -2.30 + i * 0.12, 1.90, w=0.09, h=0.20, tag="msl_flow", lo=0, hi=5, unit="Mlb/h",
              legend=f"MS LINE {line} FLOW")
    meter(v, "MSLPress", -1.78, 1.90, w=0.09, h=0.22, tag="pressure", lo=0, hi=1500, unit="psig", legend="MAIN STEAM PRESS", red=1085)
    meter(v, "TurbInletP", -1.62, 1.90, w=0.09, h=0.22, tag="turbine_inlet", lo=0, hi=1500, unit="psig", legend="TURBINE INLET PRESS")
    meter(v, "FirstStageP", -1.46, 1.90, w=0.09, h=0.22, tag="first_stage", lo=0, hi=800, unit="psig", legend="FIRST STAGE PRESS")
    nameplate(v, "MSIV   INBD        OUTBD", -1.90, 1.50, size=0.008)
    for i in range(4):
        lamp(v, f"MSIV_IB{i}", -2.15 + i * 0.09, 1.42, "green", tag="msiv_open", label=f"Inboard MSIV {'ABCD'[i]} open")
        lamp(v, f"MSIV_OB{i}", -1.70 + i * 0.09, 1.42, "green", tag="msiv_open", label=f"Outboard MSIV {'ABCD'[i]} open")
        lamp(v, f"MSIV_IBc{i}", -2.15 + i * 0.09, 1.36, "red", tag="msiv_closed", label=f"Inboard MSIV {'ABCD'[i]} closed")
        lamp(v, f"MSIV_OBc{i}", -1.70 + i * 0.09, 1.36, "red", tag="msiv_closed", label=f"Outboard MSIV {'ABCD'[i]} closed")
    nameplate(v, "TURBINE", -0.80, 2.12, size=0.016)
    meter(v, "TurbSpeed", -1.15, 1.90, w=0.09, h=0.22, tag="turbine_speed", lo=0, hi=2000, unit="rpm", legend="TURBINE SPEED", red=1980)
    meter(v, "TCVPos", -1.00, 1.90, w=0.09, h=0.22, tag="tcv", lo=0, hi=100, unit="%", legend="CONTROL VALVES")
    meter(v, "BypassPos", -0.85, 1.90, w=0.09, h=0.22, tag="bypass", lo=0, hi=100, unit="%", legend="BYPASS VALVES")
    meter(v, "Vacuum", -0.70, 1.90, w=0.09, h=0.22, tag="vacuum", lo=0, hi=30, unit="in Hg", legend="CONDENSER VACUUM", red=22)
    meter(v, "HotwellT", -0.55, 1.90, w=0.09, h=0.22, tag="hotwell_temp", lo=0, hi=200, unit="F", legend="HOTWELL TEMP")
    nameplate(v, "STOP VALVES  1   2   3   4", -0.85, 1.50, size=0.008)
    for i in range(4):
        lamp(v, f"TSV{i + 1}_open", -1.05 + i * 0.09, 1.42, "green", tag="tsv_open", label=f"Turbine stop valve {i + 1} open")
        lamp(v, f"TSV{i + 1}_closed", -1.05 + i * 0.09, 1.36, "red", tag="tsv_closed", label=f"Turbine stop valve {i + 1} closed")
    lamp(v, "TurbTripped", -0.60, 1.42, "red", tag="turbine_tripped", radius=0.016, label="Turbine tripped")
    nameplate(v, "TRIPPED", -0.60, 1.33, size=0.007)
    nameplate(v, "GENERATOR", 0.45, 2.12, size=0.016)
    meter(v, "GenMW", 0.00, 1.90, w=0.12, h=0.26, tag="gen_mw", lo=0, hi=1200, unit="MWe", legend="GENERATOR MW", red=1100, kind="round")
    meter(v, "GenMVAR", 0.20, 1.90, w=0.09, h=0.22, tag="gen_mvar", lo=-500, hi=500, unit="MVAR", legend="GENERATOR MVAR")
    meter(v, "GenKV", 0.35, 1.90, w=0.09, h=0.22, tag="gen_kv", lo=0, hi=30, unit="kV", legend="GENERATOR VOLTS")
    meter(v, "GenHz", 0.50, 1.90, w=0.09, h=0.22, tag="gen_hz", lo=55, hi=65, unit="Hz", legend="FREQUENCY")
    meter(v, "GenAmps", 0.65, 1.90, w=0.09, h=0.22, tag="gen_amps", lo=0, hi=40, unit="kA", legend="STATOR AMPS")
    meter(v, "GenH2", 0.80, 1.90, w=0.09, h=0.22, tag="gen_h2", lo=0, hi=100, unit="psig", legend="H2 PRESSURE")
    lamp(v, "GenBkrClosed", 0.30, 1.42, "red", tag="gen_breaker", radius=0.014, label="Generator output breaker closed")
    lamp(v, "GenBkrOpen", 0.42, 1.42, "green", tag="gen_breaker_open", radius=0.014, label="Generator output breaker open")
    nameplate(v, "GEN BREAKER  CLOSED  OPEN", 0.36, 1.33, size=0.007)
    recorder(v, "RecGenMW", -1.75, 1.20, tags=["gen_mw", "steam_flow"], lo=0, hi=1200, unit="MWe", legend="GEN MW / STEAM FLOW")
    recorder(v, "RecTurbine", -0.85, 1.20, tags=["pressure", "bypass"], lo=0, hi=1500, unit="psig", legend="MS PRESSURE / BYPASS")
    recorder(v, "RecGen", 0.40, 1.20, tags=["gen_mw", "gen_hz"], lo=0, hi=1200, unit="MWe", legend="MW / FREQUENCY")
    nameplate(v, "FEED PUMP TURBINES", 1.75, 2.12, size=0.016)
    for i, pump in enumerate("ABC"):
        meter(v, f"RFPT{pump}Speed", 1.45 + i * 0.15, 1.90, w=0.09, h=0.22, tag="rfpt_speed", lo=0, hi=6000, unit="rpm",
              legend=f"RFPT {pump} SPEED")
        meter(v, f"RFP{pump}Flow", 1.45 + i * 0.15, 1.55, w=0.09, h=0.22, tag="rfp_flow", lo=0, hi=10, unit="Mlb/h",
              legend=f"FEED PUMP {pump} FLOW")
    meter(v, "CondLevel", 2.05, 1.90, w=0.09, h=0.22, tag="hotwell_level", lo=0, hi=60, unit="in", legend="HOTWELL LEVEL")
    meter(v, "CondPumpDP", 2.20, 1.90, w=0.09, h=0.22, tag="cond_pump", lo=0, hi=600, unit="psig", legend="COND PUMP DISCH")
    # bench
    nameplate(b, "TURBINE", -1.80, 0.30, size=0.011)
    pushbutton(b, "TurbineTrip", -1.95, 0.08, "red", role="turbine_trip", label="Turbine trip pushbutton", radius=0.022,
               collar="collar_yellow", mushroom=True)
    nameplate(b, "TRIP", -1.95, -0.08, size=0.008)
    control_switch(b, "TurbineReset", -1.70, 0.10, role="turbine_reset", label="Turbine trip reset / latch",
                   positions=["", "NORMAL", "RESET"], tag="", lights=("red", "green"), light_tags=("turbine_tripped", "turbine_latched"), radius=0.022)
    nameplate(b, "RESET", -1.70, -0.08, size=0.008)
    nameplate(b, "EHC PRESSURE REGULATOR", -1.20, 0.32, size=0.010)
    ma_station(b, "PressReg", -1.30, 0.02, tag="pressure", setpoint_tag="pressure_setpoint", lo=900, hi=1100, unit="psig",
               legend="PRESS SETPOINT", role_up="press_sp_raise", role_down="press_sp_lower", role_auto="info",
               label="EHC pressure regulator set point (psig)")
    control_switch(b, "BypassJack", -1.05, 0.10, role="bypass_avail", label="Bypass valves: in service / out of service",
                   positions=["OOS", "", "SERVICE"], tag="bypass_avail", lights=("white",), light_tags=("bypass_avail",),
                   spring=False, radius=0.022)
    nameplate(b, "BYPASS VALVES", -1.05, -0.08, size=0.008)
    control_switch(b, "LoadSel", -0.80, 0.10, role="info", label="Load set: raise / lower (EHC)",
                   positions=["LOWER", "", "RAISE"], tag="", lights=(), radius=0.022)
    nameplate(b, "LOAD SET", -0.80, -0.08, size=0.008)
    nameplate(b, "GENERATOR", 0.30, 0.30, size=0.011)
    control_switch(b, "GenBreaker", 0.15, 0.10, role="gen_breaker", label="Generator output breaker: close / trip",
                   positions=["TRIP", "", "CLOSE"], tag="gen_breaker", light_tags=("gen_breaker", "gen_breaker_open"))
    control_switch(b, "GenField", 0.45, 0.10, role="info", label="Generator field breaker", positions=["TRIP", "", "CLOSE"],
                   tag="gen_breaker", light_tags=("gen_breaker", "gen_breaker_open"))
    control_switch(b, "Sync", 0.75, 0.10, role="info", label="Synchroscope switch", positions=["OFF", "", "ON"],
                   tag="", lights=(), spring=False, radius=0.022)
    nameplate(b, "OUTPUT BKR    FIELD BKR    SYNCHROSCOPE", 0.45, -0.08, size=0.007)
    nameplate(b, "REACTOR FEED PUMP TURBINES  A   B   C", 1.60, 0.30, size=0.010)
    for i, pump in enumerate("ABC"):
        control_switch(b, f"RFPT{pump}", 1.35 + i * 0.22, 0.10, role=f"feed_pump_{pump.lower()}", label=f"Feed pump turbine {pump}: start / trip",
                       positions=["TRIP", "", "START"], tag="feed_run", light_tags=("feed_run", "feed_stopped"))
    control_switch(b, "Condenser", 2.15, 0.10, role="condenser_avail", label="Main condenser: available / lost (instructor)",
                   positions=["LOST", "", "AVAIL"], tag="condenser_avail", lights=("white",), light_tags=("condenser_avail",),
                   spring=False, radius=0.022)
    nameplate(b, "CONDENSER", 2.15, -0.08, size=0.008)
    pushbutton(b, "SBO", 2.15, -0.22, "black", role="station_blackout", label="Instructor: station blackout (loss of all AC)", radius=0.010)
    nameplate(b, "SBO", 2.15, -0.30, size=0.007)
    for i, pump in enumerate("ABC"):
        square_button(b, f"CondPump{pump}_Run", 0.95 + i * 0.07, -0.22, "red", role="info", label=f"Condensate pump {pump}: running",
                      lamp_tag="condenser_avail")
        square_button(b, f"CondPump{pump}_Stop", 0.95 + i * 0.07, -0.29, "green", role="info", label=f"Condensate pump {pump}: stopped",
                      lamp_tag="")
    for i, pump in enumerate("ABC"):
        square_button(b, f"CircPump{pump}_Run", 1.25 + i * 0.07, -0.22, "red", role="info", label=f"Circulating water pump {pump}: running",
                      lamp_tag="condenser_avail")
        square_button(b, f"CircPump{pump}_Stop", 1.25 + i * 0.07, -0.29, "green", role="info", label=f"Circulating water pump {pump}: stopped",
                      lamp_tag="")
    nameplate(b, "COND PUMPS  A  B  C     CIRC WTR PUMPS  A  B  C", 1.12, -0.35, size=0.007)
    return fr


def build_corner(parent, name, origin, yaw, title, items, ann=None):
    """Angled corner panel (no bench) with a few meters and lamps."""
    fr = benchboard(parent, name, origin, yaw, 2.2, with_bench=False, title=title, ann=ann, ann_cols=8)
    v = fr["vert"]
    for i, (nm, tag, lo, hi, unit, legend) in enumerate(items):
        meter(v, nm, -0.75 + (i % 5) * 0.3, 1.85 - (i // 5) * 0.32, w=0.09, h=0.22, tag=tag, lo=lo, hi=hi, unit=unit, legend=legend)
    return fr


def build_back_panels(parent):
    """Vertical relay and recorder panels along the north wall behind the horseshoe (P609 to
    P618 in GE numbering), fronts facing south towards the back of the benchboards."""
    m = P.mats()
    root = empty("BackPanels", (0, 6.9, 0), parent)
    root.rotation_euler = (0, 0, math.pi / 2)
    n = 12
    w = 1.2
    MeshBuilder().box((0.3, 0, 1.15), (0.6, n * w, 2.30)).build("BackPanels_Body", m["cabinet"], root)
    trim = MeshBuilder()
    for i in range(n + 1):
        trim.box((-0.004, -n * w / 2 + i * w, 1.15), (0.008, 0.03, 2.30))
    trim.build("BackPanels_Trim", m["panel_dark"], root)
    v = face_frame("BackPanels_Frame", root, (0, 0, 0))
    labels = ["P609 RPS A", "P610 RPS B", "P611 NMS", "P612 PROCESS RAD", "P613 CONTAINMENT", "P614 ECCS RELAYS",
              "P615 ECCS RELAYS", "P616 FEEDWATER", "P617 TURBINE EHC", "P618 ELECTRICAL", "P619 FIRE", "P620 COMMS"]
    for i, lbl in enumerate(labels):
        r = -n * w / 2 + (i + 0.5) * w
        nameplate(v, lbl, r, 2.15, size=0.016)
    recorder(v, "BP_RecAPRM", -n * w / 2 + 2.5 * w, 1.75, tags=["aprm", "thermal_power"], lo=0, hi=125, unit="%", legend="APRM / THERMAL POWER")
    recorder(v, "BP_RecRad", -n * w / 2 + 3.5 * w, 1.75, tags=["msl_rad"], lo=0, hi=10, unit="mR/h", legend="MAIN STEAM LINE RADIATION")
    recorder(v, "BP_RecCont", -n * w / 2 + 4.5 * w, 1.75, tags=["torus_temp", "drywell_pressure"], lo=0, hi=250, unit="F", legend="TORUS TEMP / DW PRESSURE")
    recorder(v, "BP_RecLevel", -n * w / 2 + 7.5 * w, 1.75, tags=["level", "feed_flow"], lo=-150, hi=60, unit="in", legend="LEVEL / FEED FLOW")
    recorder(v, "BP_RecPress", -n * w / 2 + 8.5 * w, 1.75, tags=["pressure", "gen_mw"], lo=0, hi=1500, unit="psig", legend="PRESSURE / GEN MW")
    meter(v, "BP_Xenon", -n * w / 2 + 2.3 * w, 1.25, w=0.09, h=0.22, tag="xenon", lo=-5, hi=0, unit="$", legend="XENON")
    meter(v, "BP_Burnup", -n * w / 2 + 2.7 * w, 1.25, w=0.09, h=0.22, tag="burnup", lo=0, hi=100, unit="%", legend="CYCLE BURNUP")
    flat_screen(v, "BP_ScreenPower", -n * w / 2 + 3.5 * w, 1.15, w=0.44, h=0.32, tag="aprm", legend="CORE MONITOR")
    flat_screen(v, "BP_ScreenLevel", -n * w / 2 + 7.5 * w, 1.15, w=0.44, h=0.32, tag="level", legend="PLANT COMPUTER")
    for i in range(n):
        if i in (2, 3, 4, 7, 8):
            continue
        r = -n * w / 2 + (i + 0.5) * w
        # plain relay panel: a few rows of relay covers and a door handle
        rel = MeshBuilder()
        for row in range(4):
            for col in range(3):
                rel.box((-0.012, -r + (col - 1) * 0.3, 1.9 - row * 0.3), (0.024, 0.14, 0.12))
        rel.build(f"BackPanel_{i + 1}_Relays", m["panel_dark"], v, bevel=0.002)
    return root


def build_room(parent):
    m = P.mats()
    x0, x1 = ROOM_X
    y0, y1 = ROOM_Y
    MeshBuilder().box_minmax((x0, y0, -0.05), (x1, y1, 0.0)).build("Floor", m["floor"], parent)
    walls = MeshBuilder()
    t = 0.3
    walls.box_minmax((x0 - t, y0 - t, 0), (x0, y1 + t, CEILING))
    walls.box_minmax((x1, y0 - t, 0), (x1 + t, y1 + t, CEILING))
    walls.box_minmax((x0, y1, 0), (x1, y1 + t, CEILING))
    walls.box_minmax((x0, y0 - t, 0), (x1, y0, CEILING))
    walls.build("Walls", m["wall"], parent)
    # The luminous ceiling of the photos: white perforated panels lit from above in a metal grid.
    MeshBuilder().box_minmax((x0, y0, CEILING), (x1, y1, CEILING + 0.1)).build("Ceiling", m["ceiling"], parent)
    grid = MeshBuilder()
    for x in range(int(x0), int(x1) + 1):
        grid.box((x, 0, CEILING - 0.008), (0.02, y1 - y0, 0.016))
    for y in range(int(y0), int(y1) + 1):
        grid.box((0, y, CEILING - 0.008), (x1 - x0, 0.02, 0.016))
    grid.build("CeilingGrid", m["ceiling_grid"], parent)
    fix = MeshBuilder()
    for x in range(int(x0), int(x1)):
        for y in range(int(y0), int(y1)):
            fix.box((x + 0.5, y + 0.5, CEILING - 0.005), (0.96, 0.96, 0.01))
    fix.build("LightFixtures", m["fixture"], parent)
    # Red doors in grey frames in the south wall
    for x, nm in ((-7.0, "Door_West"), (7.0, "Door_East")):
        box(f"{nm}_Frame", (x, y0 + 0.02, 1.08), (1.12, 0.05, 2.16), m["door_frame"], parent)
        box(nm, (x, y0 + 0.05, 1.05), (1.0, 0.05, 2.1), m["door"], parent)
        MeshBuilder().box((x + 0.35, y0 + 0.10, 1.0), (0.03, 0.05, 0.12)).build(f"{nm}_Handle", m["chrome"], parent)
        MeshBuilder().box((x, y0 + 0.08, 1.45), (0.22, 0.01, 0.55)).build(f"{nm}_Window", m["glass"], parent)
    # Map-style mimic desk: a low table of laminated plant drawings to spread the procedures on
    mimic = empty("MimicDesk", (0.0, -5.6, 0.0), parent)
    MeshBuilder().box((0, 0, 0.80), (1.3, 2.6, 0.05)).build("Mimic_Top", m["desk"], mimic, bevel=0.004)
    MeshBuilder().box((0, -1.1, 0.39), (1.1, 0.12, 0.78)).box((0, 1.1, 0.39), (1.1, 0.12, 0.78)).build("Mimic_Legs", m["panel_dark"], mimic)
    # sheets lie flat, read by someone standing at the horseshoe end looking south
    sheets = face_frame("Mimic_Frame", mimic, (0, 0, 0.826), pitch=math.pi / 2, yaw=-math.pi / 2)
    for i, (title, zz) in enumerate([("REACTOR RECIRCULATION", -0.95), ("FEEDWATER / CONDENSATE", -0.32), ("RHR / CORE SPRAY", 0.32), ("MAIN STEAM / TURBINE", 0.95)]):
        P._face_quad(f"ui_Drawing_{i}", sheets, 0.0, zz, 1.10, 0.56, m["laminate"], stand=0.001, face="drawing", legend=title,
                     seed=i, label=f"Laminated drawing: {title}")
    # Shift supervisor's desk facing the boards from the open end of the horseshoe
    desk = empty("SupervisorDesk", (0.0, -3.6, 0.0), parent)
    MeshBuilder().box((0, 0, 0.74), (0.9, 2.2, 0.04)).build("Desk_Top", m["desk"], desk, bevel=0.004)
    MeshBuilder().box((0, -0.85, 0.36), (0.8, 0.45, 0.72)).box((0, 0.85, 0.36), (0.8, 0.45, 0.72)).build("Desk_Pedestals", m["panel_dark"], desk)
    MeshBuilder().box((0.2, 0.6, 0.78), (0.22, 0.18, 0.05)).box((0.17, 0.6, 0.82), (0.07, 0.2, 0.03)).build("Telephone_1", m["phone"], desk)
    MeshBuilder().box((0.2, -0.6, 0.78), (0.22, 0.18, 0.05)).box((0.17, -0.6, 0.82), (0.07, 0.2, 0.03)).build("Telephone_2", m["phone"], desk)
    MeshBuilder().box((-0.1, 0.0, 0.77), (0.3, 0.42, 0.02)).build("Desk_Logbook", m["paper"], desk)
    binders = MeshBuilder()
    for i in range(5):
        binders.box((0.3, -0.3 + i * 0.08, 0.90), (0.26, 0.06, 0.30))
    binders.build("Desk_Procedures", m["binder"], desk)
    _chair(parent, m, (0.0, -4.4, 0.0), "SupervisorChair", math.pi / 2)
    # Tall operator stools at the reactor and ECCS benches
    _chair(parent, m, (-1.9, 2.3, 0.0), "OperatorStool_1", math.pi / 2, tall=True)
    _chair(parent, m, (0.9, 2.3, 0.0), "OperatorStool_2", math.pi / 2, tall=True)
    _chair(parent, m, (-3.6, 0.6, 0.0), "OperatorStool_3", 0.0, tall=True)
    # Unit sign over the reactor benchboard and a wall clock
    flat_text("Sign_Unit2", "UNIT 2", m["lettering"], (0.0, 4.5, 2.95), -math.pi / 2, 0.18, depth=0.01, parent=parent)
    MeshBuilder().cylinder((0.0, y1 - 0.02, 2.75), 0.18, 0.03, 32, axis="y").build("WallClock", m["bezel"], parent)
    clock = empty("ClockFrame", (0.0, y1 - 0.05, 2.75), parent)
    clock.rotation_euler = (0, 0, -math.pi / 2)
    P._face_quad("ui_WallClock", clock, 0.0, 0.0, 0.32, 0.32, m["face"], stand=0.001, face="clock", tag="time_s", label="Wall clock")


def _chair(parent, m, origin, name, facing, tall=False):
    root = empty(name, origin, parent)
    root.rotation_euler = (0, 0, facing)
    h = 0.70 if tall else 0.46
    mb = MeshBuilder()
    mb.box((0, 0, h), (0.44, 0.44, 0.06))
    mb.box((-0.2, 0, h + 0.25), (0.05, 0.42, 0.44))
    mb.build(f"{name}_Seat", m["chair"], root, bevel=0.01)
    fr = MeshBuilder()
    fr.cylinder((0, 0, 0.05), 0.025, h - 0.08, 12)
    fr.cylinder((0, 0, 0.0), 0.30, 0.04, 20)
    fr.build(f"{name}_Frame", m["chrome"], root)


def build_control_room(parent=None):
    """Whole room, ready to export."""
    root = parent or empty("PB2_ControlRoom")
    build_room(root)
    build_p603(root)
    build_p601(root)
    build_p653(root)
    c = 0.78
    build_corner(root, "P602", (-3.6 - c, 4.0 - c, 0.0), 3 * math.pi / 4, "P602  RHR / CONTAINMENT", [
        ("P602_TorusT", "torus_temp", 0, 250, "F", "TORUS WATER TEMP"),
        ("P602_DWP", "drywell_pressure", -5, 80, "psig", "DRYWELL PRESSURE"),
        ("P602_DWT", "drywell_temp", 0, 350, "F", "DRYWELL TEMP"),
        ("P602_H2", "drywell_h2", 0, 10, "%", "DRYWELL H2"),
        ("P602_RHRHx", "rhr_hx", 0, 12000, "gpm", "RHR HX FLOW"),
    ], ann=ANN_P602)
    build_corner(root, "P652", (3.6 + c, 4.0 - c, 0.0), math.pi / 4, "P652  STATION ELECTRICAL", [
        ("P652_4kV_A", "bus_4kv", 0, 5, "kV", "4 kV BUS A"),
        ("P652_4kV_B", "bus_4kv", 0, 5, "kV", "4 kV BUS B"),
        ("P652_DG", "diesel_kw", 0, 4000, "kW", "DIESEL GEN LOAD"),
        ("P652_125V", "dc_bus", 0, 150, "V", "125 V DC BUS"),
        ("P652_Grid", "grid_kv", 0, 600, "kV", "500 kV SWITCHYARD"),
    ], ann=ANN_P652)
    build_back_panels(root)
    return root
