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
        "wall_cream": material("WallCream", (0.88, 0.84, 0.70), rough=0.9),
        "floor": material("FloorEpoxy", (0.70, 0.71, 0.70), rough=0.35),
        "floor_stripe": material("FloorStripeYellow", (0.98, 0.80, 0.08), rough=0.4),
        "carpet": material("CarpetMat", (0.22, 0.22, 0.24), rough=1.0),
        "pool_black": material("PoolWallBlack", (0.03, 0.03, 0.035), rough=0.45),
        "pool_lip": material("PoolLipGrey", (0.62, 0.64, 0.65), rough=0.5, metal=0.3),
        "lettering_white": material("LetteringWhite", (0.95, 0.95, 0.93), rough=0.5),
        "lettering_gold": material("LetteringGold", (0.95, 0.72, 0.10), rough=0.5),
        "desk_black": material("DeskBlack", (0.06, 0.06, 0.07), rough=0.45),
        "chair_blue": material("ChairBlue", (0.12, 0.28, 0.58), rough=0.9),
        "cabinet": material("CabinetBlack", (0.05, 0.05, 0.06), rough=0.4, metal=0.3),
        "module_grey": material("ModuleGrey", (0.72, 0.73, 0.72), rough=0.5, metal=0.2),
        "led_red_digits": material("LEDRedDigits", (0.6, 0.02, 0.02), emit=(1.0, 0.05, 0.02), emit_strength=6.0),
        "pipe_green": material("PipeGreen", (0.25, 0.55, 0.35), rough=0.5, metal=0.2),
        "conduit": material("Conduit", (0.75, 0.75, 0.73), rough=0.4, metal=0.5),
        "table_blue": material("TableBlueLegs", (0.20, 0.35, 0.60), rough=0.5, metal=0.3),
        "table_top": material("TableTopWhite", (0.90, 0.90, 0.88), rough=0.5),
        "whiteboard": material("Whiteboard", (0.97, 0.97, 0.97), rough=0.3),
        "ceiling": material("Ceiling", (0.85, 0.85, 0.83), rough=0.9),
        "steel": material("SteelPainted", (0.55, 0.58, 0.60), rough=0.5, metal=0.3),
        "steel_yellow": material("SteelSafetyYellow", (0.95, 0.75, 0.10), rough=0.5, metal=0.2),
        "stainless": material("Stainless", (0.80, 0.81, 0.82), rough=0.25, metal=0.9),
        "aluminum": material("Aluminum6061", (0.86, 0.87, 0.88), rough=0.35, metal=0.8),
        "aluminum_dark": material("AluminumAnodised", (0.55, 0.56, 0.58), rough=0.45, metal=0.7),
        "graphite": material("Graphite", (0.18, 0.18, 0.19), rough=0.8),
        "borated_ss": material("BoratedSS", (0.45, 0.47, 0.50), rough=0.4, metal=0.8),
        "water": material("PoolWater", (0.04, 0.18, 0.28), rough=0.05, alpha=0.72),
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
        "chair": material("ChairFabric", (0.12, 0.28, 0.58), rough=0.9),
        "keycap": material("KeyCap", (0.20, 0.20, 0.22), rough=0.55),
        "mouse": material("MousePlastic", (0.10, 0.10, 0.11), rough=0.35),
        "pc_case": material("PCCase", (0.12, 0.12, 0.13), rough=0.45, metal=0.3),
        "door_glass": material("WiredGlass", (0.16, 0.20, 0.22), rough=0.08, metal=0.2),
        "chair_green": material("ChairGreen", (0.35, 0.62, 0.22), rough=0.8),
        "grating": material("GratingGalv", (0.55, 0.57, 0.58), rough=0.45, metal=0.7),
        "duct_black": material("DuctBlack", (0.05, 0.05, 0.055), rough=0.6, metal=0.3),
        "cable_yellow": material("CableYellow", (0.85, 0.70, 0.10), rough=0.6),
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

    def sweep(self, points, radius, sides=10, bend=0.0, bend_steps=6):
        """Tube of `radius` along a polyline (cables, pipes, conduit, handrails). With `bend` > 0
        every interior corner is rounded with that bend radius, like a pipe elbow."""
        import mathutils
        pts = [mathutils.Vector(p) for p in points]
        if len(pts) < 2:
            return self
        if bend > 0 and len(pts) > 2:
            out = [pts[0]]
            for i in range(1, len(pts) - 1):
                a, p, b = pts[i - 1], pts[i], pts[i + 1]
                d1, d2 = (p - a), (b - p)
                if d1.length < 1e-6 or d2.length < 1e-6 or d1.normalized().dot(d2.normalized()) > 0.999:
                    out.append(p)
                    continue
                r = min(bend, d1.length * 0.45, d2.length * 0.45)
                t1, t2 = p - d1.normalized() * r, p + d2.normalized() * r
                for k in range(bend_steps + 1):          # quadratic Bezier t1 -> p -> t2
                    u = k / bend_steps
                    out.append((1 - u) ** 2 * t1 + 2 * (1 - u) * u * p + u ** 2 * t2)
            out.append(pts[-1])
            pts = out
        rings = []
        for i, p in enumerate(pts):
            t_in = (pts[i] - pts[i - 1]).normalized() if i > 0 else None
            t_out = (pts[i + 1] - pts[i]).normalized() if i < len(pts) - 1 else None
            t = (t_in + t_out).normalized() if (t_in and t_out and (t_in + t_out).length > 1e-6) else (t_out or t_in)
            up = mathutils.Vector((0, 0, 1)) if abs(t.z) < 0.9 else mathutils.Vector((1, 0, 0))
            n1 = t.cross(up).normalized()
            n2 = t.cross(n1).normalized()
            rings.append([tuple(p + radius * (math.cos(a) * n1 + math.sin(a) * n2))
                          for a in (2 * math.pi * k / sides for k in range(sides))])
        base = len(self.verts)
        for r in rings:
            self.verts.extend(r)
        for i in range(len(rings) - 1):
            for k in range(sides):
                l = (k + 1) % sides
                a, b = base + i * sides, base + (i + 1) * sides
                self.faces.append((a + k, a + l, b + l, b + k))
                self.smooth.append(True)
        self.faces.append(tuple(reversed(range(base, base + sides))))
        self.smooth.append(False)
        e = base + (len(rings) - 1) * sides
        self.faces.append(tuple(range(e, e + sides)))
        self.smooth.append(False)
        return self

    def arc_sweep(self, center, radius, z, a0, a1, tube_radius, segments=24, sides=10):
        """Horizontal arc of a tube around `center` (handrails, the pool's striping)."""
        cx, cy = center
        pts = [(cx + radius * math.cos(a0 + (a1 - a0) * i / segments), cy + radius * math.sin(a0 + (a1 - a0) * i / segments), z)
               for i in range(segments + 1)]
        return self.sweep(pts, tube_radius, sides)

    def sphere(self, center, radius, segments=16, rings=8, scale=(1, 1, 1), z_min=-1.0):
        """UV sphere (or ellipsoid with `scale`); `z_min` > -1 cuts it flat below that fraction
        of the radius, for domes such as a mouse or a chair caster."""
        cx, cy, cz = center
        sx, sy, sz = scale
        verts, faces = [], []
        lat0 = math.asin(max(-1.0, min(1.0, z_min)))
        lats = [lat0 + (math.pi / 2 - lat0) * j / rings for j in range(rings + 1)]
        for lat in lats[:-1]:
            for i in range(segments):
                a = 2 * math.pi * i / segments
                verts.append((cx + sx * radius * math.cos(lat) * math.cos(a),
                              cy + sy * radius * math.cos(lat) * math.sin(a), cz + sz * radius * math.sin(lat)))
        top = len(verts)
        verts.append((cx, cy, cz + sz * radius))
        for j in range(rings - 1):
            for i in range(segments):
                k = (i + 1) % segments
                faces.append((j * segments + i, j * segments + k, (j + 1) * segments + k, (j + 1) * segments + i))
        last = (rings - 1) * segments
        for i in range(segments):
            faces.append((last + i, last + (i + 1) % segments, top))
        base = len(self.verts)
        self._add(verts, faces, smooth=True)
        self._add([verts[i] for i in range(segments)], [tuple(reversed(range(segments)))])   # flat bottom
        return self

    def rotate_since(self, mark, pivot, axis, angle):
        """Rotate every vertex added since `len(self.verts) == mark` about `pivot`."""
        import mathutils
        rot = mathutils.Matrix.Rotation(angle, 3, axis.upper())
        pv = mathutils.Vector(pivot)
        for i in range(mark, len(self.verts)):
            self.verts[i] = tuple(rot @ (mathutils.Vector(self.verts[i]) - pv) + pv)
        return self

    def flange(self, center, axis, pipe_radius, thickness=0.02):
        """Pipe flange: a disc about twice the pipe diameter, centred on `center`, normal to `axis`."""
        r = pipe_radius * 2.1
        cx, cy, cz = center
        off = {"x": (cx - thickness / 2, cy, cz), "y": (cx, cy - thickness / 2, cz), "z": (cx, cy, cz - thickness / 2)}[axis]
        return self.cylinder(off, r, thickness, 20, axis=axis)

    def build(self, name: str, mat: bpy.types.Material | None = None, parent=None, location=(0, 0, 0),
              bevel: float = 0.0, bevel_segments: int = 2) -> bpy.types.Object:
        """Make the object. `bevel` rounds every hard edge by that width (applied on export), which
        takes the toy-block look off furniture, doors and electronics."""
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
        if bevel > 0:
            mod = ob.modifiers.new("Bevel", "BEVEL")
            mod.width = bevel
            mod.segments = bevel_segments
            mod.limit_method = "ANGLE"
            mod.angle_limit = math.radians(40)
            mod.use_clamp_overlap = True
            try:
                mod.harden_normals = True
                for poly in mesh.polygons:
                    poly.use_smooth = True
            except AttributeError:
                pass
        return ob


