"""Scripted BWR scenarios: operational transients and accidents on the Peach Bottom 2 model.

Each scenario builds a ``BWRSimulator``, drives it like an operator or a fault would, and
returns a summary dict. The full time history stays on the returned simulator.
"""

from __future__ import annotations

import numpy as np

from reactorsim.bwr.simulator import BWRSimulator
from reactorsim.physics import steam
from reactorsim.scenarios import Scenario

DESIGN = "peach_bottom_2"
RATED = 3293e6


def _summary(sim: BWRSimulator, **extra) -> dict:
    a = sim.history_arrays()
    i = int(a["power"].argmax())
    out = {
        "end_time_s": sim.t,
        "peak_power_percent": float(a["power"][i] / sim.design.rated_power * 100),
        "time_of_peak_s": float(a["t"][i]),
        "final_power_percent": sim.power / sim.design.rated_power * 100,
        "peak_pressure_psig": float(steam.psig(a["pressure"].max())),
        "min_level_in": float(a["level_in"].min()),
        "max_level_in": float(a["level_in"].max()),
        "peak_fuel_temp_c": float(a["peak_fuel_temp"].max()),
        "final_torus_temp_c": sim.torus_temp,
        "fuel_damage_fraction": sim.fuel_damage,
        "scrammed": sim.scrammed,
        "scram_causes": list(sim.scram_causes),
        "events": [f"{e.time:9.1f} s  {e.kind:8s} {e.message}" for e in sim.events],
    }
    out.update(extra)
    return out


def _at_power(power_fraction: float = 1.0, flow_fraction: float = 1.0, seed=None, dt: float = 0.05) -> BWRSimulator:
    sim = BWRSimulator(DESIGN, seed=seed, control_dt=dt)
    sim.initialize_at_power(power_fraction * RATED, flow_fraction)
    return sim


def steady_full_power(seed=None, minutes: float = 10.0):
    sim = _at_power()
    sim.run(minutes * 60.0, record_every=1.0)
    return sim, _summary(sim)


def turbine_trip_benchmark(seed=None, seconds: float = 5.0):
    """OECD/NEA BWR Turbine Trip benchmark (Peach Bottom 2 test TT2, April 1977): turbine stop
    valves close in 0.1 s from 61.6% power and 80.9% core flow, the bypass opens, and the
    pressure wave collapses core voids. The direct stop-valve scram was bypassed for the test,
    so the scram comes from neutron flux. Measured: peak about 3.6 times the initial power at
    about 0.74 s, with the rods moving from 0.75 s."""
    sim = _at_power(0.617, 0.809, seed, dt=0.01)
    sim.tsv_scram_enabled = False
    sim.run(1.0, record_every=0.01)
    t0 = sim.t
    sim.trip_turbine("turbine trip test TT2")
    sim.run(seconds, record_every=0.01)
    a = sim.history_arrays()
    i = int(a["power"].argmax())
    rise = a["t"] >= t0
    return sim, _summary(
        sim,
        power_ratio_at_peak=float(a["power"][i] / (0.617 * RATED)),
        time_of_peak_after_trip_s=float(a["t"][i] - t0),
        pressure_rise_at_1s_psi=float(steam.psig(a["pressure"][rise][int(1.0 / 0.01)]) - steam.psig(a["pressure"][0])),
        peak_pressure_rise_psi=float(steam.psig(a["pressure"].max()) - steam.psig(a["pressure"][0])),
    )


def turbine_trip(seed=None, bypass: bool = True, rps: bool = True, minutes: float = 3.0):
    """Turbine trip from full power: the stop valves close, the bypass takes 25% of rated steam
    flow, the stop-valve scram drops the rods, and the SRVs lift if the bypass is not enough."""
    sim = _at_power(seed=seed)
    sim.bypass_available = bypass
    sim.rps_enabled = rps
    sim.run(2.0)
    sim.trip_turbine("generator load reject")
    sim.run(minutes * 60.0, record_every=0.1)
    return sim, _summary(sim)


