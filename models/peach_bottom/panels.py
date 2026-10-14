"""Instrument kit for the GE benchboards: the analog meters, recorders, control switches,
pushbuttons, indicating lights and manual/auto stations of a 1970s BWR/4 control room.

Every instrument is built inside a *face frame*: an empty whose local -X is the panel face
normal (the operator looks along local +X) and whose local +Z is "up" on the panel. On a
vertical panel that is the world frame of the panel; on the sloped bench section the frame is
pitched so that "up" on a control runs away from the operator. Within a frame instruments are
placed by ``r`` (the operator's right, metres, so world y = -r) and ``z`` (up).

Faces the interface draws live (scales, pointers, chart paper, lamps) are meshes named
``ui_<name>`` carrying custom properties the page reads from the glTF extras:

  face     "meter" | "round" | "recorder" | "digital" | "ann" | "core" | "rodselect" | "ma"
  tag      which plant reading the face shows (see pb2world.js TAGS)
  lo, hi   scale ends; unit, legend; red (alarm mark); log (1 for a log scale)
  role     what clicking it does (switches, buttons); label  the hover text
  lamp     the reading that lights a lamp; colour  "red" | "green" | "amber" | "white" | "blue"

The real panels are GE "edgewise" vertical meters in black bezels, round Westinghouse-style
process meters, Bailey/Foxboro M/A stations, GE SB-1 pistol-grip control switches with red
(open/running) and green (closed/stopped) lights above them, and Honeywell/Leeds & Northrup
strip-chart recorders, all on grey-green panels under rows of annunciator windows.
"""
from __future__ import annotations

import math

import bpy

from models.pur1.common import MeshBuilder, empty, flat_text, material

_mats: dict[str, bpy.types.Material] = {}


