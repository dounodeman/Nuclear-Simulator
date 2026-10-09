"""Time-history plots for a finished run."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from reactorsim.simulator import Simulator  # noqa: E402


def plot_run(sim: Simulator, title: str, path: str) -> None:
    a = sim.history_arrays()
    t = a["t"]
    unit, scale = ("h", 3600.0) if t[-1] > 4 * 3600 else ("min", 60.0) if t[-1] > 600 else ("s", 1.0)
    x = t / scale
    beta = sim.design.delayed.beta_total

    fig, ax = plt.subplots(4, 1, figsize=(10, 11), sharex=True, constrained_layout=True)
    fig.suptitle(f"{sim.design.name}: {title}", fontsize=12)

    ax[0].semilogy(x, a["power"], color="#1f4e79", lw=1.4, label="true power")
    if "ind_ch2_percent" in a:
        ax[0].semilogy(x, a["ind_ch2_percent"] * sim.design.rated_power / 100, color="#c55a11", lw=0.9,
                       ls="--", label="Ch2 indicated")
    ax[0].axhline(sim.design.licensed_power, color="#999", lw=0.8, ls=":")
    ax[0].set_ylabel("Power (W)")
    ax[0].legend(loc="best", fontsize=8, frameon=False)

    for key, label in [("total", "total"), ("rods", "rods"), ("moderator_temp", "moderator temp"),
                       ("fuel_temp", "fuel temp"), ("void", "void"), ("xenon", "xenon"),
                       ("experiments", "experiments")]:
        y = a[f"rho_{key}"]
        if key in ("rods", "total") or abs(y).max() > 1e-6:
            if key == "rods":
                y = y - y[0]
                label = "rods (change)"
            ax[1].plot(x, y / beta, lw=1.6 if key == "total" else 1.0, label=label)
    ax[1].set_ylabel("Reactivity ($)")
    ax[1].legend(loc="best", fontsize=8, frameon=False, ncol=4)

    ax[2].plot(x, a["peak_fuel_temp"], label="hot-spot plate", color="#c00000", lw=1.2)
    ax[2].plot(x, a["fuel_temp"], label="average plate", color="#ed7d31", lw=1.0)
    ax[2].plot(x, a["core_temp"], label="core water", color="#2e75b6", lw=1.0)
    ax[2].plot(x, a["pool_temp"], label="pool", color="#548235", lw=1.0)
    ax[2].set_ylabel("Temperature (C)")
    ax[2].legend(loc="best", fontsize=8, frameon=False, ncol=4)

    for key in [k for k in a if k.startswith("rod_")]:
        ax[3].plot(x, a[key], label=key[4:], lw=1.2)
    ax[3].set_ylabel("Rod position (cm)")
    ax[3].set_xlabel(f"Time ({unit})")
    ax[3].legend(loc="best", fontsize=8, frameon=False)

    for e in sim.events:
        if e.kind in ("scram", "setback", "limit"):
            color = {"scram": "red", "setback": "orange", "limit": "purple"}[e.kind]
            for axis in ax:
                axis.axvline(e.time / scale, color=color, lw=0.7, alpha=0.6)
    for axis in ax:
        axis.grid(alpha=0.25)
    fig.savefig(path, dpi=120)
    plt.close(fig)