def recirc_pump_trip(seed=None, minutes: float = 5.0):
    """Both recirculation pumps trip: core flow coasts down to natural circulation and the power
    follows it down the power-flow map without a scram."""
    sim = _at_power(seed=seed)
    sim.run(2.0)
    sim.trip_recirc_pumps()
    sim.run(minutes * 60.0, record_every=0.5)
    return sim, _summary(sim)


def loss_of_feedwater(seed=None, minutes: float = 10.0):
    """All feed pumps lost: level falls to Level 3 (scram) and Level 2, HPCI and RCIC start and
    restore the level, and the operator is left controlling level with the steam-driven pumps."""
    sim = _at_power(seed=seed)
    sim.run(2.0)
    sim.trip_feedwater()
    sim.run(minutes * 60.0, record_every=0.5)
    return sim, _summary(sim)


def msiv_closure(seed=None, minutes: float = 5.0):
    """All MSIVs close in 4 s: scram on valve position, the vessel pressurizes until the SRVs
    lift and cycle, and decay heat goes to the torus."""
    sim = _at_power(seed=seed)
    sim.run(2.0)
    sim.close_msivs("spurious isolation signal")
    sim.run(minutes * 60.0, record_every=0.5)
    return sim, _summary(sim)


def station_blackout(seed=None, hours: float = 2.0):
    """Loss of all AC power: feed and recirculation pumps lost, MSIVs shut, condenser gone. The
    SRVs cycle on decay heat and RCIC and HPCI, running on steam and batteries, keep the core
    covered while the torus heats up."""
    sim = _at_power(seed=seed)
    sim.run(2.0)
    sim.station_blackout()
    sim.run(hours * 3600.0, record_every=5.0)
    return sim, _summary(sim)


def station_blackout_no_injection(seed=None, hours: float = 1.0):
    """Station blackout with HPCI and RCIC also failed: the level boils down to the top of the
    fuel and the core uncovers (a Fukushima-type sequence without operator action)."""
    sim = _at_power(seed=seed)
    sim.run(2.0)
    sim.set_available("hpci", False)
    sim.set_available("rcic", False)
    sim.station_blackout()
    sim.run(hours * 3600.0, record_every=5.0)
    a = sim.history_arrays()
    uncovered = a["t"][a["level_in"] <= sim.design.taf_level_in]
    return sim, _summary(sim, time_core_uncovered_s=float(uncovered[0]) if uncovered.size else None)


def turbine_trip_atws(seed=None, minutes: float = 2.0):
    """Turbine trip with the reactor protection system failed (ATWS): the SRVs hold pressure and
    the power settles wherever void feedback balances the rods."""
    return turbine_trip(seed, bypass=True, rps=False, minutes=minutes)


def rod_withdrawal_error(seed=None, notches: float = 4.0, minutes: float = 3.0):
    """Continuous bank withdrawal at power until the flow-biased APRM scram catches it."""
    sim = _at_power(0.9, seed=seed)
    sim.run(2.0)
    sim.withdraw_rods(notches)
    sim.run(minutes * 60.0, record_every=0.2)
    return sim, _summary(sim)