def mats() -> dict[str, bpy.types.Material]:
    """Materials of the instrument kit (cached per scene; call after reset_scene)."""
    if _mats and _mats["panel"].name in bpy.data.materials:
        return _mats
    _mats.clear()
    _mats.update({
        "panel": material("PB_PanelGreyGreen", (0.52, 0.58, 0.54), rough=0.55),
        "panel_dark": material("PB_PanelTrim", (0.30, 0.33, 0.32), rough=0.5, metal=0.2),
        "bench_top": material("PB_BenchTop", (0.56, 0.60, 0.57), rough=0.5),
        "bezel": material("PB_Bezel", (0.07, 0.07, 0.07), rough=0.45),
        "face": material("PB_MeterFace", (0.93, 0.92, 0.86), rough=0.6),
        "chart": material("PB_ChartPaper", (0.96, 0.95, 0.90), rough=0.7),
        "glass": material("PB_Glass", (0.85, 0.9, 1.0), rough=0.05, alpha=0.18),
        "escutcheon": material("PB_Escutcheon", (0.12, 0.12, 0.13), rough=0.4, metal=0.5),
        "handle": material("PB_HandleBlack", (0.05, 0.05, 0.05), rough=0.5),
        "nameplate": material("PB_Nameplate", (0.12, 0.12, 0.12), rough=0.5),
        "lettering": material("PB_Lettering", (0.95, 0.95, 0.93), rough=0.5),
        "button_red": material("PB_ButtonRed", (0.80, 0.06, 0.04), rough=0.4),
        "button_green": material("PB_ButtonGreen", (0.08, 0.55, 0.18), rough=0.4),
        "button_black": material("PB_ButtonBlack", (0.07, 0.07, 0.07), rough=0.4),
        "button_amber": material("PB_ButtonAmber", (0.90, 0.60, 0.08), rough=0.4),
        "collar_yellow": material("PB_CollarYellow", (0.95, 0.80, 0.10), rough=0.5),
        "lamp_red": material("PB_LampRed", (0.35, 0.05, 0.04), rough=0.3),
        "lamp_green": material("PB_LampGreen", (0.05, 0.25, 0.08), rough=0.3),
        "lamp_amber": material("PB_LampAmber", (0.40, 0.25, 0.04), rough=0.3),
        "lamp_white": material("PB_LampWhite", (0.45, 0.45, 0.42), rough=0.3),
        "lamp_blue": material("PB_LampBlue", (0.06, 0.12, 0.40), rough=0.3),
        "ann_box": material("PB_AnnunciatorBox", (0.22, 0.24, 0.23), rough=0.5, metal=0.2),
        "ann_window": material("PB_AnnunciatorWindow", (0.85, 0.84, 0.78), rough=0.4),
        "led": material("PB_LEDDisplay", (0.06, 0.02, 0.02), rough=0.3),
        "keyswitch": material("PB_KeyChrome", (0.80, 0.80, 0.82), rough=0.25, metal=0.9),
        "thumbwheel": material("PB_Thumbwheel", (0.90, 0.90, 0.88), rough=0.5),
        "floor": material("PB_FloorTile", (0.58, 0.56, 0.52), rough=0.5),
        "wall": material("PB_Wall", (0.84, 0.82, 0.74), rough=0.9),
        "ceiling": material("PB_Ceiling", (0.88, 0.88, 0.86), rough=0.9),
        "fixture": material("PB_LightFixture", (1.0, 1.0, 0.97), emit=(1.0, 1.0, 0.95), emit_strength=4.0),
        "desk": material("PB_DeskWood", (0.42, 0.30, 0.20), rough=0.6),
        "chair": material("PB_Chair", (0.15, 0.17, 0.22), rough=0.9),
        "chrome": material("PB_Chrome", (0.75, 0.76, 0.78), rough=0.3, metal=0.9),
        "cabinet": material("PB_BackPanel", (0.50, 0.56, 0.53), rough=0.55),
        "door": material("PB_Door", (0.45, 0.47, 0.50), rough=0.6, metal=0.2),
        "phone": material("PB_Phone", (0.10, 0.10, 0.10), rough=0.5),
        "paper": material("PB_Paper", (0.95, 0.95, 0.92), rough=0.8),
        "binder": material("PB_Binder", (0.60, 0.15, 0.12), rough=0.7),
    })
    return _mats


def face_frame(name: str, parent, location, pitch: float = 0.0, yaw: float = 0.0):
    """An instrument frame at ``location`` in the parent. ``pitch`` tips the face back (radians;
    pi/2 - slope for a bench), ``yaw`` turns it about the vertical."""
    fr = empty(name, location, parent)
    fr.rotation_euler = (0.0, pitch, yaw)
    return fr


def _props(ob, **props):
    for k, v in props.items():
        if v is not None:
            ob[k] = v
    return ob


def _face_quad(name, frame, r, z, w, h, mat, stand=0.0, **props):
    """A drawn face: a quad of w x h in the frame's y-z plane at x = -stand (proud of the panel)."""
    mb = MeshBuilder()
    v = [(-stand, -r + w / 2, z - h / 2), (-stand, -r - w / 2, z - h / 2),
         (-stand, -r - w / 2, z + h / 2), (-stand, -r + w / 2, z + h / 2)]
    mb._add(v, [(0, 1, 2, 3)])
    ob = mb.build(name, mat, frame)
    return _props(ob, **props)


def nameplate(frame, text, r, z, size=0.012, width=None, mat=None):
    """Black engraved nameplate with white lettering, as on GE panels."""
    m = mats()
    width = width or (len(text) * size * 0.72 + 0.02)
    MeshBuilder().box((-0.002, -r, z), (0.004, width, size + 0.012)).build(
        f"Nameplate_{text[:24].replace(' ', '_')}", mat or m["nameplate"], frame)
    flat_text(f"Lettering_{text[:24].replace(' ', '_')}", text, m["lettering"], (-0.0045, -r, z - size * 0.36),
              math.pi, size, depth=0.0015, parent=frame, resolution=1)


