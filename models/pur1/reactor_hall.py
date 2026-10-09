"""PUR-1 reactor hall (room B70A, Duncan Annex): pool, biological shield, bridge
with the five drives, core, in-pool storage, process loop, HVAC, doors, lights,
and the operator console / video wall in the same room.

Frame: pool centre at x = y = 0, reactor-room floor at z = 0, +X east, +Y north.
"""
from __future__ import annotations

import math

from . import dims as D
from .common import MeshBuilder, box, cylinder, empty, add_light, FT, IN
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
    walls = MeshBuilder()
    walls.box_minmax((x0 - t, y0 - t, 0), (x0, y1 + t, h))      # west
    walls.box_minmax((x1, y0 - t, 0), (x1 + t, y1 + t, h))      # east
    walls.box_minmax((x0, y0 - t, 0), (x1, y0, h))              # south
    walls.box_minmax((x0, y1, 0), (x1, y1 + t, h))              # north
    walls.build("Walls", mats["concrete_block"], root)
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

    # HVAC: HEPA-filtered inlet on the west wall, exhaust duct along the ceiling to a fan at the north wall.
    duct = MeshBuilder()
    duct.box((x0 + 0.45, 3.5, h - 0.9), (0.9, 0.9, 0.9))              # inlet HEPA housing
    duct.box((x0 + 0.45, -3.0, h - 0.9), (0.9, 0.9, 0.9))             # second inlet
    duct.box(((x0 + x1) / 2, y1 - 0.5, h - 0.6), (x1 - x0 - 1.0, 0.5, 0.5))   # exhaust trunk
    duct.box((x1 - 1.0, y1 - 0.5, h - 0.6), (1.1, 1.1, 1.1))          # exhaust fan / HEPA bank
    duct.cylinder((x1 - 1.0, y1 - 0.5, h - 0.05), 0.3, 0.35, 24)      # through-roof stack stub
    duct.build("HVAC_Ducts", mats["duct"], root)

    # High-bay light fixtures (emissive) and render lights.
    fix = MeshBuilder()
    for i, x in enumerate((-2.5, 2.5, 7.0)):
        for y in (-3.5, 3.5):
            fix.cylinder((x, y, h - 0.35), 0.25, 0.08, 24)
            add_light(f"Light_{i}_{y:+.0f}", "POINT", (x, y, h - 0.6), 1500, (1.0, 0.97, 0.9), soft=0.6)
    fix.build("LightFixtures", mats["lamp"], root)

    # Monorail hoist over the pool for fuel/experiment handling.
    rail = MeshBuilder().box((0, 0, h - 0.5), (x1 - x0 - 1.0, 0.18, 0.30))
    rail.box((0.8, 0, h - 0.95), (0.5, 0.5, 0.6))                      # hoist trolley
    rail.cylinder((0.8, 0, D.SHIELD_TOP_Z + 1.6), 0.01, h - 1.25 - D.SHIELD_TOP_Z - 1.6, 8)
    rail.build("MonorailHoist", mats["steel_yellow"], root)
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
    # Above-floor biological shield: 3 ft parapet around the tank, 4 ft thick (assumed).
    MeshBuilder().tube((0, 0, 0), D.SHIELD_OUTER_RADIUS, r + 0.05, D.SHIELD_TOP_Z, 64).build("ShieldWall_AboveFloor", mats["concrete"], root)
    # Steel tank, sand annulus, stainless liner, tank floor.
    MeshBuilder().tube((0, 0, D.TANK_BOTTOM_Z - 0.3), cav, cav - D.TANK_WALL, D.POOL_DEPTH + 0.3, 48).build("OuterSteelTank", mats["steel"], root)
    MeshBuilder().tube((0, 0, D.TANK_BOTTOM_Z - 0.3), cav - D.TANK_WALL, r + 0.012, D.POOL_DEPTH + 0.3, 48).build("SandAnnulus", mats["sand"], root)
    MeshBuilder().tube((0, 0, D.TANK_BOTTOM_Z), r + 0.012, r, D.POOL_DEPTH, 64).build("StainlessLiner", mats["stainless"], root)
    MeshBuilder().cylinder((0, 0, D.TANK_BOTTOM_Z - 0.012), r + 0.012, 0.012, 64).build("TankFloor", mats["stainless"], root)
    # Water column.
    MeshBuilder().cylinder((0, 0, D.TANK_BOTTOM_Z + 0.001), r - 0.002, D.WATER_SURFACE_Z - D.TANK_BOTTOM_Z - 0.001, 64).build("fx_PoolWater", mats["water"], root)

    # Guard rail on the shield deck.
    rail = MeshBuilder()
    rr = D.SHIELD_OUTER_RADIUS - 0.15
    n = 16
    for i in range(n):
        a = 2 * math.pi * i / n
        rail.cylinder((rr * math.cos(a), rr * math.sin(a), D.SHIELD_TOP_Z), 0.02, D.RAIL_HEIGHT, 10)
    rail.torus_ring((0, 0, D.SHIELD_TOP_Z + D.RAIL_HEIGHT), rr, 0.02, 64, 8)
    rail.torus_ring((0, 0, D.SHIELD_TOP_Z + D.RAIL_HEIGHT / 2), rr, 0.015, 64, 8)
    rail.build("GuardRail", mats["steel_yellow"], root)
    # Three steps up to the shield deck on the east (console) side.
    steps = MeshBuilder()
    for i in range(3):
        steps.box_minmax((D.SHIELD_OUTER_RADIUS + 0.9 - 0.3 * i - 0.3, -0.8, 0), (D.SHIELD_OUTER_RADIUS + 0.9 - 0.3 * i, 0.8, D.SHIELD_TOP_Z / 3 * (i + 1)))
    steps.build("ShieldDeck_Steps", mats["concrete"], root)

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
    root = empty("Bridge", (0, 0, 0), parent)
    L = 2 * D.SHIELD_OUTER_RADIUS + 0.4
    bz = D.BRIDGE_Z
    beam = MeshBuilder()
    for y in (-D.BRIDGE_WIDTH / 2, D.BRIDGE_WIDTH / 2):
        beam.box((0, y, bz - 0.15), (L, 0.12, 0.30))          # I-beam web (simplified)
        beam.box((0, y, bz - 0.01), (L, 0.20, 0.02))
        beam.box((0, y, bz - 0.29), (L, 0.20, 0.02))
    beam.box((0, 0, bz + 0.02), (L, D.BRIDGE_WIDTH, 0.04))    # grating deck
    for x in (-L / 2 + 0.3, L / 2 - 0.3):                      # support columns on the shield deck
        for y in (-D.BRIDGE_WIDTH / 2, D.BRIDGE_WIDTH / 2):
            beam.box((x, y, (D.SHIELD_TOP_Z + bz - 0.3) / 2), (0.15, 0.15, bz - 0.3 - D.SHIELD_TOP_Z))
    beam.box((0, 0, bz + 0.04 + 0.5), (L, 0.03, 0.03)).box((0, 0, bz + 0.04 + 1.0), (L, 0.03, 0.03))   # handrails
    beam.build("Bridge_Structure", mats["steel"], root)

    # Drive mechanisms over their core positions. Drive x,y from the lattice; the core is at x=y=0.
    pos = {k: lattice_xy(*v) for k, v in D.CONTROL_POSITIONS.items()}
    sx, sy = lattice_xy(1, 1)
    pos["NS"] = (sx - D.ELEMENT_W / 2 - 0.05, sy - D.ELEMENT_W / 2 - 0.05)
    fx, fy = lattice_xy(5, 5)
    pos["FC"] = (fx + D.ELEMENT_W / 2 + 0.03, fy)
    dw, dd, dh = D.DRIVE_HOUSING
    for name in D.DRIVE_NAMES:
        x, y = pos[name]
        # Drives sit on a pedestal plate on the deck, offset so five housings fit over the small core.
        mb = MeshBuilder()
        mb.box((x, y, bz + 0.04 + dh / 2 + 0.25), (dw * 0.6, dd * 0.6, dh))   # lead-screw / motor column
        mb.box((x, y, bz + 0.04 + dh + 0.25 + 0.12), (dw, dd, 0.24))         # motor head
        mb.cylinder((x, y, bz + 0.04), 0.03, 0.25, 12)                        # stand-off to deck
        ob = mb.build(f"Drive_{name}", mats["steel"], root)
        ob["drive"] = name
    # Pool-top radiation area monitor on the bridge handrail.
    ram = MeshBuilder().box((1.6, D.BRIDGE_WIDTH / 2 + 0.1, bz + 1.1), (0.12, 0.10, 0.18))
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
    # Piping: from skid up, over the parapet and down into the water (no penetrations below 8 ft above core).
    pipe = MeshBuilder()
    def run(p0, p1, r=0.03):
        (x0, y0, z0), (x1, y1, z1) = p0, p1
        if x0 != x1:
            pipe.cylinder((min(x0, x1), y0, z0), r, abs(x1 - x0), 12, axis="x")
        elif y0 != y1:
            pipe.cylinder((x0, min(y0, y1), z0), r, abs(y1 - y0), 12, axis="y")
        else:
            pipe.cylinder((x0, y0, min(z0, z1)), r, abs(z1 - z0), 12)
    # Skid origin is (-3.8, -4.6); the lines drop into the tank at about (-1.0, -0.6) absolute,
    # clearing the guard rail (z 1.98) and the bridge (along x at y = +-0.45).
    for k, (y, xe) in enumerate(((0.55, 2.8), (0.05, 2.9))):
        pz = 2.2 + 0.12 * k
        run((0.6, y, 0.1), (0.6, y, pz))
        run((0.6, y, pz), (xe, y, pz))                      # east, over the parapet
        run((xe, y, pz), (xe, 4.6 - 0.6, pz))               # north to above the water
        run((xe, 4.6 - 0.6, pz), (xe, 4.6 - 0.6, D.WATER_SURFACE_Z - 0.6))   # down into the water
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
