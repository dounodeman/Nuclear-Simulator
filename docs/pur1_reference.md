# PUR-1 reference data

The engine's PUR-1 values (`reactorsim/reactors/pur1.py`) follow the project's
**PUR-1 Simulator Parameter Sheet** and **PUR-1 Reference Compendium** (in the project
Google Drive, PUR-1 folder), which cite the licensing record: SAR 2008 (ML111890201),
SAR 2015 (ML15210A283), HEU-to-LEU conversion SAR 2006 (ML070920272), Technical
Specifications 2016 (ML16267A001) and Amendment 14 (ML18275A124), the digital I&C
specification PUR1-FRS-001 (ML17172A638), RAI responses (ML13101A044), and Theos et al.,
"The PUR-1 Cyber-Physical Digital Twin" (arXiv 2608.30186).

Tags: **Sourced** (value taken from those documents), **Derived** (computed from sourced
values), **Assumed** (not published; typical for this class of reactor).

## Kinetics and reactivity

| Parameter | Engine value | Tag |
| --- | --- | --- |
| Beta-effective | 0.00784 | Sourced (SAR 2008) |
| Six delayed groups | OpenMC lambda and beta (digital twin paper, Table VI), scaled to 0.00784 | Sourced |
| Prompt neutron lifetime (used as generation time) | 81.3 us | Sourced (SAR 2008) |
| Excess reactivity, fresh core, cold clean | 0.0042 dk/k (TS max 0.006) | Sourced (measured) |
| Shutdown margin, SS1 and RR out | 0.018 dk/k (TS min 0.010) | Sourced (measured) |
| Rod worths SS1 / SS2 / RR | 0.0393 / 0.0222 / 0.0027 dk/k | Sourced (measured) |
| Rod speeds | shims 11 cm/min, RR 43.5 cm/min | Sourced |
| Rod travel, active span, dead travel | 64.12 cm, 61 cm, 5.9 cm | Sourced / Sourced / Derived (gives banked critical at ~53.5 cm) |
| Scram | 0.1 s signal delay, about 0.6 s fall, under 1 s total | Sourced (TS, analysis) / Assumed fall |
| Moderator temperature coefficient | -9.05e-5 per C to 30 C, -1.075e-4 to 60 C, -1.229e-4 above | Sourced (SAR 2008, conversion SAR) |
| Fuel temperature coefficient | -8.05e-6 per C to 127 C, -1.387e-5 to 227 C, -8.40e-6 above | Sourced |
| Void coefficient | -1.93e-3 dk/k per % void | Sourced (valid 0-0.6% void) |
| Average thermal flux | 1.38e10 n/cm2-s per kW | Sourced (SAR 2008 MCNP) |
| Decay heat | 6.3% at shutdown, Way-Wigner shape | Sourced |

## Thermal hydraulics

| Parameter | Engine value | Tag |
| --- | --- | --- |
| Pool | 24.2 m3, 4.1 m of water over the core, 22 C start (27 C for licensing benchmarks) | Sourced |
| Chiller | 10.55 kW, on above 23.9 C, off below 18.3 C | Sourced |
| Core flow | 0.92 kg/s at 10 kW (985 cm3/s at 12 kW), scaled with power^(1/3) | Sourced / Derived |
| Plate heat capacity | 27 kJ/K (190 fueled plates) | Derived |
| Plate-to-water conductance | 4.8 kW/K (13.6 m2 at about 350 W/m2-K) | Assumed, tuned to NATCON clad temperatures |
| Hot-spot factor | 3.8 (plate peaking 2.6 x hot channel 1.5) | Derived |
| Boiling void | 0.01 per C of wall superheat, reduced by bulk subcooling, 20 ms | Assumed |
| Critical heat flux | 30 C wall superheat; film boiling conductance 0.3x | Assumed |
| Fuel limits | 530 C safety limit, 550 C blistering, 582 C clad melting | Sourced |

## Protection and control (digital I&C)

| Condition | Action | Tag |
| --- | --- | --- |
| Period under 7 s (Ch1, Ch2) | Scram | Sourced |
| Period 12 s or less | Setback: gang lower of all rods at normal speed | Sourced |
| Period 15 s or less, or Ch1 under 2 cps | Rod withdrawal interlock | Sourced |
| Ch2 / Ch4 at 120% (12 kW); Ch3 at 120% of range | Scram | Sourced |
| Ch4 at 110% (11 kW); Ch3 at 110% of range or at 0% | Setback | Sourced |
| Ch2 high voltage lost | Scram | Sourced |
| Pool top 50 mR/h; console or water process 7.5 mR/h | Scram | Sourced |
| More than one rod withdrawing | Blocked (one rod at a time) | Sourced |
| Scram | Shim magnets released; RR stays where it is | Sourced |
| Servo deviation over 5% | Alarm | Sourced |

## Benchmarks against the licensing analyses

| Case | Licensing result | Simulator |
| --- | --- | --- |
| 0.6% step from 12 kW, period trip failed, scram at 18 kW actual, SS2 only | 46.4 kW at 0.173 s, clad 57.4 C | 55 kW at 0.172 s, clad 40.5 C |
| 0.6% over 10 s, same assumptions | 18.4 kW, clad 57.5 C | 18.4 kW, clad 40.1 C |
| 0.6% step from 10 kW, no scram | 2.39 MW at about 680 s, clad 133 C | 645 kW at 3 s, then about 210 kW held by boiling voids; clad 120 C |
| Hot clad at 18 kW steady | about 43 C | 44.7 C |
| Pool heat-up at 10 kW, chiller off | about 0.36 C/h | 0.33 C/h (room losses included) |

The scram-terminated peaks and timing match well. Peak clad temperatures in the fast
transients come out lower than PARET's, which uses hot-channel factors on top of a
conservative starting state. The unscrammed case differs most: here subcooled-boiling
voids cap the power within seconds, while PARET's power keeps rising for minutes. These
are the main items left to calibrate.

## Still open

- Measured integral rod worth curves (the engine uses an S-curve fitted to the banked critical height).
- Plate-to-water heat transfer and boiling-void parameters under transient conditions.
- Full-power radiation monitor readings.
