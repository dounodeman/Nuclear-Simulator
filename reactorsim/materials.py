"""Materials laboratory: sample irradiation, neutron activation and gamma spectrometry.

Samples are prepared from a small materials library, loaded into irradiation positions
in and around the core, and activated by the reactor's live neutron flux: thermal and
epithermal neutron capture (n,gamma) and fast-neutron threshold reactions (n,p). Each
product nuclide builds up and decays exactly with the power history. Taken out, a
sample is counted on a high-purity germanium (HPGe) detector, which collects a gamma
spectrum with counting statistics, Compton continuum, room background, energy
resolution and dead time. The analysis software finds the peaks, identifies the
nuclides and works back to activities, element masses and neutron flux, the way a
neutron activation analysis lab does.

The materials experiments built on it (flux and cadmium ratio with gold foils, activation
analysis of unknowns, half-life measurement, silicon transmutation doping and radiation
damage in steel) are in ``reactorsim.experiments``.

Nuclear data: thermal (2200 m/s) cross sections, resonance integrals, half-lives and gamma
intensities are standard evaluated values (Mughabghab Atlas, ENSDF) rounded to three
figures. Flux levels at the irradiation positions are assumptions scaled from the core
average flux; the PUR-1 facility values are in docs/pur1_reference.md where known.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

AVOGADRO = 6.02214e23
BARN = 1e-24
LN2 = math.log(2)
Q_E = 1.602e-19  # C
ELECTRON_MOBILITY_SI = 1350.0  # cm2/V-s


# ---------------------------------------------------------------------------- nuclear data

@dataclass(frozen=True)
class Reaction:
    """One activation reaction on one target isotope."""

    target: str  # e.g. "Au-197"
    product: str  # e.g. "Au-198"
    abundance: float  # atom fraction of the target isotope in the element
    half_life_s: float
    lines: tuple[tuple[float, float], ...]  # (gamma energy keV, emission probability)
    sigma_b: float = 0.0  # thermal (2200 m/s) capture cross section, barns
    ri_b: float = 0.0  # resonance integral above the cadmium cut-off, barns
    fast_sigma_b: float = 0.0  # fission-spectrum averaged threshold cross section, barns

    @property
    def lam(self) -> float:
        return LN2 / self.half_life_s


@dataclass(frozen=True)
class Element:
    symbol: str
    name: str
    molar_mass: float  # g/mol
    reactions: tuple[Reaction, ...] = ()
    sigma_abs_b: float = 0.0  # thermal absorption cross section of the natural element (reactivity)


MIN, H, D, Y = 60.0, 3600.0, 86400.0, 365.25 * 86400.0

ELEMENTS: dict[str, Element] = {e.symbol: e for e in [
    Element("Al", "aluminium", 26.982, (
        Reaction("Al-27", "Al-28", 1.0, 134.5, ((1778.9, 1.0),), 0.231, 0.17),), 0.231),
    Element("Na", "sodium", 22.990, (
        Reaction("Na-23", "Na-24", 1.0, 14.96 * H, ((1368.6, 1.0), (2754.0, 0.999)), 0.53, 0.31),), 0.53),
    Element("Cl", "chlorine", 35.45, (
        Reaction("Cl-37", "Cl-38", 0.2424, 37.24 * MIN, ((1642.7, 0.333), (2167.4, 0.444)), 0.433, 0.3),), 33.5),
    Element("K", "potassium", 39.098, (
        Reaction("K-41", "K-42", 0.0673, 12.36 * H, ((1524.6, 0.181),), 1.46, 1.4),), 2.1),
    Element("Mn", "manganese", 54.938, (
        Reaction("Mn-55", "Mn-56", 1.0, 2.579 * H, ((846.8, 0.989), (1810.7, 0.272), (2113.1, 0.143)), 13.3, 14.0),),
        13.3),
    Element("Fe", "iron", 55.845, (
        Reaction("Fe-58", "Fe-59", 0.00282, 44.5 * D, ((1099.2, 0.565), (1291.6, 0.432)), 1.30, 1.2),), 2.56),
    Element("Cr", "chromium", 51.996, (
        Reaction("Cr-50", "Cr-51", 0.04345, 27.70 * D, ((320.1, 0.099),), 15.9, 7.8),), 3.05),
    Element("Ni", "nickel", 58.693, (
        Reaction("Ni-64", "Ni-65", 0.00926, 2.517 * H, ((1481.8, 0.236), (1115.5, 0.151)), 1.52, 1.1),
        Reaction("Ni-58", "Co-58", 0.6808, 70.86 * D, ((810.8, 0.994),), fast_sigma_b=0.108),), 4.49),
    Element("Co", "cobalt", 58.933, (
        Reaction("Co-59", "Co-60", 1.0, 5.271 * Y, ((1173.2, 0.9985), (1332.5, 0.9998)), 37.2, 74.0),), 37.2),
    Element("Cu", "copper", 63.546, (
        Reaction("Cu-63", "Cu-64", 0.6915, 12.70 * H, ((511.0, 0.352), (1345.8, 0.0047)), 4.5, 5.0),
        Reaction("Cu-65", "Cu-66", 0.3085, 5.12 * MIN, ((1039.2, 0.092),), 2.17, 2.2),), 3.78),
    Element("In", "indium", 114.82, (
        Reaction("In-115", "In-116m", 0.9572, 54.29 * MIN, ((1293.6, 0.848), (1097.3, 0.585), (416.9, 0.272)),
                 162.0, 2600.0),), 194.0),
    Element("Au", "gold", 196.97, (
        Reaction("Au-197", "Au-198", 1.0, 2.695 * D, ((411.8, 0.956),), 98.65, 1550.0),), 98.65),
    Element("Si", "silicon", 28.086, (
        Reaction("Si-30", "Si-31", 0.0309, 157.3 * MIN, ((1266.1, 0.0007),), 0.107, 0.08),), 0.171),
    Element("Cd", "cadmium", 112.41, (), 2520.0),
    Element("O", "oxygen", 15.999, (), 0.0002),
    Element("Zn", "zinc", 65.38, (), 1.11),
]}

REACTIONS: dict[str, tuple[str, Reaction]] = {r.product: (e.symbol, r) for e in ELEMENTS.values() for r in e.reactions}


# ---------------------------------------------------------------------------- facility

@dataclass(frozen=True)
class Position:
    key: str
    label: str
    thermal_factor: float  # thermal flux relative to the core-average flux
    epithermal_ratio: float  # epithermal flux per unit lethargy over thermal flux
    fast_ratio: float  # fast (fission spectrum) flux over thermal flux
    capacity: int = 4
    worth_factor: float = 1.0  # importance for a sample's reactivity worth


POSITIONS: dict[str, Position] = {p.key: p for p in [
    Position("core_center", "In-core, centre (CIF)", 1.60, 0.040, 0.55, worth_factor=1.0),
    Position("core_edge", "In-core, edge", 0.95, 0.030, 0.35, worth_factor=0.55),
    Position("reflector", "Graphite reflector", 0.45, 0.010, 0.05, worth_factor=0.15),
    Position("pool", "Pool, beside the core", 0.08, 0.004, 0.01, capacity=6, worth_factor=0.02),
]}


@dataclass(frozen=True)
class Material:
    key: str
    name: str
    composition: dict  # element -> mass fraction
    default_mass_g: float
    note: str = ""
    unknown: bool = False


MATERIALS: dict[str, Material] = {m.key: m for m in [
    Material("gold_foil", "Gold foil (flux monitor)", {"Au": 1.0}, 0.010, "10 mg, 0.025 mm thick"),
    Material("indium_foil", "Indium foil", {"In": 1.0}, 0.050, "50 mg; In-116m, 54 min"),
    Material("aluminium", "Aluminium coupon", {"Al": 0.995, "Mn": 0.002, "Fe": 0.003}, 0.500, "Al-28, 2.24 min"),
    Material("copper_wire", "Copper wire", {"Cu": 1.0}, 0.200),
    Material("cobalt_wire", "Cobalt wire", {"Co": 1.0}, 0.005, "makes long-lived Co-60"),
    Material("manganin", "Manganin wire (Cu-Mn-Ni)", {"Cu": 0.84, "Mn": 0.12, "Ni": 0.04}, 0.100),
    Material("steel_304", "Stainless steel 304 coupon",
             {"Fe": 0.704, "Cr": 0.185, "Ni": 0.092, "Mn": 0.018, "Co": 0.001}, 2.0,
             "Ni-58(n,p)Co-58 measures the fast flux"),
    Material("salt", "Table salt (NaCl)", {"Na": 0.3934, "Cl": 0.6066}, 0.100),
    Material("silicon_wafer", "Float-zone silicon wafer", {"Si": 1.0}, 5.0, "neutron transmutation doping"),
    Material("unknown_ore", "Unknown: geological sample", {}, 0.200, "composition to be determined", True),
    Material("unknown_alloy", "Unknown: alloy shaving", {}, 0.050, "composition to be determined", True),
]}

# The unknowns are drawn from these at the start of each session.
UNKNOWN_CHOICES = {
    "unknown_ore": [
        {"Si": 0.29, "O": 0.48, "Al": 0.080, "Fe": 0.045, "Na": 0.024, "K": 0.022, "Mn": 0.0009, "Co": 0.00002},
        {"Si": 0.22, "O": 0.46, "Al": 0.105, "Fe": 0.070, "Na": 0.012, "K": 0.035, "Mn": 0.0021, "Co": 0.00004},
        {"Si": 0.33, "O": 0.50, "Al": 0.050, "Fe": 0.021, "Na": 0.031, "K": 0.012, "Mn": 0.0004, "Cl": 0.002},
    ],
    "unknown_alloy": [
        {"Cu": 0.88, "Al": 0.09, "Fe": 0.025, "Mn": 0.005},           # aluminium bronze
        {"Cu": 0.65, "Zn": 0.33, "Mn": 0.012, "Al": 0.008},           # manganese brass
        {"Fe": 0.66, "Cr": 0.17, "Ni": 0.12, "Mn": 0.045, "Co": 0.005},  # high-Mn stainless
    ],
}

# Reactivity of a sample at the core centre per (mol of absorber x barn); calibrated so 1 g of
# cadmium at the centre is worth about -$0.15 (with self-shielding folded in).
WORTH_DOLLARS_PER_MOL_BARN = -0.15 / (1.0 / 112.41 * 2520.0)
CADMIUM_COVER_DOLLARS = -0.04  # a 0.5 mm cadmium box at the core centre


@dataclass
class Sample:
    id: int
    material: str
    name: str
    mass_g: float
    composition: dict
    cadmium: bool
    location: str = "bench"  # "bench", a position key, "detector", "waste"
    atoms: dict = field(default_factory=dict)  # product -> atoms
    fluence_thermal: float = 0.0
    fluence_epithermal: float = 0.0
    fluence_fast: float = 0.0
    irradiation_s: float = 0.0
    energy_j: float = 0.0  # reactor energy released while the sample was in the core
    last_position: str | None = None
    time_in: float | None = None
    time_out: float | None = None  # end of irradiation (EOI)
    worth_dollars: float = 0.0  # reactivity currently added to the core by this sample
    counts: list = field(default_factory=list)  # completed spectra (analysis results)

    def target_atoms(self, element: str, reaction: Reaction) -> float:
        return self.mass_g * self.composition.get(element, 0.0) / ELEMENTS[element].molar_mass * AVOGADRO \
            * reaction.abundance

    def location_label(self) -> str:
        return POSITIONS[self.location].label if self.location in POSITIONS else self.location

    @property
    def average_power_w(self) -> float:
        return self.energy_j / self.irradiation_s if self.irradiation_s > 0 else 0.0

    def activities(self) -> dict[str, float]:
        """Present activity of each product, Bq."""
        return {p: n * REACTIONS[p][1].lam for p, n in self.atoms.items() if n > 0}

    def dose_rate_mr_h(self, distance_cm: float = 30.0) -> float:
        """Gamma dose rate from the rule of thumb R/h at 1 ft = 6 C E (C in Ci, E in MeV)."""
        total = 0.0
        for p, a in self.activities().items():
            e_mev = sum(e * i for e, i in REACTIONS[p][1].lines) / 1000.0
            total += 6.0 * a / 3.7e10 * e_mev
        return 1000.0 * total * (30.48 / distance_cm) ** 2


# ---------------------------------------------------------------------------- HPGe detector

N_CHANNELS = 4096
KEV_PER_CHANNEL = 0.75
SHELVES_CM = (5.0, 10.0, 25.0, 50.0)
DEAD_TIME_S = 8e-6  # per event, non-paralyzable
BACKGROUND_LINES = ((351.9, 0.04, "Pb-214"), (511.0, 0.06, "annihilation"), (609.3, 0.05, "Bi-214"),
                    (1460.8, 0.12, "K-40"), (2614.5, 0.03, "Tl-208"))
BACKGROUND_CONTINUUM_CPS = 12.0


def efficiency(e_kev: float, distance_cm: float = 10.0) -> float:
    """Absolute full-energy peak efficiency of a 30% relative HPGe (coaxial, end-cap geometry)."""
    eff = 0.0055 * (e_kev / 1000.0) ** -0.9
    if e_kev < 120.0:
        eff *= (e_kev / 120.0) ** 2
    return eff * (10.0 / (distance_cm + 1.0)) ** 2 * (11.0 / 10.0) ** 2


def fwhm_kev(e_kev: float) -> float:
    return math.sqrt(0.9 ** 2 + 0.0011 * e_kev)


def peak_to_total(e_kev: float) -> float:
    return min(1.0, 0.45 * (e_kev / 300.0) ** -0.6)


_CH = (np.arange(N_CHANNELS) + 0.5) * KEV_PER_CHANNEL


def _line_shape(e_kev: float) -> np.ndarray:
    """Per-count channel distribution for one gamma line: photopeak plus Compton continuum."""
    sig = fwhm_kev(e_kev) / 2.3548
    peak = np.exp(-0.5 * ((_CH - e_kev) / sig) ** 2)
    peak /= peak.sum()
    edge = e_kev * (1 - 1 / (1 + 2 * e_kev / 511.0))
    cont = np.where(_CH < edge, 1.0 + 0.6 * (_CH / edge) ** 3, 0.0)
    cont += np.where((_CH > edge) & (_CH < e_kev - 3 * sig), 0.08, 0.0)
    bs = 0.25 * np.exp(-0.5 * ((_CH - e_kev / (1 + 2 * e_kev / 511.0)) / 12.0) ** 2)  # backscatter
    cont = cont + bs
    cont /= cont.sum() if cont.sum() > 0 else 1.0
    pt = peak_to_total(e_kev)
    return pt * peak + (1 - pt) * cont


_SHAPES: dict[float, np.ndarray] = {}


def line_shape(e_kev: float) -> np.ndarray:
    if e_kev not in _SHAPES:
        _SHAPES[e_kev] = _line_shape(e_kev)
    return _SHAPES[e_kev]


def _background_shape() -> np.ndarray:
    cont = np.exp(-_CH / 350.0) + 0.05
    cont = BACKGROUND_CONTINUUM_CPS * cont / cont.sum()
    for e, cps, _ in BACKGROUND_LINES:
        cont = cont + cps / peak_to_total(e) * line_shape(e)
    return cont


@dataclass
class Count:
    sample_id: int
    shelf_cm: float
    preset_live_s: float
    start_t: float
    spectrum: np.ndarray = field(default_factory=lambda: np.zeros(N_CHANNELS))
    live_s: float = 0.0
    real_s: float = 0.0
    input_cps: float = 0.0
    done: bool = False


# ---------------------------------------------------------------------------- the lab

class MaterialsLab:
    def __init__(self, flux_per_watt: float, beta: float, rng: np.random.Generator | None = None,
                 unknown_seed: int | None = None):
        self.flux_per_watt = flux_per_watt  # core-average thermal flux per watt
        self.beta = beta
        self.rng = rng if rng is not None else np.random.default_rng(0)
        pick = np.random.default_rng(unknown_seed)
        self.unknowns = {k: dict(v[int(pick.integers(len(v)))]) for k, v in UNKNOWN_CHOICES.items()}
        self.samples: dict[int, Sample] = {}
        self._next_id = 1
        self.count: Count | None = None
        self.last_count: Count | None = None
        self.background = _background_shape()
        self.events: list[str] = []  # messages for the simulator's event log, drained by the session

    # -------------------------------------------------------------- flux

    def flux(self, position: str, power_w: float) -> tuple[float, float, float]:
        """Thermal, epithermal (per unit lethargy) and fast flux at a position, n/cm2-s."""
        p = POSITIONS[position]
        th = self.flux_per_watt * max(power_w, 0.0) * p.thermal_factor
        return th, th * p.epithermal_ratio, th * p.fast_ratio

    # -------------------------------------------------------------- samples

    def prepare(self, material: str, mass_g: float | None = None, cadmium: bool = False) -> Sample:
        if material not in MATERIALS:
            raise ValueError(f"unknown material {material!r}")
        m = MATERIALS[material]
        mass = m.default_mass_g if mass_g is None else float(mass_g)
        if not 1e-5 <= mass <= 50.0:
            raise ValueError("sample mass must be between 0.01 mg and 50 g")
        comp = self.unknowns[material] if m.unknown else dict(m.composition)
        s = Sample(self._next_id, material, m.name, mass, comp, bool(cadmium))
        self.samples[s.id] = s
        self._next_id += 1
        return s

    def sample(self, sid: int) -> Sample:
        try:
            return self.samples[int(sid)]
        except (KeyError, ValueError, TypeError):
            raise ValueError(f"no sample {sid!r}") from None

    def occupants(self, position: str) -> list[Sample]:
        return [s for s in self.samples.values() if s.location == position]

    def reactivity_worth(self, s: Sample, position: str) -> float:
        """Reactivity (dk/k) the sample adds at a position: absorbers are negative."""
        mol_barn = sum(s.mass_g * f / ELEMENTS[el].molar_mass * ELEMENTS[el].sigma_abs_b
                       for el, f in s.composition.items() if el in ELEMENTS)
        dollars = WORTH_DOLLARS_PER_MOL_BARN * mol_barn + (CADMIUM_COVER_DOLLARS if s.cadmium else 0.0)
        return dollars * POSITIONS[position].worth_factor * self.beta

    def insert(self, sid: int, position: str, t: float) -> float:
        """Load a sample into an irradiation position; returns the reactivity it adds."""
        s = self.sample(sid)
        if position not in POSITIONS:
            raise ValueError(f"unknown irradiation position {position!r}")
        if s.location == "detector":
            raise ValueError("the sample is on the detector; stop the count first")
        if s.location == "waste":
            raise ValueError("the sample has gone to radioactive waste")
        if s.location in POSITIONS:
            raise ValueError(f"sample {s.id} is already in {POSITIONS[s.location].label}")
        if len(self.occupants(position)) >= POSITIONS[position].capacity:
            raise ValueError(f"{POSITIONS[position].label} is full")
        if s.last_position not in (None, position) and s.irradiation_s > 0:
            raise ValueError("a sample stays in one position so its flux is known; prepare a new one")
        s.location = position
        s.last_position = position
        s.time_in = t
        rho = self.reactivity_worth(s, position)
        s.worth_dollars = rho / self.beta
        return rho

    def remove(self, sid: int, t: float) -> float:
        """Take a sample out of the core; returns the reactivity change (minus its worth)."""
        s = self.sample(sid)
        if s.location not in POSITIONS:
            raise ValueError(f"sample {s.id} is not in an irradiation position")
        s.location = "bench"
        s.time_out = t
        rho = -s.worth_dollars * self.beta
        s.worth_dollars = 0.0
        return rho

    def discard(self, sid: int) -> None:
        s = self.sample(sid)
        if s.location in POSITIONS:
            raise ValueError("take the sample out of the core first")
        if self.count and self.count.sample_id == s.id:
            self.stop_count()
        s.location = "waste"

    # -------------------------------------------------------------- time

    def advance(self, dt: float, power_w: float, t: float) -> None:
        if dt <= 0:
            return
        # Count first: the detector sees the decays of the atoms present at the start of the step.
        if self.count and not self.count.done:
            self._count_step(dt, t)
        for s in self.samples.values():
            inside = s.location in POSITIONS
            th, epi, fast = self.flux(s.location, power_w) if inside else (0.0, 0.0, 0.0)
            if inside:
                s.fluence_thermal += th * dt
                s.fluence_epithermal += epi * dt
                s.fluence_fast += fast * dt
                s.irradiation_s += dt
                s.energy_j += max(power_w, 0.0) * dt
            for el in s.composition:
                e = ELEMENTS.get(el)
                if e is None:
                    continue
                for r in e.reactions:
                    n0 = s.atoms.get(r.product, 0.0)
                    rate = 0.0
                    if inside:
                        sig_th = 0.0 if s.cadmium else r.sigma_b * th
                        rate = s.target_atoms(el, r) * BARN * (sig_th + r.ri_b * epi + r.fast_sigma_b * fast)
                    if rate == 0.0 and n0 == 0.0:
                        continue
                    k = math.exp(-r.lam * dt)
                    s.atoms[r.product] = n0 * k + rate / r.lam * (1.0 - k)

    # -------------------------------------------------------------- counting

    def start_count(self, sid: int, live_s: float, shelf_cm: float, t: float) -> Count:
        s = self.sample(sid)
        if s.location in POSITIONS:
            raise ValueError("take the sample out of the core before counting it")
        if s.location == "waste":
            raise ValueError("the sample has gone to radioactive waste")
        if shelf_cm not in SHELVES_CM:
            raise ValueError(f"shelf must be one of {SHELVES_CM} cm")
        if not 1.0 <= live_s <= 86400.0:
            raise ValueError("count time must be 1 s to 24 h")
        if self.count and not self.count.done:
            self.stop_count()
        if self.count:
            self._release_detector()
        s.location = "detector"
        self.count = Count(s.id, float(shelf_cm), float(live_s), t)
        return self.count

    def _release_detector(self) -> None:
        c = self.count
        if c is not None and c.sample_id in self.samples and self.samples[c.sample_id].location == "detector":
            self.samples[c.sample_id].location = "bench"

    def stop_count(self) -> None:
        c = self.count
        if c is None:
            return
        if not c.done:
            c.done = True
            if c.live_s > 0:
                self._finish(c)
        self._release_detector()

    def _expected(self, s: Sample, dt: float, shelf_cm: float) -> np.ndarray:
        """Expected detector events per channel over ``dt`` from the sample and the room."""
        out = self.background * dt
        for p, n in s.atoms.items():
            r = REACTIONS[p][1]
            decays = n * (1.0 - math.exp(-r.lam * dt))
            if decays <= 0:
                continue
            for e, i in r.lines:
                peak_counts = decays * i * efficiency(e, shelf_cm)
                out = out + peak_counts / peak_to_total(e) * line_shape(e)
        return out

    def _count_step(self, dt: float, t: float) -> None:
        c = self.count
        s = self.samples[c.sample_id]
        need = c.preset_live_s - c.live_s
        expected = self._expected(s, dt, c.shelf_cm)
        input_cps = float(expected.sum()) / dt
        live_frac = 1.0 / (1.0 + input_cps * DEAD_TIME_S)
        live = dt * live_frac
        frac = 1.0
        if live >= need:
            frac = need / live
            live = need
        c.spectrum += self.rng.poisson(expected * live_frac * frac)
        c.live_s += live
        c.real_s += dt * frac
        c.input_cps = input_cps
        if c.live_s >= c.preset_live_s - 1e-9:
            c.done = True
            self._finish(c)
            self._release_detector()

    def _finish(self, c: Count) -> None:
        s = self.samples[c.sample_id]
        result = self.analyze(c)
        s.counts.append(result)
        self.last_count = c
        self.events.append(f"Count of sample {s.id} ({s.name}) finished: {len(result['peaks'])} peaks")

    # -------------------------------------------------------------- analysis software

    def analyze(self, c: Count) -> dict:
        """Peak search against the nuclide library, net areas, and activities corrected back to
        the start of the count and to the end of irradiation."""
        s = self.samples[c.sample_id]
        # The lab's long room-background count, scaled to this live time, is subtracted first.
        spec = c.spectrum - self.background * c.live_s
        peaks = []
        library = sorted({(e, i, p) for p, (_, r) in REACTIONS.items() for e, i in r.lines}, key=lambda x: x[0])
        for e, inten, product in library:
            w = fwhm_kev(e)
            lo, hi = int((e - 1.4 * w) / KEV_PER_CHANNEL), int((e + 1.4 * w) / KEV_PER_CHANNEL) + 1
            nb = max(3, hi - lo)
            if lo - nb < 0 or hi + nb >= N_CHANNELS:
                continue
            gross = float(spec[lo:hi].sum())
            left, right = spec[lo - nb:lo].mean(), spec[hi:hi + nb].mean()
            base = np.linspace(left, right, hi - lo)
            net_ch = spec[lo:hi] - base
            net = float(net_ch.sum())
            raw = float(c.spectrum[lo:hi].sum())
            sigma = math.sqrt(raw + float(c.spectrum[lo - nb:lo].sum() + c.spectrum[hi:hi + nb].sum())
                              * ((hi - lo) / (2 * nb)) ** 2 + 1.0)
            if net < 3 * sigma or net < 10:
                continue
            # The peak has to sit where the line is: centroid within half a FWHM.
            centroid = float((net_ch.clip(min=0) * _CH[lo:hi]).sum() / max(net_ch.clip(min=0).sum(), 1e-9))
            if abs(centroid - e) > 0.5 * w:
                continue
            peaks.append({"energy_kev": e, "nuclide": product, "intensity": inten, "net": net, "sigma": sigma,
                          "centroid_kev": centroid})
        # A nuclide counts as identified only when every line it should show above the detection
        # limit is there (one stray coincidence with another nuclide's line is not enough).
        found = {}
        for pk in peaks:
            found.setdefault(pk["nuclide"], []).append(pk)
        out = []
        for product, pks in found.items():
            r = REACTIONS[product][1]
            ref = max(pks, key=lambda p: p["net"])
            ref_rate = ref["net"] / (ref["intensity"] * efficiency(ref["energy_kev"], c.shelf_cm))
            seen = {p["energy_kev"] for p in pks}
            missing = [e for e, i in r.lines if e not in seen and ref_rate * i * efficiency(e, c.shelf_cm)
                       > 6 * ref["sigma"] * max(1.0, (ref["sigma"] / max(ref["net"], 1)) * 10)]
            if missing:
                continue
            for pk in pks:
                lam = r.lam
                t_real = max(c.real_s, 1e-9)
                eff = efficiency(pk["energy_kev"], c.shelf_cm)
                # Mean activity during the count, corrected for decay during the count and dead time.
                decay_in_count = (1 - math.exp(-lam * t_real)) / (lam * t_real)
                a_start = pk["net"] / (pk["intensity"] * eff * c.live_s * decay_in_count)
                eoi = s.time_out
                a_eoi = a_start * math.exp(lam * (c.start_t - eoi)) if eoi is not None else None
                out.append({**pk, "background_line": False,
                            "half_life_s": r.half_life_s, "efficiency": eff,
                            "activity_start_bq": a_start, "activity_eoi_bq": a_eoi,
                            "element": REACTIONS[product][0], "mid_time": c.start_t + c.real_s / 2})
        out.sort(key=lambda p: p["energy_kev"])
        return {"sample_id": s.id, "start_t": c.start_t, "live_s": c.live_s, "real_s": c.real_s,
                "shelf_cm": c.shelf_cm, "dead_time": 1 - c.live_s / max(c.real_s, 1e-9),
                "decay_time_s": None if s.time_out is None else c.start_t - s.time_out, "peaks": out}

    # -------------------------------------------------------------- derived results

    @staticmethod
    def saturation(r: Reaction, irr_s: float) -> float:
        return 1.0 - math.exp(-r.lam * irr_s)

    def best_peak(self, s: Sample, product: str) -> dict | None:
        """The most precise measurement of a product's EOI activity over all counts of a sample."""
        best = None
        for res in s.counts:
            for pk in res["peaks"]:
                if pk["nuclide"] == product and pk["activity_eoi_bq"] is not None:
                    if best is None or pk["sigma"] / pk["net"] < best["sigma"] / best["net"]:
                        best = pk
        return best

    def reaction_rate_per_atom(self, s: Sample, element: str, product: str) -> float | None:
        """Measured saturated reaction rate per target atom (s^-1), assuming steady power."""
        _, r = REACTIONS[product]
        pk = self.best_peak(s, product)
        if pk is None or s.irradiation_s <= 0:
            return None
        n = s.target_atoms(element, r)
        return pk["activity_eoi_bq"] / (n * self.saturation(r, s.irradiation_s))

    def foil_flux(self, bare: Sample, covered: Sample) -> dict | None:
        """Thermal and epithermal flux and the cadmium ratio from a bare and a cadmium-covered gold foil."""
        rb = self.reaction_rate_per_atom(bare, "Au", "Au-198")
        rc = self.reaction_rate_per_atom(covered, "Au", "Au-198")
        if rb is None or rc is None or rc <= 0:
            return None
        r = REACTIONS["Au-198"][1]
        phi_epi = rc / (r.ri_b * BARN)
        phi_th = (rb - rc) / (r.sigma_b * BARN)
        return {"thermal_flux": phi_th, "epithermal_flux": phi_epi, "cadmium_ratio": rb / rc}

    def element_masses(self, s: Sample, phi_th: float, phi_epi: float) -> dict[str, float]:
        """Absolute-method activation analysis: element mass (g) from each identified product."""
        out = {}
        for res in s.counts:
            for pk in res["peaks"]:
                if pk.get("background_line"):
                    continue
                el, r = REACTIONS[pk["nuclide"]]
                if r.fast_sigma_b:
                    continue
                best = self.best_peak(s, pk["nuclide"])
                if best is None or s.irradiation_s <= 0:
                    continue
                rate = BARN * ((0.0 if s.cadmium else r.sigma_b * phi_th) + r.ri_b * phi_epi)
                atoms = best["activity_eoi_bq"] / (rate * self.saturation(r, s.irradiation_s))
                out[el] = atoms / (AVOGADRO * r.abundance) * ELEMENTS[el].molar_mass
        return out

    def half_life(self, s: Sample, product: str) -> dict | None:
        """Half-life from a least-squares fit of ln(activity at count start) over repeated counts."""
        pts = []
        for res in s.counts:
            pk = max((p for p in res["peaks"] if p["nuclide"] == product), key=lambda p: p["net"], default=None)
            if pk is not None:
                # The activity is referred to the start of each count, so that is its time stamp.
                pts.append((res["start_t"], pk["activity_start_bq"], pk["sigma"] / pk["net"]))
        if len(pts) < 3:
            return None
        t = np.array([p[0] for p in pts])
        y = np.log([p[1] for p in pts])
        w = 1 / np.array([max(p[2], 1e-3) for p in pts]) ** 2
        slope = np.polyfit(t, y, 1, w=np.sqrt(w))[0]
        if slope >= 0:
            return None
        return {"half_life_s": LN2 / -slope, "points": len(pts)}

    @staticmethod
    def ntd(s: Sample, phi_th_fluence: float, initial_resistivity_ohm_cm: float = 5000.0) -> dict:
        """Neutron transmutation doping of silicon: Si-30(n,g)Si-31 -> P-31 donors."""
        r = REACTIONS["Si-31"][1]
        n_si30 = 2.329 / ELEMENTS["Si"].molar_mass * AVOGADRO * r.abundance  # per cm3
        donors = n_si30 * r.sigma_b * BARN * phi_th_fluence
        n0 = 1.0 / (Q_E * ELECTRON_MOBILITY_SI * initial_resistivity_ohm_cm)
        rho = 1.0 / (Q_E * ELECTRON_MOBILITY_SI * (n0 + donors))
        return {"phosphorus_per_cm3": donors, "resistivity_ohm_cm": rho,
                "initial_resistivity_ohm_cm": initial_resistivity_ohm_cm}

    @staticmethod
    def damage(fast_fluence: float) -> dict:
        """Displacements per atom in steel (NRT, ~1500 b displacement cross section for a fission
        spectrum) and the yield-strength increase from a sqrt(dpa) hardening correlation."""
        dpa = 1500.0 * BARN * fast_fluence
        return {"dpa": dpa, "hardening_mpa": 450.0 * math.sqrt(dpa / 0.01) if dpa > 0 else 0.0}

    # -------------------------------------------------------------- state for the page

    def state(self, power_w: float, t: float, include_spectrum: bool = True, truth: bool = True) -> dict:
        samples = []
        for s in self.samples.values():
            if s.location == "waste":
                continue
            acts = s.activities()
            samples.append({
                "id": s.id, "material": s.material, "name": s.name, "mass_g": s.mass_g, "cadmium": s.cadmium,
                "location": s.location,
                "location_label": s.location_label(),
                "irradiation_s": s.irradiation_s,
                "in_core_s": (t - s.time_in) if s.location in POSITIONS and s.time_in is not None else None,
                "since_eoi_s": (t - s.time_out) if s.time_out is not None and s.location not in POSITIONS else None,
                "dose_mr_h_30cm": s.dose_rate_mr_h(30.0),
                "worth_dollars": s.worth_dollars,
                "counts": len(s.counts),
                "true": {"activity_bq": sum(acts.values()), "activities_bq": acts,
                         "composition": s.composition, "fluence_thermal": s.fluence_thermal,
                         "fluence_fast": s.fluence_fast} if truth else None,
            })
        positions = []
        for p in POSITIONS.values():
            th, epi, fast = self.flux(p.key, power_w)
            positions.append({"key": p.key, "label": p.label, "capacity": p.capacity,
                              "samples": [s.id for s in self.occupants(p.key)],
                              "true_thermal_flux": th, "true_fast_flux": fast})
        c = self.count
        det = None
        if c is not None:
            det = {"sample_id": c.sample_id, "shelf_cm": c.shelf_cm, "preset_live_s": c.preset_live_s,
                   "live_s": c.live_s, "real_s": c.real_s, "done": c.done,
                   "dead_time": 1.0 - (c.live_s / c.real_s) if c.real_s > 0 else 0.0,
                   "input_cps": c.input_cps, "total_counts": float(c.spectrum.sum())}
            if include_spectrum:
                det["spectrum"] = c.spectrum.reshape(-1, 4).sum(axis=1).astype(int).tolist()  # 1024 bins of 3 keV
                det["kev_per_bin"] = KEV_PER_CHANNEL * 4
        return {
            "materials": [{"key": m.key, "name": m.name, "mass_g": m.default_mass_g, "note": m.note}
                          for m in MATERIALS.values()],
            "positions": positions,
            "shelves_cm": list(SHELVES_CM),
            "samples": samples,
            "detector": det,
            "results": self.results(t),
        }

    def results(self, t: float) -> dict:
        """What the analysis software can work out from the counts taken so far."""
        out: dict = {"analyses": {}, "flux": {}, "half_lives": {}, "ntd": {}, "damage": {}}
        # Flux at each position from the latest bare and cadmium-covered gold foil pair irradiated
        # there, normalised to 1 kW of reactor power so it applies to any later irradiation.
        gold = [s for s in self.samples.values() if s.material == "gold_foil" and s.counts and s.irradiation_s > 0]
        for pos in POSITIONS:
            bare = [s for s in gold if not s.cadmium and s.last_position == pos]
            cov = [s for s in gold if s.cadmium and s.last_position == pos]
            if not bare or not cov:
                continue
            b, c = bare[-1], cov[-1]
            f = self.foil_flux(b, c)
            if not f or b.average_power_w <= 0 or c.average_power_w <= 0:
                continue
            out["flux"][pos] = {"label": POSITIONS[pos].label, "cadmium_ratio": f["cadmium_ratio"],
                                "thermal_per_kw": f["thermal_flux"] / (b.average_power_w / 1000),
                                "epithermal_per_kw": f["epithermal_flux"] / (c.average_power_w / 1000),
                                "foils": [b.id, c.id], "power_w": b.average_power_w}
        flux = out["flux"]

        def sample_flux(s: Sample):
            f = flux.get(s.last_position)
            if f is None or s.irradiation_s <= 0:
                return None
            kw = s.average_power_w / 1000
            return f["thermal_per_kw"] * kw, f["epithermal_per_kw"] * kw

        for s in self.samples.values():
            if not s.counts:
                continue
            peaks = s.counts[-1]["peaks"]
            out["analyses"][s.id] = {"name": s.name, "count": len(s.counts),
                                     "peaks": [{k: p[k] for k in ("energy_kev", "nuclide", "net", "sigma",
                                                                    "activity_start_bq", "activity_eoi_bq",
                                                                    "half_life_s", "element", "background_line")}
                                               for p in peaks],
                                     "dead_time": s.counts[-1]["dead_time"], "live_s": s.counts[-1]["live_s"]}
            sf = sample_flux(s)
            if sf and s.material != "gold_foil":
                out["analyses"][s.id]["element_masses_g"] = self.element_masses(s, *sf)
            elif s.material != "gold_foil":
                out["analyses"][s.id]["needs_flux"] = POSITIONS[s.last_position].label if s.last_position else None
            for product in {p["nuclide"] for p in peaks if not p.get("background_line")}:
                hl = self.half_life(s, product)
                if hl:
                    out["half_lives"][f"{s.id}:{product}"] = {**hl, "sample": s.id, "nuclide": product,
                                                              "library_s": REACTIONS[product][1].half_life_s}
            if s.material == "steel_304":
                rate = self.reaction_rate_per_atom(s, "Ni", "Co-58")
                if rate is not None:
                    phi_fast = rate / (REACTIONS["Co-58"][1].fast_sigma_b * BARN)
                    out["damage"][s.id] = {"fast_flux": phi_fast, "fast_fluence": phi_fast * s.irradiation_s,
                                           **self.damage(phi_fast * s.irradiation_s)}
        for s in self.samples.values():
            sf = sample_flux(s) if s.material == "silicon_wafer" else None
            if sf:
                out["ntd"][s.id] = self.ntd(s, sf[0] * s.irradiation_s)
        return out
