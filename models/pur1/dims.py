"""PUR-1 geometry used by the models, with provenance.

Tag each value: SOURCED (a published number, see docs/pur1_reference.md and the
"PUR-1 Reference Compendium" in the project Drive folder) or ASSUMED (a modelling
choice that no retrievable drawing fixes yet; refine when the SAR drawings
ML111890201 / ML070920272 Fig. 4-1 or the reference photos are in hand).
"""
import math

from .common import FT, IN

# ---- Pool and shield ---------------------------------------------------------
POOL_RADIUS = 4.0 * FT               # SOURCED: 8 ft diameter tank
POOL_DEPTH = 17 * FT + 4 * IN        # SOURCED: 17 ft 4 in deep
TANK_BOTTOM_Z = -15.0 * FT           # SOURCED: tank bottom ~15 ft below reactor-room floor
TANK_TOP_Z = TANK_BOTTOM_Z + POOL_DEPTH   # = +0.71 m above floor (derived)
WATER_SURFACE_Z = TANK_TOP_Z - 4 * IN     # SOURCED: water normally 4 in below tank top
LINER_THICKNESS = 1.0 / 16 * IN      # SOURCED: 1/16 in stainless liner (1968)
TANK_WALL = 0.5 * IN                 # ASSUMED: outer carbon-steel tank wall
SAND_GAP = 0.30                      # ASSUMED: sand-filled annulus between liner tank and steel tank
SHIELD_TOP_Z = 3.0 * FT              # SOURCED: concrete biological shield wall 3 ft above floor
SHIELD_OUTER_RADIUS = 2.0            # ASSUMED from the reference photos: the black-clad pool wall is about 4 m across
SHIELD_BELOW_HALF = 3.5              # ASSUMED: half-width of the square concrete block below floor
POOL_LIP_WIDTH = 0.18                # ASSUMED (photos): grey top lip around the water opening
POOL_STRIPE_WIDTH = 0.10             # ASSUMED (photos): yellow stripe on the outer edge of the top lip
GRAPHIC_ANGLE = math.radians(231)   # ASSUMED (map): the PUR-1 lettering on the SW face of the pool wall

# ---- Core --------------------------------------------------------------------
GRID_PITCH = 3.0 * IN                # ASSUMED: lattice pitch (element footprint ~7 cm + clearance)
GRID_N = 6                           # derived: 4x4 fuel + 20 reflector positions = 6x6 lattice
CORE_N = 4                           # SOURCED: 4 x 4 core array
GRID_PLATE_THICK = 0.075             # ASSUMED: 6061 Al grid plate thickness
GRID_PLATE_Z = TANK_BOTTOM_Z + 0.20  # ASSUMED: grid plate stands on short legs above the tank floor
ELEMENT_W = 0.070                    # SOURCED: element footprint ~7 cm x 7 cm
ACTIVE_LENGTH = 0.6096               # SOURCED: active length 60.96 cm
PLATE_LENGTH = 0.6386                # SOURCED: plate 638.6 mm
PLATE_WIDTH = 0.0702                 # SOURCED: plate 70.2 mm (modelled 66 mm inside the side plates)
PLATE_THICK = 0.00127                # SOURCED: plate 1.27 mm
PLATE_PITCH_STD = 0.00371            # SOURCED: standard assembly pitch 3.71 mm
PLATE_PITCH_CTRL = 0.00500           # SOURCED: control assembly pitch 5.00 mm
PLATES_STD = 14                      # SOURCED: up to 14 plates per standard assembly
PLATES_CTRL = 8                      # SOURCED: up to 8 fuelled plates per control assembly
NOZZLE_LENGTH = 0.10                 # ASSUMED: inlet nozzle below the plates
HANDLE_LENGTH = 0.12                 # ASSUMED: bail/handle above the plates
BLADE_THICK = 0.0048                 # ASSUMED: 3/16 in borated-SS blade
BLADE_WIDTH = 0.060                  # ASSUMED: blade width inside the control-assembly slot
BLADE_LENGTH = 0.70                  # ASSUMED: slightly longer than the active length
ROD_TRAVEL = 0.6412                  # SOURCED: RR upper limit 64.12 cm
# Core positions (row, col) in the 4 x 4, 1-based, rows numbered from the north as on the SAR core
# map: SS1 at 4-4 (SE) per the SAR08 bundle-power table; SS2 NW and RR NE as on the layout map.
CONTROL_POSITIONS = {"SS1": (4, 4), "SS2": (1, 1), "RR": (1, 4)}   # SS1 SOURCED, SS2/RR ASSUMED
IRRADIATION_SIDE = "east"            # ASSUMED: the 6 graphite assemblies with Al tubes (F4-F9) on one side
IRRADIATION_TUBE_R = 0.028           # ASSUMED: tube fits inside the 7 cm can (sources say up to 3.5 in samples)