def bezel(frame, name, r, z, w, h, depth=0.025, lip=0.012):
    """Black rectangular meter bezel standing proud of the panel, open at the front."""
    m = mats()
    mb = MeshBuilder()
    # four lips around a recessed face
    mb.box((-depth / 2, -r - w / 2 + lip / 2, z), (depth, lip, h))
    mb.box((-depth / 2, -r + w / 2 - lip / 2, z), (depth, lip, h))
    mb.box((-depth / 2, -r, z + h / 2 - lip / 2), (depth, w - 2 * lip, lip))
    mb.box((-depth / 2, -r, z - h / 2 + lip / 2), (depth, w - 2 * lip, lip))
    mb.box((-0.004, -r, z), (0.008, w, h))  # back plate
    return mb.build(f"Bezel_{name}", m["bezel"], frame, bevel=0.002)


def meter(frame, name, r, z, w=0.07, h=0.17, *, tag, lo=0.0, hi=100.0, unit="", legend="",
          red=None, log=0, kind="meter", label=None):
    """A GE edgewise vertical meter (default) or a round process meter (kind="round")."""
    m = mats()
    bezel(frame, name, r, z, w, h, depth=0.03 if kind == "meter" else 0.04)
    face = _face_quad(f"ui_{name}", frame, r, z, w - 0.024, h - 0.024, m["face"], stand=0.009,
                      face=kind, tag=tag, lo=lo, hi=hi, unit=unit, legend=legend or name, red=red, log=log,
                      label=label or f"{legend or name} meter")
    _face_quad(f"Glass_{name}", frame, r, z, w - 0.02, h - 0.02, m["glass"], stand=0.028)
    return face


def recorder(frame, name, r, z, w=0.30, h=0.36, *, tags, lo, hi, unit="", legend="", colours=None, label=None):
    """A strip-chart recorder: a black case with a chart window and pen indicators. ``tags`` lists
    one to three readings drawn as pens (red, green, blue)."""
    m = mats()
    mb = MeshBuilder()
    mb.box((-0.03, -r, z), (0.06, w, h))
    case = mb.build(f"Recorder_{name}", m["bezel"], frame, bevel=0.003)
    _props(case, label=label or f"{legend or name} recorder")
    face = _face_quad(f"ui_{name}", frame, r, z + 0.01, w - 0.04, h - 0.07, m["chart"], stand=0.062,
                      face="recorder", tag=",".join(tags), lo=lo, hi=hi, unit=unit, legend=legend or name,
                      colours=",".join(colours or ["red", "green", "blue"][:len(tags)]),
                      label=label or f"{legend or name} recorder")
    _face_quad(f"Glass_{name}", frame, r, z + 0.01, w - 0.03, h - 0.06, m["glass"], stand=0.064)
    # chart drive knob and pen-lift lever below the window
    MeshBuilder().cylinder((-0.06, -r + w / 2 - 0.04, z - h / 2 + 0.02), 0.012, 0.015, 16, axis="x").build(
        f"Recorder_{name}_Knob", m["handle"], frame)
    return face


def digital(frame, name, r, z, w=0.12, h=0.045, *, tag, digits=4, unit="", legend="", label=None):
    """Red LED numeric display behind a dark window (rod position, rod select, timers)."""
    m = mats()
    bezel(frame, name, r, z, w, h, depth=0.012, lip=0.006)
    return _face_quad(f"ui_{name}", frame, r, z, w - 0.012, h - 0.012, m["led"], stand=0.004,
                      face="digital", tag=tag, digits=digits, unit=unit, legend=legend or name,
                      label=label or legend or name)


def lamp(frame, name, r, z, colour="red", *, tag, radius=0.011, label=None):
    """Indicating light: a short chrome collar with a coloured lens."""
    m = mats()
    MeshBuilder().cylinder((-0.012, -r, z), radius + 0.004, 0.012, 18, axis="x").build(
        f"Collar_{name}", m["escutcheon"], frame)
    lens = MeshBuilder().cylinder((-0.020, -r, z), radius, 0.008, 18, axis="x").build(
        f"ui_{name}", m[f"lamp_{colour}"], frame)
    return _props(lens, face="lamp", lamp=tag, colour=colour, label=label)


