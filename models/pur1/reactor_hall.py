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
from .core import build_core, lattice_xy


def build_room(parent, mats):
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
    fl.build("Floor", mats["floor"], root)
    # Yellow safety striping painted on the floor: a ring around the pool and a line along the
    # console and cabinet area (photos).
    stripe = MeshBuilder()
    rs = D.FLOOR_STRIPE_RADIUS
    n = 96
    ring = []
    for i in range(n):
        a = 2 * math.pi * i / n
        ring.append((math.cos(a), math.sin(a)))
    for i in range(n):
        j = (i + 1) % n
        (c0, s0), (c1, s1) = ring[i], ring[j]
        stripe._add([(rs * c0, rs * s0, 0.002), (rs * c1, rs * s1, 0.002),
                     ((rs + 0.1) * c1, (rs + 0.1) * s1, 0.002), ((rs + 0.1) * c0, (rs + 0.1) * s0, 0.002)],
                    [(0, 1, 2, 3)])
    stripe.box_minmax((D.CONSOLE_POS[0] - 1.9, -3.2, 0.001), (D.CONSOLE_POS[0] - 1.8, 5.5, 0.003))
    stripe.build("FloorStriping", mats["floor_stripe"], root)

    walls = MeshBuilder()
    walls.box_minmax((x0 - t, y0 - t, 0), (x0, y1 + t, h))      # west
    walls.box_minmax((x1, y0 - t, 0), (x1 + t, y1 + t, h))      # east
    walls.box_minmax((x0, y0 - t, 0), (x1, y0, h))              # south
    walls.box_minmax((x0, y1, 0), (x1, y1 + t, h))              # north
    walls.build("Walls", mats["wall_cream"], root)
    MeshBuilder().box_minmax((x0 - t, y0 - t, h), (x1 + t, y1 + t, h + 0.3)).build("Ceiling", mats["ceiling"], root)

    # Doors: main personnel door (south, east end), west personnel door, north personnel door,
    # storage-room door (north, west end). Hallway scram push-button outside the main door.
    # Each door is a hollow-metal leaf in a pressed-steel frame on the room-side face of its wall.
    doors = {
        "Door_Main_South": ((6.0, y0, 0), 0.0),
        "Door_West": ((x0, -4.0, 0), -math.pi / 2),
        "Door_North": ((4.8, y1, 0), math.pi),             # east of the stair platform
        "Door_StorageRoom_North": ((-3.5, y1, 0), math.pi),
    }
    for nm, (pos, facing) in doors.items():
        props.door(root, mats, nm, pos, facing, D.DOOR_W, D.DOOR_H, t)
    hb = cylinder("ui_Scram_Hallway", (6.9, y0 - t - 0.03, 1.3), 0.035, 0.04, mats["button_red"], root, 16, axis="y")
    hb["role"] = "manual_scram_hallway"

    # Exposed services on the walls (photos): conduit runs and a green process line along the
    # west and north walls, a panel board, and overhead ductwork.
    cond = MeshBuilder()
    for z in (2.6, 3.1, 3.4):
        cond.sweep([(x0 + 0.06, y0 + 0.5, z), (x0 + 0.06, y1 - 0.5, z)], 0.025, 8)       # west wall runs
    for z in (2.9, 3.3):
        cond.sweep([(x0 + 0.5, y1 - 0.06, z), (x1 - 0.5, y1 - 0.06, z)], 0.025, 8)       # north wall runs
    for x in (-3.5, -1.5, 0.5, 2.5):
        cond.sweep([(x, y1 - 0.06, 3.3), (x, y1 - 0.06, h - 0.1)], 0.02, 8)             # drops to the ceiling
    cond.sweep([(x0 + 0.06, -2.0, 0.4), (x0 + 0.06, -2.0, 2.6)], 0.02, 8)
    cond.build("Conduit", mats["conduit"], root)
    green = MeshBuilder()
    green.sweep([(x0 + 0.12, y0 + 0.3, 3.75), (x0 + 0.12, y1 - 0.12, 3.75), (x1 - 0.3, y1 - 0.12, 3.75)], 0.05, 16, bend=0.35)
    for y in (y0 + 3.5, 0.5, y1 - 2.5):                                   # flanged joints
        green.flange((x0 + 0.12, y, 3.75), "y", 0.05, 0.03)
    green.build("ProcessLine_Green", mats["pipe_green"], root)
    brk = MeshBuilder()                                                  # wall brackets and U-bolts
    for y in [y0 + 1.0 + 1.5 * k for k in range(int((y1 - y0 - 1.5) / 1.5) + 1)]:
        brk.box((x0 + 0.06, y, 3.68), (0.12, 0.05, 0.03))
        brk.box((x0 + 0.12, y, 3.808), (0.13, 0.03, 0.008))             # strap over the pipe
    for x in [x0 + 1.5 + 1.5 * k for k in range(int((x1 - x0 - 2.0) / 1.5) + 1)]:
        brk.box((x, y1 - 0.06, 3.68), (0.05, 0.12, 0.03))
    for z in (2.6, 3.1, 3.4):                                            # conduit straps
        for y in (y0 + 1.5, 0.0, y1 - 1.5):
            brk.box((x0 + 0.03, y, z), (0.06, 0.04, 0.06))
    brk.box((x0 + 0.08, -2.0, 2.65), (0.12, 0.14, 0.14))                # junction box
    brk.build("PipeBrackets", mats["steel"], root)
    pan = MeshBuilder().box((x0 + 0.08, 0.5, 1.6), (0.16, 0.7, 0.9)).box((x0 + 0.08, 1.4, 1.5), (0.14, 0.4, 0.6))
    pan.build("PanelBoards_West", mats["door_frame"], root)

    # HVAC: HEPA-filtered inlet on the west wall, exhaust duct along the ceiling to a fan at the north wall.
    duct = MeshBuilder()
    duct.box((x0 + 0.45, 3.5, h - 0.9), (0.9, 0.9, 0.9))              # inlet HEPA housing
    duct.box((x0 + 0.45, -3.0, h - 0.9), (0.9, 0.9, 0.9))             # second inlet
    duct.box(((x0 + x1) / 2, y1 - 0.5, h - 0.6), (x1 - x0 - 1.0, 0.5, 0.5))   # exhaust trunk
    duct.box(((x0 + x1) / 2, -1.5, h - 0.75), (x1 - x0 - 2.0, 0.7, 0.45))     # supply trunk across the room
    duct.box((x1 - 1.0, y1 - 0.5, h - 0.6), (1.1, 1.1, 1.1))          # exhaust fan / HEPA bank
    duct.cylinder((x1 - 1.0, y1 - 0.5, h - 0.05), 0.3, 0.35, 24)      # through-roof stack stub
    duct.build("HVAC_Ducts", mats["duct"], root)

    # Fluorescent tube fixtures hung from the ceiling (photos), plus render lights.
    fix = MeshBuilder()
    for i, x in enumerate((-3.0, 0.5, 4.0, 7.5)):
        for y in (-3.8, 0.0, 3.8):
            fix.box((x, y, h - 0.45), (1.25, 0.30, 0.08))
            if y != 0.0 or x in (0.5, 7.5):
                add_light(f"Light_{i}_{y:+.0f}", "POINT", (x, y, h - 0.7), 1200, (1.0, 0.97, 0.9), soft=0.6)
    fix.build("LightFixtures", mats["lamp"], root)

    # Monorail hoist over the pool for fuel/experiment handling.
    rail = MeshBuilder().box((0, 0, h - 0.5), (x1 - x0 - 1.0, 0.18, 0.30))
    rail.box((0.8, 0, h - 0.95), (0.5, 0.5, 0.6))                      # hoist trolley
    rail.cylinder((0.8, 0, D.SHIELD_TOP_Z + 1.6), 0.01, h - 1.25 - D.SHIELD_TOP_Z - 1.6, 8)
    rail.build("MonorailHoist", mats["steel_yellow"], root)

    # Stair and platform along the north wall (photos show a stair rising behind the pool). The
    # treads are 1 m wide against the wall; the platform at the top comes out into the room.
    sx, sy, _ = D.STAIR_ORIGIN
    rise, run, nsteps = D.STAIR_RISE, D.STAIR_RUN, D.STAIR_STEPS
    pl, pd = D.PLATFORM_SIZE
    wall_y = D.ROOM_Y[1]
    top = nsteps * rise
    px0, px1 = sx + nsteps * run, sx + nsteps * run + pl      # platform x extent
    py0 = wall_y - pd                                          # platform room-side edge
    st = MeshBuilder()
    for i in range(nsteps):
        st.box_minmax((sx + i * run, sy, i * rise), (sx + (i + 1) * run + 0.02, wall_y, (i + 1) * rise))
        st.box_minmax((sx + i * run, sy - 0.03, max(0.0, i * rise - 0.22)), (sx + (i + 1) * run + 0.02, sy, (i + 1) * rise))  # stringer
    st.box_minmax((px0, py0, top - 0.08), (px1, wall_y, top))                                   # platform deck
    st.box_minmax((px0, py0, top - 0.30), (px1, py0 + 0.05, top - 0.08))                        # platform edge beam
    for x in (px0 + 0.1, px1 - 0.1):
        st.box((x, py0 + 0.1, top / 2), (0.1, 0.1, top))                                         # posts
    st.build("Stair_North", mats["steel"], root)
    hr = MeshBuilder()
    rail_pts = [(sx + i * run + run / 2, sy - 0.03, i * rise + 1.0) for i in range(nsteps)]
    rail_pts += [(px0, sy - 0.03, top + 1.0), (px0, py0, top + 1.0), (px1, py0, top + 1.0), (px1, wall_y, top + 1.0)]
    hr.sweep(rail_pts, 0.02, 8)
    for i in range(0, nsteps, 2):
        hr.sweep([(sx + i * run + run / 2, sy - 0.03, i * rise), (sx + i * run + run / 2, sy - 0.03, i * rise + 1.0)], 0.012, 6)
    for x, y in ((px0, sy - 0.03), (px0, py0), ((px0 + px1) / 2, py0), (px1, py0), (px1, (py0 + wall_y) / 2)):
        hr.sweep([(x, y, top), (x, y, top + 1.0)], 0.012, 6)
    hr.sweep([(px0, py0, top + 0.5), (px1, py0, top + 0.5), (px1, wall_y, top + 0.5)], 0.012, 6)     # mid rail
    hr.build("Stair_North_Handrail", mats["steel_yellow"], root)
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
    """Reactor top (photos): a bridge of round stainless girders and square-tube cross members
    resting on the pool wall, with a galvanised bar-grating deck that leaves an opening over the
    core; an aluminium cage over the core carrying the tall stainless drive tubes, each with its
    motor and encoder head and a junction box; black cable bundles looping from the heads down to
    the junction boxes and away along the bridge to the console side; guide tubes and the three
    fixed ion-chamber tubes going down into the water; and the black pool-top exhaust duct."""
    root = empty("Bridge", (0, 0, 0), parent)
    R = D.SHIELD_OUTER_RADIUS
    L = 2 * R + 0.3
    bz = D.SHIELD_TOP_Z + 0.08
    W = D.BRIDGE_WIDTH
    hole = 0.36                                   # half-width of the deck opening over the core (x)

    # Girders, cross members and feet.
    gird = MeshBuilder()
    for y in (-W / 2, W / 2):
        gird.sweep([(-L / 2, y, bz), (L / 2, y, bz)], 0.06, 20)                         # lower girder
        gird.sweep([(-L / 2 + 0.1, y, bz + 0.22), (L / 2 - 0.1, y, bz + 0.22)], 0.04, 16)   # upper rail
        for x in (-L / 2 + 0.25, -1.3, -hole - 0.05, hole + 0.05, 1.3, L / 2 - 0.25):
            gird.sweep([(x, y, bz), (x, y, bz + 0.22)], 0.018, 10)                       # rail posts
    gird.build("Bridge_Structure", mats["stainless"], root)
    frame = MeshBuilder()
    for x in (-L / 2 + 0.15, -1.3, -hole - 0.05, hole + 0.05, 1.3, L / 2 - 0.15):
        frame.box((x, 0, bz - 0.01), (0.08, W, 0.08))                                    # cross members
    for x in (-L / 2 + 0.15, L / 2 - 0.15):                                              # feet on the pool wall
        for y in (-W / 2, W / 2):
            frame.box((x, y, (D.SHIELD_TOP_Z + bz - 0.06) / 2 + 0.0), (0.16, 0.16, bz - 0.06 - D.SHIELD_TOP_Z + 0.02))
            frame.box((x, y, D.SHIELD_TOP_Z + 0.005), (0.22, 0.22, 0.01))                # bearing plate
    frame.build("Bridge_Frame", mats["aluminum"], root, bevel=0.004)

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
    grate.build("Bridge_Grating", mats["grating"], root)

    # Drive cage over the core: four aluminium square-tube posts and three ring frames.
    cage_x, cage_y, cage_h = 0.32, 0.30, 2.3
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
    cage.build("Drive_Cage", mats["aluminum"], root, bevel=0.004)

    # Drive mechanisms over their core positions. Drive x,y from the lattice; the core is at x=y=0.
    pos = {k: lattice_xy(*v) for k, v in D.CONTROL_POSITIONS.items()}
    sx, sy = lattice_xy(1, 1)
    pos["NS"] = (sx - D.ELEMENT_W / 2 - 0.05, sy - D.ELEMENT_W / 2 - 0.05)
    fx, fy = lattice_xy(5, 5)
    pos["FC"] = (fx + D.ELEMENT_W / 2 + 0.03, fy)
    heights = {"SS1": 2.75, "SS2": 2.75, "RR": 2.6, "NS": 2.2, "FC": 2.0}
    core_top = D.GRID_PLATE_Z + D.NOZZLE_LENGTH + D.PLATE_LENGTH + D.HANDLE_LENGTH + 0.12
    cables, yellow, boxes, heads = MeshBuilder(), MeshBuilder(), MeshBuilder(), MeshBuilder()
    guides = MeshBuilder()
    jb_spots = {"SS1": (cage_x + 0.09, -0.15), "SS2": (-cage_x - 0.09, -0.15), "RR": (cage_x + 0.09, 0.15),
                "NS": (-cage_x - 0.09, 0.15), "FC": (0.0, cage_y + 0.08)}
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
        jx, jy = jb_spots[name]
        jz = bz + 1.25 + 0.08 * (i % 2)
        boxes.box((jx, jy, jz), (0.12, 0.14, 0.20))
        boxes.box((jx, jy, jz + 0.105), (0.13, 0.15, 0.01))                         # lid
        ztop = zt + 0.31
        side = 1 if jx >= 0 else -1
        loop = [(x + 0.075, y, zt + 0.11), (x + 0.12, y, zt + 0.2), (x + 0.12, y, ztop + 0.15)]
        for k in range(1, 9):
            a = math.pi * k / 9
            loop.append((x + 0.12 + side * 0.22 * (1 - math.cos(a)), y + 0.12 * math.sin(a), ztop + 0.15 + 0.35 * math.sin(a)))
        loop += [(jx, jy, zt - 0.1), (jx, jy, jz + 0.11)]
        cables.sweep(loop, 0.016, 8, bend=0.08)
        # Bundle from the junction box down the cage and out to the east end of the bridge.
        cables.sweep([(jx, jy + 0.04, jz - 0.10), (jx, jy + 0.04, bz + 0.16), (cage_x + 0.12, W / 2 - 0.12 + 0.025 * i, bz + 0.16),
                      (L / 2 - 0.2, W / 2 - 0.12 + 0.025 * i, bz + 0.16)], 0.012, 8, bend=0.06)
        if name in ("SS1", "RR"):                                                   # coiled slack on two heads
            coil = [(x + 0.2 * math.cos(2 * math.pi * k / 16) * 0.6, y + 0.12 + 0.2 * math.sin(2 * math.pi * k / 16) * 0.6,
                     zt - 0.35 - 0.012 * k) for k in range(48)]
            cables.sweep(coil, 0.010, 6)
    # Trunk off the east end of the bridge, down the pool wall and across the floor to the console.
    trunk = [(L / 2 - 0.2, W / 2 - 0.05, bz + 0.16), (R + 0.05, W / 2 - 0.05, bz + 0.16), (R + 0.05, W / 2 - 0.05, 0.03),
             (D.CONSOLE_POS[0] - 0.4, W / 2 - 0.05, 0.03)]
    cables.sweep(trunk, 0.035, 10, bend=0.15)
    yellow.sweep([(pos["FC"][0] + 0.06, pos["FC"][1], bz + heights["FC"] + 0.2), (pos["FC"][0] + 0.25, pos["FC"][1] + 0.1, bz + 2.6),
                  (pos["FC"][0] + 0.45, pos["FC"][1] + 0.2, bz + 1.9), (cage_x + 0.1, cage_y + 0.08, bz + 1.3),
                  (cage_x + 0.1, cage_y + 0.08, bz + 0.2)], 0.008, 6, bend=0.15)
    cables.build("DriveCables", mats["hv_cable"], root)
    yellow.build("DriveCable_Yellow", mats["cable_yellow"], root)
    boxes.build("Drive_JunctionBoxes", mats["stainless"], root, bevel=0.006)
    heads.build("Drive_MotorHeads", mats["rack"], root, bevel=0.004)
    # Three fixed ion chambers in aluminium tubes on the edge of the core (one per safety channel).
    for k, (ix, iy) in enumerate(((0.24, -0.06), (-0.22, 0.20), (0.06, -0.26))):
        guides.cylinder((ix, iy, core_top - 0.3), 0.038, bz + 0.55 - (core_top - 0.3), 16)
        guides.cylinder((ix, iy, bz + 0.55), 0.05, 0.08, 16)
        cables.sweep([(ix, iy, bz + 0.63), (ix, iy, bz + 0.8), (cage_x - 0.05, iy, bz + 0.8)], 0.01, 6)
    guides.build("Drive_GuideTubes", mats["aluminum"], root)
    # Pool-top radiation area monitor on the cage.
    ram = MeshBuilder().box((cage_x + 0.1, cage_y + 0.1, bz + 1.9), (0.12, 0.10, 0.18))
    ram.cylinder((cage_x + 0.1, cage_y + 0.1, bz + 1.99), 0.012, 0.12, 8)
    ram.build("RAM_PoolTop", mats["steel"], root, bevel=0.005)

    # Pool-sweep exhaust: a black duct dropping from the ceiling beside the pool, turning in over
    # the pool edge to a hood above the water (photos).
    dx, dy = -1.75, 1.35
    duct = MeshBuilder()
    duct.box((dx, dy, (D.ROOM_H + 2.75) / 2), (0.28, 0.28, D.ROOM_H - 2.75))
    duct.sweep([(dx, dy, 2.9), (dx, dy, 2.62), (-1.05, 0.8, 2.62)], 0.13, 16, bend=0.2)
    duct.box((-1.05, 0.8, 2.52), (0.42, 0.34, 0.12))                                  # hood
    for z in (3.6, 4.8, 6.0):
        duct.box((dx, dy, z), (0.31, 0.31, 0.04))                                      # duct joints
    duct.build("PoolExhaust_Duct", mats["duct_black"], root, bevel=0.01)
    return root


