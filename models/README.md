# PUR-1 3D models

Scripted Blender models of the PUR-1 reactor hall (room B70A) and its operator
console area, built headlessly with `bpy` so every dimension is a number in a
script that can be corrected when better drawings arrive. The exported `.glb`
files are the assets the future control-room interface will load.

| File | What it is |
| --- | --- |
| `export/reactor_hall.glb` | The whole room: pool and biological shield, bridge with the five drives, core, in-pool fuel storage, process loop, HVAC, doors, hoist, console, video wall and racks |
| `export/control_room.glb` | The console area alone (console, two displays, hard-wired controls, chairs, 4 x 3 video wall, equipment racks) on a floor slab with the east wall |
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
- `pur1/core.py` the core.
- `pur1/control_room.py` console, video wall, racks.
- `pur1/reactor_hall.py` room, pool, shield, bridge and drives, process loop; places the core and the console area.
- `build.py` entry point, cameras and lights for the previews.

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
size and layout, rack count, placement of everything in the room, the hoist, the
steps up to the shield deck, and the door locations. The building level (ground
floor high bay vs basement) does not affect the room model.

Reference images could not be downloaded in the build environment (purdue.edu,
nrc.gov and arxiv.org are blocked there); the models follow the captions and
written descriptions in the Drive "PUR-1 Reference Images" index. The first
things to check against the real photos are the console footprint, the height
of the parapet and the position of the console relative to the pool.
