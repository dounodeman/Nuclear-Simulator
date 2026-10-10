"""PUR-1 reactor hall (room B70A, Duncan Annex): pool, biological shield, bridge
with the five drives, core, in-pool storage, process loop, HVAC, doors, lights,
and the operator console / video wall in the same room.

Appearance follows the reference photos in the project Drive folder ("PUR-1
Reference Images"): a round black-clad pool wall carrying the PUR-1 graphic,
a grey top lip with a yellow stripe, the bridge with its vertical drive tubes
and looped black cables, cream walls with exposed piping and conduit, a light
grey floor with yellow safety striping, a stair up to a platform on the north
wall, the desk console with blue chairs, the black digital I&C cabinets and
the diagnostics bench.

Frame: pool centre at x = y = 0, reactor-room floor at z = 0, +X east, +Y north.
"""
from __future__ import annotations

import math

from . import dims as D
from .common import MeshBuilder, box, curved_text, text_width, cylinder, empty, add_light, FT, IN
from . import props
from .control_room import build_control_room
from .core import build_core, control_xy, lattice_xy


def build_room(parent, mats):
    """Room B70A after the layout map: walls with the main door (east wall, SE corner), the
    storage-room door (west wall), the opening to the adjacent lab and the platform-level door
    (north wall); the stair along the north wall rising east to the NE platform; the white
    soffit along the north side; services on the walls; HVAC, light fixtures and the monorail."""
    x0, x1 = D.ROOM_X
    y0, y1 = D.ROOM_Y
    h, t = D.ROOM_H, D.WALL_T
    root = empty("Room_B70A", (0, 0, 0), parent)
    # Floor slab in four strips around the below-floor shield block (which fills the middle at z <= 0).
    s = D.SHIELD_BELOW_HALF
    fl = MeshBuilder()
    fl.box_minmax((x0, y0, -0.15), (-s, y1, 0.0))
    fl.box_minmax((s, y0, -0.15), (x1, y1, 0.0))
    fl.box_minmax((-s, y0, -0.15), (s, -s, 0.0))
    fl.box_minmax((-s, s, -0.15), (s, y1, 0.0))
    lx0, lx1, ly0, ly1 = D.LAB
    fl.box_minmax((lx0, y1, -0.15), (lx1, ly1, 0.0))                 # lab floor
    fl.build("Floor", mats["floor"], root)
    # Yellow safety stripe painted on the floor around the pool.
    stripe = MeshBuilder()
    rs = D.FLOOR_STRIPE_RADIUS
    n = 96
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        stripe._add([(rs * c0, rs * s0, 0.002), (rs * c1, rs * s1, 0.002),
                     ((rs + 0.1) * c1, (rs + 0.1) * s1, 0.002), ((rs + 0.1) * c0, (rs + 0.1) * s0, 0.002)],
                    [(0, 1, 2, 3)])
    stripe.build("FloorStriping", mats["floor_stripe"], root)

    # Walls. The north wall has the 1.6 m opening to the lab (with a lintel over it).
    ox0, ox1 = D.LAB_OPENING_X
    walls = MeshBuilder()
    walls.box_minmax((x0 - t, y0 - t, 0), (x0, y1 + t, h))      # west
    walls.box_minmax((x1, y0 - t, 0), (x1 + t, y1 + t, h))      # east
    walls.box_minmax((x0, y0 - t, 0), (x1, y0, h))              # south
    walls.box_minmax((x0, y1, 0), (ox0, y1 + t, h))             # north, west of the opening
    walls.box_minmax((ox1, y1, 0), (x1, y1 + t, h))             # north, east of the opening
    walls.box_minmax((ox0, y1, 2.4), (ox1, y1 + t, h))          # lintel
    # Adjacent lab: walls and a low ceiling.
    lh = D.LAB_H
    walls.box_minmax((lx0 - t, y1 + t, 0), (lx0, ly1 + t, lh + 0.2))
    walls.box_minmax((lx1, y1 + t, 0), (lx1 + t, ly1 + t, lh + 0.2))
    walls.box_minmax((lx0, ly1, 0), (lx1, ly1 + t, lh + 0.2))
    walls.build("Walls", mats["wall_cream"], root)
    ceil = MeshBuilder().box_minmax((x0 - t, y0 - t, h), (x1 + t, y1 + t, h + 0.3))
    ceil.box_minmax((lx0 - t, y1 + t, lh), (lx1 + t, ly1 + t, lh + 0.2))
    ceil.build("Ceiling", mats["ceiling"], root)
    # White soffit (bulkhead) along the north side over the console area.
    sx0, sx1, sy0, sz = D.SOFFIT
    MeshBuilder().box_minmax((sx0, sy0, sz), (sx1, y1, h)).build("Soffit_North", mats["pvc"], root)
    # Steel frame round the lab opening.
    jf = MeshBuilder()
    for x in (ox0, ox1):
        jf.box((x, y1 - 0.02, 1.2), (0.08, 0.06, 2.4))
    jf.box(((ox0 + ox1) / 2, y1 - 0.02, 2.4), (ox1 - ox0 + 0.08, 0.06, 0.08))
    jf.build("LabOpening_Frame", mats["door_frame"], root, bevel=0.004)

    # Doors: main personnel door on the east wall (SE corner), storage-room door on the west wall,
    # and the platform-level door in the NE corner at the top of the stair.
    top = D.STAIR_STEPS * D.STAIR_RISE
    doors = {
        "Door_Main_East": ((x1, D.MAIN_DOOR_Y, 0), math.pi / 2),
        "Door_StorageRoom_West": ((x0, D.STORAGE_DOOR_Y, 0), -math.pi / 2),
        "Door_Platform_North": ((3.75, y1, top), math.pi),
    }
    for nm, (pos, facing) in doors.items():
        props.door(root, mats, nm, pos, facing, D.DOOR_W if "Platform" not in nm else 0.75, D.DOOR_H, t)
    # Illuminated EXIT signs over the main door and the platform door.
    ex = MeshBuilder().box((x1 - 0.06, D.MAIN_DOOR_Y, 2.45), (0.10, 0.34, 0.16))
    ex.box((3.75, y1 - 0.06, top + 2.45), (0.34, 0.10, 0.16))
    ex.build("ExitSigns", mats["led_green"], root)
    # The hallway scram button is outside the main door in the plant; here it sits on the wall
    # just inside the door so it can be reached.
    hb = cylinder("ui_Scram_Hallway", (x1 - 0.04, D.MAIN_DOOR_Y + 0.85, 1.3), 0.035, 0.04, mats["button_red"], root, 16, axis="x")
    hb["role"] = "manual_scram_hallway"
    MeshBuilder().box((x1 - 0.015, D.MAIN_DOOR_Y + 0.85, 1.3), (0.03, 0.14, 0.14)).build("Scram_Hallway_Box", mats["sign_yellow"], root)

    # Exposed services (photos): conduit along the west and north walls, panel boards and an
    # emergency light on the west wall, grey enclosures and a fire extinguisher on the north wall,
    # postings and electrical boxes on the south wall.
    cond = MeshBuilder()
    for z in (2.6, 3.0):
        cond.sweep([(x0 + 0.06, y0 + 0.5, z), (x0 + 0.06, y1 - 0.5, z)], 0.025, 8)       # west wall runs
        cond.sweep([(x0 + 0.5, y1 - 0.06, z), (ox0 - 0.3, y1 - 0.06, z)], 0.025, 8)       # north wall, under the soffit
    for x in (-5.6, -4.4, -2.4):
        cond.sweep([(x, y1 - 0.06, 1.2), (x, y1 - 0.06, 2.6)], 0.02, 8)                # drops to boxes
    cond.sweep([(x0 + 0.06, -2.0, 0.4), (x0 + 0.06, -2.0, 2.6)], 0.02, 8)
    cond.sweep([(x1 - 0.06, y0 + 0.4, 3.2), (x1 - 0.06, -3.2, 3.2), (x1 - 0.06, -3.2, 4.0)], 0.025, 8)  # east wall
    cond.build("Conduit", mats["conduit"], root)
    brk = MeshBuilder()
    for z in (2.6, 3.0):
        for y in (y0 + 1.5, -1.0, 1.5):
            brk.box((x0 + 0.03, y, z), (0.06, 0.04, 0.06))
        for x in (-6.0, -4.0, -2.0):
            brk.box((x, y1 - 0.03, z), (0.04, 0.06, 0.06))
    brk.box((x0 + 0.08, -2.0, 2.65), (0.12, 0.14, 0.14))                # junction box
    for x in (-5.6, -4.4, -2.4):
        brk.box((x, y1 - 0.06, 1.1), (0.16, 0.10, 0.2))                 # boxes on the north wall
    brk.build("PipeBrackets", mats["steel"], root)
    pan = MeshBuilder().box((x0 + 0.08, 2.35, 1.6), (0.16, 0.6, 0.9)).box((x0 + 0.08, 3.0, 1.5), (0.14, 0.4, 0.6))
    pan.box((x0 + 0.06, 2.65, 2.35), (0.12, 0.35, 0.12))                # emergency light
    pan.build("PanelBoards_West", mats["door_frame"], root)
    enc = MeshBuilder().box((-1.72, y1 - 0.12, 1.55), (0.6, 0.24, 0.8)).box((-1.55, y1 - 0.1, 0.75), (0.3, 0.2, 0.4))
    enc.box((0.15 - 0.75, y0 + 0.06, 1.55), (0.5, 0.12, 0.6)).box((0.15, y0 + 0.05, 1.45), (0.4, 0.10, 0.5))
    enc.box((-0.25, y0 + 0.02, 1.45), (0.5, 0.04, 0.7))
    enc.build("Electrical_Enclosures", mats["module_grey"], root, bevel=0.004)
    ext = MeshBuilder().cylinder((-1.3, y1 - 0.12, 0.6), 0.08, 0.55, 18)
    ext.cylinder((-1.3, y1 - 0.12, 1.15), 0.025, 0.06, 10)
    ext.build("FireExtinguisher", mats["button_red"], root)

    # HVAC: the HEPA-filtered air handler high on the west side with its ductwork, and an
    # exhaust trunk along the north side to a fan bank.
    duct = MeshBuilder()
    duct.box((-6.05, -1.9, h - 1.0), (1.7, 1.6, 1.0))                  # HEPA air handler
    duct.box((-6.05, -1.9, h - 0.25), (0.6, 0.6, 0.5))                 # riser to the roof
    duct.box((-3.0, -1.9, h - 0.75), (4.4, 0.6, 0.45))                 # supply trunk east from the handler
    duct.box((-0.5, y1 - 0.5, h - 0.6), (6.0, 0.5, 0.5))               # exhaust trunk, north side
    duct.box((2.9, y1 - 0.5, h - 0.6), (1.1, 1.1, 1.1))                # exhaust fan / HEPA bank
    duct.cylinder((2.9, y1 - 0.5, h - 0.05), 0.3, 0.35, 24)            # through-roof stack stub
    duct.build("HVAC_Ducts", mats["duct"], root)

    # Fluorescent tube fixtures hung from the ceiling (photos), plus render lights.
    fix = MeshBuilder()
    for i, x in enumerate((-5.5, -2.5, 0.5, 3.2)):
        for y in (-3.4, 0.0, 2.6):
            fix.box((x, y, h - 0.45), (1.25, 0.30, 0.08))
            if y != 0.0 or x in (-2.5, 3.2):
                add_light(f"Light_{i}_{y:+.0f}", "POINT", (x, y, h - 0.7), 1200, (1.0, 0.97, 0.9), soft=0.6)
    for x in (-2.6, -0.4):                                              # lab: surface fixtures
        fix.box((x, (ly0 + ly1) / 2 + 0.3, lh - 0.05), (1.25, 0.30, 0.08))
    fix.build("LightFixtures", mats["lamp"], root)

    # Monorail hoist over the pool, east-west, for fuel and experiment handling.
    rail = MeshBuilder().box((-0.5, 0.15, h - 0.5), (8.2, 0.18, 0.30))
    rail.box((0.8, 0.15, h - 0.95), (0.5, 0.5, 0.6))                   # hoist trolley
    rail.cylinder((0.8, 0.15, D.SHIELD_TOP_Z + 1.6), 0.01, h - 1.25 - D.SHIELD_TOP_Z - 1.6, 8)
    rail.build("MonorailHoist", mats["steel_yellow"], root)

    # Stair along the north wall, rising east to the platform in the NE corner.
    sx, sy, _ = D.STAIR_ORIGIN
    rise, run, nsteps = D.STAIR_RISE, D.STAIR_RUN, D.STAIR_STEPS
    pl, pd = D.PLATFORM_SIZE
    wall_y = y1
    px0, px1 = sx + nsteps * run, x1                           # platform x extent (to the east wall)
    py0 = wall_y - pd                                          # platform room-side edge
    st = MeshBuilder()
    for i in range(nsteps):
        st.box_minmax((sx + i * run, sy, i * rise), (sx + (i + 1) * run + 0.02, wall_y, (i + 1) * rise))
        st.box_minmax((sx + i * run, sy - 0.03, max(0.0, i * rise - 0.22)), (sx + (i + 1) * run + 0.02, sy, (i + 1) * rise))  # stringer
    st.box_minmax((px0, py0, top - 0.08), (px1, wall_y, top))                                   # platform deck
    st.box_minmax((px0, py0, top - 0.30), (px1, py0 + 0.05, top - 0.08))                        # platform edge beam
    st.box((px0 + 0.1, py0 + 0.1, top / 2), (0.1, 0.1, top))                                     # post
    st.build("Stair_North", mats["steel"], root)
    hr = MeshBuilder()
    rail_pts = [(sx + i * run + run / 2, sy - 0.03, i * rise + 1.0) for i in range(nsteps)]
    rail_pts += [(px0, sy - 0.03, top + 1.0), (px0, py0, top + 1.0), (px1 - 0.05, py0, top + 1.0)]
    hr.sweep(rail_pts, 0.02, 8)
    for i in range(0, nsteps, 2):
        hr.sweep([(sx + i * run + run / 2, sy - 0.03, i * rise), (sx + i * run + run / 2, sy - 0.03, i * rise + 1.0)], 0.012, 6)
    for x, y in ((px0, sy - 0.03), (px0, py0), ((px0 + px1) / 2, py0), (px1 - 0.05, py0)):
        hr.sweep([(x, y, top), (x, y, top + 1.0)], 0.012, 6)
    hr.sweep([(px0, py0, top + 0.5), (px1 - 0.05, py0, top + 0.5)], 0.012, 6)     # mid rail
    hr.build("Stair_North_Handrail", mats["steel_yellow"], root)
    return root


