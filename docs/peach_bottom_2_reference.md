# Peach Bottom Unit 2 reference data

The engine's Peach Bottom 2 values (`reactorsim/reactors/peach_bottom_2.py`) follow the
project's **Peach Bottom Unit 2 Reference Sheet (BWR/4)** in the project Google Drive, which
in turn points at the OECD/NEA BWR Turbine Trip benchmark specification NEA/NSC/DOC(2001)1,
the Peach Bottom UFSAR and Technical Specifications (Appendix A to DPR-44), NUREG-1433
(BWR/4 standard technical specifications) and the NRC's GE BWR/4 technology manuals.

The plant is modelled at its **original licensed power of 3,293 MWt**, the state of the April
1977 turbine trip tests at the end of Cycle 2. Today's plant runs at 4,016 MWt with 10x10 fuel.

Tags: **Sourced** (a found public source states the value), **Typical** (a GE BWR/4 number
from the training manuals or standard technical specifications; Peach Bottom's own value has
not been checked), **Tuned** (chosen so a transient matches plant behaviour), **Assumed**.

## Core and kinetics

| Parameter | Engine value | Tag |
| --- | --- | --- |
| Rated / licensed power | 3,293 MWt | Sourced |
| Fuel assemblies | 764 (benchmark core: GE 7x7 and 8x8) | Sourced |
| Control rods | 185 cruciform blades, 48 notches of 6 in, bank speed 3 in/s | Typical |
| Beta-effective, generation time | 0.0053 (Keepin U-235 groups), 40 us | Typical (benchmark has the cycle-specific set) |
| Excess reactivity, cold clean | 0.12 dk/k | Assumed (held down by rods and gadolinia) |
| Rod bank worth | 0.18 dk/k, S-shaped | Assumed |
| Void coefficient | -1.6e-3 dk/k per % core-average void | Tuned (typical -0.8e-3 to -1.4e-3; the model's 28% average void at rated is below a real core's ~40%, so per unit quality it is in range) |
| Doppler coefficient | -2.0e-5 dk/k per C of average fuel temperature | Typical |
| Moderator (liquid) coefficient | -2.0e-5 dk/k per C | Typical, small |
| Void lag | 0.4 s at rated flow, growing as 1/sqrt(flow) | Tuned (about half the core transit time) |
| Average thermal flux | 3e13 n/cm2-s at rated (9.1e3 per W) | Typical |
| Fission and absorption cross sections | 0.0027 / 0.0060 1/cm (equilibrium xenon about -0.03 dk/k) | Typical |
| Decay heat | 6.6% at shutdown, Way-Wigner shape | Typical |

## Thermal hydraulics

| Parameter | Engine value | Tag |
| --- | --- | --- |
| Fuel heat capacity, conductance | 4.6e7 J/K (153 t UO2), 1.0e7 W/K (fuel 600 C average at rated, 4.6 s time constant) | Typical |
| Direct coolant heating | 4% of fission heat | Typical |
| Rated core flow | 102.5 Mlb/h (12,900 kg/s) | Typical BWR/4 |
| Natural circulation | 35% of rated flow at rated void, following the square root of the void | Tuned (two-pump trip ends at 39% power, 36% flow) |
| Pump speed lag, coastdown | 2 s, 4.5 s | Typical |
| Core coolant volume, separator swell volume | 27 m3, 10 m3 | Assumed |
| Slip ratio | 2.0 | Assumed |
| Steam space (dome and lines) | 160 m3 | Tuned (pressurization rate on the turbine trip) |
| Condensing liquid, time constant | 150 t following saturation with a 3 s lag | Tuned |
| Vessel liquid inventory, downcomer area | 250 t, 12.3 m2 (251 in vessel) | Sourced (vessel) / Assumed |
| Dome pressure | 1,020 psig at rated, pressure regulator band 20 psi | Typical |
| Feedwater temperature | 376 F (191 C) | Typical for the original power |
| Feed pump lag, level gain | 5 s, 1% of rated steam flow per inch of level error | Assumed |
| Downcomer and lower plenum transit | 8 s (two 4 s mixing stages) | Assumed |
| Torus water | 123,000 ft3 (3,480 t) at 30 C | Typical Mark I |

## Steam lines and relief

| Parameter | Engine value | Tag |
| --- | --- | --- |
| Main steam lines, MSIV stroke | 4, 4 s | Typical |
| Turbine stop valve stroke | 0.1 s | Sourced (benchmark) |
| Bypass capacity, stroke | 25% of rated steam flow, 0.3 s | Typical |
| Safety/relief valves | 11: three at 1,135, four at 1,145, four at 1,155 psig; reseat 40 psi lower; 870,000 lb/h each | Sourced (count, ADS uses 5) / Typical (set points) |

## Protection and ECCS set points (inches above instrument zero)

