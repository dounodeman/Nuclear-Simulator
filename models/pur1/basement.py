"""The basement around the reactor room, from the PUR-1 floor plan: the corridor that runs south
from B70A's main door, and the rooms off it that the simulator models inside.

- B70B  Expanding lab space, east of the reactor room (the corridor's north end runs into it)
- B86   Undergraduate thermal-hydraulics lab (natural-circulation loop)
- B85   Beta-voltaic facility (glovebox, light-tight probe station, source safe)
- B77   Chemistry facility room (fume hoods, epoxy-top bench, safety shower)
- B84   Subcritical pile (graphite stack with its testbed, Pu-Be source cask, counting bench)

Other rooms on the plan (B76, B87, the south stair) get a closed door on the corridor and are not
built. Positions and door swings follow the plan (see the basement section of `dims.py`); the
furnishings are representative of each kind of lab, not taken from photos.

Frame: as the hall, +X east, +Y north, floor at z = 0, metres.
"""
from __future__ import annotations

import math

from . import dims as D
from . import props
from .common import MeshBuilder, box, cylinder, empty, flat_text

T = D.BASEMENT_WALL_T
H = D.BASEMENT_H
DOOR_TOP = D.DOOR_H + 0.06          # top of a door frame; lintels start here


def _wall(mb, lo, hi, run, gaps=()):
    """A wall box from `lo` to `hi` (x, y) running along `run` ("x" or "y"), full height, with
    door openings at (centre, width) along the run and a lintel over each."""
    k = 0 if run == "x" else 1
    a0, a1 = lo[k], hi[k]
    cuts = sorted((c - w / 2, c + w / 2) for c, w in gaps)
    pos = a0
    for g0, g1 in cuts + [(a1, a1)]:
        if g0 > pos:
            p0, p1 = list(lo), list(hi)
            p0[k], p1[k] = pos, g0
            mb.box_minmax((p0[0], p0[1], 0.0), (p1[0], p1[1], H))
        if g1 > g0:
            p0, p1 = list(lo), list(hi)
            p0[k], p1[k] = g0, g1
            mb.box_minmax((p0[0], p0[1], DOOR_TOP), (p1[0], p1[1], H))
        pos = max(pos, g1)


def _plate(root, mats, name, pos, facing, number, title):
    """Room plate by a door: dark panel, the room number large and its name under it."""
    nx, ny = math.cos(facing), math.sin(facing)
    x, y = pos
    rx, ry = -ny, nx
    plate = MeshBuilder().box((x, y, 1.6), (0.48 * abs(rx) + 0.012 * abs(nx), 0.48 * abs(ry) + 0.012 * abs(ny), 0.22))
    ob = plate.build(name, mats["panel"], root, bevel=0.003)
    flat_text(f"{name}_Number", number, mats["lettering_white"], (x + nx * 0.006, y + ny * 0.006, 1.64), facing, 0.075, parent=root)
    if title:
        flat_text(f"{name}_Title", title, mats["lettering_white"], (x + nx * 0.006, y + ny * 0.006, 1.55), facing, 0.03, parent=root)
    return ob


def _posting(root, mats, name, pos, facing, z=1.7):
    """Yellow-and-magenta radiation area posting on a wall."""
    nx, ny = math.cos(facing), math.sin(facing)
    x, y = pos
    rx, ry = -ny, nx
    MeshBuilder().box((x, y, z), (0.30 * abs(rx) + 0.006 * abs(nx), 0.30 * abs(ry) + 0.006 * abs(ny), 0.38)).build(name, mats["sign_yellow"], root)
    MeshBuilder().cylinder((x + nx * 0.003, y + ny * 0.003, z + 0.05), 0.07, 0.004, 24,
                           axis="x" if abs(nx) > 0.5 else "y").build(f"{name}_Trefoil", mats["sign_magenta"], root)


def _monitor(root, mats, name, x, y, z, face):
    """A monitor standing at (x, y) on a surface at height z, its screen facing `face`
    ("north", "south", "east" or "west")."""
    turn = {"west": 0.0, "south": math.pi / 2, "east": math.pi, "north": -math.pi / 2}[face]
    fr = props._frame(root, f"{name}_Frame", (x, y, z), turn)
    return props.monitor(fr, mats, name, f"{name}_Screen", 0.1, 0.0, 0.0, 0.53, 0.30)


