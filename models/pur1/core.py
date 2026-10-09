"""PUR-1 core: grid plate, 13 standard + 3 control MTR assemblies, 20 graphite
reflectors (6 with irradiation tubes), control blades, detectors and source.

build_core(parent, mats, origin) places the core so that the grid plate top is
at `origin[2]`; lattice centre at origin x,y. Returns a dict of key objects.
"""
from __future__ import annotations

from . import dims as D
from .common import MeshBuilder, box, cylinder, empty


def lattice_xy(row: int, col: int, origin=(0.0, 0.0)):
    """Centre of a 6x6 lattice position (1-based, row = +Y north, col = +X east)."""
    off = (D.GRID_N - 1) / 2
    return (origin[0] + (col - 1 - off) * D.GRID_PITCH, origin[1] + (row - 1 - off) * D.GRID_PITCH)


def core_positions():
    """Rows/cols of the 4x4 fuel region inside the 6x6 lattice (2..5)."""
    return [(r, c) for r in range(2, 6) for c in range(2, 6)]


def _assembly_can(mb: MeshBuilder, x, y, z0, h, w=D.ELEMENT_W, t=0.0015):
    """Thin-walled square aluminium can (4 side plates)."""
    mb.box((x - w / 2 + t / 2, y, z0 + h / 2), (t, w, h))
    mb.box((x + w / 2 - t / 2, y, z0 + h / 2), (t, w, h))
    mb.box((x, y - w / 2 + t / 2, z0 + h / 2), (w, t, h))
    mb.box((x, y + w / 2 - t / 2, z0 + h / 2), (w, t, h))