| Signal | Engine value | Tag |
| --- | --- | --- |
| APRM high (Run) | 120% | Typical |
| APRM flow-biased | 0.66 x core flow % + 54% | Typical |
| APRM setdown (Startup) | 15% | Typical |
| Reactor pressure high | 1,085 psig | Typical |
| Level 8 (turbine and feed pump trip, HPCI/RCIC stop) | +54 in | Typical |
| Level 7 / Level 4 alarms | +45 / +27 in | Typical |
| Normal level | +35 in | Typical |
| Level 3 scram | +1 in | Typical |
| Level 2 (HPCI, RCIC, recirc pump trip) | -48 in | Typical |
| Level 1 (core spray, LPCI, MSIV closure, ADS timer) | -160 in | Typical |
| Top / bottom of active fuel | -160 / -304 in | Assumed convention (the 144 in fuel column) |
| Stop valve scram bypass | below 30% power | Typical |
| MSL pressure low isolation (Run) | 850 psig | Typical |
| ATWS recirculation pump trip | 1,135 psig | Typical |
| ADS delay | 120 s | Typical |
| Scram delay, stroke | 0.1 s, 3.5 s | Sourced (delay) / Typical |
| HPCI | 5,000 gpm above 150 psig, rated flow 30 s after the signal | Sourced (flow) / Typical |
| RCIC | 600 gpm above 150 psig, 30 s | Typical |
| Core spray | two loops of 6,250 gpm, 290 psi shutoff | Sourced (flow) / Typical |
| LPCI | four pumps of 10,000 gpm, 220 psi shutoff | Typical |
| Low-pressure pump start | 40 s (diesel start and run-up) | Typical |
| Safety limit, peak fuel | 1,325 psig dome pressure (Sourced); fuel limits 1,200 / 2,200 / 2,840 C (Assumed) | |

## Validation against the 1977 turbine trip test (TT2)

The OECD/NEA benchmark measured, from 61.6% power and 80.9% core flow with the stop valves
closing in 0.1 s and the direct stop-valve scram bypassed: a power peak of about **3.6 times
the initial power at 0.74 s**, with the scram rods moving from 0.75 s.

`pb2_turbine_trip_benchmark` gives a peak of **1.9 times at 0.63 s**, a flux scram at about
0.5 s, a dome pressure rise of about 50 psi in the first second, and the power down below 3% by
5 s. The shape is right (pressure wave, void collapse, flux scram, rods ending it) but the peak
is low: a point-kinetics core with one lumped void cannot reproduce the 3-D flux redistribution
and the steam-line pressure wave that the benchmark participants needed coupled 3-D codes for.
The test in `tests/test_peach_bottom_2.py` holds the peak between 1.5 and 4 times and the peak
time between 0.3 and 1.0 s. Closing that gap is the first physics task once the benchmark
specification (NEA/NSC/DOC(2001)1) can be read in full.

## Other checks

| Scenario | Result | Expectation |
| --- | --- | --- |
| Two recirculation pump trip | no scram; settles at 39% power, 36% flow | Plant runs back to natural circulation at roughly 40% power |
| Loss of feedwater | Level 3 scram at 9 s, Level 2 at 17 s, HPCI and RCIC injecting from 47 s, level bottoms at -76 in | Core stays covered; HPCI restores level |
| MSIV closure | scram on valve position, SRVs lift at 1,135 psig and cycle, torus warms | SRVs carry decay heat to the torus |
| Turbine trip, no scram (ATWS) | ATWS-RPT at 1,135 psig, power settles near 50% on natural circulation under cycling SRVs, pressure stays under 1,150 psig | Below the 1,325 psig safety limit |
| Station blackout, no injection | core uncovers after 24 minutes | Comparable to Fukushima Daiichi Unit 1 timescales |

## Known simplifications

- One lumped core: no axial or radial flux shape, no hot-channel boiling transition (MCPR), no
  core-wide or regional density-wave instability (the exclusion-region alarm is a map check).
- One fuel node: an uncovered core heats as an average, so cladding peak temperatures are
  under-predicted.
- No drywell pressure, so ECCS and ADS act on level alone; no containment venting.
- Rods move as one bank; no rod pattern, rod worth minimizer or rod block monitor.
- Instruments read the true plant state (no noise or channel faults yet).
- The control room (`/pb2.html`) shows the plant model's readings on analog instruments; the
  instruments read true values, and the systems the model does not carry (drywell pressure,
  torus level, generator electrical values, feed pump turbine speeds) show plausible fixed or
  derived numbers so the panels are complete.
- The balance of plant and auxiliaries on the side benchboards (condensate, feedwater heater
  strings, circulating water and condenser vacuum, air ejectors and offgas, RWCU, CRD hydraulics,
  instrument air, HPSW and RHR torus cooling, reactor building HVAC and SGTS, the four diesel
  generators, radiation monitors) are simple lumped models in `reactorsim/app/bwr_aux.py` with
  typical or assumed numbers: vacuum trip 22.5 inHg and MSIV closure at 7 inHg, scram on scram
  air header below 60 psig, about 1 MW/K per RHR heat exchanger loop, 10 s diesel start.