def build_shell(parent, mats):
    """Floor, ceiling, walls, doors, room plates and ceiling fixtures."""
    root = empty("Basement", (0, 0, 0), parent)
    cw, ce = D.CORRIDOR_X
    ex = D.EAST_WALL_X
    rx1 = D.ROOM_X[1]                       # B70A's east wall inner face (wall to rx1 + WALL_T)
    ry0, ry1 = D.ROOM_Y
    hy = D.CORRIDOR_HEAD_Y
    s84, n84 = D.B84_Y
    h = T / 2

    # One slab under everything from B70A's east wall out, so every threshold has floor.
    fl = MeshBuilder()
    fl.box_minmax((rx1, s84 - h, -0.15), (ex + h, ry1 + D.WALL_T, 0.0))
    fl.box_minmax((D.B77_X - h, D.B77_Y[0] - h, -0.15), (rx1, D.B77_Y[1] + h, 0.0))
    fl.build("Basement_Floor", mats["floor"], root)
    ce_ = MeshBuilder()
    ce_.box_minmax((rx1, s84 - h, H), (ex + h, ry1 + D.WALL_T, H + 0.2))
    ce_.box_minmax((D.B77_X - h, D.B77_Y[0] - h, H), (rx1, D.B77_Y[1] + h, H + 0.2))
    ce_.build("Basement_Ceiling", mats["ceiling"], root)

    w = MeshBuilder()
    # Corridor: west wall from B70A's south-east corner to the B84 wall, east wall from the
    # corridor's north end to the same wall, and the short wall closing its north end.
    _wall(w, (cw - h, n84 - h), (cw + h, ry0 - D.WALL_T), "y", [D.DOOR_B77[:2]])
    _wall(w, (rx1 + D.WALL_T, hy - h), (ce + h, hy + h), "x")
    _wall(w, (ce - h, n84 - h), (ce + h, hy - h), "y", [D.DOOR_B70B[:2], D.DOOR_B86[:2], D.DOOR_B85[:2]])
    # B70B: north wall in line with B70A's, the east wall that B86, B85 and B84 share, and its
    # south wall east of the corridor.
    _wall(w, (rx1 + D.WALL_T, ry1), (ex + h, ry1 + D.WALL_T), "x")
    _wall(w, (ex - h, s84 - h), (ex + h, ry1), "y")
    _wall(w, (ce + h, D.B70B_SOUTH_Y - h), (ex - h, D.B70B_SOUTH_Y + h), "x")
    # B86, B85, B84 cross walls; the B84 wall also ends the corridor and carries B84's door.
    _wall(w, (ce + h, D.B86_Y[1] - h), (ex - h, D.B86_Y[1] + h), "x")
    _wall(w, (ce + h, D.B86_Y[0] - h), (ex - h, D.B86_Y[0] + h), "x")
    _wall(w, (cw - h, n84 - h), (ex - h, n84 + h), "x", [D.DOOR_B84[:2]])
    _wall(w, (cw - h, s84 - h), (cw + h, n84 - h), "y")
    _wall(w, (cw - h, s84 - h), (ex - h, s84 + h), "x")
    # B77 west of the corridor.
    b0, b1 = D.B77_Y
    _wall(w, (D.B77_X - h, b0 - h), (D.B77_X + h, b1 + h), "y")
    _wall(w, (D.B77_X + h, b1 - h), (cw - h, b1 + h), "x")
    _wall(w, (D.B77_X + h, b0 - h), (cw - h, b0 + h), "x")
    w.build("Basement_Walls", mats["wall_cream"], root)

    # Doors. Faces: corridor west face cw + h, corridor east face ce - h, B70B side ce + h.
    E, W_, N = -math.pi / 2, math.pi / 2, 0.0      # door facings whose local +Y points east, west, north
    doors = [
        ("Door_B70B", (ce + h, D.DOOR_B70B[0]), E, D.DOOR_B70B, 90),     # swings into B70B
        ("Door_B86", (ce - h, D.DOOR_B86[0]), W_, D.DOOR_B86, 90),       # the rest swing into the corridor
        ("Door_B85", (ce - h, D.DOOR_B85[0]), W_, D.DOOR_B85, 90),
        ("Door_B77", (cw + h, D.DOOR_B77[0]), E, D.DOOR_B77, 90),
        ("Door_B84", (D.DOOR_B84[0], n84 + h), N, D.DOOR_B84, 90),
        ("Door_B76", (cw + h, D.DOOR_B76[0]), E, D.DOOR_B76, 0),         # closed: rooms not modelled
        ("Door_B87", (ce - h, D.DOOR_B87[0]), W_, D.DOOR_B87, 0),
        ("Door_Stair", (cw + h, D.DOOR_STAIR[0]), E, D.DOOR_STAIR, 0),
    ]
    for nm, (x, y), facing, (_, width, leaves), open_deg in doors:
        props.door(root, mats, nm, (x, y, 0), facing, width, D.DOOR_H, T,
                   sign=nm in ("Door_B84", "Door_B85"), leaves=leaves, open_deg=open_deg)

    # Room plates on the corridor side of each door (and B70B's on its door from the corridor).
    pe, pw = ce - h - 0.006, cw + h + 0.006
    plates = [
        ("Sign_B70B", (pe, D.DOOR_B70B[0] - 1.2), math.pi, "B70B", "EXPANDING LAB SPACE"),
        ("Sign_B86", (pe, D.DOOR_B86[0] + 1.25), math.pi, "B86", "UNDERGRAD THERMAL HYDRAULICS LAB"),
        ("Sign_B85", (pe, D.DOOR_B85[0] + 1.25), math.pi, "B85", "BETA VOLTAIC FACILITY"),
        ("Sign_B77", (pw, D.DOOR_B77[0] + 1.15), 0.0, "B77", "CHEM FACILITY ROOM"),
        ("Sign_B84", (D.DOOR_B84[0] + 0.95, n84 + h + 0.006), math.pi / 2, "B84", "SUBCRITICAL PILE"),
        ("Sign_B70A", (pw, -5.2), 0.0, "B70A", "PUR-1 REACTOR"),
        ("Sign_B76", (pw, D.DOOR_B76[0] + 1.15), 0.0, "B76", ""),
        ("Sign_B87", (pe, D.DOOR_B87[0] + 0.8), math.pi, "B87", ""),
    ]
    for nm, pos, facing, number, title in plates:
        _plate(root, mats, nm, pos, facing, number, title)
    _posting(root, mats, "Posting_B84", (D.DOOR_B84[0] - 0.95, n84 + h + 0.004), math.pi / 2)
    _posting(root, mats, "Posting_B70A", (pw - 0.002, -6.3), 0.0)

    # Recessed 2 x 4 ft troffers.
    fx = MeshBuilder()
    spots = [(6.1, y) for y in (-4.0, -8.5, -13.0, -17.5, -22.0)]
    spots += [(x, y) for x in (6.1, 9.2, 12.3) for y in (-1.5, 2.2) if not (x == 6.1 and y == -1.5)]
    spots += [(x, -3.5) for x in (9.2, 12.3)]
    spots += [(x, y) for x in (9.6, 12.8) for y in ((D.B86_Y[0] + D.B86_Y[1]) / 2, (D.B85_Y[0] + D.B85_Y[1]) / 2)]
    spots += [(x, (s84 + n84) / 2) for x in (7.5, 10.5, 13.4)]
    spots += [(2.6, y) for y in (-12.9, -15.9)]
    for x, y in spots:
        fx.box((x, y, H - 0.01), (0.6, 1.2, 0.02))
    fx.build("Basement_LightFixtures", mats["lamp"], root)
    return root


