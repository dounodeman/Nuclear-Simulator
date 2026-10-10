"""Furniture, doors, computer parts and pipe fittings shared by the hall and the console area.

Each builder makes its parts in a local frame and hangs them under an empty placed and turned
in the room, so the same chair or door can stand anywhere. Hard edges are bevelled (see
`MeshBuilder.build(bevel=...)`) and parts that a person would see as separate pieces (a key cap,
a caster, a door handle) are modelled as such, so the props read as real objects up close.
"""
from __future__ import annotations

import math

from .common import MeshBuilder, box, empty


def _frame(parent, name, origin, facing):
    root = empty(name, origin, parent)
    root.rotation_euler = (0, 0, facing)
    return root


# ---------------------------------------------------------------------------------------- chairs
def office_chair(parent, mats, origin, name, facing=0.0, seat_mat="chair_blue"):
    """Task chair: five-star base on casters, gas lift, cushioned seat and back, padded armrests.
    The sitter faces local +X; `facing` turns the chair about Z (0 = facing +X)."""
    root = _frame(parent, name, origin, facing)
    base = MeshBuilder()
    base.cylinder((0, 0, 0.065), 0.055, 0.05, 20)                                 # hub
    for k in range(5):
        a = 2 * math.pi * k / 5 + math.pi / 10
        c, s = math.cos(a), math.sin(a)
        base.sweep([(0.04 * c, 0.04 * s, 0.09), (0.31 * c, 0.31 * s, 0.075)], 0.018, 8)   # leg
        mark = len(base.verts)
        base.box((0.31 * c, 0.31 * s, 0.06), (0.04, 0.03, 0.03))                   # caster fork
        base.rotate_since(mark, (0.31 * c, 0.31 * s, 0.06), "z", a)
        mark = len(base.verts)
        base.cylinder((0.31 * c + 0.012, 0.31 * s - 0.012, 0.026), 0.026, 0.024, 14, axis="y")   # wheel
        base.rotate_since(mark, (0.31 * c, 0.31 * s, 0.026), "z", a)
    base.cylinder((0, 0, 0.09), 0.034, 0.20, 16)                                  # lift sleeve
    base.box((0, 0, 0.405), (0.26, 0.24, 0.03))                                   # tilt mechanism
    base.box((-0.20, 0, 0.42), (0.20, 0.06, 0.03))                                # back support arm
    base.box((-0.29, 0, 0.56), (0.03, 0.06, 0.30))
    for y in (-0.24, 0.24):                                                       # armrest posts
        base.box((-0.02, y, 0.47), (0.08, 0.03, 0.03))
        base.box((0.0, y, 0.58), (0.04, 0.03, 0.22))
        base.box((0.0, y, 0.69), (0.26, 0.07, 0.025))                              # pads
    base.build(f"{name}_Base", mats["rack"], root, bevel=0.006)
    lift = MeshBuilder().cylinder((0, 0, 0.29), 0.022, 0.12, 14)
    lift.build(f"{name}_Lift", mats["stainless"], root)
    seat = MeshBuilder()
    seat.box((0.0, 0, 0.465), (0.48, 0.48, 0.07))                                 # seat cushion
    mark = len(seat.verts)
    seat.box((-0.32, 0, 0.82), (0.07, 0.44, 0.50))                                # back cushion
    seat.rotate_since(mark, (-0.30, 0, 0.56), "y", math.radians(-10))
    seat.build(f"{name}_Seat", mats[seat_mat], root, bevel=0.025, bevel_segments=3)
    return root


