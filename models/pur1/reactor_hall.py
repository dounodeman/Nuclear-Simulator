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
from .common import MeshBuilder, box, curved_text, cylinder, empty, add_light, FT, IN
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
    doors = {
        "Door_Main_South": ((6.0, y0 - t / 2, 0), "y"),
        "Door_West": ((x0 - t / 2, -4.0, 0), "x"),
        "Door_North": ((2.0, y1 + t / 2, 0), "y"),
        "Door_StorageRoom_North": ((-3.5, y1 + t / 2, 0), "y"),
    }
    for nm, ((x, y, z), orient) in doors.items():
        size = (D.DOOR_W, t + 0.02, D.DOOR_H) if orient == "y" else (t + 0.02, D.DOOR_W, D.DOOR_H)
        fsize = (D.DOOR_W + 0.16, t + 0.06, D.DOOR_H + 0.08) if orient == "y" else (t + 0.06, D.DOOR_W + 0.16, D.DOOR_H + 0.08)
        box(f"{nm}_Frame", (x, y, D.DOOR_H / 2 + 0.04), fsize, mats["door_frame"], root)
        box(nm, (x, y, D.DOOR_H / 2), size, mats["door"], root)
        # Radiation area sign on the inside face.
        sx, sy = (x, y + (t / 2 + 0.02) * (1 if y < 0 else -1)) if orient == "y" else (x + t / 2 + 0.02, y)
        box(f"{nm}_Sign", (sx, sy, 1.6), (0.25, 0.01, 0.18) if orient == "y" else (0.01, 0.25, 0.18), mats["sign_yellow"], root)
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
    green.sweep([(x0 + 0.12, y0 + 0.3, 3.75), (x0 + 0.12, y1 - 0.12, 3.75), (x1 - 0.3, y1 - 0.12, 3.75)], 0.05, 12)
    green.build("ProcessLine_Green", mats["pipe_green"], root)
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
    curved_text("Graphic_PUR1", "PUR-1", mats["lettering_white"], R, a, 0.50, 0.62, parent=root)
    curved_text("Graphic_Tagline", "THE NATION'S FIRST ALL-DIGITAL I&C", mats["lettering_gold"], R, a, 0.21, 0.10, parent=root)
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
    """Bridge across the pool top (photos): a welded frame of square tube resting on the pool
    wall, carrying the tall vertical drive tubes with black cables looped over the top."""
    root = empty("Bridge", (0, 0, 0), parent)
    R = D.SHIELD_OUTER_RADIUS
    L = 2 * R + 0.5
    bz = D.SHIELD_TOP_Z + 0.08
    W = D.BRIDGE_WIDTH
    beam = MeshBuilder()
    for y in (-W / 2, W / 2):
        beam.box((0, y, bz), (L, 0.10, 0.10))                 # main rails
    for x in (-L / 2 + 0.2, -0.9, 0.0, 0.9, L / 2 - 0.2):
        beam.box((x, 0, bz), (0.10, W, 0.10))                 # cross members
    beam.box((0, 0, bz + 0.06), (L, W, 0.02))                 # deck plate
    for x in (-L / 2 + 0.2, L / 2 - 0.2):                     # feet on the pool wall
        for y in (-W / 2, W / 2):
            beam.box((x, y, (D.SHIELD_TOP_Z + bz - 0.05) / 2), (0.14, 0.14, bz - 0.05 - D.SHIELD_TOP_Z))
    # Upper frame that the drive tubes are clamped to.
    for y in (-W / 2, W / 2):
        beam.box((0, y, bz + 1.1), (1.6, 0.06, 0.06))
    for x in (-0.8, 0.8):
        beam.box((x, 0, bz + 1.1), (0.06, W, 0.06))
        for y in (-W / 2, W / 2):
            beam.box((x, y, bz + 0.6), (0.06, 0.06, 1.0))
    beam.build("Bridge_Structure", mats["steel"], root)

    # Drive mechanisms over their core positions. Drive x,y from the lattice; the core is at x=y=0.
    pos = {k: lattice_xy(*v) for k, v in D.CONTROL_POSITIONS.items()}
    sx, sy = lattice_xy(1, 1)
    pos["NS"] = (sx - D.ELEMENT_W / 2 - 0.05, sy - D.ELEMENT_W / 2 - 0.05)
    fx, fy = lattice_xy(5, 5)
    pos["FC"] = (fx + D.ELEMENT_W / 2 + 0.03, fy)
    tube_h = 2.2
    cables = MeshBuilder()
    for i, name in enumerate(D.DRIVE_NAMES):
        x, y = pos[name]
        mb = MeshBuilder()
        mb.cylinder((x, y, bz + 0.07), 0.045, tube_h, 16)                          # drive tube
        mb.cylinder((x, y, bz + 0.07 + tube_h), 0.07, 0.16, 16)                    # motor head
        mb.box((x, y, bz + 0.07 + 0.35), (0.12, 0.12, 0.12))                        # lower clamp
        ob = mb.build(f"Drive_{name}", mats["stainless"], root)
        ob["drive"] = name
        # Black cable: up from the motor head, over in a loop, down to the cable tray on the frame.
        zt = bz + 0.07 + tube_h + 0.16
        loop = [(x, y, zt), (x, y, zt + 0.25 + 0.05 * i)]
        for k in range(1, 8):
            a = math.pi * k / 8
            loop.append((x + 0.25 * (1 - math.cos(a)) * 0.5 + 0.3 * math.sin(a) * 0.2, y + 0.35 * math.sin(a),
                         zt + 0.25 + 0.05 * i + 0.45 * math.sin(a)))
        loop += [(x, y + 0.7 + 0.03 * i, zt - 0.4), (x, y + 0.7 + 0.03 * i, bz + 1.15)]
        cables.sweep(loop, 0.014, 8)
    cables.sweep([(-0.3, W / 2 + 0.3, bz + 1.15), (0.3, W / 2 + 0.3, bz + 1.15), (0.3, W / 2 + 0.3, bz + 0.1),
                  (L / 2, W / 2 + 0.3, bz + 0.1)], 0.02, 8)   # trunk to the console side
    cables.build("DriveCables", mats["hv_cable"], root)
    # Pool-top radiation area monitor on the bridge frame.
    ram = MeshBuilder().box((0.9, W / 2 + 0.1, bz + 1.2), (0.12, 0.10, 0.18))
    ram.build("RAM_PoolTop", mats["steel"], root)
    return root


