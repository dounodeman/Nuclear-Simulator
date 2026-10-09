"""Build the PUR-1 3D models headlessly and export glTF (.glb) plus preview renders.

Usage (from the repo root, with the `bpy` wheel or Blender's bundled Python):

    pip install bpy            # Blender as a Python module (4.2+ / 5.x)
    python models/build.py                 # all three models, export only
    python models/build.py --render        # also render previews to models/renders/
    python models/build.py reactor_hall    # one model

or with a Blender install:

    blender --background --python models/build.py -- --render

Outputs: models/export/{reactor_hall,control_room,pur1_core}.glb
         models/renders/*.png (with --render)
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from models.pur1 import dims as D  # noqa: E402
from models.pur1.common import add_camera, add_light, export_glb, palette, render, reset_scene, empty  # noqa: E402

EXPORT = os.path.join(HERE, "export")
RENDERS = os.path.join(HERE, "renders")


def build_reactor_hall(do_render: bool, quality: int):
    from models.pur1.reactor_hall import build_reactor_hall
    reset_scene()
    mats = palette()
    build_reactor_hall(mats)
    export_glb(os.path.join(EXPORT, "reactor_hall.glb"))
    if do_render:
        cam = add_camera("Cam_Overview", (-4.4, -5.4, 5.2), (2.5, 0.5, 0.8), lens=22)
        render(os.path.join(RENDERS, "reactor_hall_overview.png"), cam, samples=quality)
        cam = add_camera("Cam_PoolTop", (0.6, -2.6, 5.0), (0.0, 0.2, -3.5), lens=24)
        render(os.path.join(RENDERS, "reactor_hall_pool_top.png"), cam, samples=quality)
        cam = add_camera("Cam_Console", (2.6, -3.2, 2.1), (6.8, 0.3, 1.5), lens=24)
        render(os.path.join(RENDERS, "reactor_hall_console.png"), cam, samples=quality)


def build_control_room(do_render: bool, quality: int):
    from models.pur1.control_room import build_standalone_scene
    reset_scene()
    mats = palette()
    build_standalone_scene(mats)
    export_glb(os.path.join(EXPORT, "control_room.glb"))
    if do_render:
        add_light("Key", "AREA", (4.5, -2.0, 3.8), 1500, size=3.0, rotation=(0.6, 0.0, 0.0))
        add_light("Fill", "POINT", (6.5, 2.5, 3.5), 800)
        cx, cy, cz = D.CONSOLE_POS
        cam = add_camera("Cam_Console", (cx - 3.0, cy - 2.6, 2.1), (cx + 1.2, cy + 0.3, 1.4), lens=24)
        render(os.path.join(RENDERS, "control_room_console.png"), cam, samples=quality)
        cam = add_camera("Cam_Operator", (cx - 1.1, cy - 0.3, 1.45), (cx + 2.4, cy, 1.9), lens=20)
        render(os.path.join(RENDERS, "control_room_operator_view.png"), cam, samples=quality)
        cam = add_camera("Cam_Turret", (cx - 1.0, cy - 0.5, 1.45), (cx + 0.3, cy - 0.3, 0.95), lens=35)
        render(os.path.join(RENDERS, "control_room_controls.png"), cam, samples=quality)


def build_core(do_render: bool, quality: int):
    from models.pur1.core import build_core as _core
    reset_scene()
    mats = palette()
    root = empty("PUR1_Core")
    _core(root, mats, (0.0, 0.0, 0.0))
    # Trim the long guide tubes for the stand-alone asset: keep them 1 m tall.
    import bpy
    for ob in bpy.data.objects:
        if ob.type == "MESH" and ("Tube" in ob.name or "Guide" in ob.name or "ui_Rod" in ob.name or "IonChamber" in ob.name):
            for v in ob.data.vertices:
                if v.co.z > 1.2:
                    v.co.z = 1.2
    export_glb(os.path.join(EXPORT, "pur1_core.glb"))
    if do_render:
        add_light("Key", "AREA", (1.5, -1.5, 2.0), 400, size=2.0, rotation=(0.8, 0.0, 0.8))
        add_light("Fill", "POINT", (-1.5, 1.0, 1.0), 150)
        cam = add_camera("Cam_Core", (1.7, -2.1, 1.5), (0.0, 0.0, 0.4), lens=35)
        render(os.path.join(RENDERS, "core_isometric.png"), cam, samples=quality)
        cam = add_camera("Cam_CoreTop", (0.0, -0.25, 2.4), (0.0, 0.0, 0.3), lens=35)
        render(os.path.join(RENDERS, "core_top.png"), cam, samples=quality)


TARGETS = {"reactor_hall": build_reactor_hall, "control_room": build_control_room, "core": build_core}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*", default=list(TARGETS), choices=list(TARGETS))
    ap.add_argument("--render", action="store_true", help="render preview PNGs (slow without a GPU)")
    ap.add_argument("--quality", type=int, default=24, help="EEVEE samples for renders")
    args = ap.parse_args(argv)
    for t in args.targets:
        print(f"== building {t}")
        TARGETS[t](args.render, args.quality)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(argv)
