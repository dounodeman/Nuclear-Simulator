"""Nuclear and process instrumentation.

Models the four PUR-1-style neutron channels (startup fission chamber, log-N,
linear and safety), process sensors and radiation monitors. Each channel sees
the true plant state through its own calibration, range, noise and fault mode,
so a miscalibrated or failed instrument misleads the operator and the
protection system exactly the way a real one would.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

FAULT_MODES = ("none", "fail_low", "fail_high", "stuck", "drift", "gain", "hv_loss")


@dataclass
class ChannelFault:
    mode: str = "none"
    value: float = 1.0  # gain for "gain"; rate (fraction per hour) for "drift"

    def __post_init__(self):
        if self.mode not in FAULT_MODES:
            raise ValueError(f"unknown fault mode {self.mode!r}; choose from {FAULT_MODES}")


@dataclass(frozen=True)
class InstrumentParams:
    rated_power: float
    startup_cps_per_watt: float
    startup_background_cps: float
    startup_max_cps: float
    log_min_percent: float
    log_max_percent: float
    linear_ranges_w: tuple[float, ...]
    safety_max_percent: float
    period_filter_s: float
    ion_chamber_noise: float  # relative 1-sigma


class PeriodMeter:
    """Period from the filtered rate of change of ln(signal)."""

    def __init__(self, tau: float):
        self.tau = tau
        self.last_ln: float | None = None
        self.rate = 0.0  # filtered d(ln x)/dt, 1/s

    def update(self, signal: float, dt: float) -> float:
        ln = math.log(max(signal, 1e-30))
        if self.last_ln is not None and dt > 0:
            raw = (ln - self.last_ln) / dt
            a = dt / (self.tau + dt)
            self.rate += a * (raw - self.rate)
        self.last_ln = ln
        return self.period

    @property
    def period(self) -> float:
        if abs(self.rate) < 1e-4:
            return math.inf
        return 1.0 / self.rate


@dataclass
class Readings:
    ch1_cps: float = 0.0
    ch1_period: float = math.inf
    ch1_saturated: bool = False
    ch2_percent: float = 0.0
    ch2_period: float = math.inf
    ch2_hv_ok: bool = True
    ch3_range: int = 0
    ch3_range_w: float = 0.0
    ch3_percent_of_range: float = 0.0
    ch3_power_w: float = 0.0
    ch4_percent: float = 0.0
    pool_temp: float = 0.0
    pool_level_m: float = 0.0
    rad_pool_top: float = 0.0
    rad_console: float = 0.0
    rad_water: float = 0.0
    rad_air: float = 0.0
    downscale: list[str] = field(default_factory=list)


class Instruments:
    CHANNELS = ("ch1", "ch2", "ch3", "ch4")

    def __init__(self, p: InstrumentParams, rng: np.random.Generator | None = None):
        self.p = p
        self.rng = rng
        self.faults: dict[str, ChannelFault] = {c: ChannelFault() for c in self.CHANNELS}
        self._drift_gain = {c: 1.0 for c in self.CHANNELS}
        self._last = {c: 0.0 for c in self.CHANNELS}
        self.ch1_period = PeriodMeter(p.period_filter_s)
        self.ch2_period = PeriodMeter(p.period_filter_s)
        self.ch3_range = len(p.linear_ranges_w) - 1
        self._ch1_filtered: float | None = None
        self.readings = Readings()

    def set_fault(self, channel: str, mode: str, value: float = 1.0) -> None:
        if channel not in self.faults:
            raise ValueError(f"unknown channel {channel!r}")
        self.faults[channel] = ChannelFault(mode, value)
        if mode == "none":
            self._drift_gain[channel] = 1.0

    def _apply(self, ch: str, true_value: float, dt: float, high: float) -> float:
        f = self.faults[ch]
        if f.mode == "drift":
            self._drift_gain[ch] *= max(1.0 - f.value * dt / 3600.0, 0.0)
        gain = {"gain": f.value, "drift": self._drift_gain[ch]}.get(f.mode, 1.0)
        v = true_value * gain
        if self.rng is not None and ch != "ch1":
            v *= 1.0 + self.p.ion_chamber_noise * self.rng.standard_normal()
        if f.mode in ("fail_low", "hv_loss"):
            v = 0.0
        elif f.mode == "fail_high":
            v = high
        elif f.mode == "stuck":
            v = self._last[ch]
        self._last[ch] = v
        return v

    def update(self, dt: float, power_w: float, pool_temp: float, level_m: float,
               rad: dict[str, float]) -> Readings:
        p = self.p
        r = Readings()

        # Channel 1: fission chamber count rate (counting statistics when an RNG is supplied).
        cps_true = power_w * p.startup_cps_per_watt + p.startup_background_cps
        cps = self._apply("ch1", cps_true, dt, p.startup_max_cps)
        if self.rng is not None and self.faults["ch1"].mode in ("none", "gain", "drift") and dt > 0:
            cps = self.rng.poisson(max(cps, 0.0) * dt) / dt
            tau = max(1.0, 30.0 / math.sqrt(max(cps, 1.0)))  # count-rate meter time constant
            self._ch1_filtered = cps if self._ch1_filtered is None else (
                self._ch1_filtered + dt / (tau + dt) * (cps - self._ch1_filtered))
            cps = self._ch1_filtered
        r.ch1_saturated = cps >= p.startup_max_cps
        r.ch1_cps = min(cps, p.startup_max_cps)
        r.ch1_period = self.ch1_period.update(r.ch1_cps, dt)

        # Channel 2: log power and period.
        pct_true = power_w / p.rated_power * 100.0
        pct = self._apply("ch2", pct_true, dt, p.log_max_percent)
        r.ch2_hv_ok = self.faults["ch2"].mode != "hv_loss"
        r.ch2_percent = min(max(pct, p.log_min_percent), p.log_max_percent)
        r.ch2_period = self.ch2_period.update(r.ch2_percent, dt)
        if pct < p.log_min_percent * 0.5:
            r.downscale.append("ch2")

        # Channel 3: linear power on an operator-selected range.
        w = self._apply("ch3", power_w, dt, p.linear_ranges_w[-1] * 1.5)
        r.ch3_range = self.ch3_range
        r.ch3_range_w = p.linear_ranges_w[self.ch3_range]
        r.ch3_percent_of_range = min(w / r.ch3_range_w * 100.0, 150.0)
        r.ch3_power_w = min(w, r.ch3_range_w * 1.5)
        if self.faults["ch3"].mode == "fail_low":
            r.downscale.append("ch3")

        # Channel 4: safety channel, percent of rated power.
        s = self._apply("ch4", pct_true, dt, p.safety_max_percent)
        r.ch4_percent = min(s, p.safety_max_percent)
        if self.faults["ch4"].mode == "fail_low":
            r.downscale.append("ch4")

        r.pool_temp = pool_temp
        r.pool_level_m = level_m
        r.rad_pool_top = rad["pool_top"]
        r.rad_console = rad["console"]
        r.rad_water = rad["water"]
        r.rad_air = rad["air"]
        self.readings = r
        return r

    def range_up(self) -> None:
        self.ch3_range = min(self.ch3_range + 1, len(self.p.linear_ranges_w) - 1)

    def range_down(self) -> None:
        self.ch3_range = max(self.ch3_range - 1, 0)

    def auto_range(self, power_w: float) -> None:
        """Pick the lowest range that keeps the reading under 90% of full scale."""
        for i, fs in enumerate(self.p.linear_ranges_w):
            if power_w < 0.9 * fs:
                self.ch3_range = i
                return
        self.ch3_range = len(self.p.linear_ranges_w) - 1