# --------------------------------------------------------------------------------------- B70B
def build_b70b(parent, mats):
    """Expanding lab space: mostly open floor, a first pair of benches on the north wall, an empty
    equipment rack, crates of new equipment on a pallet and taped outlines where benches will go."""
    root = empty("Room_B70B", (0, 0, 0), parent)
    y1 = D.ROOM_Y[1]
    for i, x in enumerate((7.3, 9.2)):
        props.work_table(root, mats, f"B70B_Bench_{i + 1}", (x, y1 - 0.45, 0), 1.6, 0.75)
        props.office_chair(root, mats, (x, y1 - 1.2, 0), f"B70B_Chair_{i + 1}", facing=math.pi / 2)
    _monitor(root, mats, "B70B_Monitor", 7.3, y1 - 0.3, 0.74, "south")
    # Whiteboard on the north wall over the benches.
    box("B70B_Whiteboard", (8.25, y1 - 0.015, 1.65), (2.4, 0.02, 1.1), mats["whiteboard"], root)
    MeshBuilder().box((8.25, y1 - 0.04, 1.08), (2.4, 0.06, 0.03)).build("B70B_Whiteboard_Tray", mats["aluminum"], root)
    # Empty 19 in rack against the east wall, waiting for equipment.
    rk = MeshBuilder()
    xr = D.EAST_WALL_X - T / 2 - 0.45
    for dy in (-0.28, 0.28):
        for dx in (-0.38, 0.38):
            rk.box((xr + dx, -1.0 + dy, 1.0), (0.04, 0.04, 2.0))
    rk.box((xr, -1.0, 1.99), (0.8, 0.6, 0.03)).box((xr, -1.0, 0.05), (0.8, 0.6, 0.1))
    rk.build("B70B_Rack", mats["rack"], root, bevel=0.004)
    # Pallet with crates and boxes.
    px, py = 13.4, 2.6
    pal = MeshBuilder()
    for dy in (-0.45, 0.0, 0.45):
        pal.box((px, py + dy, 0.05), (1.2, 0.1, 0.1))
    for dx in range(-5, 6):
        pal.box((px + dx * 0.11, py, 0.12), (0.09, 1.0, 0.02))
    pal.build("B70B_Pallet", mats["wood"], root)
    cr = MeshBuilder()
    cr.box((px - 0.25, py - 0.2, 0.13 + 0.35), (0.65, 0.55, 0.7))
    cr.box((px + 0.3, py + 0.25, 0.13 + 0.25), (0.5, 0.45, 0.5))
    cr.box((px + 0.3, py - 0.25, 0.13 + 0.2), (0.45, 0.4, 0.4))
    cr.box((px - 0.25, py - 0.2, 0.83 + 0.15), (0.45, 0.4, 0.3))
    cr.build("B70B_Crates", mats["cardboard"], root, bevel=0.006)
    box("B70B_Crate_Wood", (13.6, 0.0, 0.45), (1.1, 0.8, 0.9), mats["wood"], root)
    # Utility cart.
    ct = MeshBuilder()
    for z in (0.25, 0.85):
        ct.box((10.4, -3.6, z), (0.9, 0.5, 0.03))
    for dx in (-0.43, 0.43):
        for dy in (-0.23, 0.23):
            ct.box((10.4 + dx, -3.6 + dy, 0.5), (0.03, 0.03, 0.9))
            ct.cylinder((10.4 + dx, -3.6 + dy, 0.0), 0.04, 0.05, 12)
    ct.build("B70B_Cart", mats["steel"], root, bevel=0.004)
    # Floor tape marking the next benches.
    tape = MeshBuilder()
    for x0, y0, x1, y1_ in ((8.5, -1.6, 12.5, -0.6), (8.5, 0.6, 12.5, 1.6)):
        for a, b in (((x0, y0), (x1, y0 + 0.05)), ((x0, y1_ - 0.05), (x1, y1_)), ((x0, y0), (x0 + 0.05, y1_)), ((x1 - 0.05, y0), (x1, y1_))):
            tape.box_minmax((a[0], a[1], 0.0), (b[0], b[1], 0.002))
    tape.build("B70B_FloorTape", mats["floor_stripe"], root)
    return root