def build_core(parent, mats, origin=(0.0, 0.0, 0.0)):
    ox, oy, oz = origin
    core = empty("Core", (ox, oy, oz), parent)
    out = {"root": core}

    # Grid plate: 6x6 lattice of nozzle holes on a 6061 Al plate.
    span = D.GRID_N * D.GRID_PITCH + 0.05
    gp = MeshBuilder().box((0, 0, -D.GRID_PLATE_THICK / 2), (span, span, D.GRID_PLATE_THICK))
    for i in range(4):   # legs to the tank floor
        sx = -1 if i in (0, 3) else 1
        sy = -1 if i < 2 else 1
        gp.cylinder((sx * span * 0.42, sy * span * 0.42, -(D.GRID_PLATE_Z - D.TANK_BOTTOM_Z)), 0.03, D.GRID_PLATE_Z - D.TANK_BOTTOM_Z, 12)
    out["grid_plate"] = gp.build("GridPlate", mats["aluminum"], core)

    plate_z0 = D.NOZZLE_LENGTH               # plates start above the nozzle
    can_h = D.NOZZLE_LENGTH + D.PLATE_LENGTH + D.HANDLE_LENGTH
    ctrl_lookup = {v: k for k, v in D.CONTROL_POSITIONS.items()}

    for (r, c) in core_positions():
        rel = (r - 1, c - 1)
        x, y = lattice_xy(r, c)
        name = f"{r}-{c}"
        if rel in ctrl_lookup:
            rod = ctrl_lookup[rel]
            _build_control_assembly(core, mats, x, y, name, rod, plate_z0, can_h, out)
        else:
            _build_standard_assembly(core, mats, x, y, name, plate_z0, can_h)

    # Reflector ring: 20 graphite assemblies around the 4x4 core.
    east_col = D.GRID_N
    tube_positions = []
    for r in range(1, D.GRID_N + 1):
        for c in range(1, D.GRID_N + 1):
            if 2 <= r <= 5 and 2 <= c <= 5:
                continue
            x, y = lattice_xy(r, c)
            mb = MeshBuilder()
            _assembly_can(mb, x, y, 0, can_h)
            mb.cylinder((x, y, -0.02), 0.018, D.NOZZLE_LENGTH, 12)   # nozzle
            can = mb.build(f"ReflectorCan_{r}-{c}", mats["aluminum"], core)
            g = MeshBuilder().box((x, y, plate_z0 + D.ACTIVE_LENGTH / 2), (D.ELEMENT_W - 0.004, D.ELEMENT_W - 0.004, D.ACTIVE_LENGTH))
            g.build(f"Graphite_{r}-{c}", mats["graphite"], core)
            if c == east_col:
                tube_positions.append((r, c, x, y))

    # Irradiation facility F4..F9: aluminium tubes in the six east reflectors, reaching the pool top.
    tubes = MeshBuilder()
    for i, (r, c, x, y) in enumerate(tube_positions[:6]):
        tubes.tube((x, y, plate_z0), D.IRRADIATION_TUBE_R, D.IRRADIATION_TUBE_R - 0.002, D.WATER_SURFACE_Z - oz + 0.3 - plate_z0, 20)
    out["irradiation_tubes"] = tubes.build("IrradiationTubes_F4-F9", mats["aluminum"], core)

    # Fixed ion chambers (Log-N CIC, linear UIC, safety UIC) on the west/north/south faces.
    half = D.GRID_N / 2 * D.GRID_PITCH
    chambers = {
        "IonChamber_LogN_CIC": (-half - 0.08, 0.0),
        "IonChamber_Linear_UIC": (0.0, half + 0.08),
        "IonChamber_Safety_UIC": (0.0, -half - 0.08),
    }
    for nm, (x, y) in chambers.items():
        mb = MeshBuilder().cylinder((x, y, plate_z0 + 0.1), 0.03, 0.35, 20)
        mb.cylinder((x, y, plate_z0 + 0.45), 0.012, D.WATER_SURFACE_Z - oz + 0.3 - plate_z0 - 0.45, 10)  # support/cable tube
        out[nm] = mb.build(nm, mats["aluminum_dark"], core)

    # Movable fission chamber (startup channel) in a guide tube attached to the NE fuel element.
    fx, fy = lattice_xy(5, 5)
    fx += D.ELEMENT_W / 2 + 0.03
    mb = MeshBuilder().tube((fx, fy, plate_z0), 0.022, 0.019, D.WATER_SURFACE_Z - oz + 0.3 - plate_z0, 16)
    out["fc_guide"] = mb.build("FissionChamberGuideTube", mats["aluminum"], core)
    fc = cylinder("ui_FissionChamber", (fx, fy, plate_z0 + 0.15), 0.015, 0.25, mats["stainless"], core, 16)
    out["fission_chamber"] = fc

    # Pu-Be startup source in a 6061 Al container outside the core (SW corner), on its own drive.
    sx, sy = lattice_xy(1, 1)
    sx -= D.ELEMENT_W / 2 + 0.05
    sy -= D.ELEMENT_W / 2 + 0.05
    mb = MeshBuilder().tube((sx, sy, plate_z0), 0.03, 0.027, D.WATER_SURFACE_Z - oz + 0.3 - plate_z0, 16)
    out["source_guide"] = mb.build("SourceGuideTube", mats["aluminum"], core)
    out["source"] = cylinder("ui_PuBeSource", (sx, sy, plate_z0 + 0.25), 0.022, 0.12, mats["aluminum_dark"], core, 16)

    # Drop tubes next to the core: 5/8 in and 1.75 in (Al), 3 in PVC, 5 in stainless.
    dx, dy = lattice_xy(6, 1)
    dx += D.GRID_PITCH
    drops = [("DropTube_0.625in", 0.625 / 2 * 0.0254, mats["aluminum"], (dx, dy + 0.10)),
             ("DropTube_1.75in", 1.75 / 2 * 0.0254, mats["aluminum"], (dx, dy + 0.20)),
             ("DropTube_3in_PVC", 1.5 * 0.0254, mats["pvc"], (dx + 0.12, dy + 0.12)),
             ("DropTube_5in_SS", 2.5 * 0.0254, mats["stainless"], (dx + 0.25, dy + 0.30))]
    for nm, rad, mat, (x, y) in drops:
        MeshBuilder().tube((x, y, plate_z0), rad, rad - 0.003, D.WATER_SURFACE_Z - oz + 0.35 - plate_z0, 20).build(nm, mat, core)

    # Cherenkov glow volume for renders / the interface (toggle visibility with power).
    glow = MeshBuilder().box((0, 0, plate_z0 + D.ACTIVE_LENGTH / 2), (D.CORE_N * D.GRID_PITCH + 0.02, D.CORE_N * D.GRID_PITCH + 0.02, D.ACTIVE_LENGTH + 0.1))
    out["cherenkov"] = glow.build("fx_CherenkovGlow", mats["cherenkov"], core)
    return out