# ---- Drives and bridge -------------------------------------------------------
BRIDGE_Z = SHIELD_TOP_Z + 0.10       # ASSUMED: bridge deck just above the shield top
BRIDGE_WIDTH = 0.90                  # ASSUMED
BRIDGE_ANGLE = math.radians(135)     # ASSUMED (photos, map): the bridge runs NW-SE across the pool
DRIVE_HOUSING = (0.25, 0.25, 0.80)   # ASSUMED: motor + lead-screw housing size
DRIVE_NAMES = ["SS1", "SS2", "RR", "NS", "FC"]   # SOURCED: five drives

# ---- Room (B70A) -------------------------------------------------------------
# Layout from the project's PUR-1 layout map (maps/pur1_layout_map.png, drawn from the
# reference photos and published documents): pool centre at the origin, +X east, +Y north.
ROOM_X = (-7.2, 4.4)                 # ASSUMED (layout map): about 11.6 m east-west
ROOM_Y = (-5.0, 4.2)                 # ASSUMED (layout map): about 9.2 m north-south
ROOM_H = 7.0                         # ASSUMED: high bay; free volume comfortably > 424 m3 (TS minimum)
WALL_T = 0.30                        # ASSUMED: concrete block
DOOR_W, DOOR_H = 0.9, 2.1            # ASSUMED: personnel doors
MAIN_DOOR_Y = -4.0                   # PLAN (basement floor plan): pair of doors in the east wall near its south end
MAIN_DOOR_W = 1.6                    # PLAN: a pair of leaves swinging into the room, open to the corridor
STORAGE_DOOR_Y = -2.95               # ASSUMED (layout map): storage-room door, west wall
LAB_OPENING_X = (-1.2, 0.4)          # ASSUMED (layout map): opening in the north wall to the adjacent lab
LAB = (-3.6, 1.4, 4.2, 7.9)          # ASSUMED (layout map): adjacent lab x0, x1, y0, y1 (the floor plan puts B70B east of B70A; see basement.py)
LAB_H = 3.0                          # ASSUMED: ordinary ceiling height in the lab
SOFFIT = (-7.2, 0.4, 3.4, 3.3)       # ASSUMED (photos): white bulkhead along the north side: x0, x1, y0, underside z
FLOOR_STRIPE_RADIUS = 2.6            # ASSUMED (photos, map): yellow floor stripe around the pool

# ---- Console, cabinets and video wall ------------------------------------------
CONSOLE_POS = (-3.5, 2.75, 0.0)      # ASSUMED (map, photos): desk console NW of the pool, operator faces north
CONSOLE_FACING = math.pi / 2         # the console is built with the operator facing +X; turn it to face +Y
CONSOLE_SIZE = (0.80, 2.00, 0.74)    # ASSUMED (photos): desk depth x width x height
CONSOLE_MONITORS = 3                 # ASSUMED (photos): three monitors on the desk, one of them the RTP operator display
CARPET = [(-6.0, -1.0, -4.7, 1.2), (-6.0, 1.2, -1.9, 3.35)]   # ASSUMED (map): L-shaped mat under console and cabinets
CABINET_SIZE = (0.80, 0.60, 2.10)    # ASSUMED (photos): black digital I&C cabinets (depth, width, height)
CABINET_COUNT = 4                    # ASSUMED (photos): four cabinets in a row on the operator's left
CABINET_ROW = (-6.2, -0.3)           # ASSUMED (map): first cabinet centre; the row runs north, fronts face east
CABLE_POST = (-2.1, 1.75)            # ASSUMED (map): black cable gantry from the bridge comes down a post here
WALL_DISPLAY_X = -3.0                # ASSUMED (map): wall display on the north wall above the console
DIAG_BENCH_POS = (-1.55, 7.35, 0.0)  # ASSUMED (map): diagnostics bench along the lab's north wall
VIDEO_WALL_CENTER_Y = -0.1           # ASSUMED (map): 4 x 3 video wall on the east wall, y -2.9 .. 2.7
STAIR_ORIGIN = (0.75, 3.25, 0.0)     # ASSUMED (map): stair along the north wall rising east
STAIR_RISE, STAIR_RUN, STAIR_STEPS = 0.19, 0.24, 11   # ASSUMED: 2.1 m platform height
PLATFORM_SIZE = (1.0, 1.35)          # ASSUMED (map): NE platform, x 3.4 .. 4.4, y 2.85 .. 4.2
SKID_POS = (-5.25, -4.4)             # ASSUMED (map): purification skid in the SW corner
VIDEO_WALL_PANEL = (1.44, 0.81)      # ASSUMED: 65 in 16:9 panels
VIDEO_WALL_GRID = (4, 3)             # derived: 12 x 1.17 m2 = 14 m2 = 150 ft2 (SOURCED total area)
VIDEO_WALL_CENTER_Z = 2.3            # ASSUMED
RACK_SIZE = (0.80, 0.60, 2.00)       # ASSUMED: standard 19 in equipment racks (depth, width, height)
RACK_COUNT = 5                       # ASSUMED: RTP 3000, Mirion NI channels, historian, data diode, UPS