# -------------------------------------------------------------------------------------- tables
def work_table(parent, mats, name, center, length, depth, height=0.74, top_mat="table_top", leg_mat="table_blue"):
    """Lab bench: a laminate top with a dark edge band, square-tube legs with levelling feet, side
    rails and a modesty panel at the back (+Y side). Runs along local X."""
    cx, cy, cz = center
    root = empty(name, (cx, cy, cz), parent)
    top = MeshBuilder().box((0, 0, height - 0.016), (length, depth, 0.032))
    top.build(f"{name}_Top", mats[top_mat], root, bevel=0.004)
    edge = MeshBuilder()
    for y in (-depth / 2, depth / 2):
        edge.box((0, y, height - 0.016), (length + 0.004, 0.006, 0.034))
    for x in (-length / 2, length / 2):
        edge.box((x, 0, height - 0.016), (0.006, depth + 0.004, 0.034))
    edge.build(f"{name}_EdgeBand", mats["desk_black"], root)
    legs = MeshBuilder()
    for x in (-length / 2 + 0.05, length / 2 - 0.05):
        for y in (-depth / 2 + 0.05, depth / 2 - 0.05):
            legs.box((x, y, (height - 0.032) / 2 + 0.01), (0.05, 0.05, height - 0.052))
        legs.box((x, 0, height - 0.06), (0.04, depth - 0.1, 0.05))                  # top side rail
        legs.box((x, 0, 0.12), (0.04, depth - 0.1, 0.035))                           # low stretcher
    legs.box((0, depth / 2 - 0.05, height - 0.06), (length - 0.1, 0.04, 0.05))         # back rail
    legs.build(f"{name}_Legs", mats[leg_mat], root, bevel=0.005)
    feet = MeshBuilder()
    for x in (-length / 2 + 0.05, length / 2 - 0.05):
        for y in (-depth / 2 + 0.05, depth / 2 - 0.05):
            feet.cylinder((x, y, 0.0), 0.025, 0.012, 12)
    feet.build(f"{name}_Feet", mats["rack"], root)
    panel = MeshBuilder().box((0, depth / 2 - 0.03, height * 0.55), (length - 0.14, 0.012, height * 0.5))
    panel.build(f"{name}_ModestyPanel", mats[leg_mat], root, bevel=0.003)
    return root


# ----------------------------------------------------------------------------- computer parts
def keyboard(parent, mats, name, center, width=0.44, depth=0.15, facing=0.0):
    """Full-size keyboard: a low wedge case with five rows of key caps and a space bar. The typist
    sits on local -X; rows run along local Y. Returns the case object (pick target)."""
    root = _frame(parent, f"{name}_Frame", center, facing)
    case = MeshBuilder()
    case.box((0, 0, 0.008), (depth, width, 0.016))
    case.box((depth / 2 - 0.02, 0, 0.018), (0.04, width, 0.012))                  # raised back
    ob = case.build(name, mats["panel"], root, bevel=0.003)
    keys = MeshBuilder()
    pitch = 0.019
    cols = int((width - 0.03) / pitch)
    y0 = -(cols - 1) * pitch / 2
    for r in range(5):
        x = depth / 2 - 0.035 - r * pitch
        for c in range(cols):
            keys.box((x, y0 + c * pitch, 0.022), (0.016, 0.016, 0.009))
    x = depth / 2 - 0.035 - 5 * pitch
    keys.box((x, -0.02, 0.022), (0.016, 0.11, 0.009))                             # space bar
    for c in (0, 1, cols - 2, cols - 1):
        keys.box((x, y0 + c * pitch, 0.022), (0.016, 0.016, 0.009))
    keys.build(f"{name}_Keys", mats["keycap"], root)
    return ob


def mouse(parent, mats, name, center, facing=0.0, pad=True, pad_size=(0.20, 0.23)):
    """Two-button mouse on a mouse pad; the cable leaves towards local +X."""
    root = _frame(parent, f"{name}_Frame", center, facing)
    if pad:
        box(f"{name}_Pad", (0, 0, 0.002), (pad_size[0], pad_size[1], 0.004), mats["carpet"], root)
    m = MeshBuilder().sphere((0, 0, 0.004), 0.058, 20, 8, scale=(1.0, 0.56, 0.34), z_min=0.0)
    ob = m.build(name, mats["mouse"], root)
    MeshBuilder().box((0.035, 0, 0.022), (0.04, 0.002, 0.004)).build(f"{name}_ButtonSplit", mats["panel"], root)
    MeshBuilder().sweep([(0.058, 0, 0.01), (0.10, 0, 0.006), (0.14, 0.02, 0.004)], 0.0025, 6).build(
        f"{name}_Cable", mats["hv_cable"], root)
    return ob


def trackball(parent, mats, name, center, facing=0.0):
    """Industrial trackball: a low housing with a large ball and two buttons, as on HMI consoles."""
    root = _frame(parent, f"{name}_Frame", center, facing)
    h = MeshBuilder().box((0, 0, 0.018), (0.13, 0.11, 0.036))
    ob = h.build(name, mats["panel"], root, bevel=0.008)
    MeshBuilder().sphere((0.01, 0, 0.03), 0.026, 18, 9).build(f"{name}_Ball", mats["button_red"], root)
    btn = MeshBuilder()
    for y in (-0.035, 0.035):
        btn.box((-0.045, y, 0.037), (0.03, 0.03, 0.006))
    btn.build(f"{name}_Buttons", mats["keycap"], root, bevel=0.002, bevel_segments=1)
    return ob