def _build_standard_assembly(core, mats, x, y, name, plate_z0, can_h):
    mb = MeshBuilder()
    _assembly_can(mb, x, y, 0, can_h)
    mb.cylinder((x, y, -0.02), 0.018, D.NOZZLE_LENGTH, 12)                  # inlet nozzle into the grid plate
    mb.box((x, y, can_h - 0.02), (D.ELEMENT_W - 0.01, 0.012, 0.012))        # handle bar
    mb.build(f"FuelCan_{name}", mats["aluminum"], core)
    plates = MeshBuilder()
    n = D.PLATES_STD
    x0 = x - (n - 1) / 2 * D.PLATE_PITCH_STD
    for i in range(n):
        plates.box((x0 + i * D.PLATE_PITCH_STD, y, plate_z0 + D.PLATE_LENGTH / 2), (D.PLATE_THICK, D.PLATE_WIDTH - 0.006, D.PLATE_LENGTH))
    plates.build(f"FuelPlates_{name}", mats["aluminum_dark"], core)


def _build_control_assembly(core, mats, x, y, name, rod, plate_z0, can_h, out):
    mb = MeshBuilder()
    _assembly_can(mb, x, y, 0, can_h + 0.25)                               # taller can: blade guide
    mb.cylinder((x, y, -0.02), 0.018, D.NOZZLE_LENGTH, 12)
    mb.build(f"ControlCan_{name}_{rod}", mats["aluminum"], core)
    plates = MeshBuilder()
    n = D.PLATES_CTRL
    gap = D.BLADE_THICK + 2 * 0.004 + 2 * 0.0015      # blade + water gaps + Al guide plates
    half_n = n // 2
    for side in (-1, 1):
        for i in range(half_n):
            px = x + side * (gap / 2 + 0.004 + i * D.PLATE_PITCH_CTRL)
            plates.box((px, y, plate_z0 + D.PLATE_LENGTH / 2), (D.PLATE_THICK, D.PLATE_WIDTH - 0.006, D.PLATE_LENGTH))
        gx = x + side * (gap / 2 - 0.00075)
        plates.box((gx, y, plate_z0 + D.PLATE_LENGTH / 2), (0.0015, D.PLATE_WIDTH - 0.006, D.PLATE_LENGTH))  # Al guide plate
    plates.build(f"FuelPlates_{name}_{rod}", mats["aluminum_dark"], core)
    # Blade: modelled fully inserted; the interface translates `ui_Rod_<name>` in +Z (0 .. ROD_TRAVEL).
    mat = mats["borated_ss"] if rod.startswith("SS") else mats["stainless"]
    blade = MeshBuilder().box((0, 0, D.BLADE_LENGTH / 2), (D.BLADE_THICK, D.BLADE_WIDTH, D.BLADE_LENGTH))
    blade.cylinder((0, 0, D.BLADE_LENGTH), 0.008, D.WATER_SURFACE_Z - D.GRID_PLATE_Z + 0.8 - D.BLADE_LENGTH, 10)  # extension rod to the drive
    ob = blade.build(f"ui_Rod_{rod}", mat, core, location=(x, y, plate_z0))
    ob["rod"] = rod
    ob["travel_m"] = D.ROD_TRAVEL
    out[f"rod_{rod}"] = ob
