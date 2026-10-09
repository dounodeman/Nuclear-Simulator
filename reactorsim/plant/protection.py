"""Reactor protection system (scrams, setbacks, rod withdrawal interlocks) and alarms.

Evaluated once per digital control cycle from instrument readings only, never
from the true plant state, so instrument faults propagate realistically.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from reactorsim.plant.instruments import Readings


@dataclass(frozen=True)
class ProtectionSetpoints:
    period_scram_s: float
    period_setback_s: float
    period_interlock_s: float
    startup_min_cps: float
    power_scram_percent: float  # of rated, channels 2 and 4
    power_setback_percent: float
    linear_scram_percent: float  # of selected range, channel 3
    linear_setback_percent: float
    pool_top_scram: float  # mR/h
    console_scram: float
    water_scram: float
    air_alarm: float
    pool_temp_alarm: float  # C
    pool_level_alarm_m: float
    servo_deviation_alarm: float  # fraction
    rod_drift_setback_cm: float
    shim_interlock_height_cm: float  # shims cannot go past this unless all channels operable


@dataclass
class ProtectionOutput:
    scram_causes: list[str] = field(default_factory=list)
    setback_causes: list[str] = field(default_factory=list)
    interlock_causes: list[str] = field(default_factory=list)
    alarms: list[str] = field(default_factory=list)
    channels_operable: bool = True
    setback_clear: bool = True


def _short(period: float, limit: float) -> bool:
    """True when the period is positive and shorter than ``limit`` seconds."""
    return 0 < period < limit and math.isfinite(period)


class ProtectionSystem:
    def __init__(self, sp: ProtectionSetpoints, rated_power: float):
        self.sp = sp
        self.rated_power = rated_power
        self.enabled = True  # False models a failed RPS (anticipated transient without scram)

    def evaluate(self, r: Readings, rod_drift_cm: float, servo_error: float | None,
                 shutdown: bool) -> ProtectionOutput:
        sp = self.sp
        out = ProtectionOutput()

        # --- channel health ---
        if not r.ch2_hv_ok:
            out.scram_causes.append("Ch2 high voltage lost")
            out.channels_operable = False
        for ch in r.downscale:
            out.alarms.append(f"{ch.upper()} downscale")
            out.channels_operable = False

        # --- period ---
        ch1_period_valid = not r.ch1_saturated
        periods = [("Ch2", r.ch2_period)] + ([("Ch1", r.ch1_period)] if ch1_period_valid else [])
        for name, period in periods:
            if _short(period, sp.period_scram_s):
                out.scram_causes.append(f"{name} period under {sp.period_scram_s:g} s")
            elif _short(period, sp.period_setback_s):
                out.setback_causes.append(f"{name} period under {sp.period_setback_s:g} s")
            if _short(period, sp.period_interlock_s):
                out.interlock_causes.append(f"{name} period under {sp.period_interlock_s:g} s")

        # --- power level ---
        if r.ch2_percent >= sp.power_scram_percent:
            out.scram_causes.append(f"Ch2 power {sp.power_scram_percent:g}%")
        if r.ch4_percent >= sp.power_scram_percent:
            out.scram_causes.append(f"Ch4 safety power {sp.power_scram_percent:g}%")
        elif r.ch4_percent >= sp.power_setback_percent:
            out.setback_causes.append(f"Ch4 safety power {sp.power_setback_percent:g}%")
        if r.ch3_percent_of_range >= sp.linear_scram_percent:
            out.scram_causes.append(f"Ch3 linear {sp.linear_scram_percent:g}% of range")
        elif r.ch3_percent_of_range >= sp.linear_setback_percent:
            out.setback_causes.append(f"Ch3 linear {sp.linear_setback_percent:g}% of range")

        # --- startup count rate ---
        if r.ch1_cps < sp.startup_min_cps:
            out.interlock_causes.append(f"Ch1 under {sp.startup_min_cps:g} cps")

        # --- radiation ---
        if r.rad_pool_top >= sp.pool_top_scram:
            out.scram_causes.append("Pool top radiation high")
        if r.rad_console >= sp.console_scram:
            out.scram_causes.append("Console radiation high")
        if r.rad_water >= sp.water_scram:
            out.scram_causes.append("Water process radiation high")
        if r.rad_air >= sp.air_alarm:
            out.alarms.append("Continuous air monitor high")

        # --- process alarms ---
        if r.pool_temp > sp.pool_temp_alarm:
            out.alarms.append("Pool temperature high")
        if r.pool_level_m < sp.pool_level_alarm_m:
            out.alarms.append("Pool level low")
        if servo_error is not None and abs(servo_error) > sp.servo_deviation_alarm:
            out.alarms.append("Servo deviation over 5%")
        if rod_drift_cm > sp.rod_drift_setback_cm:
            out.setback_causes.append("Rod drive drift")

        # Setback hysteresis: once started, a setback runs until power is 5% below its setpoint
        # and the period is longer than the interlock value, so rods do not chatter at the limit.
        out.setback_clear = (
            r.ch4_percent < sp.power_setback_percent - 5
            and r.ch3_percent_of_range < sp.linear_setback_percent - 5
            and not _short(r.ch2_period, sp.period_interlock_s)
            and not (not r.ch1_saturated and _short(r.ch1_period, sp.period_interlock_s))
            and rod_drift_cm <= sp.rod_drift_setback_cm
        )

        if not out.channels_operable:
            out.alarms.append("Channel inoperable")
        if not self.enabled:
            # A failed RPS still annunciates but takes no protective action.
            out.alarms.extend(f"RPS FAILED - would scram: {c}" for c in out.scram_causes)
            out.alarms.extend(f"RPS FAILED - would set back: {c}" for c in out.setback_causes)
            out.scram_causes = []
            out.setback_causes = []
            out.setback_clear = True
        return out