def build_lab(parent, mats):
    """The adjacent lab through the north opening (layout map): the real-time diagnostics bench
    along its north wall, a whiteboard on wheels, and two lab tables with green chairs."""
    root = empty("Lab_Adjacent", (0, 0, 0), parent)
    lx0, lx1, ly0, ly1 = D.LAB
    for i, x in enumerate((-2.6, -0.4)):
        props.work_table(root, mats, f"LabTable_{i + 1}", (x, 5.9, 0), 1.4, 0.7)
        for k, dx in enumerate((-0.35, 0.35)):                       # chairs pushed in, clear of the doorway
            props.office_chair(root, mats, (x + dx, 5.3, 0), f"LabChair_{i + 1}_{k + 1}",
                               facing=math.pi / 2, seat_mat="chair_green")
    # Whiteboard on wheels east of the bench.
    wb = empty("Whiteboard_Stand", (0.72, 7.25, 0), root)
    box("Whiteboard", (0, 0, 1.35), (1.05, 0.02, 0.85), mats["whiteboard"], wb)
    fr = MeshBuilder()
    for x in (-0.55, 0.55):
        fr.box((x, 0, 0.9), (0.04, 0.04, 1.75))
        fr.box((x, 0, 0.06), (0.06, 0.5, 0.04))
        for y in (-0.22, 0.22):
            fr.cylinder((x, y, 0.0), 0.025, 0.04, 10)
    fr.box((0, 0.02, 0.9), (1.05, 0.06, 0.02))                          # pen tray
    fr.build("Whiteboard_Frame", mats["aluminum"], wb, bevel=0.004)
    return root