# ---------------------------------------------------------------------------------------- B86
def build_b86(parent, mats):
    """Undergraduate thermal-hydraulics lab: a natural-circulation water loop on a strut frame
    along the east wall (glass heated test section, cooler, expansion tank), its reservoir, pump
    and heater power supply, and student benches with the data-acquisition PCs."""
    root = empty("Room_B86", (0, 0, 0), parent)
    s, n = D.B86_Y
    xe = D.EAST_WALL_X - T / 2
    xf = xe - 0.55                             # loop plane
    ym = (s + n) / 2
    # Strut frame.
    fr = MeshBuilder()
    for y in (ym - 1.5, ym, ym + 1.5):
        for x in (xf - 0.3, xf + 0.3):
            fr.box((x, y, 1.3), (0.042, 0.042, 2.6))
        fr.box((xf, y, 2.58), (0.65, 0.042, 0.042))
    for z in (0.15, 2.58):
        for x in (xf - 0.3, xf + 0.3):
            fr.box((x, ym, z), (0.042, 3.04, 0.042))
    fr.build("TH_Frame", mats["steel_yellow"], root, bevel=0.003)
    # Loop: heated leg (glass test section) at the south, cold leg with the cooler at the north.
    yh, yc = ym - 1.0, ym + 1.0
    glass = MeshBuilder().cylinder((xf, yh, 0.75), 0.055, 1.4, 24)
    glass.build("TH_TestSection", mats["glass"], root)
    MeshBuilder().cylinder((xf, yh, 0.7), 0.012, 1.5, 12).build("TH_HeaterRod", mats["stainless"], root)
    pipe = MeshBuilder()
    pipe.cylinder((xf, yh, 0.5), 0.09, 0.25, 24).cylinder((xf, yh, 2.15), 0.09, 0.25, 24)     # plena
    props.pipe_with_fittings(pipe, pipe, [(xf, yh, 2.4), (xf, yh, 2.45), (xf, yc, 2.45), (xf, yc, 2.2)], 0.025)
    props.pipe_with_fittings(pipe, pipe, [(xf, yc, 1.1), (xf, yc, 0.3), (xf, yh, 0.3), (xf, yh, 0.5)], 0.025)
    pipe.cylinder((xf, ym + 0.4, 2.45), 0.012, 0.25, 10)                                       # to the expansion tank
    pipe.build("TH_Piping", mats["stainless"], root)
    box("TH_Cooler", (xf, yc, 1.65), (0.3, 0.3, 1.1), mats["aluminum_dark"], root)
    cylinder("TH_ExpansionTank", (xf, ym + 0.4, 2.62), 0.12, 0.3, mats["stainless"], root, 20)
    box("TH_Flowmeter", (xf - 0.1, ym, 0.3), (0.12, 0.25, 0.14), mats["module_grey"], root)
    # Thermocouple leads from the test section to the DAQ.
    tc = MeshBuilder().sweep([(xf - 0.06, yh, 1.6), (xf - 0.35, yh, 1.6), (xf - 0.35, ym - 0.2, 0.9)], 0.008, 6)
    tc.build("TH_Thermocouples", mats["cable_yellow"], root)
    # Reservoir and pump on the floor, heater power supply cabinet in the corner.
    cylinder("TH_Reservoir", (xf - 1.2, ym + 1.9, 0.0), 0.35, 1.05, mats["stainless"], root, 32)
    pm = MeshBuilder().cylinder((xf - 1.2, ym + 1.0, 0.0), 0.16, 0.08, 20).cylinder((xf - 1.2, ym + 1.0, 0.08), 0.11, 0.26, 20)
    pm.build("TH_Pump", mats["pipe_green"], root, bevel=0.004)
    box("TH_PowerSupply", (xe - 0.35, s + T / 2 + 0.35, 0.95), (0.6, 0.6, 1.9), mats["rack"], root)
    box("TH_PowerSupply_Panel", (xe - 0.66, s + T / 2 + 0.35, 1.45), (0.02, 0.5, 0.5), mats["rack_front"], root)
    # Student benches along the south wall with the DAQ PCs.
    for i, x in enumerate((9.0, 11.4)):
        y = s + 0.55
        props.work_table(root, mats, f"TH_Bench_{i + 1}", (x, y, 0), 2.2, 0.75)
        _monitor(root, mats, f"TH_Monitor_{i + 1}", x - 0.3, y + 0.05, 0.74, "north")
        props.pc_tower(root, mats, f"TH_PC_{i + 1}", (x + 0.7, y, 0.74))
        props.office_chair(root, mats, (x - 0.3, y + 0.8, 0), f"TH_Chair_{i + 1}", facing=-math.pi / 2)
    return root


