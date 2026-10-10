"""PUR-1 operator area, modelled after the reference photos in the project
Drive folder: a desk-style black console with three monitors and blue chairs on a
carpet mat a few feet from the pool, the 150 ft2 tiled video wall on the east
wall, a row of tall black digital I&C cabinets with red LED readouts, and a
diagnostics bench with monitors and a whiteboard by the south wall.

PUR-1 has no separate control room: the console stands in the reactor room
(B70A) with the pool in view. `build_control_room()` therefore builds the
operator area as a group that `reactor_hall.py` places inside the hall, and the
stand-alone control_room.glb adds just a floor and the east wall around it.

Interactive objects carry a `ui_` prefix and custom properties so the in-hall
interface (reactorsim/app/static/world.js) can find them by name:
  ui_Display_Left / Center / Right       operator workstation monitors
  ui_VideoWall_r{row}c{col}              12 video-wall tiles
  ui_Scram_Console, ui_Scram_Hallway     manual scram push-buttons
  ui_KeySwitch_Master                    master key switch (also a scram)
  ui_Rod_{SS1,SS2,RR,NS,FC}_{Up,Down}    drive push-buttons
  ui_Readout_{drive}                     drive position readouts
  ui_MagnetPower_Switch                  shim-safety magnet power supply
  ui_Annunciator_{n}                     annunciator window tiles
All screens face west (-X), towards the operator.
"""
from __future__ import annotations

import math

from . import dims as D
from . import props
from .common import MeshBuilder, box, cylinder, empty

MONITOR_W, MONITOR_H = 0.54, 0.31      # 24 in 16:9 panel
MONITOR_SPACING = 0.66


def _monitor(parent, mats, name, x_back, y, z_base, w=MONITOR_W, h=MONITOR_H, role=None, stand=True, slim_foot=False):
    """A flat-panel monitor whose screen faces -X (see props.monitor). Console monitors are named
    Display_<side> and their screens ui_Display_<side>; other monitors use `name` for the screen."""
    screen = f"ui_Display_{name.split('_')[-1]}" if name.startswith("Display") else name
    return props.monitor(parent, mats, name, screen, x_back, y, z_base, w, h, role, stand, slim_foot)