def build_pool(parent, mats):
    root = empty("Pool", (0, 0, 0), parent)
    r = D.POOL_RADIUS
    # Below-floor concrete block with the tank cavity.
    s = D.SHIELD_BELOW_HALF
    cav = r + D.SAND_GAP + D.TANK_WALL
    blk = MeshBuilder()
    blk.box_minmax((-s, -s, D.TANK_BOTTOM_Z - 0.6), (s, s, D.TANK_BOTTOM_Z - 0.3))     # base slab
    # Four wall boxes around a square cavity, then a ring to round it off.
    blk.box_minmax((-s, -s, D.TANK_BOTTOM_Z - 0.3), (-cav, s, 0.0))
    blk.box_minmax((cav, -s, D.TANK_BOTTOM_Z - 0.3), (s, s, 0.0))
    blk.box_minmax((-cav, -s, D.TANK_BOTTOM_Z - 0.3), (cav, -cav, 0.0))
    blk.box_minmax((-cav, cav, D.TANK_BOTTOM_Z - 0.3), (cav, s, 0.0))
    blk.tube((0, 0, D.TANK_BOTTOM_Z - 0.3), cav * 1.42, cav, -D.TANK_BOTTOM_Z + 0.3, 48)
    blk.build("ShieldBlock_BelowFloor", mats["concrete"], root)
    # Above-floor biological shield, clad in black (photos), with a grey top lip around the water
    # opening and a yellow stripe on the lip's outer edge.
    R = D.SHIELD_OUTER_RADIUS
    top = D.SHIELD_TOP_Z
    MeshBuilder().tube((0, 0, 0), R, r + 0.05, top - 0.03, 96).build("ShieldWall_AboveFloor", mats["pool_black"], root)
    lip = MeshBuilder().tube((0, 0, top - 0.03), R + 0.01, r + 0.012, 0.03, 96)
    lip.build("PoolTopLip", mats["pool_lip"], root)
    stripe = MeshBuilder().tube((0, 0, top), R + 0.012, R - D.POOL_STRIPE_WIDTH, 0.004, 96)
    stripe.tube((0, 0, 0.0), R + 0.012, R, 0.12, 96)          # yellow kick band at the floor
    stripe.build("PoolTopStripe", mats["floor_stripe"], root)
    # The PUR-1 graphic on the black wall.
    a = D.GRAPHIC_ANGLE
    # Bold white "PUR-1", the gold tagline, and "150 GIANT LEAPS" (Purdue's 150th) under it,
    # left-aligned with the tagline, as in the photos.
    curved_text("Graphic_PUR1", "PUR-1", mats["lettering_white"], R, a, 0.60, 0.50, parent=root)
    tag = "THE NATION'S FIRST ALL-DIGITAL I&C"
    curved_text("Graphic_Tagline", tag, mats["lettering_gold"], R, a, 0.31, 0.085, parent=root)
    start = a - text_width(tag, 0.085) / 2 / R
    for part, mat in (("150 ", "lettering_white"), ("GIANT", "lettering_gold"), ("LEAPS", "lettering_white")):
        curved_text(f"Graphic_150_{part.strip()}", part, mats[mat], R, start, 0.18, 0.095, parent=root, align="LEFT")
        start += (text_width(part, 0.095) + (0.04 if part == "150 " else 0.0)) / R
    # Steel tank, sand annulus, stainless liner, tank floor.
    MeshBuilder().tube((0, 0, D.TANK_BOTTOM_Z - 0.3), cav, cav - D.TANK_WALL, D.POOL_DEPTH + 0.3, 48).build("OuterSteelTank", mats["steel"], root)
    MeshBuilder().tube((0, 0, D.TANK_BOTTOM_Z - 0.3), cav - D.TANK_WALL, r + 0.012, D.POOL_DEPTH + 0.3, 48).build("SandAnnulus", mats["sand"], root)
    MeshBuilder().tube((0, 0, D.TANK_BOTTOM_Z), r + 0.012, r, D.POOL_DEPTH + (top - D.TANK_TOP_Z), 64).build("StainlessLiner", mats["stainless"], root)
    MeshBuilder().cylinder((0, 0, D.TANK_BOTTOM_Z - 0.012), r + 0.012, 0.012, 64).build("TankFloor", mats["stainless"], root)
    # Water column.
    MeshBuilder().cylinder((0, 0, D.TANK_BOTTOM_Z + 0.001), r - 0.002, D.WATER_SURFACE_Z - D.TANK_BOTTOM_Z - 0.001, 64).build("fx_PoolWater", mats["water"], root)

    # In-pool fuel storage racks: two racks of 2 x 9, BORAL sheet between rows, on the north side.
    for k, x in enumerate((-0.5, 0.5)):
        rk = MeshBuilder()
        y = 0.75
        rk.box((x, y, D.TANK_BOTTOM_Z + 0.03), (0.78, 0.22, 0.06))
        for i in range(9):
            for j in (-1, 1):
                rk.tube((x - 0.32 + i * 0.08, y + j * 0.05, D.TANK_BOTTOM_Z + 0.06), 0.036, 0.033, 0.75, 12)
        rk.box((x, y, D.TANK_BOTTOM_Z + 0.06 + 0.375), (0.78, 0.0064, 0.75))   # 1/4 in BORAL
        rk.build(f"FuelStorageRack_{k + 1}", mats["aluminum"], root)
    return root


