# reactorsim

A physics-first nuclear reactor simulator. It is built to be a credible engineering
model first and a control-room experience second, and it is designed to grow from
one reactor to many.

The first reactor is **PUR-1**, Purdue University's 10 kW pool research reactor
and the first US reactor licensed with an all-digital safety and control system.
It is the test bed: a small, well-documented core whose digital controls can be modeled one-for-one.

![Startup to 10 kW](docs/img/startup.png)

## What it models

| Area | Model |
| --- | --- |
| Neutron kinetics | Point kinetics, 6 delayed groups (Keepin U-235), Pu-Be startup source; advanced exactly with a matrix exponential, so prompt-critical bursts are stable and accurate |
| Feedback | Fuel (Doppler), moderator temperature, and void from subcooled and bulk boiling |
| Thermal hydraulics | Fuel plates, core channel water and pool as heat-capacity nodes; natural circulation; boiling curve with critical heat flux and film boiling; chiller with thermostat; pool draining below the core |
| Poisons and fuel | I-135/Xe-135 and Pm-149/Sm-149 chains; U-235 depletion; 17-group decay heat |
| Control rods | S-shaped worth curves, motor drive speeds, electromagnet gravity scram, re-latching after a scram, stuck and runaway drive faults |
| Instruments | PUR-1's four neutron channels (startup fission chamber, log-N, linear with 16 ranges, safety), period meters, counting noise, radiation monitors; fault modes: fail low/high, stuck, gain error, drift, HV loss |
| Protection and control | Scrams, setbacks and withdrawal interlocks at PUR-1's setpoints; regulating-rod power servo; a failed-RPS mode for beyond-design accidents |
| Consequences | Fuel safety limit, cladding blistering and melting, fission-product release into the pool, dose rates as shielding water is lost |

Every PUR-1 number, where it came from, and which ones are still assumptions are in
[docs/pur1_reference.md](docs/pur1_reference.md).

## Quick start

```bash
pip install -e .[dev]
python -m reactorsim list
python -m reactorsim run startup --plot startup.png
python -m pytest            # 28 validation tests
```

```python
from reactorsim import Simulator

sim = Simulator("pur1")
sim.initialize_at_power(10_000)          # critical at 10 kW
sim.set_servo(True, 10_000)
sim.insert_reactivity(0.003)             # an experiment at the tech-spec limit
sim.run(60)
print(sim.status()["scram_causes"])      # period and power scrams
```

## Scenarios

| Scenario | What happens |
| --- | --- |
| `startup` | Cold shutdown to 10 kW following the startup procedure (about 33 minutes) |
| `scram` | Scram from 10 kW: prompt drop, then the textbook -80 s period |
| `xenon` | 40 h at power, then shutdown; shows why xenon barely matters at 10 kW |
| `experiment` | A 0.003 dk/k experiment inserted at full power |
| `rod_withdrawal` / `rod_withdrawal_atws` | A shim drive runs away, with and without protection |
| `reactivity_accident` / `reactivity_accident_large` | Hypothetical $1.50 and $4.00 step insertions with the RPS failed |
| `loss_of_chiller` | Pool heats about 0.33 C/h at 10 kW; temperature alarm after about 27 h |
| `loss_of_pool_water` | A pool leak: radiation monitors scram the reactor, then the core is uncovered |
| `calibration_error` | Recreates the 2019-2020 event where new instruments read 3x low |
| `linear_channel_failure` | The servo's channel fails; the safety channel has to catch the rise |

## Validation so far

| Check | Expected | Simulator |
| --- | --- | --- |
| Period after scram | about -80 s (longest delayed group) | -80.1 s |
| Stable periods for step insertions | inhour equation | within 2% |
| Prompt jump | beta / (beta - rho) | within 3% |
| Pool heat-up without chiller at 10 kW | 0.36 C/h less room losses | 0.33 C/h |
| $4 excursion, no scram | SPERT-I destructive test ($3.3): 2.3 GW, 31 MJ, plates melted | 3.4 GW, 27 MJ, melting |
| $1.50 excursion, no scram | SPERT-I: self-limiting, no damage | 132 MW peak, 251 C, no damage |
| Instruments reading 3x low | 2019-2020 PUR-1 event: ran above the 12 kW license limit | 28 kW true at 9.4 kW indicated |

## Layout

```
reactorsim/
  physics/     kinetics, thermal, poisons, burnup, decay heat (reactor independent)
  plant/       rods, instruments, radiation, protection, servo
  reactors/    one module per reactor design (pur1.py)
  simulator.py the control loop and operator actions
  scenarios.py scripted operations and accidents
tests/         validation tests
docs/          reference data and plots
```

Adding a reactor means writing one `ReactorDesign` in `reactorsim/reactors/`. Larger
power reactors will need a spatial core model and a primary loop, which slot in
beside the current lumped models.

## Roadmap

1. PUR-1 reference data (done; open questions in the reference doc)
2. Core physics engine with validation (this release)
3. Control system detail and a fuller accident set
4. Control-room operator interface on top of the engine