BOLD_FONTS = (   # first one found is used for the wall graphic; Blender's own font otherwise
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)


def _bold_font():
    for path in BOLD_FONTS:
        if os.path.exists(path):
            return bpy.data.fonts.load(path, check_existing=True)
    return None


def _text_mesh(text, size, depth, align="CENTER"):
    curve = bpy.data.curves.new("text_curve", "FONT")
    curve.body = text
    curve.size = size
    curve.extrude = depth / 2
    curve.align_x = align
    curve.align_y = "CENTER"
    curve.resolution_u = 3        # the glyph outlines: enough for 0.5 m letters, far fewer triangles
    font = _bold_font()
    if font:
        curve.font = font
    tmp = bpy.data.objects.new("text_tmp", curve)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(curve)
    return mesh


def text_width(text, size):
    """Width of `text` set in the graphic's font at `size`, in metres."""
    mesh = _text_mesh(text, size, 0.001, "LEFT")
    xs = [v.co.x for v in mesh.vertices]
    bpy.data.meshes.remove(mesh)
    return (max(xs) - min(xs)) if xs else 0.0


def curved_text(name, text, mat, radius, center_angle, z_center, size, depth=0.006, parent=None, align="CENTER"):
    """Lettering wrapped around a vertical cylinder of `radius` about the origin, facing outward,
    at `center_angle` (radians; the start of the text when align="LEFT") and height `z_center`.
    Set in a bold sans (BOLD_FONTS) like the real graphic."""
    import mathutils
    mesh = _text_mesh(text, size, depth, align)
    for v in mesh.vertices:
        x, y, zz = v.co
        a = center_angle + x / radius
        r = radius + zz + depth / 2
        v.co = mathutils.Vector((r * math.cos(a), r * math.sin(a), z_center + y))
    mesh.name = name
    mesh.validate()
    mesh.update()
    mesh.materials.append(mat)
    ob = bpy.data.objects.new(name, mesh)
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