def build_bridge_and_drives(parent, mats, core_objs):
    """Reactor top (photos, layout map): a bridge running NW-SE across the pool, of round
    stainless girders and square-tube cross members resting on the pool wall, with a galvanised
    bar-grating deck that leaves an opening over the core; an aluminium cage over the core
    carrying the tall stainless drive tubes, each with its motor and encoder head and a junction
    box; black cable bundles looping from the heads down to the junction boxes and along the
    bridge to its NW end, where a black cable gantry carries them to a post beside the console
    and down to the I&C cabinets; guide tubes and the three fixed ion-chamber tubes going down
    into the water; and the underwater camera looking at the core."""
    root = empty("Bridge", (0, 0, 0), parent)
    deck = empty("Bridge_Deck", (0, 0, 0), root)
    ang = D.BRIDGE_ANGLE
    deck.rotation_euler = (0, 0, ang)            # bridge-local +X points NW, along the bridge
    ca, sa = math.cos(ang), math.sin(ang)

    def w(x, y):
        """Bridge-local (x along the bridge, y across it) to hall coordinates."""
        return (x * ca - y * sa, x * sa + y * ca)

    R = D.SHIELD_OUTER_RADIUS
    L = 2 * R + 0.3
    bz = D.SHIELD_TOP_Z + 0.08
    W = D.BRIDGE_WIDTH
    hole = 0.36                                   # half-length of the deck opening over the core

    # Girders, cross members and feet.
    gird = MeshBuilder()
    for y in (-W / 2, W / 2):
        gird.sweep([(-L / 2, y, bz), (L / 2, y, bz)], 0.06, 20)                         # lower girder
        gird.sweep([(-L / 2 + 0.1, y, bz + 0.22), (L / 2 - 0.1, y, bz + 0.22)], 0.04, 16)   # upper rail
        for x in (-L / 2 + 0.25, -1.3, -hole - 0.05, hole + 0.05, 1.3, L / 2 - 0.25):
            gird.sweep([(x, y, bz), (x, y, bz + 0.22)], 0.018, 10)                       # rail posts
    gird.build("Bridge_Structure", mats["stainless"], deck)
    frame = MeshBuilder()
    for x in (-L / 2 + 0.15, -1.3, -hole - 0.05, hole + 0.05, 1.3, L / 2 - 0.15):
        frame.box((x, 0, bz - 0.01), (0.08, W, 0.08))                                    # cross members
    for x in (-L / 2 + 0.15, L / 2 - 0.15):                                              # feet on the pool wall
        for y in (-W / 2, W / 2):
            frame.box((x, y, (D.SHIELD_TOP_Z + bz - 0.06) / 2 + 0.0), (0.16, 0.16, bz - 0.06 - D.SHIELD_TOP_Z + 0.02))
            frame.box((x, y, D.SHIELD_TOP_Z + 0.005), (0.22, 0.22, 0.01))                # bearing plate
    frame.build("Bridge_Frame", mats["aluminum"], deck, bevel=0.004)

    # Bar-grating deck on each side of the core opening, with toe boards along the edges.
    grate = MeshBuilder()
    dz = bz + 0.045
    for xa, xb in ((-L / 2 + 0.12, -hole), (hole, L / 2 - 0.12)):
        n_bear = int(W / 0.045)
        for k in range(n_bear + 1):                                                      # bearing bars
            y = -W / 2 + 0.03 + k * (W - 0.06) / n_bear
            grate.box(((xa + xb) / 2, y, dz), (xb - xa, 0.005, 0.03))
        n_cross = int((xb - xa) / 0.10)
        for k in range(n_cross + 1):                                                     # cross rods
            x = xa + k * (xb - xa) / n_cross
            grate.box((x, 0, dz + 0.013), (0.006, W - 0.06, 0.006))
        for y in (-W / 2 + 0.03, W / 2 - 0.03):
            grate.box(((xa + xb) / 2, y, dz + 0.04), (xb - xa, 0.006, 0.11))             # toe boards
        for x in (xa, xb):
            grate.box((x, 0, dz), (0.008, W - 0.06, 0.03))                               # end bands
    grate.build("Bridge_Grating", mats["grating"], deck)

    # Drive cage over the core: four aluminium square-tube posts and ring frames, on the girders.
    cage_x, cage_y, cage_h = 0.32, 0.32, 2.3
    cage = MeshBuilder()
    for x in (-cage_x, cage_x):
        for y in (-cage_y, cage_y):
            cage.box((x, y, bz + cage_h / 2), (0.05, 0.05, cage_h))
    for z in (bz + 0.10, bz + 0.9, bz + 1.7, bz + cage_h):
        for y in (-cage_y, cage_y):
            cage.box((0, y, z), (2 * cage_x + 0.05, 0.04, 0.04))
        for x in (-cage_x, cage_x):
            cage.box((x, 0, z), (0.04, 2 * cage_y + 0.05, 0.04))
    for x in (-cage_x, cage_x):                                                          # cage feet onto the girders
        cage.box((x, 0, bz + 0.03), (0.08, W, 0.04))
    cage.build("Drive_Cage", mats["aluminum"], deck, bevel=0.004)

    # Drive mechanisms straight over their assemblies in the core (hall coordinates).
    pos = {k: control_xy(k) for k in D.CONTROL_POSITIONS}
    sx, sy = lattice_xy(6, 1)                                   # source drive: SW of the core
    pos["NS"] = (sx - D.ELEMENT_W / 2 - 0.05, sy - D.ELEMENT_W / 2 - 0.05)
    fx, fy = lattice_xy(2, 5)                                   # fission chamber: by the NE element
    pos["FC"] = (fx + D.ELEMENT_W / 2 + 0.03, fy)
    heights = {"SS1": 2.75, "SS2": 2.75, "RR": 2.6, "NS": 2.2, "FC": 2.0}
    core_top = D.GRID_PLATE_Z + D.NOZZLE_LENGTH + D.PLATE_LENGTH + D.HANDLE_LENGTH + 0.12
    cables, yellow, boxes, heads = MeshBuilder(), MeshBuilder(), MeshBuilder(), MeshBuilder()
    guides = MeshBuilder()
    # Junction boxes on the cage sides (bridge-local), each fed from the nearest drive.
    jb_local = [(cage_x + 0.09, -0.15), (cage_x + 0.09, 0.15), (-cage_x - 0.09, -0.15), (-cage_x - 0.09, 0.15),
                (0.0, cage_y + 0.08)]
    spots = [w(*p) for p in jb_local]
    jb_spots = {}
    for name in D.DRIVE_NAMES:
        x, y = pos[name]
        k = min((i for i in range(len(spots)) if i not in jb_spots.values()),
                key=lambda i: (spots[i][0] - x) ** 2 + (spots[i][1] - y) ** 2)
        jb_spots[name] = k
    for i, name in enumerate(D.DRIVE_NAMES):
        x, y = pos[name]
        th = heights[name]
        mb = MeshBuilder()
        mb.cylinder((x, y, bz - 0.25), 0.045, th + 0.25, 20)                       # drive tube
        for z in (bz + 0.10, bz + 0.9, bz + 1.7):                                   # clamps to the cage
            mb.cylinder((x, y, z - 0.02), 0.055, 0.04, 20)
        for z in [bz + 0.5 + 0.7 * k for k in range(int(th / 0.7))]:                # flanged joints
            mb.cylinder((x, y, z), 0.06, 0.02, 20)
        mb.flange((x, y, bz + th - 0.01), "z", 0.04, 0.025)
        ob = mb.build(f"Drive_{name}", mats["stainless"], root)
        ob["drive"] = name
        zt = bz + th
        heads.cylinder((x, y, zt), 0.072, 0.22, 24)                                 # motor
        heads.cylinder((x, y, zt + 0.22), 0.055, 0.09, 20)                          # encoder
        heads.box((x + 0.075, y, zt + 0.11), (0.05, 0.07, 0.09))                     # connector housing
        # Guide tube from the bridge down through the water to just above the core.
        if name in ("SS1", "SS2", "RR"):
            guides.cylinder((x, y, core_top), 0.026, bz - 0.25 - core_top, 14)
        # Junction box on the cage and the cable bundle from the motor: up, over in a loop, down.
        kk = jb_spots[name]
        jx, jy = spots[kk]
        jz = bz + 1.25 + 0.08 * (i % 2)
        boxes.box((jx, jy, jz), (0.13, 0.13, 0.20))
        boxes.box((jx, jy, jz + 0.105), (0.14, 0.14, 0.01))                         # lid
        ztop = zt + 0.31
        dxj, dyj = jx - x, jy - y
        loop = [(x + 0.075, y, zt + 0.11), (x + 0.12, y, zt + 0.2), (x + 0.12, y, ztop + 0.15)]
        for k in range(1, 9):
            a = math.pi * k / 9
            f = (1 - math.cos(a)) / 2
            loop.append((x + 0.12 + dxj * f, y + dyj * f + 0.10 * math.sin(a), ztop + 0.15 + 0.35 * math.sin(a)))
        loop += [(jx, jy, zt - 0.1), (jx, jy, jz + 0.11)]
        cables.sweep(loop, 0.016, 8, bend=0.08)
        # Bundle from the junction box down the cage and along the bridge to its NW end.
        lane = W / 2 - 0.12 + 0.025 * i
        a0, a1 = w(cage_x + 0.12, lane), w(L / 2 - 0.2, lane)
        cables.sweep([(jx, jy, jz - 0.10), (jx, jy, bz + 0.16), (a0[0], a0[1], bz + 0.16), (a1[0], a1[1], bz + 0.16)],
                     0.012, 8, bend=0.06)
        if name in ("SS1", "RR"):                                                   # coiled slack on two heads
            coil = [(x + 0.2 * math.cos(2 * math.pi * k / 16) * 0.6, y + 0.12 + 0.2 * math.sin(2 * math.pi * k / 16) * 0.6,
                     zt - 0.35 - 0.012 * k) for k in range(48)]
            cables.sweep(coil, 0.010, 6)
    # Cable gantry (map): from the NW end of the bridge a black tray rises and runs to a post
    # beside the console, and the trunk comes down the post and along the floor to the cabinets.
    end = w(L / 2 - 0.2, W / 2 - 0.05)
    px, py = D.CABLE_POST
    gz = 2.4
    gan = MeshBuilder()
    gan.box((px, py, gz / 2), (0.16, 0.16, gz))                                     # post
    gan.box((px, py, 0.01), (0.3, 0.3, 0.02))                                       # base plate
    gan.box((end[0], end[1], (bz + 0.25 + gz) / 2), (0.14, 0.14, gz - bz - 0.25))  # riser off the bridge
    mx, my, ln = (end[0] + px) / 2, (end[1] + py) / 2, math.hypot(px - end[0], py - end[1])
    gan.build("CableGantry_Post", mats["duct_black"], root, bevel=0.006)
    tray_root = empty("CableGantry_Frame", (mx, my, gz), root)
    tray_root.rotation_euler = (0, 0, math.atan2(py - end[1], px - end[0]))
    MeshBuilder().box((0, 0, 0), (ln + 0.16, 0.22, 0.10)).build("CableGantry", mats["duct_black"], tray_root, bevel=0.006)
    cx0, cy0 = D.CABINET_ROW
    trunk = [(end[0], end[1], bz + 0.16), (end[0], end[1], gz - 0.1), (px, py, gz - 0.1), (px + 0.1, py, gz - 0.1),
             (px + 0.1, py, 0.03), (px + 0.1, 0.6, 0.03), (cx0 + 0.45, 0.6, 0.03)]
    cables.sweep(trunk, 0.035, 10, bend=0.15)
    ramp = MeshBuilder().box(((px + 0.1 + cx0 + 0.45) / 2, 0.6, 0.012), (px + 0.1 - cx0 - 0.45, 0.16, 0.024))
    ramp.box((px + 0.1, (py + 0.6) / 2, 0.012), (0.16, py - 0.6, 0.024))
    ramp.build("CableRamp", mats["duct_black"], root)
    yellow.sweep([(pos["FC"][0] + 0.06, pos["FC"][1], bz + heights["FC"] + 0.2), (pos["FC"][0] + 0.25, pos["FC"][1] + 0.1, bz + 2.6),
                  (pos["FC"][0] + 0.45, pos["FC"][1] + 0.05, bz + 1.9), (spots[4][0], spots[4][1], bz + 1.3),
                  (spots[4][0], spots[4][1], bz + 0.2)], 0.008, 6, bend=0.15)
    cables.build("DriveCables", mats["hv_cable"], root)
    yellow.build("DriveCable_Yellow", mats["cable_yellow"], root)
    boxes.build("Drive_JunctionBoxes", mats["stainless"], root, bevel=0.006)
    heads.build("Drive_MotorHeads", mats["rack"], root, bevel=0.004)
    # Three fixed ion chambers in aluminium tubes on the edge of the core (one per safety channel).
    for k, (ix, iy) in enumerate(((0.24, -0.06), (-0.22, 0.20), (0.06, -0.26))):
        guides.cylinder((ix, iy, core_top - 0.3), 0.038, bz + 0.55 - (core_top - 0.3), 16)
        guides.cylinder((ix, iy, bz + 0.55), 0.05, 0.08, 16)
    guides.build("Drive_GuideTubes", mats["aluminum"], root)
    # Pool-top radiation area monitor on the cage.
    rx, ry = w(cage_x + 0.1, -cage_y - 0.1)
    ram = MeshBuilder().box((rx, ry, bz + 1.9), (0.12, 0.12, 0.18))
    ram.cylinder((rx, ry, bz + 1.99), 0.012, 0.12, 8)
    ram.build("RAM_PoolTop", mats["steel"], root, bevel=0.005)
    # Underwater camera (map): hung from the SE half of the bridge, looking down at the core.
    ux, uy = 0.6, -0.6
    camz = D.WATER_SURFACE_Z - 3.05
    MeshBuilder().cylinder((ux, uy, camz + 0.16), 0.012, bz - camz - 0.16, 8).build("CoreCamera_Pole", mats["stainless"], root)
    head = MeshBuilder().cylinder((ux, uy, camz), 0.05, 0.16, 16)
    head.build("CoreCamera", mats["rack"], root, bevel=0.006)
    return root


