"""PUR-1 geometry used by the models, with provenance.

Tag each value: SOURCED (a published number, see docs/pur1_reference.md and the
"PUR-1 Reference Compendium" in the project Drive folder) or ASSUMED (a modelling
choice that no retrievable drawing fixes yet; refine when the SAR drawings
ML111890201 / ML070920272 Fig. 4-1 or the reference photos are in hand).
"""
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
SHIELD_OUTER_RADIUS = 8.0 * FT       # ASSUMED: ~4 ft of concrete around the tank above floor
SHIELD_BELOW_HALF = 3.5              # ASSUMED: half-width of the square concrete block below floor
RAIL_HEIGHT = 42 * IN                # ASSUMED: guard rail on top of the shield (OSHA height)

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
# Lattice positions (row, col), 1-based, SS1 at 4-4 per SAR08 bundle-power table.
CONTROL_POSITIONS = {"SS1": (4, 4), "SS2": (1, 1), "RR": (1, 4)}   # SS1 SOURCED, SS2/RR ASSUMED
IRRADIATION_SIDE = "east"            # ASSUMED: the 6 graphite assemblies with Al tubes (F4-F9) on one side
IRRADIATION_TUBE_R = 0.028           # ASSUMED: tube fits inside the 7 cm can (sources say up to 3.5 in samples)

# ---- Drives and bridge -------------------------------------------------------
BRIDGE_Z = SHIELD_TOP_Z + 0.10       # ASSUMED: bridge deck just above the shield top
BRIDGE_WIDTH = 0.90                  # ASSUMED
DRIVE_HOUSING = (0.25, 0.25, 0.80)   # ASSUMED: motor + lead-screw housing size
DRIVE_NAMES = ["SS1", "SS2", "RR", "NS", "FC"]   # SOURCED: five drives

# ---- Room (B70A) -------------------------------------------------------------
ROOM_X = (-5.0, 9.0)                 # ASSUMED: 14 m east-west
ROOM_Y = (-6.0, 6.0)                 # ASSUMED: 12 m north-south (gross ~168 m2 incl. shield)
ROOM_H = 7.0                         # ASSUMED: high bay; free volume comfortably > 424 m3 (TS minimum)
WALL_T = 0.30                        # ASSUMED: concrete block
DOOR_W, DOOR_H = 1.0, 2.1            # ASSUMED: personnel doors (3) + storage-room door (1)

# ---- Console and video wall --------------------------------------------------
CONSOLE_POS = (5.6, 0.0, 0.0)        # ASSUMED: console east of the pool, operator faces the video wall
CONSOLE_SIZE = (0.95, 2.60, 0.78)    # ASSUMED: depth x width x desk height
VIDEO_WALL_PANEL = (1.44, 0.81)      # ASSUMED: 65 in 16:9 panels
VIDEO_WALL_GRID = (4, 3)             # derived: 12 x 1.17 m2 = 14 m2 = 150 ft2 (SOURCED total area)
VIDEO_WALL_CENTER_Z = 2.3            # ASSUMED
RACK_SIZE = (0.80, 0.60, 2.00)       # ASSUMED: standard 19 in equipment racks (depth, width, height)
RACK_COUNT = 5                       # ASSUMED: RTP 3000, Mirion NI channels, historian, data diode, UPS