def monitor(parent, mats, name, screen_name, x_back, y, z_base, w, h, role=None, stand=True, slim_foot=False):
    """Flat-panel monitor; the screen faces -X. `x_back` is the rear of the stand; `z_base` the
    surface it stands on. The screen is its own thin object (`screen_name`) so the hall can draw on
    it; bezel, back housing and stand are one object named `{name}_Bezel`."""
    zc = z_base + (0.17 if stand else 0.0) + h / 2
    xf = x_back - 0.075                      # front face of the bezel
    mb = MeshBuilder()
    if stand:
        if slim_foot:                                                             # foot for a narrow shelf
            mb.box((x_back - 0.04, y, z_base + 0.006), (0.08, 0.26, 0.012))
        else:
            mb.cylinder((x_back - 0.09, y, z_base), 0.10, 0.012, 28)              # round foot
        mb.box((x_back - 0.03, y, z_base + 0.10), (0.025, 0.06, 0.19))             # neck
        mb.box((x_back - 0.04, y, zc - 0.02), (0.03, 0.10, 0.10))                  # VESA mount
    mb.box((xf + 0.012, y, zc), (0.024, w + 0.026, h + 0.026))                     # bezel
    mb.box((xf + 0.040, y, zc - 0.01), (0.035, w * 0.7, h * 0.65))                 # back housing
    mb.box((xf + 0.002, y, zc - h / 2 - 0.006), (0.004, 0.04, 0.006))              # power LED strip
    mb.build(f"{name}_Bezel", mats["screen_bezel"], parent, bevel=0.004)
    scr = box(screen_name, (xf - 0.001, y, zc), (0.003, w, h), mats["screen"], parent)
    scr["role"] = role or screen_name
    return scr


def pc_tower(parent, mats, name, center, facing=0.0):
    """Desktop PC under a desk: case with a front bezel, drive bay and a green power LED."""
    root = _frame(parent, f"{name}_Frame", center, facing)
    case = MeshBuilder().box((0, 0, 0.22), (0.44, 0.19, 0.44))
    ob = case.build(name, mats["pc_case"], root, bevel=0.006)
    front = MeshBuilder().box((-0.222, 0, 0.22), (0.006, 0.17, 0.42))
    front.build(f"{name}_Bezel", mats["panel"], root, bevel=0.003)
    MeshBuilder().box((-0.226, 0, 0.36), (0.004, 0.13, 0.04)).build(f"{name}_DriveBay", mats["keycap"], root)
    MeshBuilder().box((-0.226, 0.05, 0.40), (0.004, 0.012, 0.012)).build(f"{name}_LED", mats["led_green"], root)
    return ob