# ---------------------------------------------------------------------------------------- B85
def build_b85(parent, mats):
    """Beta-voltaic facility: a glovebox for handling the beta sources, a light-tight probe
    station with source-measure units for the cells, a lead source safe and a desk."""
    root = empty("Room_B85", (0, 0, 0), parent)
    s, n = D.B85_Y
    xe = D.EAST_WALL_X - T / 2
    ym = (s + n) / 2
    # Glovebox along the east wall: stand, stainless box, glass front facing west, four ports.
    gx = xe - 0.5
    st = MeshBuilder()
    for dx in (-0.35, 0.35):
        for dy in (-0.85, 0.85):
            st.box((gx + dx, ym + dy, 0.42), (0.05, 0.05, 0.84))
    st.box((gx, ym, 0.84), (0.8, 1.8, 0.04))
    st.build("Glovebox_Stand", mats["steel"], root, bevel=0.003)
    box("Glovebox", (gx + 0.05, ym, 1.31), (0.7, 1.8, 0.9), mats["stainless"], root)
    box("Glovebox_Window", (gx - 0.302, ym, 1.33), (0.006, 1.6, 0.7), mats["glass"], root)
    gp = MeshBuilder()
    for dy in (-0.55, -0.2, 0.2, 0.55):
        gp.cylinder((gx - 0.32, ym + dy, 1.22), 0.08, 0.03, 20, axis="x")
    gp.build("Glovebox_Ports", mats["button_black"], root)
    cylinder("Glovebox_Antechamber", (gx + 0.05, ym + 0.9, 1.25), 0.18, 0.4, mats["stainless"], root, 24, axis="y")
    # Probe station on a bench: light-tight box, microscope column and the SMU rack beside it.
    props.work_table(root, mats, "Beta_Bench", (10.2, n - 0.55, 0), 2.6, 0.8)
    box("ProbeStation", (9.7, n - 0.55, 1.0), (0.6, 0.55, 0.5), mats["desk_black"], root)
    cylinder("ProbeStation_Microscope", (9.7, n - 0.55, 1.25), 0.04, 0.3, mats["aluminum"], root, 16)
    sm = MeshBuilder()
    for k in range(3):
        sm.box((10.8, n - 0.55, 0.82 + 0.1 * k), (0.42, 0.42, 0.09))
    sm.build("SourceMeasureUnits", mats["module_grey"], root, bevel=0.003)
    box("SourceMeasureUnits_Fronts", (10.8, n - 0.765, 0.92), (0.4, 0.004, 0.28), mats["panel"], root)
    _monitor(root, mats, "Beta_Monitor", 11.55, n - 0.5, 0.74, "south")
    props.office_chair(root, mats, (10.2, n - 1.35, 0), "Beta_Chair_1", facing=math.pi / 2)
    # Lead source safe in the south-west corner, with a posting over it.
    box("SourceSafe", (8.3, s + T / 2 + 0.4, 0.45), (0.6, 0.6, 0.9), mats["lead"], root)
    box("SourceSafe_Door", (8.3, s + T / 2 + 0.705, 0.5), (0.45, 0.01, 0.6), mats["steel"], root)
    _posting(root, mats, "Posting_B85", (8.3, s + T / 2 + 0.004), math.pi / 2)
    # Desk on the south wall.
    props.work_table(root, mats, "Beta_Desk", (11.2, s + 0.5, 0), 1.6, 0.7)
    _monitor(root, mats, "Beta_Monitor_2", 11.2, s + 0.4, 0.74, "north")
    props.office_chair(root, mats, (11.2, s + 1.2, 0), "Beta_Chair_2", facing=-math.pi / 2)
    return root