def pushbutton(frame, name, r, z, colour="black", *, role, label, radius=0.011, collar=None, mushroom=False):
    """Momentary pushbutton. A scram button gets a mushroom head on a yellow collar."""
    m = mats()
    MeshBuilder().cylinder((-0.010, -r, z), radius + 0.006, 0.010, 20, axis="x").build(
        f"Ring_{name}", m[collar or "escutcheon"], frame)
    mb = MeshBuilder()
    if mushroom:
        mb.cylinder((-0.016, -r, z), radius * 0.6, 0.016, 20, axis="x")
        mb.sphere((-0.034, -r, z), radius, 20, 10, scale=(0.55, 1, 1))
    else:
        mb.cylinder((-0.022, -r, z), radius, 0.014, 20, axis="x")
    ob = mb.build(f"ui_{name}", m[f"button_{colour}"], frame)
    return _props(ob, role=role, label=label)


def control_switch(frame, name, r, z, *, role, label, positions, tag=None, lights=("red", "green"),
                   light_tags=(), spring=True, radius=0.03):
    """GE SB-1 style pistol-grip control switch: round escutcheon, black handle, with the
    red/green indicating lights above it. ``positions`` names the handle positions left to
    right; ``tag`` is the reading that picks the handle's resting position."""
    m = mats()
    MeshBuilder().cylinder((-0.008, -r, z), radius, 0.008, 28, axis="x").build(
        f"Escutcheon_{name}", m["escutcheon"], frame)
    mb = MeshBuilder()
    mb.cylinder((-0.030, -r, z), 0.010, 0.024, 16, axis="x")                    # shaft
    mb.box((-0.040, -r, z - 0.012), (0.022, 0.016, 0.060))                      # pistol grip, hanging down
    mb.sphere((-0.040, -r, z - 0.044), 0.011, 12, 6)
    ob = mb.build(f"ui_{name}", m["handle"], frame, bevel=0.002)
    _props(ob, role=role, label=label, positions=",".join(positions), tag=tag, spring=1 if spring else 0,
           pivot_z=z, pivot_y=-r)
    if lights:
        n = len(lights)
        for i, (colour, lt) in enumerate(zip(lights, list(light_tags) + [None] * n)):
            lamp(frame, f"{name}_L{i + 1}", r + (i - (n - 1) / 2) * 0.034, z + radius + 0.026, colour, tag=lt or "")
    return ob


def keyswitch(frame, name, r, z, *, role, label, positions, tag):
    """Keylock selector (the reactor mode switch): a big escutcheon with a chrome key barrel."""
    m = mats()
    MeshBuilder().cylinder((-0.010, -r, z), 0.045, 0.010, 32, axis="x").build(
        f"Escutcheon_{name}", m["escutcheon"], frame)
    mb = MeshBuilder()
    mb.cylinder((-0.022, -r, z), 0.014, 0.012, 16, axis="x")
    mb.box((-0.034, -r, z + 0.012), (0.004, 0.006, 0.040))                     # the key
    ob = mb.build(f"ui_{name}", m["keyswitch"], frame)
    return _props(ob, role=role, label=label, positions=",".join(positions), tag=tag, spring=0,
                  pivot_z=z, pivot_y=-r)