def build_process_loop(parent, mats):
    """Primary purification and cooling loop on a skid in the SW corner, piped the way the water
    actually flows: a suction line hangs over the pool wall into the water, drops to the pump,
    and the water goes pump -> filter -> mixed-bed ion exchanger -> chiller -> return line back
    over the pool wall. 2 in stainless pipe with long-radius elbows, flanged connections, gate
    valves on the suction and return, and trapeze hangers from the ceiling under the high runs
    (no pool penetrations: both lines enter over the top)."""
    ox, oy = -3.55, -4.7
    root = empty("ProcessLoop", (ox, oy, 0), parent)
    pcx, pcy = -ox, -oy                                   # pool centre in local coordinates
    r = 0.03                                              # 2 in pipe
    skid = MeshBuilder().box((0, 0, 0.05), (2.6, 1.4, 0.10))
    for x in (-1.25, 1.25):
        skid.box((x, 0, 0.05), (0.10, 1.4, 0.12))            # channel ends
    skid.build("Skid", mats["steel"], root, bevel=0.004)
    zc = 0.33                                             # pump centreline
    pump = MeshBuilder()
    pump.cylinder((-1.20, -0.3, zc), 0.15, 0.16, 28, axis="x")     # volute
    pump.cylinder((-1.04, -0.3, zc), 0.06, 0.10, 16, axis="x")     # bearing frame
    pump.box((-0.95, -0.3, 0.14), (0.62, 0.30, 0.08))               # baseplate
    pump.cylinder((-1.20, -0.3, zc + 0.15), r * 1.1, 0.06, 14)      # discharge nozzle
    pump.build("Pump_30gpm", mats["pipe_green"], root, bevel=0.004)
    motor = MeshBuilder()
    motor.cylinder((-0.94, -0.3, zc), 0.12, 0.34, 28, axis="x")
    for k in range(8):                                    # cooling fins
        motor.cylinder((-0.90 + k * 0.035, -0.3, zc), 0.13, 0.008, 28, axis="x")
    motor.box((-0.78, -0.3, zc + 0.14), (0.12, 0.10, 0.08))           # terminal box
    motor.build("Pump_Motor", mats["steel"], root, bevel=0.003)
    flt = MeshBuilder().cylinder((-0.1, 0.3, 0.12), 0.22, 1.10, 32)
    flt.sphere((-0.1, 0.3, 1.22), 0.22, 24, 6, z_min=0.0, scale=(1, 1, 0.5))
    for z in (0.35, 1.0):
        flt.cylinder((-0.1, 0.3, z), 0.235, 0.03, 32)                     # body flanges / bands
    flt.build("Filter", mats["stainless"], root)
    ix = MeshBuilder().cylinder((0.6, 0.3, 0.12), 0.28, 1.45, 32)
    ix.sphere((0.6, 0.3, 1.57), 0.28, 24, 6, z_min=0.0, scale=(1, 1, 0.45))
    ix.build("IonExchanger_MixedBed", mats["stainless"], root)
    legs = MeshBuilder()
    for (cx, cy, rr) in ((-0.1, 0.3, 0.22), (0.6, 0.3, 0.28)):
        for k in range(3):
            a = 2 * math.pi * k / 3 + 0.5
            legs.box((cx + rr * 0.85 * math.cos(a), cy + rr * 0.85 * math.sin(a), 0.11), (0.05, 0.05, 0.03))
    legs.build("Vessel_Feet", mats["steel"], root)
    ch = MeshBuilder().box((0.9, -0.3, 0.6), (0.9, 0.6, 1.0))
    ch.build("Chiller_36kBtu", mats["duct"], root, bevel=0.01)
    grill = MeshBuilder()
    for k in range(9):                                    # condenser louvres on the front
        grill.box((0.9, -0.605, 0.25 + k * 0.08), (0.8, 0.01, 0.03))
    grill.build("Chiller_Louvres", mats["rack_front"], root)
    MeshBuilder().box((1.36, -0.3, 0.95), (0.02, 0.18, 0.12)).build("Chiller_Controller", mats["panel"], root)

    pipe, fl = MeshBuilder(), MeshBuilder()
    vb, vw = MeshBuilder(), MeshBuilder()
    ws = D.WATER_SURFACE_Z - 0.6
    # Suction: from the pool, over the wall, along the high run, down to the pump inlet.
    sx, sy = pcx - 1.00, pcy - 0.55
    props.pipe_with_fittings(pipe, fl, [(sx, sy, ws), (sx, sy, 2.2), (sx, -0.75, 2.2), (-1.55, -0.75, 2.2),
                                         (-1.55, -0.75, zc), (-1.55, -0.62, zc)], r, flange_ends=False)
    pipe.sweep([(-1.55, -0.40, zc), (-1.55, -0.3, zc), (-1.36, -0.3, zc)], r, 14, bend=0.08)
    fl.flange((-1.36, -0.3, zc), "x", r)
    props.gate_valve(vb, vw, (-1.55, -0.51, zc), "y", r)
    # Pump -> filter (top inlet).
    props.pipe_with_fittings(pipe, fl, [(-1.20, -0.3, zc + 0.21), (-1.20, -0.3, 1.6), (-0.1, -0.3, 1.6),
                                         (-0.1, 0.3, 1.6), (-0.1, 0.3, 1.33)], r)
    # Filter -> ion exchanger, a low cross-over.
    props.pipe_with_fittings(pipe, fl, [(0.12, 0.3, 0.40), (0.32, 0.3, 0.40)], r)
    # Ion exchanger top -> chiller top.
    props.pipe_with_fittings(pipe, fl, [(0.6, 0.3, 1.70), (0.6, 0.3, 1.9), (0.9, 0.3, 1.9), (0.9, -0.3, 1.9),
                                         (0.9, -0.3, 1.1)], r)
    # Return: chiller side outlet, valve, up to the high run and back over the wall into the pool.
    rx, ry = pcx - 0.75, pcy - 0.80
    props.pipe_with_fittings(pipe, fl, [(1.35, -0.3, 0.8), (1.42, -0.3, 0.8)], r)
    props.gate_valve(vb, vw, (1.51, -0.3, 0.8), "x", r)
    props.pipe_with_fittings(pipe, fl, [(1.60, -0.3, 0.8), (1.80, -0.3, 0.8), (1.80, -0.3, 2.34), (rx, -0.3, 2.34),
                                         (rx, ry, 2.34), (rx, ry, ws)], r, flange_ends=False)
    fl.flange((1.60, -0.3, 0.8), "x", r)
    pipe.build("ProcessPiping", mats["stainless"], root)
    fl.build("ProcessPiping_Flanges", mats["stainless"], root)
    vb.build("ProcessValves", mats["steel"], root)
    vw.build("ProcessValve_Handwheels", mats["button_red"], root)
    # Trapeze hangers from the ceiling under the high runs.
    hang = MeshBuilder()
    for y in (0.6, 2.2):
        hang.box(((sx + rx) / 2, y, 2.15), (abs(rx - sx) + 0.25, 0.04, 0.04))
        hang.box(((sx + rx) / 2, y, 2.29), (0.10, 0.04, 0.04))
        for x in (min(sx, rx) - 0.1, max(sx, rx) + 0.1):
            hang.cylinder((x, y, 2.13), 0.008, D.ROOM_H - 2.13, 8)
    for x in (-0.6, 1.2):
        hang.box((x, -0.75, 2.15), (0.04, 0.12, 0.04))
        hang.cylinder((x, -0.75, 2.13), 0.008, D.ROOM_H - 2.13, 8)
    hang.build("ProcessPiping_Hangers", mats["steel"], root)
    MeshBuilder().box((-1.1, 0.5, 1.0), (0.12, 0.10, 0.18)).build("RAM_WaterProcess", mats["steel"], root, bevel=0.005)
    # Continuous air monitor near the pool.
    cam = MeshBuilder().box((2.6, 0.9, 0.55), (0.5, 0.5, 1.1))
    cam.cylinder((2.6, 0.9, 1.1), 0.03, 0.25, 12)          # sample inlet
    cam.build("CAM", mats["duct"], root, bevel=0.008)
    return root


def build_reactor_hall(mats, with_console=True):
    root = empty("PUR1_ReactorHall")
    build_room(root, mats)
    build_pool(root, mats)
    core_objs = build_core(root, mats, (0.0, 0.0, D.GRID_PLATE_Z))
    build_bridge_and_drives(root, mats, core_objs)
    build_process_loop(root, mats)
    if with_console:
        build_control_room(root, mats)
    # Cherenkov light for renders (not exported).
    add_light("CherenkovLight", "POINT", (0, 0, D.GRID_PLATE_Z + 0.4), 600, (0.3, 0.55, 1.0))
    return root, core_objs
