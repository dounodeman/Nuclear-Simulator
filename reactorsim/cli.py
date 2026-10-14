"""Command line: list and run scenarios.

    python -m reactorsim list
    python -m reactorsim run startup --plot startup.png --csv startup.csv
    python -m reactorsim run pb2_turbine_trip --plot tt.png   # Peach Bottom 2 (BWR/4)
    python -m reactorsim experiments       # list the reactor physics experiments
    python -m reactorsim experiment rod_calibration --plot rr.png --json rr.json
    python -m reactorsim app               # interactive control room
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys

from reactorsim.bwr.scenarios import BWR_SCENARIOS, plot_bwr_run
from reactorsim.experiments import EXPERIMENTS
from reactorsim.scenarios import SCENARIOS as POOL_SCENARIOS

SCENARIOS = {**POOL_SCENARIOS, **BWR_SCENARIOS}


def _jsonable(v):
    if isinstance(v, float) and not math.isfinite(v):
        return str(v)
    return v


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["app"]:
        from reactorsim.app.desktop import main as app_main
        return app_main(argv[1:])
    ap = argparse.ArgumentParser(prog="reactorsim", description="Nuclear reactor simulator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list scenarios")
    sub.add_parser("app", help="open the interactive control room (see: reactorsim app --help)")
    run = sub.add_parser("run", help="run a scenario")
    run.add_argument("scenario", choices=sorted(SCENARIOS))
    run.add_argument("--seed", type=int, default=None, help="enable instrument noise with this seed")
    run.add_argument("--plot", help="write a PNG of the time history")
    run.add_argument("--csv", help="write the recorded time history as CSV")
    sub.add_parser("experiments", help="list the reactor physics experiments")
    exp = sub.add_parser("experiment", help="run a reactor physics experiment")
    exp.add_argument("name", choices=sorted(EXPERIMENTS))
    exp.add_argument("--seed", type=int, default=1, help="instrument noise seed (default 1)")
    exp.add_argument("--no-noise", action="store_true", help="noise-free instruments")
    exp.add_argument("--plot", help="write a PNG of the measurement")
    exp.add_argument("--json", help="write the full result as JSON")
    args = ap.parse_args(argv)

    if args.cmd == "experiments":
        for e in EXPERIMENTS.values():
            print(f"{e.key:28s} {e.title}\n{'':28s} {e.objective}")
        return 0
    if args.cmd == "experiment":
        return _run_experiment(args)

    if args.cmd == "list":
        for s in SCENARIOS.values():
            print(f"{s.key:28s} {s.title}\n{'':28s} {s.description}")
        return 0

    sc = SCENARIOS[args.scenario]
    sim, summary = sc.run(seed=args.seed)
    events = summary.pop("events")
    print(f"{sc.title}\n{'=' * len(sc.title)}")
    print(json.dumps({k: _jsonable(v) for k, v in summary.items()}, indent=2))
    print("\nEvent log:")
    print("\n".join(events) if events else "  (none)")
    if args.plot:
        if sc.key in BWR_SCENARIOS:
            plot_bwr_run(sim, sc.title, args.plot)
        else:
            from reactorsim.plotting import plot_run
            plot_run(sim, sc.title, args.plot)
        print(f"\nPlot written to {args.plot}")
    if args.csv:
        arrays = sim.history_arrays()
        keys = list(arrays)
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(keys)
            for i in range(len(arrays["t"])):
                w.writerow([f"{arrays[k][i]:.6g}" for k in keys])
        print(f"History written to {args.csv}")
    return 0


def _run_experiment(args) -> int:
    e = EXPERIMENTS[args.name]
    sim, result = e.run(seed=None if args.no_noise else args.seed)
    print(f"{e.title}\n{'=' * len(e.title)}\n{e.objective}\n")
    width = max(len(k) for part in ("measured", "reference", "error") for k in result.get(part, {}))
    for part in ("measured", "reference", "error"):
        print(part.capitalize())
        for k, v in result.get(part, {}).items():
            print(f"  {k:{width}s}  {_jsonable(v)}")
    table = result.get("table")
    if table:
        cols = table["columns"]
        w = [max(len(c), 10) for c in cols]
        print("\n" + "  ".join(f"{c:>{n}s}" for c, n in zip(cols, w)))
        for row in table["rows"]:
            print("  ".join(f"{'-' if v is None else _jsonable(v)!s:>{n}s}" for v, n in zip(row, w)))
    for note in result.get("notes", []):
        print(f"\nNote: {note}")
    if args.plot and e.plot:
        e.plot(sim, result, args.plot)
        print(f"\nPlot written to {args.plot}")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f, indent=2, default=_jsonable)
        print(f"Result written to {args.json}")
    return 0