def ma_station(frame, name, r, z, *, tag, setpoint_tag, lo, hi, unit, legend, role_up, role_down, role_auto,
               label):
    """Bailey-style manual/auto station: a vertical deviation meter, set point readout, raise and
    lower pushbuttons and an auto/manual button with its lights."""
    m = mats()
    w, h = 0.09, 0.22
    MeshBuilder().box((-0.015, -r, z), (0.03, w, h)).build(f"MA_{name}", m["bezel"], frame, bevel=0.002)
    _face_quad(f"ui_{name}", frame, r, z + 0.045, w - 0.02, 0.11, m["face"], stand=0.032,
               face="ma", tag=tag, lo=lo, hi=hi, unit=unit, legend=legend, setpoint=setpoint_tag, label=label)
    pushbutton(frame, f"{name}_Raise", r - 0.02, z - 0.035, "black", role=role_up, label=f"{legend}: raise", radius=0.008)
    pushbutton(frame, f"{name}_Lower", r + 0.02, z - 0.035, "black", role=role_down, label=f"{legend}: lower", radius=0.008)
    pushbutton(frame, f"{name}_Auto", r, z - 0.075, "black", role=role_auto, label=f"{legend}: auto / manual", radius=0.008)
    lamp(frame, f"{name}_AutoL", r - 0.026, z - 0.075, "green", tag=f"{tag}_auto", radius=0.006)
    lamp(frame, f"{name}_ManL", r + 0.026, z - 0.075, "amber", tag=f"{tag}_manual", radius=0.006)


def thumbwheel(frame, name, r, z, *, tag, digits, legend, role_up, role_down, label):
    """Digital set point thumbwheel with raise/lower buttons beside it."""
    m = mats()
    w = 0.018 * digits + 0.02
    MeshBuilder().box((-0.008, -r, z), (0.016, w + 0.03, 0.045)).build(f"TW_{name}", m["bezel"], frame)
    _face_quad(f"ui_{name}", frame, r, z, w, 0.028, m["thumbwheel"], stand=0.017,
               face="thumbwheel", tag=tag, digits=digits, legend=legend, label=label)
    pushbutton(frame, f"{name}_Up", r - w / 2 - 0.02, z, "black", role=role_up, label=f"{legend}: raise", radius=0.007)
    pushbutton(frame, f"{name}_Down", r + w / 2 + 0.02, z, "black", role=role_down, label=f"{legend}: lower", radius=0.007)


def annunciator_box(parent, name, r, z, w, rows, cols, *, keys, tilt=math.radians(12)):
    """Annunciator window box above a benchboard: ``rows`` x ``cols`` engraved windows, one
    canvas. ``keys`` names the alarm of each window, row by row, left to right ("" = spare)."""
    m = mats()
    h = rows * 0.075 + 0.04
    fr = face_frame(f"AnnFrame_{name}", parent, (0.0, -r, z), pitch=-tilt)
    MeshBuilder().box((0.09, 0, 0), (0.18, w + 0.06, h + 0.05)).build(f"AnnBox_{name}", m["ann_box"], fr, bevel=0.004)
    return _face_quad(f"ui_{name}", fr, 0.0, 0.0, w, h, m["ann_window"], stand=0.002,
                      face="ann", rows=rows, cols=cols, keys="|".join(keys), label=f"Annunciator panel {name[-4:]}")


def core_display(frame, name, r, z, size=0.62):
    """The full core display: a black panel with a 4-digit readout per control rod."""
    m = mats()
    MeshBuilder().box((-0.012, -r, z), (0.024, size + 0.04, size + 0.04)).build(f"Frame_{name}", m["bezel"], frame, bevel=0.003)
    return _face_quad(f"ui_{name}", frame, r, z, size, size, m["led"], stand=0.026,
                      face="core", tag="rod_notch", label="Full core display: control rod positions")


def rod_select_matrix(frame, name, r, z, size=0.40):
    m = mats()
    MeshBuilder().box((-0.010, -r, z), (0.020, size + 0.03, size + 0.03)).build(f"Frame_{name}", m["bezel"], frame, bevel=0.003)
    return _face_quad(f"ui_{name}", frame, r, z, size, size, m["face"], stand=0.022,
                      face="rodselect", tag="rod_select", role="rod_select", label="Rod select matrix: pick a control rod")