def build_process_loop(parent, mats):
    """Primary purification and cooling loop on a skid in the SW corner (layout map; position
    assumed), piped the way the water flows: a suction line from the pool rises over the pool wall,
    runs south and then west high along the south wall, and drops at the west end to the pump;
    the water goes pump -> filter -> mixed-bed ion exchanger -> chiller, and the return line rises
    at the east end of the skid and runs back along the south wall and north over the pool wall
    into the water (no pool penetrations). 2 in pipe painted green, long-radius elbows, flanged
    connections, gate valves on the suction and return, wall brackets along the south wall and
    trapeze hangers from the ceiling over the run to the pool."""
    ox, oy = D.SKID_POS
    root = empty("ProcessLoop", (ox, oy, 0), parent)
    r = 0.03                                              # 2 in pipe
    y_wall = D.ROOM_Y[0] - oy                             # south wall in local coordinates
    skid = MeshBuilder().box((0, 0, 0.05), (2.7, 0.9, 0.10))
    for x in (-1.3, 1.3):
        skid.box((x, 0, 0.05), (0.10, 0.9, 0.12))            # channel ends
    skid.build("Skid", mats["steel"], root, bevel=0.004)
    zc = 0.33                                             # pump centreline
    pump = MeshBuilder()
    pump.cylinder((-1.25, 0, zc), 0.15, 0.16, 28, axis="x")        # volute (suction eye faces west)
    pump.cylinder((-1.09, 0, zc), 0.06, 0.10, 16, axis="x")        # bearing frame
    pump.box((-0.95, 0, 0.14), (0.62, 0.30, 0.08))                  # baseplate
    pump.cylinder((-1.17, 0, zc + 0.15), r * 1.1, 0.06, 14)        # discharge nozzle
    pump.build("Pump_30gpm", mats["pipe_green"], root, bevel=0.004)
    motor = MeshBuilder()
    motor.cylinder((-0.99, 0, zc), 0.12, 0.34, 28, axis="x")
    for k in range(8):                                    # cooling fins
        motor.cylinder((-0.95 + k * 0.035, 0, zc), 0.13, 0.008, 28, axis="x")
    motor.box((-0.83, 0, zc + 0.14), (0.12, 0.10, 0.08))             # terminal box
    motor.build("Pump_Motor", mats["steel"], root, bevel=0.003)
    fx, ix_, cx = -0.3, 0.3, 0.98
    flt = MeshBuilder().cylinder((fx, 0, 0.12), 0.19, 1.10, 32)
    flt.sphere((fx, 0, 1.22), 0.19, 24, 6, z_min=0.0, scale=(1, 1, 0.5))
    for z in (0.35, 1.0):
        flt.cylinder((fx, 0, z), 0.205, 0.03, 32)                       # body flanges / bands
    flt.build("Filter", mats["stainless"], root)
    ix = MeshBuilder().cylinder((ix_, 0, 0.12), 0.22, 1.45, 32)
    ix.sphere((ix_, 0, 1.57), 0.22, 24, 6, z_min=0.0, scale=(1, 1, 0.45))
    ix.build("IonExchanger_MixedBed", mats["stainless"], root)
    legs = MeshBuilder()
    for (vx, rr) in ((fx, 0.19), (ix_, 0.22)):
        for k in range(3):
            a = 2 * math.pi * k / 3 + 0.5
            legs.box((vx + rr * 0.85 * math.cos(a), rr * 0.85 * math.sin(a), 0.11), (0.05, 0.05, 0.03))
    legs.build("Vessel_Feet", mats["steel"], root)
    ch = MeshBuilder().box((cx, 0, 0.6), (0.65, 0.7, 1.0))
    ch.build("Chiller_36kBtu", mats["duct"], root, bevel=0.01)
    grill = MeshBuilder()
    for k in range(9):                                    # condenser louvres on the north face
        grill.box((cx, 0.355, 0.25 + k * 0.08), (0.55, 0.01, 0.03))
    grill.build("Chiller_Louvres", mats["rack_front"], root)
    MeshBuilder().box((cx - 0.15, 0.36, 0.95), (0.18, 0.02, 0.12)).build("Chiller_Controller", mats["panel"], root)

    pipe, fl = MeshBuilder(), MeshBuilder()
    vb, vw = MeshBuilder(), MeshBuilder()
    ws = D.WATER_SURFACE_Z - 0.6
    pcx, pcy = -ox, -oy                                   # pool centre in local coordinates
    ys, yr = y_wall + 0.12, y_wall + 0.24                 # suction and return runs along the south wall
    zs, zr = 2.5, 2.65
    xn_s, xn_r = -1.0 - ox, -0.88 - ox                    # the runs turn north here, towards the pool
    s_end = (pcx - 0.70, pcy - 0.85)                      # ends in the water (inside the 1.22 m liner)
    r_end = (pcx - 0.48, pcy - 0.98)
    # Suction: pool -> over the wall -> south -> west along the wall -> down -> pump suction eye.
    props.pipe_with_fittings(pipe, fl, [(s_end[0], s_end[1], ws), (s_end[0], s_end[1], zs), (xn_s, pcy - 1.9, zs),
                                         (xn_s, ys, zs), (-1.65, ys, zs), (-1.65, ys, zc), (-1.65, -0.12, zc)],
                             r, bend=0.15, flange_ends=False)
    pipe.sweep([(-1.65, -0.12, zc), (-1.65, 0.0, zc), (-1.27, 0.0, zc)], r, 14, bend=0.08)
    fl.flange((-1.30, 0, zc), "x", r)
    props.gate_valve(vb, vw, (-1.65, -0.24, zc), "y", r)
    # Pump -> filter (top inlet).
    props.pipe_with_fittings(pipe, fl, [(-1.17, 0, zc + 0.21), (-1.17, 0, 1.6), (fx, 0, 1.6), (fx, 0, 1.33)], r)
    # Filter -> ion exchanger, a low cross-over.
    props.pipe_with_fittings(pipe, fl, [(fx + 0.19, 0, 0.40), (ix_ - 0.22, 0, 0.40)], r)
    # Ion exchanger top -> chiller top.
    props.pipe_with_fittings(pipe, fl, [(ix_, 0, 1.70), (ix_, 0, 1.9), (cx, 0, 1.9), (cx, 0, 1.1)], r)
    # Return: chiller east outlet, valve, up at the east end of the skid, east along the wall,
    # north over the pool wall and down into the water.
    props.pipe_with_fittings(pipe, fl, [(cx + 0.33, 0, 0.8), (cx + 0.42, 0, 0.8)], r)
    props.gate_valve(vb, vw, (cx + 0.51, 0, 0.8), "x", r)
    props.pipe_with_fittings(pipe, fl, [(cx + 0.60, 0, 0.8), (1.62, 0, 0.8), (1.62, yr, 0.8), (1.62, yr, zr),
                                         (xn_r, yr, zr), (xn_r, pcy - 1.9, zr), (r_end[0], r_end[1], zr),
                                         (r_end[0], r_end[1], ws)], r, bend=0.15, flange_ends=False)
    fl.flange((cx + 0.60, 0, 0.8), "x", r)
    pipe.build("ProcessPiping", mats["pipe_green"], root)
    fl.build("ProcessPiping_Flanges", mats["pipe_green"], root)
    vb.build("ProcessValves", mats["steel"], root)
    vw.build("ProcessValve_Handwheels", mats["button_red"], root)
    # Wall brackets along the south wall and trapeze hangers over the run to the pool.
    hang = MeshBuilder()
    for x in [-1.6 + 1.2 * k for k in range(int((xn_r + 1.6) / 1.2) + 1)]:
        hang.box((x, y_wall + 0.15, zs - r - 0.02), (0.05, 0.30, 0.03))
        hang.box((x, y_wall + 0.21, zr - r - 0.02), (0.05, 0.18, 0.03))
    for y in (y_wall + 1.2, y_wall + 2.4):
        hang.box(((xn_s + xn_r) / 2, y, zs - r - 0.02), (0.35, 0.04, 0.04))
        for x in (xn_s - 0.12, xn_r + 0.12):
            hang.cylinder((x, y, zs - r - 0.03), 0.008, D.ROOM_H - zs + r + 0.03, 8)
    hang.build("ProcessPiping_Hangers", mats["steel"], root)
    MeshBuilder().box((-0.6, -0.40, 1.0), (0.12, 0.10, 0.18)).build("RAM_WaterProcess", mats["steel"], root, bevel=0.005)
    # Continuous air monitor beside the skid.
    cam = MeshBuilder().box((2.25, 0.25, 0.55), (0.5, 0.5, 1.1))
    cam.cylinder((2.25, 0.25, 1.1), 0.03, 0.25, 12)          # sample inlet
    cam.build("CAM", mats["duct"], root, bevel=0.008)
    return root


def build_reactor_hall(mats, with_console=True):
    root = empty("PUR1_ReactorHall")
    build_room(root, mats)
    build_pool(root, mats)
    core_objs = build_core(root, mats, (0.0, 0.0, D.GRID_PLATE_Z))
    build_bridge_and_drives(root, mats, core_objs)
    build_process_loop(root, mats)
    build_lab(root, mats)
    if with_console:
        build_control_room(root, mats)
    # Cherenkov light for renders (not exported).
    add_light("CherenkovLight", "POINT", (0, 0, D.GRID_PLATE_Z + 0.4), 600, (0.3, 0.55, 1.0))
    return root, core_objs