def build_process_loop(parent, mats):
    """Pump, filter, ion exchanger and chiller skid in the SW corner; 2 in lines over the parapet."""
    root = empty("ProcessLoop", (-3.8, -4.6, 0), parent)
    skid = MeshBuilder().box((0, 0, 0.05), (2.6, 1.4, 0.10))
    skid.build("Skid", mats["steel"], root)
    MeshBuilder().cylinder((-1.0, -0.3, 0.1), 0.18, 0.5, 24, axis="x").cylinder((-0.55, -0.3, 0.1), 0.14, 0.4, 24).build("Pump_30gpm", mats["steel"], root)
    MeshBuilder().cylinder((-0.1, 0.3, 0.1), 0.22, 1.2, 32).build("Filter", mats["stainless"], root)
    MeshBuilder().cylinder((0.6, 0.3, 0.1), 0.28, 1.6, 32).build("IonExchanger_MixedBed", mats["stainless"], root)
    ch = MeshBuilder().box((0.9, -0.3, 0.6), (0.9, 0.6, 1.0))
    ch.build("Chiller_36kBtu", mats["duct"], root)
    # Piping: from skid up, over the pool wall and down into the water (no penetrations below 8 ft above core).
    pipe = MeshBuilder()
    for k, (y, xe) in enumerate(((0.55, 2.8), (0.05, 2.9))):
        pz = 2.2 + 0.12 * k
        pipe.sweep([(0.6, y, 0.1), (0.6, y, pz), (xe, y, pz), (xe, 4.6 - 0.6, pz),
                    (xe, 4.6 - 0.6, D.WATER_SURFACE_Z - 0.6)], 0.03, 12)
    pipe.build("ProcessPiping", mats["stainless"], root)
    MeshBuilder().box((-1.1, 0.5, 1.0), (0.12, 0.10, 0.18)).build("RAM_WaterProcess", mats["steel"], root)
    # Continuous air monitor near the pool.
    MeshBuilder().box((2.6, 0.9, 0.55), (0.5, 0.5, 1.1)).build("CAM", mats["duct"], root)
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