# ---------------------------------------------------------------------------------------- B77
def build_b77(parent, mats):
    """Chemistry facility room: two fume hoods on the west wall, an epoxy-top island bench with a
    reagent shelf and sink, a yellow flammables cabinet and a safety shower with eyewash."""
    root = empty("Room_B77", (0, 0, 0), parent)
    s, n = D.B77_Y
    xw = D.B77_X + T / 2
    for i, y in enumerate((n - 1.4, n - 3.0)):
        hx = xw + 0.42
        base = MeshBuilder().box((hx, y, 0.43), (0.84, 1.4, 0.86))
        base.build(f"FumeHood_{i + 1}_Base", mats["pvc"], root, bevel=0.004)
        hood = MeshBuilder()
        hood.box((hx + 0.1, y, 1.0 + 0.04), (0.64, 1.4, 0.08))       # work surface
        hood.box((hx, y - 0.68, 1.6), (0.84, 0.04, 1.2)).box((hx, y + 0.68, 1.6), (0.84, 0.04, 1.2))   # side panels
        hood.box((hx - 0.05, y, 2.25), (0.74, 1.4, 0.3))               # top and airfoil
        hood.box((hx - 0.4, y, 1.6), (0.04, 1.4, 1.2))                 # back baffle
        hood.build(f"FumeHood_{i + 1}", mats["pvc"], root, bevel=0.004)
        box(f"FumeHood_{i + 1}_Sash", (hx + 0.4, y, 1.55), (0.01, 1.3, 0.75), mats["glass"], root)
        cylinder(f"FumeHood_{i + 1}_Exhaust", (hx - 0.1, y, 2.4), 0.13, H - 2.4, mats["duct"], root, 20)
    # Island bench: black epoxy top on base cabinets, reagent shelf over it, sink at the south end.
    ix, iy0, iy1 = 2.95, s + 0.9, n - 0.9
    iy = (iy0 + iy1) / 2
    cab = MeshBuilder().box((ix, iy, 0.43), (0.7, iy1 - iy0, 0.86))
    cab.build("ChemBench_Cabinets", mats["table_top"], root, bevel=0.004)
    box("ChemBench", (ix, iy, 0.89), (0.76, iy1 - iy0 + 0.04, 0.03), mats["desk_black"], root)
    sh = MeshBuilder()
    for y in (iy0 + 0.05, iy, iy1 - 0.05):
        sh.box((ix, y, 1.35), (0.03, 0.03, 0.9))
    for z in (1.3, 1.75):
        sh.box((ix, iy, z), (0.3, iy1 - iy0, 0.02))
    sh.build("ChemBench_Shelf", mats["steel"], root, bevel=0.003)
    box("ChemBench_Sink", (ix, iy0 + 0.35, 0.89), (0.45, 0.4, 0.035), mats["stainless"], root)
    MeshBuilder().sweep([(ix + 0.15, iy0 + 0.35, 0.9), (ix + 0.15, iy0 + 0.35, 1.2), (ix, iy0 + 0.35, 1.2)], 0.012, 8).build(
        "ChemBench_Faucet", mats["stainless"], root)
    bt = MeshBuilder()
    for k in range(6):
        bt.cylinder((ix - 0.06 + 0.12 * (k % 2), iy - 0.8 + 0.3 * k, 1.31), 0.035, 0.16, 12)
    bt.build("ChemBench_Bottles", mats["glass"], root)
    # Flammables cabinet on the north wall, safety shower and eyewash by the door.
    box("FlammablesCabinet", (1.5, n - T / 2 - 0.25, 0.85), (1.1, 0.46, 1.7), mats["steel_yellow"], root)
    shw = MeshBuilder()
    sx, sy = D.CORRIDOR_X[0] - T / 2 - 0.25, s + 0.5
    shw.sweep([(sx, sy, 0.0), (sx, sy, 2.3), (sx - 0.45, sy, 2.3)], 0.022, 10)
    shw.build("SafetyShower", mats["pipe_green"], root)
    shw2 = MeshBuilder().cylinder((sx - 0.45, sy, 2.18), 0.13, 0.1, 20).cylinder((sx - 0.1, sy, 1.0), 0.09, 0.05, 16)
    shw2.build("SafetyShower_Heads", mats["sign_yellow"], root)
    return root