# ---- Basement around B70A (floor plan) ---------------------------------------------------------
# From the PUR-1 basement floor plan the project was given (20 ft scale bar = 152 px, so
# 0.0401 m per px). Read with the plan's top as north, which is how the plan's B70A matches the
# reference photos the room model follows (stair along the north wall up to the NE door, storage
# room B72 off the west wall, the main door on the east wall near its south end). The plan's
# north arrow points down and to the right; the model keeps the photo frame, so "north" here
# means the model's +Y.
# The reactor room keeps its photo-based size (11.6 m x 9.2 m; the plan draws it about
# 8.0 m x 11.6 m), so everything below is placed from the main door, at the plan's scale:
# x = 4.7 + (px - 388) * 0.0401, y = -5.0 - (py - 483) * 0.0401.
BASEMENT_H = 3.0                     # ASSUMED: ordinary basement ceiling height (rooms and corridor)
BASEMENT_WALL_T = 0.20               # ASSUMED: interior block walls
# Wall centre lines (m). Corridor along the east side of B70A, running south from the main door.
CORRIDOR_X = (4.6, 7.6)              # PLAN: corridor walls at px 390 / 460, 2.8 m clear
CORRIDOR_HEAD_Y = -2.75              # PLAN: corridor's north end, px 427 (B70B wraps over it)
EAST_WALL_X = 14.8                   # PLAN: east wall of B70B, B86, B85 and B84, px 640
B70B_SOUTH_Y = -5.1                  # PLAN: B70B's south wall east of the corridor, px 485
B86_Y = (-17.4, -11.35)              # PLAN: B86 between px 645 and 792 (south, north wall)
B85_Y = (-23.6, -17.4)               # PLAN: B85 between px 792 and 947
B84_Y = (-29.5, -23.6)               # PLAN: B84 between px 947 and 1095; its north wall ends the corridor
B77_X = 0.5                          # PLAN: B77's west wall, px 285 (its east wall is the corridor's)
B77_Y = (-17.4, -11.35)              # PLAN: B77 level with B86, px 645 .. 790
# Doors: (wall position along the wall, width, leaves). Double doors where the plan draws pairs.
DOOR_B70B = (-3.8, 1.6, 2)           # PLAN: pair in the corridor's east wall, px 432..475, swinging into B70B
DOOR_B86 = (-12.8, 1.6, 2)           # PLAN: pair, px 655..700, swinging into the corridor
DOOR_B85 = (-18.95, 1.6, 2)          # PLAN: pair, px 810..852, swinging into the corridor
DOOR_B77 = (-14.4, 1.4, 2)           # PLAN: pair in the corridor's west wall, px 700..735
DOOR_B84 = (6.3, 1.0, 1)             # PLAN: single door at the corridor's south end, px 410..445
DOOR_B76 = (-8.2, 1.4, 2)            # PLAN: B76 (not modelled inside), closed
DOOR_B87 = (-8.85, 0.9, 1)           # PLAN: B87 (not modelled inside), closed
DOOR_STAIR = (-22.9, 0.9, 1)         # PLAN: toward the south stair and B78..B83 (not modelled), closed
# Subcritical pile in B84: a graphite stack 172.7 cm x 172.7 cm x 203.2 cm (Purdue pile geometry
# table, Instruments 9(2):13, 2025); the plan draws it as a square near the room's middle.
PILE_SIZE = (1.727, 1.727, 2.032)    # SOURCED
PILE_POS = (11.6, -25.6)             # PLAN: square at px 540..580, py 977..1017
PILE_TESTBED = 0.53                  # ASSUMED shape: a cube of ~1.5e5 cm3 (SOURCED volume) let into the top