# ------------------------------------------------------------------------------------------ doors
def door(parent, mats, name, origin, facing, width, height, wall_t, sign=True):
    """Hollow-metal personnel door in a pressed-steel frame, with a narrow wired-glass vision
    panel, a lever handle, a kick plate, three hinges and an overhead closer. `origin` is the
    door's centre at floor level on the room-side face of the wall; local +Y points into the room,
    local X runs along the wall. The leaf object is named `name`."""
    root = _frame(parent, f"{name}_Assembly", origin, facing)
    fw, fd = 0.06, 0.10                       # frame face width and depth
    fr = MeshBuilder()
    for x in (-width / 2 - fw / 2, width / 2 + fw / 2):
        fr.box((x, fd / 2 - 0.03, (height + fw) / 2), (fw, fd, height + fw))       # jambs
    fr.box((0, fd / 2 - 0.03, height + fw / 2), (width + 2 * fw, fd, fw))          # head
    fr.build(f"{name}_Frame", mats["door_frame"], root, bevel=0.006)
    t = 0.045
    yl = 0.0                                  # leaf centre plane, flush with the frame stop
    leaf = MeshBuilder().box((0, yl, height / 2 + 0.006), (width - 0.006, t, height - 0.012))
    ob = leaf.build(name, mats["door"], root, bevel=0.004)
    # Vision panel on the latch side, with a trim frame.
    vx, vz, vw, vh = width / 2 - 0.26, 1.45, 0.16, 0.62
    MeshBuilder().box((vx, yl, vz), (vw, t + 0.004, vh)).build(f"{name}_Glass", mats["door_glass"], root)
    trim = MeshBuilder()
    for side in (-1, 1):
        y = yl + side * (t / 2 + 0.004)
        trim.box((vx, y, vz + vh / 2 + 0.012), (vw + 0.048, 0.008, 0.024))
        trim.box((vx, y, vz - vh / 2 - 0.012), (vw + 0.048, 0.008, 0.024))
        trim.box((vx - vw / 2 - 0.012, y, vz), (0.024, 0.008, vh))
        trim.box((vx + vw / 2 + 0.012, y, vz), (0.024, 0.008, vh))
    trim.build(f"{name}_GlassTrim", mats["door_frame"], root)
    hw = MeshBuilder()
    for side in (-1, 1):                      # lever handles both sides
        y = yl + side * (t / 2 + 0.004)
        y_out = y if side > 0 else y - 0.057
        hw.cylinder((width / 2 - 0.08, y if side > 0 else y - 0.012, 1.0), 0.032, 0.012, 20, axis="y")  # rose
        hw.cylinder((width / 2 - 0.08, y_out + (0.012 if side > 0 else 0.0), 1.0), 0.012, 0.045, 12, axis="y")
        hw.box((width / 2 - 0.135, y + side * 0.06, 1.0), (0.13, 0.018, 0.022))     # lever
        hw.box((0, y + side * 0.001, 0.14), (width - 0.06, 0.003, 0.26))            # kick plate
    for z in (0.25, height / 2, height - 0.25):                                    # hinges
        hw.cylinder((-width / 2 + 0.005, yl + t / 2, z - 0.06), 0.011, 0.12, 10)
    hw.build(f"{name}_Hardware", mats["stainless"], root)
    closer = MeshBuilder()
    closer.box((-width / 2 + 0.24, yl + t / 2 + 0.03, height - 0.10), (0.30, 0.05, 0.06))
    closer.box((-width / 2 + 0.24, yl + t / 2 + 0.06, height + 0.02), (0.24, 0.015, 0.02))   # arm
    closer.build(f"{name}_Closer", mats["door_frame"], root, bevel=0.005)
    if sign:
        sg = MeshBuilder().box((-0.10, yl + t / 2 + 0.003, 1.55), (0.25, 0.004, 0.18))
        sg.build(f"{name}_Sign", mats["sign_yellow"], root)
        tre = MeshBuilder().cylinder((-0.10, yl + t / 2 + 0.006, 1.57), 0.035, 0.002, 18, axis="y")
        tre.build(f"{name}_SignTrefoil", mats["sign_magenta"], root)
    return ob


# ----------------------------------------------------------------------------------- pipe fittings
def gate_valve(body, wheel, center, axis, pipe_r):
    """Flanged gate valve on a horizontal pipe along `axis` ('x' or 'y'): body, flanges, bonnet,
    rising stem and a handwheel with spokes. Adds to the `body` and `wheel` builders."""
    cx, cy, cz = center
    L = 0.18
    start = (cx - L / 2, cy, cz) if axis == "x" else (cx, cy - L / 2, cz)
    body.cylinder(start, pipe_r * 2.0, L, 20, axis=axis)
    for d in (-L / 2, L / 2):
        p = (cx + d, cy, cz) if axis == "x" else (cx, cy + d, cz)
        body.flange(p, axis, pipe_r, 0.025)
    body.cylinder((cx, cy, cz), pipe_r * 1.3, 0.16, 16)                          # bonnet
    body.cylinder((cx, cy, cz + 0.16), pipe_r * 1.8, 0.025, 16)                   # bonnet flange
    body.cylinder((cx, cy, cz + 0.185), 0.008, 0.10, 8)                           # stem
    zw = cz + 0.26
    wheel.torus_ring((cx, cy, zw), 0.08, 0.009, 32, 8)
    wheel.cylinder((cx, cy, zw - 0.015), 0.018, 0.03, 12)                         # hub
    for a in (0.0, math.pi / 2):
        mark = len(wheel.verts)
        wheel.box((cx, cy, zw), (0.16, 0.012, 0.012))
        wheel.rotate_since(mark, (cx, cy, zw), "z", a)
    return body, wheel


def pipe_with_fittings(pipe, flanges, points, r, bend=0.12, flange_ends=True):
    """A pipe run with rounded elbows and a flange at each end where it meets equipment."""
    pipe.sweep(points, r, 14, bend=bend)
    if flange_ends:
        for p, q in ((points[0], points[1]), (points[-1], points[-2])):
            d = [abs(a - b) for a, b in zip(p, q)]
            axis = "xyz"[d.index(max(d))]
            flanges.flange(p, axis, r)
    return pipe