BWR_SCENARIOS: dict[str, Scenario] = {s.key: s for s in [
    Scenario("pb2_steady", "Peach Bottom 2: steady full power",
             "Ten minutes at 3,293 MWt; nothing should move.", steady_full_power),
    Scenario("pb2_turbine_trip_benchmark", "Peach Bottom 2: 1977 turbine trip test (OECD/NEA benchmark)",
             "Stop valves close from 61.6% power and 80.9% flow; peak measured at 3.6x in 0.74 s.",
             turbine_trip_benchmark),
    Scenario("pb2_turbine_trip", "Peach Bottom 2: turbine trip from full power",
             "Load reject with bypass; stop-valve scram, SRVs if needed.", turbine_trip),
    Scenario("pb2_turbine_trip_atws", "Peach Bottom 2: turbine trip without scram",
             "ATWS: RPS failed, SRVs cycle, power settles on void feedback.", turbine_trip_atws),
    Scenario("pb2_recirc_pump_trip", "Peach Bottom 2: two recirculation pump trip",
             "Flow coasts down to natural circulation; power follows.", recirc_pump_trip),
    Scenario("pb2_loss_of_feedwater", "Peach Bottom 2: loss of feedwater",
             "Level 3 scram, Level 2 HPCI/RCIC start, level recovers.", loss_of_feedwater),
    Scenario("pb2_msiv_closure", "Peach Bottom 2: MSIV closure",
             "Isolation scram; SRVs lift and cycle to the torus.", msiv_closure),
    Scenario("pb2_rod_withdrawal", "Peach Bottom 2: rod withdrawal error at power",
             "Bank withdrawn four notches at 90% power.", rod_withdrawal_error),
    Scenario("pb2_station_blackout", "Peach Bottom 2: station blackout",
             "Loss of all AC for two hours; RCIC and HPCI on steam and batteries.", station_blackout),
    Scenario("pb2_station_blackout_no_injection", "Peach Bottom 2: station blackout, no injection",
             "HPCI and RCIC failed; the core boils down and uncovers.", station_blackout_no_injection),
]}


def plot_bwr_run(sim: BWRSimulator, title: str, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    a = sim.history_arrays()
    t = a["t"]
    unit, scale = ("h", 3600.0) if t[-1] > 4 * 3600 else ("min", 60.0) if t[-1] > 600 else ("s", 1.0)
    x = t / scale
    d = sim.design
    fig, ax = plt.subplots(4, 1, figsize=(10, 11), sharex=True, constrained_layout=True)
    fig.suptitle(f"{d.name}: {title}", fontsize=12)
    ax[0].plot(x, a["power"] / d.rated_power * 100, color="#1f4e79", lw=1.4, label="neutron power")
    ax[0].plot(x, a["thermal_power"] / d.rated_power * 100, color="#c55a11", lw=0.9, ls="--", label="thermal power")
    ax[0].plot(x, a["core_flow"] / d.rated_core_flow * 100, color="#548235", lw=1.0, label="core flow")
    ax[0].set_ylabel("% of rated")
    ax[0].legend(loc="best", fontsize=8, frameon=False, ncol=3)
    ax[1].plot(x, [steam.psig(p) for p in a["pressure"]], color="#7030a0", lw=1.2)
    ax[1].set_ylabel("Dome pressure (psig)")
    ax[2].plot(x, a["level_in"], color="#2e75b6", lw=1.2, label="level")
    ax[2].axhline(d.setpoints.level3_scram_in, color="#c00000", lw=0.7, ls=":", label="L3")
    ax[2].axhline(d.taf_level_in, color="#999", lw=0.7, ls=":", label="top of fuel")
    ax[2].set_ylabel("Level (in)")
    ax[2].legend(loc="best", fontsize=8, frameon=False, ncol=3)
    ax[3].plot(x, a["steam_flow"], label="steam out", lw=1.0)
    ax[3].plot(x, a["feed_flow"], label="feedwater", lw=1.0)
    ax[3].plot(x, a["eccs_flow"], label="ECCS", lw=1.0)
    ax[3].set_ylabel("Flow (kg/s)")
    ax[3].set_xlabel(f"Time ({unit})")
    ax[3].legend(loc="best", fontsize=8, frameon=False, ncol=3)
    for e in sim.events:
        if e.kind in ("scram", "limit"):
            for axis in ax:
                axis.axvline(e.time / scale, color="red" if e.kind == "scram" else "purple", lw=0.7, alpha=0.6)
    for axis in ax:
        axis.grid(alpha=0.25)
    fig.savefig(path, dpi=120)
    plt.close(fig)
