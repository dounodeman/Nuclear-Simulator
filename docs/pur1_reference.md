# PUR-1 reference data

Values the engine uses for PUR-1 (`reactorsim/reactors/pur1.py`), tagged by where they come from:
**Sourced** (NRC filing or Purdue), **Derived** (computed from sourced values) or **Assumed**
(typical for this reactor class, to be replaced when better data is found).

## Plant

| Item | Value | Tag |
| --- | --- | --- |
| Power | 10 kW normal, 12 kW licensed maximum (license R-87) | Sourced |
| Fuel | 19.75% U3Si2-Al MTR plates (BWXT), 6061-T6 Al clad 0.381 mm | Sourced |
| Core | 13 standard (up to 14 plates, 180 g U-235) + 3 control assemblies (up to 8 plates, 103 g); about 1 x 1 x 2 ft | Sourced |
| Reflector | 20 graphite assemblies, 6 used as irradiation positions | Sourced |
| Pool | 8 ft dia, 17 ft deep, 6,400 gal; at least 13 ft over the core; 30 C limit | Sourced |
| Chiller | 36,000 Btu/h (10.5 kW), control band 18.3-23.9 C | Sourced |
| Fuel safety limit | 530 C; blistering about 550 C; clad melting about 582 C | Sourced |
| Shim-safety rods | 2 x borated 304 SS, 5.8% dk/k together, 11 cm/min, drop under 1 s | Sourced |
| Regulating rod | hollow 304 SS, 0.47% dk/k, 43.5 cm/min, not scrammable | Sourced |
| Excess reactivity limit | 0.006 dk/k | Sourced |
| Shutdown margin | at least 0.010 dk/k with most reactive shim and reg rod out | Sourced |
| Temperature coefficient | -1.9e-4 dk/k per C at 20 C | Sourced |
| Neutron lifetime | 5.4e-5 s | Sourced |
| Average / peak thermal flux | 1.2e10 / 2.1e10 n/cm2-s at 1 kW | Sourced |

## Protection setpoints (digital RPS)

| Condition | Action | Tag |
| --- | --- | --- |
| Period under 7 s (Ch1, Ch2) | Scram | Sourced |
| Period 12 s or less | Setback | Sourced |
| Period 15 s or less, or Ch1 under 2 cps | Rod withdrawal interlock | Sourced |
| 120% power (Ch2, Ch3 of range, Ch4) | Scram | Sourced |
| 110% power (Ch3 of range, Ch4) | Setback | Sourced |
| Ch2 high voltage lost | Scram | Sourced |
| Pool top 50 mR/h; console or water process 7.5 mR/h | Scram | Sourced |
| Rod drive drift over 3 cm after stop | Setback | Sourced |
| Pool over 29.7 C | Alarm | Sourced |
| Pool level under 13 ft above core | Alarm | Assumed (from the TS minimum) |

## Engine parameters that are not published

| Parameter | Engine value | Tag |
| --- | --- | --- |
| Beta-effective | 0.0076 with Keepin U-235 group shape | Assumed |
| Excess reactivity, cold clean | +0.0055 dk/k | Assumed (under the 0.006 limit) |
| Shim worth split | 0.029 dk/k each | Derived |
| Fuel / moderator coefficient split | -0.2e-4 / -1.7e-4 per C | Assumed |
| Void coefficient | -2e-3 dk/k per % void | Assumed |
| Plate heat capacity | 31.5 kJ/K | Derived |
| Plate-to-water conductance | 8.7 kW/K (17 m2 at 500 W/m2-K) | Assumed |
| Natural circulation | 1.0 kg/s at 10 kW, scaled by power^(1/3) | Assumed |
| Hot-spot factor | 2.0 | Assumed |
| Boiling void | 0.01 per C of wall superheat, cut by subcooling (e-fold 40 C), 20 ms time constant | Assumed, tuned to SPERT-I burst data |
| Critical heat flux | at 30 C wall superheat, film boiling conductance 0.3x | Assumed |
| U-235 in core | 2,650 g | Derived (upper bound) |
| Burnup reactivity | -0.3 dk/k per unit fractional U-235 loss | Assumed |
| Startup source | about 1 mW subcritical with all rods in | Assumed |
| Startup channel calibration | 2e4 cps per W | Derived |
| Radiation at full power | pool top 10, console 0.5, water 1.0 mR/h | Assumed |

## Open questions

- Measured beta-effective and rod worth curves for the LEU core.
- Exact core map and as-loaded plate counts.
- Measured split of fuel and moderator temperature coefficients.
- Full-power radiation monitor readings.

## Sources

- [NRC ML14136A083: license renewal and Technical Specifications](https://www.nrc.gov/docs/ML1413/ML14136A083.pdf)
- [NRC ML17172A638: digital I&C functional requirements, PUR1-FRS-001](https://www.nrc.gov/docs/ML1717/ML17172A638.pdf)
- [NRC ML15329A289: safety analysis excerpt](https://www.nrc.gov/docs/ML1532/ML15329A289.pdf)
- [NRC ML16267A466: emergency plan](https://www.nrc.gov/docs/ML1626/ML16267A466.pdf)
- [NRC ML20065R492: operator licensing exam](https://www.nrc.gov/docs/ML2006/ML20065R492.pdf)
- [Purdue NE: PUR-1](https://engineering.purdue.edu/NE/research/facilities/reactor)
- [Wikipedia: Purdue University Reactor Number One](https://en.wikipedia.org/wiki/Purdue_University_Reactor_Number_One)
- [POWER: remote automated power control at PUR-1](https://powermag.com/purdue-nuclear-reactor-test-demonstrates-remote-automated-power-control)
