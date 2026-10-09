"""Shared helpers for the scripted (headless bpy) PUR-1 models.

Everything is built from explicit vertex/face lists so the scripts run the same
in `blender --background --python` and in the `bpy` pip wheel, without any
operator or UI context. Units are metres, Z up. The glTF exporter converts to
the Y-up convention the web viewers expect.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

import bpy

IN = 0.0254   # inch to metre
FT = 0.3048   # foot to metre


# ----------------------------------------------------------------------------
# Scene
# ----------------------------------------------------------------------------
def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    _MATERIALS.clear()


def empty(name: str, location=(0, 0, 0), parent: bpy.types.Object | None = None) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = "PLAIN_AXES"
    ob.empty_display_size = 0.2
    ob.location = location
    ob.parent = parent
    bpy.context.scene.collection.objects.link(ob)
    return ob


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------
_MATERIALS: dict[str, bpy.types.Material] = {}


def material(name: str, rgb, *, rough=0.6, metal=0.0, alpha=1.0, emit=None, emit_strength=0.0) -> bpy.types.Material:
    """Create (or reuse) a Principled BSDF material."""
    if name in _MATERIALS:
        return _MATERIALS[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    r, g, b = rgb
    bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Alpha"].default_value = alpha
    if emit is not None:
        er, eg, eb = emit
        bsdf.inputs["Emission Color"].default_value = (er, eg, eb, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit_strength
    if alpha < 1.0:
        # EEVEE Next (4.2+) and legacy both honour one of these.
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
        if hasattr(mat, "blend_method"):
            try:
                mat.blend_method = "BLEND"
            except Exception:
                pass
        mat.use_backface_culling = False
    mat.diffuse_color = (r, g, b, alpha)
    _MATERIALS[name] = mat
    return mat


def palette() -> dict[str, bpy.types.Material]:
    """The material set shared by all three models (one place to retune)."""
    return {
        "concrete": material("Concrete", (0.62, 0.61, 0.58), rough=0.95),
        "concrete_block": material("ConcreteBlock", (0.78, 0.77, 0.72), rough=0.95),
        "floor": material("FloorEpoxy", (0.45, 0.47, 0.50), rough=0.35),
        "ceiling": material("Ceiling", (0.85, 0.85, 0.83), rough=0.9),
        "steel": material("SteelPainted", (0.55, 0.58, 0.60), rough=0.5, metal=0.3),
        "steel_yellow": material("SteelSafetyYellow", (0.95, 0.75, 0.10), rough=0.5, metal=0.2),
        "stainless": material("Stainless", (0.80, 0.81, 0.82), rough=0.25, metal=0.9),
        "aluminum": material("Aluminum6061", (0.86, 0.87, 0.88), rough=0.35, metal=0.8),
        "aluminum_dark": material("AluminumAnodised", (0.55, 0.56, 0.58), rough=0.45, metal=0.7),
        "graphite": material("Graphite", (0.18, 0.18, 0.19), rough=0.8),
        "borated_ss": material("BoratedSS", (0.45, 0.47, 0.50), rough=0.4, metal=0.8),
        "water": material("PoolWater", (0.10, 0.45, 0.75), rough=0.05, alpha=0.30),
        "cherenkov": material("Cherenkov", (0.2, 0.5, 1.0), alpha=0.35, emit=(0.25, 0.55, 1.0), emit_strength=8.0),
        "pvc": material("PVCWhite", (0.92, 0.92, 0.90), rough=0.5),
        "door": material("DoorGrey", (0.50, 0.52, 0.55), rough=0.6, metal=0.2),
        "door_frame": material("DoorFrame", (0.30, 0.31, 0.33), rough=0.6, metal=0.3),
        "duct": material("Duct", (0.70, 0.72, 0.74), rough=0.4, metal=0.6),
        "console": material("ConsoleShell", (0.22, 0.24, 0.27), rough=0.5),
        "console_top": material("ConsoleTop", (0.85, 0.85, 0.84), rough=0.4),
        "panel": material("PanelDark", (0.12, 0.13, 0.15), rough=0.5),
        "screen": material("Screen", (0.05, 0.06, 0.08), rough=0.2, emit=(0.35, 0.55, 0.80), emit_strength=1.2),
        "screen_bezel": material("ScreenBezel", (0.05, 0.05, 0.05), rough=0.5),
        "button_red": material("ButtonRed", (0.85, 0.08, 0.05), rough=0.4),
        "button_green": material("ButtonGreen", (0.10, 0.70, 0.20), rough=0.4),
        "button_black": material("ButtonBlack", (0.08, 0.08, 0.08), rough=0.4),
        "button_amber": material("ButtonAmber", (0.95, 0.65, 0.10), rough=0.4),
        "lamp": material("Lamp", (1.0, 1.0, 1.0), emit=(1.0, 1.0, 0.95), emit_strength=5.0),
        "chair": material("ChairFabric", (0.15, 0.16, 0.20), rough=0.9),
        "rack": material("Rack", (0.18, 0.19, 0.21), rough=0.5, metal=0.3),
        "rack_front": material("RackFront", (0.35, 0.36, 0.38), rough=0.5, metal=0.4),
        "led_green": material("LEDGreen", (0.1, 1.0, 0.2), emit=(0.1, 1.0, 0.2), emit_strength=4.0),
        "led_red": material("LEDRed", (1.0, 0.1, 0.1), emit=(1.0, 0.1, 0.1), emit_strength=4.0),
        "sand": material("Sand", (0.76, 0.70, 0.50), rough=1.0),
        "lead": material("Lead", (0.40, 0.41, 0.43), rough=0.7, metal=0.6),
        "hv_cable": material("Cable", (0.1, 0.1, 0.1), rough=0.8),
        "glass": material("Glass", (0.8, 0.9, 1.0), rough=0.05, alpha=0.2),
        "sign_yellow": material("SignYellow", (1.0, 0.85, 0.0), rough=0.6),
        "sign_magenta": material("SignMagenta", (0.75, 0.0, 0.55), rough=0.6),
    }


# ----------------------------------------------------------------------------
# Mesh builder
# ----------------------------------------------------------------------------
@dataclass
class MeshBuilder:
    """Accumulates boxes / cylinders / tubes into one mesh (one draw call in glTF)."""

    verts: list = field(default_factory=list)
    faces: list = field(default_factory=list)
    smooth: list = field(default_factory=list)

    def _add(self, verts, faces, smooth=False):
        base = len(self.verts)
        self.verts.extend(verts)
        self.faces.extend([tuple(base + i for i in f) for f in faces])
        self.smooth.extend([smooth] * len(faces))
        return self

    def box(self, center, size):
        cx, cy, cz = center
        sx, sy, sz = (s / 2 for s in size)
        v = [(cx - sx, cy - sy, cz - sz), (cx + sx, cy - sy, cz - sz), (cx + sx, cy + sy, cz - sz), (cx - sx, cy + sy, cz - sz),
             (cx - sx, cy - sy, cz + sz), (cx + sx, cy - sy, cz + sz), (cx + sx, cy + sy, cz + sz), (cx - sx, cy + sy, cz + sz)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        return self._add(v, f)

    def box_minmax(self, lo, hi):
        c = tuple((a + b) / 2 for a, b in zip(lo, hi))
        s = tuple(b - a for a, b in zip(lo, hi))
        return self.box(c, s)

    def cylinder(self, center_bottom, radius, height, segments=32, axis="z", cap=True):
        """Solid cylinder; axis 'z' (default), 'x' or 'y'."""
        cx, cy, cz = center_bottom
        ring_b, ring_t = [], []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            u, w = radius * math.cos(a), radius * math.sin(a)
            if axis == "z":
                ring_b.append((cx + u, cy + w, cz)); ring_t.append((cx + u, cy + w, cz + height))
            elif axis == "x":
                ring_b.append((cx, cy + u, cz + w)); ring_t.append((cx + height, cy + u, cz + w))
            else:
                ring_b.append((cx + u, cy, cz + w)); ring_t.append((cx + u, cy + height, cz + w))
        verts = ring_b + ring_t
        faces = []
        for i in range(segments):
            j = (i + 1) % segments
            faces.append((i, j, segments + j, segments + i))
        self._add(verts, faces, smooth=True)
        if cap:
            self._add(ring_b, [tuple(reversed(range(segments)))])
            self._add(ring_t, [tuple(range(segments))])
        return self

    def tube(self, center_bottom, r_outer, r_inner, height, segments=48):
        """Hollow cylinder with annular caps (shield walls, pool liner, pipes)."""
        cx, cy, cz = center_bottom
        outer_b, outer_t, inner_b, inner_t = [], [], [], []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            c, s = math.cos(a), math.sin(a)
            outer_b.append((cx + r_outer * c, cy + r_outer * s, cz)); outer_t.append((cx + r_outer * c, cy + r_outer * s, cz + height))
            inner_b.append((cx + r_inner * c, cy + r_inner * s, cz)); inner_t.append((cx + r_inner * c, cy + r_inner * s, cz + height))
        n = segments
        verts = outer_b + outer_t + inner_b + inner_t
        faces = []
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, n + j, n + i))                       # outer wall
            faces.append((2 * n + j, 2 * n + i, 3 * n + i, 3 * n + j))  # inner wall (flipped)
            faces.append((n + i, n + j, 3 * n + j, 3 * n + i))       # top annulus
            faces.append((j, i, 2 * n + i, 2 * n + j))               # bottom annulus
        return self._add(verts, faces, smooth=True)

    def torus_ring(self, center, radius, thickness, segments=48, sides=8):
        cx, cy, cz = center
        verts, faces = [], []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            for k in range(sides):
                b = 2 * math.pi * k / sides
                rr = radius + thickness * math.cos(b)
                verts.append((cx + rr * math.cos(a), cy + rr * math.sin(a), cz + thickness * math.sin(b)))
        for i in range(segments):
            j = (i + 1) % segments
            for k in range(sides):
                l = (k + 1) % sides
                faces.append((i * sides + k, j * sides + k, j * sides + l, i * sides + l))
        return self._add(verts, faces, smooth=True)

    def build(self, name: str, mat: bpy.types.Material | None = None, parent=None, location=(0, 0, 0)) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(self.verts, [], self.faces)
        mesh.validate()
        mesh.update()
        for poly, sm in zip(mesh.polygons, self.smooth):
            poly.use_smooth = sm
        if mat is not None:
            mesh.materials.append(mat)
        ob = bpy.data.objects.new(name, mesh)
        ob.location = location
        ob.parent = parent
        bpy.context.scene.collection.objects.link(ob)
        return ob


def box(name, center, size, mat, parent=None):
    return MeshBuilder().box(center, size).build(name, mat, parent)


def cylinder(name, center_bottom, radius, height, mat, parent=None, segments=32, axis="z"):
    return MeshBuilder().cylinder(center_bottom, radius, height, segments, axis).build(name, mat, parent)


# ----------------------------------------------------------------------------
# Lights, cameras, export, render
# ----------------------------------------------------------------------------
def add_light(name, kind, location, energy, color=(1, 1, 1), size=1.0, rotation=(0, 0, 0), soft=0.25):
    data = bpy.data.lights.new(name, kind)
    data.energy = energy
    data.color = color
    if hasattr(data, "shadow_soft_size"):
        data.shadow_soft_size = soft
    if kind == "AREA":
        data.size = size
    ob = bpy.data.objects.new(name, data)
    ob.location = location
    ob.rotation_euler = rotation
    bpy.context.scene.collection.objects.link(ob)
    return ob


def add_camera(name, location, look_at, lens=28.0):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_end = 200
    ob = bpy.data.objects.new(name, cam)
    ob.location = location
    bpy.context.scene.collection.objects.link(ob)
    import mathutils
    direction = mathutils.Vector(look_at) - mathutils.Vector(location)
    ob.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return ob


def export_glb(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Cameras and lights are kept out of the asset; the interface adds its own.
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_apply=True,
                              export_cameras=False, export_lights=False, export_yup=True)
    print(f"exported {path} ({os.path.getsize(path) / 1024:.0f} kB)")


def render(path: str, camera: bpy.types.Object, width=1280, height=720, samples=24) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scene = bpy.context.scene
    scene.camera = camera
    scene.render.engine = "BLENDER_EEVEE"
    if hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = samples
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    scene.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in scene.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.05, 0.05, 0.06, 1)
        bg.inputs[1].default_value = 0.6
    bpy.ops.render.render(write_still=True)
    print(f"rendered {path}")