# ---------------------------------------------------------------------------------------- B84
def build_b84(parent, mats):
    """Subcritical pile: a graphite stack on a steel base with fuel channels in its face and the
    testbed let into its top, the Pu-Be source cask, a BF3 counter on a stand and the counting
    bench along the south wall."""
    root = empty("Room_B84", (0, 0, 0), parent)
    s, n = D.B84_Y
    px, py = D.PILE_POS
    w, d, hh = D.PILE_SIZE
    base_h = 0.10
    box("SubcriticalPile_Base", (px, py, base_h / 2), (w + 0.1, d + 0.1, base_h), mats["steel"], root)
    # The graphite: a stack of bricks, the courses shown by thin grooves.
    pile = MeshBuilder()
    z0 = base_h
    course = 0.1016                            # 4 in courses (ASSUMED brick height)
    k = 0
    while z0 + course <= base_h + hh + 1e-6:
        inset = 0.004 if k % 2 else 0.0
        pile.box((px, py, z0 + course / 2 - 0.002), (w - inset, d - inset, course - 0.004))
        z0 += course
        k += 1
    pile.build("SubcriticalPile", mats["graphite"], root)
    top = base_h + hh
    # Fuel channels: a square array of aluminium plugs in the west face.
    ch = MeshBuilder()
    for i in range(7):
        for j in range(7):
            ch.cylinder((px - w / 2 - 0.012, py - 0.6 + 0.2 * i, base_h + 0.35 + 0.22 * j), 0.025, 0.014, 12, axis="x")
    ch.build("SubcriticalPile_Channels", mats["aluminum"], root)
    # Source port low in the north face, testbed at the top centre.
    cylinder("SubcriticalPile_SourcePort", (px, py + d / 2, base_h + 0.25), 0.06, 0.02, mats["sign_yellow"], root, 20, axis="y")
    tb = D.PILE_TESTBED
    box("Pile_Testbed", (px, py, top + 0.02), (tb, tb, 0.04), mats["aluminum"], root)
    hd = MeshBuilder()
    for dy in (-tb / 3, tb / 3):
        hd.box((px, py + dy, top + 0.06), (0.14, 0.02, 0.04))
    hd.build("Pile_Testbed_Handles", mats["stainless"], root)
    # Pu-Be source cask: a yellow drum with a posting.
    cylinder("PuBe_SourceCask", (8.6, s + T / 2 + 0.45, 0.0), 0.3, 0.85, mats["sign_yellow"], root, 28)
    cylinder("PuBe_SourceCask_Lid", (8.6, s + T / 2 + 0.45, 0.85), 0.31, 0.04, mats["steel"], root, 28)
    MeshBuilder().cylinder((8.6, s + T / 2 + 0.45 - 0.302, 0.55), 0.09, 0.004, 20, axis="y").build(
        "PuBe_SourceCask_Trefoil", mats["sign_magenta"], root)
    # BF3 counter on a stand beside the pile's west face.
    sx, sy = px - w / 2 - 0.6, py
    stand = MeshBuilder().cylinder((sx, sy, 0.0), 0.2, 0.03, 20).cylinder((sx, sy, 0.03), 0.015, 1.1, 10)
    stand.build("BF3_Stand", mats["steel"], root)
    cylinder("BF3_Detector", (sx, sy - 0.25, 1.13), 0.025, 0.5, mats["aluminum"], root, 16, axis="y")
    cb = MeshBuilder().sweep([(sx, sy + 0.25, 1.13), (sx, sy + 0.4, 1.0), (sx - 0.4, s + 1.3, 0.9), (sx - 1.2, s + 0.8, 0.9)], 0.006, 6)
    cb.build("BF3_Cable", mats["hv_cable"], root)
    # Counting bench along the south wall: NIM bin, scaler, scope, PC.
    props.work_table(root, mats, "Pile_Bench", (6.6, s + 0.5, 0), 2.6, 0.75)
    box("NIM_Bin", (6.1, s + 0.45, 0.94), (0.48, 0.4, 0.4), mats["rack"], root)
    nm = MeshBuilder()
    for k in range(8):
        nm.box((6.1 - 0.2 + 0.057 * k, s + 0.45 - 0.205, 0.95), (0.05, 0.01, 0.34))
    nm.build("NIM_Modules", mats["rack_front"], root)
    _monitor(root, mats, "Pile_Monitor", 7.2, s + 0.4, 0.74, "north")
    props.office_chair(root, mats, (6.6, s + 1.2, 0), "Pile_Chair", facing=-math.pi / 2)
    _posting(root, mats, "Posting_B84_Inside", (D.EAST_WALL_X - T / 2 - 0.004, py), math.pi)
    return root


def build_basement(parent, mats):
    build_shell(parent, mats)
    build_b70b(parent, mats)
    build_b86(parent, mats)
    build_b85(parent, mats)
    build_b77(parent, mats)
    build_b84(parent, mats)
