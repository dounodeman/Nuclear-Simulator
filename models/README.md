# PUR-1 3D models

Scripted Blender models of the PUR-1 reactor hall (room B70A) and its operator
console area, built headlessly with `bpy` so every dimension is a number in a
script that can be corrected when better drawings arrive. The exported `.glb`
files are the assets the future control-room interface will load.

| File | What it is |
| --- | --- |
| `export/reactor_hall.glb` | The whole room: black-clad pool wall with the PUR-1 graphic, bridge with the five drives and their cables, core, in-pool fuel storage, process loop, HVAC, conduit, doors, hoist, stair and platform, console, video wall, I&C cabinets and diagnostics bench |
| `export/control_room.glb` | The operator area alone (desk console with three monitors, hard-wired panel, blue chairs, carpet mat, 4 x 3 video wall, four I&C cabinets, diagnostics bench) on a floor slab with the east and south walls |
| `export/pur1_core.glb` | The core alone: grid plate, 13 standard + 3 control assemblies with plates, 20 graphite reflectors, irradiation tubes, control blades, ion chambers, fission chamber, source, drop tubes |
| `renders/*.png` | Preview renders of each model |

## Build

```bash
pip install bpy                        # Blender as a Python module (4.2 or newer)
python models/build.py                 # export all three .glb files
python models/build.py --render        # also render previews (software GL is fine, a few minutes)
python models/build.py core            # one model
# or, with a Blender install:
blender --background --python models/build.py -- --render
```

Headless rendering needs an EGL-capable Mesa (`apt-get install libegl1 libgl1-mesa-dri`
on Debian/Ubuntu) and `LIBGL_ALWAYS_SOFTWARE=1` when there is no GPU.

## Layout of the code

- `pur1/dims.py` every dimension used, tagged `SOURCED` (a published number) or `ASSUMED` (a modelling choice). Change numbers here, not in the builders.
- `pur1/common.py` scene reset, material palette, a `MeshBuilder` that accumulates boxes, cylinders, tubes and rings into one mesh, export and render helpers.
- `pur1/props.py` furniture and fittings shared by the hall and the console area: office chairs, work tables, keyboards, mice, trackballs, monitors, PC towers, doors with frames, vision glass and hardware, gate valves and flanged pipe runs. Small parts get bevelled edges (a Bevel modifier, applied on export) so they catch the light.
- `pur1/core.py` the core.
- `pur1/control_room.py` desk console, video wall, I&C cabinets, diagnostics bench.
- `pur1/reactor_hall.py` room, pool, shield, bridge and drives, process loop; places the core and the console area.
- `build.py` entry point, cameras and lights for the previews.

The models carry flat colours only. The app adds surface detail when it loads them
(`reactorsim/app/static/textures.js`): painted block, epoxy speckle, carpet and chair fabric,
brushed stainless and aluminium, acoustic ceiling tiles and so on, chosen by material name and
projected in world metres. Keep the material names in `palette()` when renaming.

Frame: pool centre at x = y = 0, reactor-room floor at z = 0, +X east (toward
the console and video wall), +Y north, metres. The glTF exporter rotates to Y up.

## Hooks for the interface

Objects the interface should drive carry a `ui_` prefix and a `role` custom
property (exported as glTF `extras`):

| Object | Role |
| --- | --- |
| `ui_Rod_SS1`, `ui_Rod_SS2`, `ui_Rod_RR` | control blades, modelled fully inserted; translate along the pool axis by 0 to `travel_m` (0.6412 m) |
| `ui_FissionChamber`, `ui_PuBeSource` | the movable startup detector and the source, on their own drives |
| `ui_Display_Left`, `ui_Display_Right` | workstation panel displays (texture targets) |
| `ui_VideoWall_r{1..3}c{1..4}` | the 12 video-wall tiles |
| `ui_Scram_Console`, `ui_Scram_Hallway`, `ui_KeySwitch_Master`, `ui_MagnetPower_Switch` | manual scram paths |
| `ui_Rod_{SS1,SS2,RR,NS,FC}_{Up,Down}`, `ui_Readout_*` | drive push-buttons and position readouts |
| `ui_Annunciator_01..24` | annunciator tiles |
| `fx_CherenkovGlow`, `fx_PoolWater` | emissive glow (scale with power) and the water volume |

## What is sourced and what is assumed

Sourced (SAR 2008/2015, conversion SAR 2006, Technical Specifications, FRS
PUR1-FRS-001, NRC 2015 slides; all collected in the project Drive folder):
8 ft diameter by 17 ft 4 in deep stainless-lined tank, bottom 15 ft below the
room floor, water 4 in below the tank top, 3 ft concrete shield wall above the
floor; 4 x 4 core on an aluminium grid plate with 20 graphite reflectors, six
of them carrying irradiation tubes; plate and assembly dimensions and plate
pitches; SS1 at lattice position 4-4; five drives (SS1, SS2, RR, source,
fission chamber); three fixed ion chambers; fuel storage racks of 2 x 9 with
BORAL; pump, filter, mixed-bed ion exchanger and chiller; three personnel doors
plus a storage-room door; HEPA-filtered inlet and exhaust; a 150 ft2 video wall;
two workstation displays; console, hallway, key-switch and magnet-supply scrams.

Assumed, pending drawings or photos (see `pur1/dims.py`): room size and height,
shield thickness and outer radius, lattice pitch, positions of SS2 and RR, which
side carries the irradiation tubes, bridge and drive-housing geometry, console
size and layout, cabinet count, placement of everything in the room, the hoist, the
stair and platform, and the door locations. The four reference photos in the Drive
"PUR-1 Reference Images" folder fix the look of the pool wall, console, cabinets,
video wall, stair, walls, floor striping and diagnostics bench; the dimensions read
off them are still marked ASSUMED. The building level (ground
floor high bay vs basement) does not affect the room model.

The four reference photos of the real room (pool wall, console, cabinets, video wall,
stair, diagnostics bench) are in the Drive "PUR-1 Reference Images" folder, and the
models follow them; the other reference images could not be downloaded in the build
environment (purdue.edu, nrc.gov and arxiv.org are blocked there), so the core and
in-pool detail still follow the captions and written descriptions in the folder's index.
