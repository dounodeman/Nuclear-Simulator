"""PUR-1 operator area: the Curtiss-Wright/Mirion digital console (2019), the
150 ft2 video wall, equipment racks, operator chairs and the hallway scram.

PUR-1 has no separate control room: the console stands in the reactor room
(B70A) with the pool in view. `build_control_room()` therefore builds the
console area as a group that `reactor_hall.py` places inside the hall, and the
stand-alone control_room.glb adds just a floor and the east wall around it.

Interactive objects carry a `ui_` prefix and custom properties so the future
control-room interface can find them by name:
  ui_Display_Left / ui_Display_Right     operator workstation panel displays
  ui_VideoWall_r{row}c{col}              12 video-wall tiles
  ui_Scram_Console, ui_Scram_Hallway     manual scram push-buttons
  ui_KeySwitch_Master                    master key switch (also a scram)
  ui_Rod_{SS1,SS2,RR,NS,FC}_{Up,Down}    drive push-buttons
  ui_MagnetPower_Switch                  shim-safety magnet power supply
  ui_Annunciator_{n}                     annunciator window tiles
"""
from __future__ import annotations

from . import dims as D
from .common import MeshBuilder, box, cylinder, empty, FT, IN


def build_console(parent, mats, origin=(0, 0, 0)):
    """Console at `origin` (floor level, centre of the desk footprint); operator faces +X."""
    ox, oy, oz = origin
    root = empty("Console", (ox, oy, oz), parent)
    depth, width, h = D.CONSOLE_SIZE
    out = {"root": root}

    # Desk shell: body, kick space, worktop with a sloped instrument panel at the back.
    body = MeshBuilder()
    body.box((0, 0, h / 2 - 0.02), (depth, width, h - 0.04))
    body.box((0.0, -width / 2 - 0.02, h / 2), (depth - 0.1, 0.04, h))     # end cheeks
    body.box((0.0, width / 2 + 0.02, h / 2), (depth - 0.1, 0.04, h))
    body.build("Console_Body", mats["console"], root)
    top = MeshBuilder().box((0, 0, h + 0.015), (depth + 0.04, width + 0.08, 0.03))
    top.build("Console_Worktop", mats["console_top"], root)
    # Sloped back panel (the "turret"): a wedge made from a box rotated later by the interface is
    # harder for glTF consumers, so build it from explicit vertices.
    px0, px1 = depth / 2 - 0.42, depth / 2        # back 42 cm of the desk
    z0, z1 = h + 0.03, h + 0.03 + 0.34
    wedge = MeshBuilder()
    v = [(px0, -width / 2, z0), (px1, -width / 2, z0), (px1, width / 2, z0), (px0, width / 2, z0),
         (px1 - 0.10, -width / 2, z1), (px1, -width / 2, z1), (px1, width / 2, z1), (px1 - 0.10, width / 2, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    wedge._add(v, f)
    wedge.build("Console_Turret", mats["panel"], root)

    # Two workstation displays (27 in, 16:9) on the turret.
    for side, nm in ((-1, "Left"), (1, "Right")):
        y = side * 0.62
        bez = MeshBuilder().box((px1 - 0.09, y, z1 + 0.22), (0.03, 0.62, 0.37))
        bez.cylinder((px1 - 0.09, y, z1), 0.012, 0.05, 10)
        bez.build(f"Display_{nm}_Bezel", mats["screen_bezel"], root)
        scr = box(f"ui_Display_{nm}", (px1 - 0.105, y, z1 + 0.22), (0.005, 0.598, 0.337), mats["screen"], root)
        scr["role"] = f"workstation_display_{nm.lower()}"

    # Hard-wired controls on the sloped turret face. The face runs from (px0, z0) to (px1 - 0.10, z1);
    # each control sits proud of the face at its own height.
    def face_x(z):
        return px0 + (z - z0) / (z1 - z0) * (px1 - 0.10 - px0)

    def button(name, y, z, mat, r=0.014, role=None):
        ob = cylinder(name, (face_x(z) - 0.02, y, z), r, 0.035, mat, root, 16, axis="x")
        ob["role"] = role or name
        return ob

    def plate(name, y, z, w, h, mat, role):
        ob = box(name, (face_x(z) + 0.004, y, z), (0.006, w, h), mat, root)
        ob["role"] = role
        return ob

    # Scram (red mushroom), master key switch, magnet power supply switch.
    button("ui_Scram_Console", 0.0, z0 + 0.22, mats["button_red"], r=0.03, role="manual_scram")
    button("ui_KeySwitch_Master", -0.14, z0 + 0.22, mats["button_black"], r=0.016, role="master_key_switch")
    button("ui_MagnetPower_Switch", 0.14, z0 + 0.22, mats["button_black"], r=0.016, role="magnet_power_switch")
    # Five drive up/down pairs with a position readout each (left of centre).
    for i, drive in enumerate(D.DRIVE_NAMES):
        y = -0.95 + i * 0.16
        button(f"ui_Rod_{drive}_Up", y, z0 + 0.22, mats["button_green"], role=f"drive_{drive}_up")
        button(f"ui_Rod_{drive}_Down", y, z0 + 0.15, mats["button_black"], role=f"drive_{drive}_down")
        plate(f"ui_Readout_{drive}", y, z0 + 0.07, 0.12, 0.035, mats["screen"], f"drive_{drive}_position")
    # Annunciator tiles (3 rows x 8) right of centre.
    for r in range(3):
        for c in range(8):
            n = r * 8 + c + 1
            plate(f"ui_Annunciator_{n:02d}", 0.34 + c * 0.075, z0 + 0.25 - r * 0.075, 0.068, 0.062,
                  mats["button_amber"] if n in (3, 11) else mats["panel"], f"annunciator_{n}")
    # Keyboard and trackball on the worktop.
    box("Keyboard", (-0.05, -0.62, h + 0.045), (0.16, 0.44, 0.02), mats["panel"], root)
    box("Keyboard_2", (-0.05, 0.62, h + 0.045), (0.16, 0.44, 0.02), mats["panel"], root)
    cylinder("Trackball", (-0.05, -0.30, h + 0.03), 0.03, 0.03, mats["panel"], root, 16)
    # Pool-top / console radiation area monitor on the desk end.
    ram = MeshBuilder().box((0.0, width / 2 + 0.12, h + 0.12), (0.12, 0.10, 0.18))
    ram.cylinder((0.0, width / 2 + 0.12, h + 0.21), 0.01, 0.15, 8)
    out["ram_console"] = ram.build("RAM_Console", mats["steel"], root)

    # Two operator chairs.
    for i, y in enumerate((-0.62, 0.62)):
        _chair(root, mats, (-0.65, y, 0), f"Chair_{i + 1}")
    return out


def _chair(parent, mats, origin, name):
    x, y, z = origin
    mb = MeshBuilder()
    mb.cylinder((x, y, z), 0.03, 0.40, 12)                      # gas lift
    for k in range(5):                                           # star base
        import math
        a = 2 * math.pi * k / 5
        mb.box((x + 0.17 * math.cos(a), y + 0.17 * math.sin(a), z + 0.03), (0.30, 0.04, 0.03))
    mb.build(f"{name}_Base", mats["rack"], parent)
    seat = MeshBuilder().box((x, y, z + 0.47), (0.48, 0.48, 0.08))
    seat.box((x - 0.22, y, z + 0.75), (0.06, 0.46, 0.50))        # backrest
    seat.build(f"{name}_Seat", mats["chair"], parent)


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


def build_racks(parent, mats, origin, count, spacing=None):
    """Row of 19 in equipment racks along a wall, fronts facing -X. origin = centre of first rack footprint."""
    d, w, h = D.RACK_SIZE
    spacing = spacing or w + 0.02
    labels = ["RTP3000_RPS_RCS", "Mirion_NI_Channels", "Historian_Workstation", "DataDiode_Network", "UPS_30min"]
    root = empty("EquipmentRacks", origin, parent)
    for i in range(count):
        y = i * spacing
        rack = MeshBuilder().box((0, y, h / 2), (d, w, h))
        rack.build(f"Rack_{i + 1}_{labels[i % len(labels)]}", mats["rack"], root)
        # Front panel: modules with LEDs.
        front = MeshBuilder()
        for u in range(9):
            front.box((-d / 2 - 0.005, y, 0.15 + u * 0.20), (0.01, w - 0.08, 0.17))
        front.build(f"Rack_{i + 1}_Modules", mats["rack_front"], root)
        leds = MeshBuilder()
        for u in range(9):
            leds.box((-d / 2 - 0.012, y - w / 2 + 0.07, 0.15 + u * 0.20 + 0.05), (0.004, 0.012, 0.012))
        leds.build(f"Rack_{i + 1}_LEDs", mats["led_green"], root)
    return root


def build_control_room(parent, mats):
    """Console + video wall + racks at their positions in the hall frame (pool centre = origin)."""
    out = {}
    out["console"] = build_console(parent, mats, D.CONSOLE_POS)
    wall_inner_x = D.ROOM_X[1]
    out["video_wall"] = build_video_wall(parent, mats, wall_inner_x, D.CONSOLE_POS[1], D.VIDEO_WALL_CENTER_Z)
    d, w, h = D.RACK_SIZE
    out["racks"] = build_racks(parent, mats, (wall_inner_x - d / 2 - 0.05, 3.3, 0.0), D.RACK_COUNT)
    return out


def build_standalone_scene(mats):
    """Floor slab and east wall only, so control_room.glb is self-contained."""
    root = empty("ControlRoom")
    x0, x1 = D.CONSOLE_POS[0] - 3.0, D.ROOM_X[1]
    y0, y1 = -3.5, 6.0
    floor = MeshBuilder().box_minmax((x0, y0, -0.05), (x1, y1, 0.0))
    floor.build("Floor", mats["floor"], root)
    wall = MeshBuilder().box_minmax((x1, y0, 0.0), (x1 + D.WALL_T, y1, 4.5))
    wall.build("Wall_East", mats["concrete_block"], root)
    build_control_room(root, mats)
    return root