def build_console(parent, mats, origin=(0, 0, 0)):
    """Desk console at `origin` (floor level, centre of the desk footprint); operator faces +X."""
    ox, oy, oz = origin
    root = empty("Console", (ox, oy, oz), parent)
    depth, width, h = D.CONSOLE_SIZE
    out = {"root": root}

    # Carpet mat under the console and chairs.
    mw, ml = D.MAT_SIZE
    box("CarpetMat", (-0.45, 0, 0.004), (mw, ml, 0.008), mats["carpet"], root)

    # Black desk: thin top, two pedestals, modesty panel at the back, cable tray.
    desk = MeshBuilder()
    desk.box((0, 0, h - 0.015), (depth, width, 0.03))                                       # top
    for y in (-width / 2 + 0.25, width / 2 - 0.25):
        desk.box((0.05, y, (h - 0.03) / 2), (depth - 0.15, 0.45, h - 0.03))                # pedestals
    desk.box((depth / 2 - 0.03, 0, (h - 0.03) / 2), (0.03, width - 0.9, h - 0.03))         # modesty panel
    desk.build("Console_Desk", mats["desk_black"], root, bevel=0.004)

    # Low hard-wired panel along the back edge of the desk, with a sloped face towards the operator.
    px0, px1 = depth / 2 - 0.26, depth / 2
    z0, z1 = h + 0.0, h + 0.13
    wedge = MeshBuilder()
    v = [(px0, -width / 2, z0), (px1, -width / 2, z0), (px1, width / 2, z0), (px0, width / 2, z0),
         (px1 - 0.08, -width / 2, z1), (px1, -width / 2, z1), (px1, width / 2, z1), (px1 - 0.08, width / 2, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    wedge._add(v, f)
    wedge.build("Console_HardwiredPanel", mats["panel"], root, bevel=0.003)

    def face_x(z):
        return px0 + (z - z0) / (z1 - z0) * (px1 - 0.08 - px0)

    def button(name, y, z, mat, r=0.012, role=None):
        ob = cylinder(name, (face_x(z) - 0.018, y, z), r, 0.03, mat, root, 16, axis="x")
        ob["role"] = role or name
        return ob

    def plate(name, y, z, w, hh, mat, role):
        ob = box(name, (face_x(z) + 0.004, y, z), (0.006, w, hh), mat, root)
        ob["role"] = role
        return ob

    # The operator faces +X, so their left is +Y. Five drive up/down pairs with a position readout
    # each on the right half of the panel, SS1 nearest the centre.
    for i, drive in enumerate(D.DRIVE_NAMES):
        y = -0.26 - i * 0.15
        button(f"ui_Rod_{drive}_Up", y - 0.035, z0 + 0.095, mats["button_green"], role=f"drive_{drive}_up")
        button(f"ui_Rod_{drive}_Down", y + 0.035, z0 + 0.095, mats["button_black"], role=f"drive_{drive}_down")
        plate(f"ui_Readout_{drive}", y, z0 + 0.04, 0.11, 0.032, mats["screen"], f"drive_{drive}_position")
    # Scram (red mushroom), master key switch, magnet power supply switch, in the middle.
    button("ui_Scram_Console", 0.0, z0 + 0.07, mats["button_red"], r=0.03, role="manual_scram")
    button("ui_KeySwitch_Master", -0.12, z0 + 0.07, mats["button_black"], r=0.015, role="master_key_switch")
    button("ui_MagnetPower_Switch", 0.12, z0 + 0.07, mats["button_black"], r=0.015, role="magnet_power_switch")
    # Annunciator tiles (2 rows x 12) on the left half, numbered left to right as the operator reads them.
    for r in range(2):
        for c in range(12):
            n = r * 12 + c + 1
            plate(f"ui_Annunciator_{n:02d}", 0.92 - c * 0.058, z0 + 0.095 - r * 0.055, 0.052, 0.048,
                  mats["button_amber"] if n in (3, 11) else mats["panel"], f"annunciator_{n}")

    # Three monitors on stands behind the panel: Left (reactor control), Center (RTP operator display),
    # Right (plant data). The stands sit on top of the hard-wired panel.
    out["displays"] = {}
    for i, nm in enumerate(("Left", "Center", "Right")):
        y = (1 - i) * MONITOR_SPACING
        out["displays"][nm] = _monitor(root, mats, f"Display_{nm}", px1 + 0.02, y, z1,
                                       role=f"workstation_display_{nm.lower()}", slim_foot=True)
    # Keyboards, mice and the trackball on the worktop.
    props.keyboard(root, mats, "Keyboard", (-0.08, MONITOR_SPACING, h))
    props.keyboard(root, mats, "Keyboard_2", (-0.08, -MONITOR_SPACING, h))
    props.keyboard(root, mats, "Keyboard_3", (-0.08, 0.0, h))
    props.trackball(root, mats, "Trackball", (-0.08, 0.34, h))
    props.mouse(root, mats, "Mouse", (-0.08, -0.34, h), pad_size=(0.20, 0.17))
    # Telephone (left end) and the console radiation monitor (right end) on the desk.
    tel = MeshBuilder().box((0.12, width / 2 - 0.14, h + 0.025), (0.20, 0.18, 0.05))
    tel.box((0.16, width / 2 - 0.14, h + 0.06), (0.06, 0.20, 0.03))                 # handset
    tel.build("Telephone", mats["panel"], root, bevel=0.006)
    ram = MeshBuilder().box((0.12, -width / 2 + 0.12, h + 0.09), (0.12, 0.10, 0.18))
    ram.cylinder((0.12, -width / 2 + 0.12, h + 0.18), 0.01, 0.15, 8)
    out["ram_console"] = ram.build("RAM_Console", mats["steel"], root)

    # Two blue operator chairs.
    for i, y in enumerate((-MONITOR_SPACING, MONITOR_SPACING)):
        props.office_chair(root, mats, (-0.75, y, 0), f"Chair_{i + 1}", facing=0.08 * (1 if y > 0 else -1))
    return out


def build_video_wall(parent, mats, wall_x, center_y, center_z):
    """Grid of panels mounted flush on a wall whose inner face is at x = wall_x (facing -X)."""
    pw, ph = D.VIDEO_WALL_PANEL
    cols, rows = D.VIDEO_WALL_GRID
    root = empty("VideoWall", (wall_x, center_y, center_z), parent)
    frame = MeshBuilder().box((-0.04, 0, 0), (0.08, cols * pw + 0.10, rows * ph + 0.10))
    frame.build("VideoWall_Frame", mats["screen_bezel"], root)
    for r in range(rows):
        for c in range(cols):
            y = (c - (cols - 1) / 2) * pw
            z = ((rows - 1) / 2 - r) * ph
            tile = box(f"ui_VideoWall_r{r + 1}c{c + 1}", (-0.085, y, z), (0.01, pw - 0.01, ph - 0.01), mats["screen"], root)
            tile["role"] = f"video_wall_tile_{r + 1}_{c + 1}"
    return root


CABINET_LABELS = ["RTP3000_RPS_RCS", "Mirion_NI_Channels", "Historian_DataDiode", "UPS_30min"]


def build_cabinets(parent, mats, origin, count, spacing=None, direction=-1):
    """Row of tall black digital I&C cabinets along a wall, fronts facing -X.
    origin = centre of the first cabinet footprint; the row runs along +Y * direction."""
    d, w, h = D.CABINET_SIZE
    spacing = spacing or w + 0.03
    root = empty("ICCabinets", origin, parent)
    for i in range(count):
        y = direction * i * spacing
        name = f"Cabinet_{i + 1}_{CABINET_LABELS[i % len(CABINET_LABELS)]}"
        cab = MeshBuilder().box((0, y, h / 2), (d, w, h))
        cab.box((0, y, h + 0.015), (d + 0.02, w + 0.02, 0.03))                                 # top cap
        cab.build(name, mats["cabinet"], root)
        # Front: a glass door frame with grey plug-in modules behind it, each with a red LED readout.
        front = MeshBuilder()
        leds = MeshBuilder()
        n_mod = 6 if i < 2 else 4
        for u in range(n_mod):
            zc = 0.35 + u * 0.27
            front.box((-d / 2 - 0.004, y, zc), (0.008, w - 0.12, 0.22))
            front.box((-d / 2 - 0.010, y - (w - 0.12) / 2 + 0.03, zc), (0.006, 0.02, 0.20))   # module handle strip
            leds.box((-d / 2 - 0.012, y + 0.08, zc + 0.055), (0.004, 0.14, 0.035))             # red digit readout
            leds.box((-d / 2 - 0.012, y - 0.05, zc - 0.06), (0.004, 0.012, 0.012))             # status LED
        if i == 3:                                                                              # the UPS has a bigger display
            leds.box((-d / 2 - 0.012, y, 1.55), (0.004, 0.22, 0.09))
        front.build(f"Cabinet_{i + 1}_Modules", mats["module_grey"], root)
        leds.build(f"Cabinet_{i + 1}_LEDs", mats["led_red_digits"], root)
        door = MeshBuilder().box((-d / 2 - 0.02, y, h / 2), (0.006, w - 0.05, h - 0.10))
        door.build(f"Cabinet_{i + 1}_GlassDoor", mats["glass"], root)
        frame = MeshBuilder()
        for dy in (-(w - 0.05) / 2, (w - 0.05) / 2):
            frame.box((-d / 2 - 0.02, y + dy, h / 2), (0.02, 0.03, h - 0.10))
        for dz in (0.05, h - 0.05):
            frame.box((-d / 2 - 0.02, y, dz), (0.02, w - 0.05, 0.03))
        frame.build(f"Cabinet_{i + 1}_DoorFrame", mats["cabinet"], root)
    # Cable tray above the row feeding the cabinets.
    tray = MeshBuilder().box((0.0, direction * (count - 1) * spacing / 2, h + 0.30), (0.30, count * spacing, 0.10))
    tray.build("Cabinet_CableTray", mats["conduit"], root)
    return root


def build_diag_bench(parent, mats, origin):
    """Diagnostics bench against the south wall: a blue-legged table with three monitors, a wall monitor,
    a small instrument rack and a whiteboard. The table runs along X; the analyst sits on the north side."""
    ox, oy, oz = origin
    root = empty("DiagBench", (ox, oy, oz), parent)
    length, depth, h = 2.4, 0.76, 0.74
    table = props.work_table(root, mats, "DiagBench", (0, 0, 0), length, depth, h)
    table.rotation_euler = (0, 0, math.pi)          # modesty panel towards the wall (-Y)
    # Three monitors on the bench, screens facing -Y (towards the analyst), built along X then rotated.
    mon = empty("DiagBench_Monitors", (0, 0, 0), root)
    mon.rotation_euler = (0, 0, -math.pi / 2)       # local (x, y) -> world (y, -x): screens (local -X) face world +Y
    for i, dx in enumerate((-0.75, 0.0, 0.75)):
        _monitor(mon, mats, f"DiagBench_Monitor_{i + 1}", 0.30, dx, h, w=0.52, h=0.30)
    for i, dx in enumerate((-0.75, 0.0, 0.75)):
        props.keyboard(root, mats, f"DiagBench_Keyboard_{i + 1}", (dx, 0.08, h), facing=-math.pi / 2)
    props.mouse(root, mats, "DiagBench_Mouse", (0.36, 0.10, h), facing=-math.pi / 2, pad_size=(0.18, 0.20))
    lap = MeshBuilder().box((0.0, 0.0, 0.01), (0.32, 0.22, 0.02))
    lap.box((0.0, -0.11, 0.12), (0.32, 0.012, 0.21))                               # open lid
    lap.build("DiagBench_Laptop", mats["pc_case"], empty("DiagBench_LaptopFrame", (1.0, 0.02, h), root), bevel=0.004)
    for i, dx in enumerate((-1.0, 0.9)):
        props.pc_tower(root, mats, f"DiagBench_PC_{i + 1}", (dx, -0.10, 0), facing=-math.pi / 2)
    # Small instrument rack at the west end of the bench and a wall monitor + whiteboard on the wall behind.
    rk = MeshBuilder().box((-length / 2 - 0.35, 0.0, 0.60), (0.50, 0.55, 1.20))
    rk.build("DiagBench_Rack", mats["rack"], root, bevel=0.006)
    rkm = MeshBuilder()
    for u in range(4):
        rkm.box((-length / 2 - 0.35, -0.28, 0.20 + u * 0.26), (0.46, 0.008, 0.20))
    rkm.build("DiagBench_Rack_Modules", mats["rack_front"], root)
    wall_y = D.ROOM_Y[0]
    dy = wall_y - oy
    wm = empty("DiagBench_WallMonitor", (0, 0, 0), root)
    wm.rotation_euler = (0, 0, -math.pi / 2)
    _monitor(wm, mats, "DiagBench_WallMonitor_1", -dy - 0.02, -0.3, 1.45, w=1.10, h=0.62, stand=False)
    box("Whiteboard", (1.1, dy + 0.02, 1.55), (1.2, 0.02, 0.9), mats["whiteboard"], root)
    box("Whiteboard_Tray", (1.1, dy + 0.04, 1.10), (1.2, 0.05, 0.02), mats["conduit"], root)
    props.office_chair(root, mats, (0.0, 0.75, 0), "DiagBench_Chair", facing=-math.pi / 2, seat_mat="chair_green")
    return root


def build_control_room(parent, mats):
    """Console + video wall + cabinets + diagnostics bench in the hall frame (pool centre = origin)."""
    out = {}
    out["console"] = build_console(parent, mats, D.CONSOLE_POS)
    wall_inner_x = D.ROOM_X[1]
    out["video_wall"] = build_video_wall(parent, mats, wall_inner_x, D.CONSOLE_POS[1], D.VIDEO_WALL_CENTER_Z)
    d, w, h = D.CABINET_SIZE
    out["cabinets"] = build_cabinets(parent, mats, (wall_inner_x - d / 2 - 0.05, D.CABINET_FIRST_Y, 0.0), D.CABINET_COUNT)
    out["diag_bench"] = build_diag_bench(parent, mats, D.DIAG_BENCH_POS)
    return out


def build_standalone_scene(mats):
    """Floor slab, east and south walls only, so control_room.glb is self-contained."""
    root = empty("ControlRoom")
    x0, x1 = D.CONSOLE_POS[0] - 3.0, D.ROOM_X[1]
    y0, y1 = D.ROOM_Y[0], 6.0
    floor = MeshBuilder().box_minmax((x0, y0, -0.05), (x1, y1, 0.0))
    floor.build("Floor", mats["floor"], root)
    wall = MeshBuilder().box_minmax((x1, y0, 0.0), (x1 + D.WALL_T, y1, 4.5))
    wall.box_minmax((x0, y0 - D.WALL_T, 0.0), (x1, y0, 4.5))
    wall.build("Walls", mats["wall_cream"], root)
    build_control_room(root, mats)
    return root
