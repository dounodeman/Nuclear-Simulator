"""Launch the control room: in its own window (pywebview) or in the default browser.

    python -m reactorsim app              # window if pywebview is installed, else the browser
    python -m reactorsim app --browser    # always the browser
    reactorsim-app                        # entry point used by the packaged Mac app
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser

from reactorsim.app.server import ControlRoomServer
from reactorsim.app.session import INITIAL_STATES, SimSession

WINDOW_TITLE = "PUR-1 Simulator"


def run(initial: str = "cold", port: int = 0, browser: bool = False, verbose: bool = False) -> int:
    session = SimSession(initial)
    session.start()
    server = ControlRoomServer(session, port=port, verbose=verbose)
    server.start_background()

    webview = None
    if not browser:
        try:
            import webview  # pywebview
        except ImportError:
            print("pywebview is not installed; opening the control room in your browser instead.\n"
                  "  (pip install pywebview for a separate window)")

    try:
        if webview is not None:
            window = webview.create_window(WINDOW_TITLE, server.url, width=1440, height=900,
                                           min_size=(1100, 700), background_color="#0d1117")
            server.on_quit = window.destroy
            webview.start()
        else:
            print(f"Control room running at {server.url}  (Ctrl+C to stop)")
            webbrowser.open(server.url)
            stop = threading.Event()
            server.on_quit = stop.set
            try:
                stop.wait()
            except KeyboardInterrupt:
                pass
    finally:
        server.shutdown()
        session.stop()
    return 0


def selftest() -> int:
    """Start the session and server, fetch the page and a few states, and exit. Used by CI to
    check that the packaged app actually runs (no window is opened)."""
    import json
    import time
    import urllib.request

    session = SimSession("power_10kw")
    session.start()
    server = ControlRoomServer(session)
    server.start_background()
    try:
        def get(path):
            with urllib.request.urlopen(server.url + path.lstrip("/"), timeout=10) as r:
                return r.read()
        assert b"PUR-1" in get("/")
        assert get("/vendor/three/three.module.min.js")
        assert b"HallWorld" in get("/world.js")
        info = json.loads(get("/api/info"))
        time.sleep(1.0)
        state = json.loads(get("/api/state"))
        assert state["time_s"] > 0.5, "simulation is not advancing"
        assert abs(state["true"]["power_w"] - 10_000) < 500
        print(f"selftest ok: build {info['build']}, models {info['models']}, "
              f"t={state['time_s']:.2f} s, P={state['true']['power_w']:.0f} W")
        if getattr(sys, "frozen", False) and not info["models"]:
            raise AssertionError("3D models missing from the packaged app")
        return 0
    finally:
        server.shutdown()
        session.stop()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reactorsim app", description="PUR-1 control room")
    ap.add_argument("--initial", choices=sorted(INITIAL_STATES), default="cold")
    ap.add_argument("--port", type=int, default=0, help="port on 127.0.0.1 (default: any free port)")
    ap.add_argument("--browser", action="store_true", help="open in the default browser, not a window")
    ap.add_argument("--verbose", action="store_true", help="log HTTP requests")
    ap.add_argument("--selftest", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return run(args.initial, args.port, args.browser, args.verbose)


if __name__ == "__main__":
    # PyInstaller on macOS may pass a -psn_ argument when launched from Finder.
    sys.exit(main([a for a in sys.argv[1:] if not a.startswith("-psn")]))
