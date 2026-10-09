"""Command line: list and run scenarios.

    python -m reactorsim list
    python -m reactorsim run startup --plot startup.png --csv startup.csv
    python -m reactorsim app               # interactive control room
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys

from reactorsim.scenarios import SCENARIOS


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
    args = ap.parse_args(argv)

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
