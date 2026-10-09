"""Local HTTP server for the control room: static page, 3D models and a small JSON API.

    GET  /api/state?events_after=N&trend_after=T   plant state, new events and new trend samples
    POST /api/command   {"action": ..., ...}       operator and instructor actions
    GET  /api/info                                  reactor, initial states, speeds, build
    GET  /api/update                                check GitHub for a newer app build
    POST /api/update/token  {"token": ...}          store (or clear) the GitHub token
    POST /api/update/install                        download, swap and relaunch (packaged app)

It listens on 127.0.0.1 only.
"""

from __future__ import annotations

import json
import mimetypes
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from reactorsim import _build, __version__
from reactorsim.app import updates
from reactorsim.app.session import INITIAL_STATES, SPEEDS, CommandError, SimSession

STATIC_DIR = Path(__file__).with_name("static")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("model/gltf-binary", ".glb")


def models_dir() -> Path | None:
    """The exported .glb models: bundled in the packaged app, or models/export in a checkout."""
    candidates = []
    if getattr(sys, "_MEIPASS", None):
        candidates.append(Path(sys._MEIPASS) / "models" / "export")
    candidates.append(Path(__file__).resolve().parents[2] / "models" / "export")
    return next((c for c in candidates if c.is_dir()), None)


class _Handler(BaseHTTPRequestHandler):
    server: "ControlRoomServer"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quiet by default
        if self.server.verbose:
            super().log_message(fmt, *args)

    # ------------------------------------------------------------------ helpers

    def _send(self, code: int, body: bytes, ctype: str, cache: bool = False) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, allow_nan=False).encode(), "application/json")

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            raise CommandError("request too large")
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            raise CommandError("request body is not JSON") from None
        if not isinstance(data, dict):
            raise CommandError("request body must be a JSON object")
        return data

    def _file(self, root: Path, rel: str, cache: bool) -> None:
        path = (root / rel).resolve()
        if root.resolve() not in path.parents or not path.is_file():
            self._send(404, b"not found", "text/plain")
            return
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send(200, path.read_bytes(), ctype, cache)

    # ------------------------------------------------------------------ routes

    def do_GET(self):
        url = urlparse(self.path)
        p = url.path
        q = parse_qs(url.query)
        if p == "/api/state":
            events_after = int(q.get("events_after", ["0"])[0])
            trend_after = float(q.get("trend_after", ["-1"])[0])
            self._json(self.server.session.state(events_after, trend_after))
        elif p == "/api/info":
            self._json({
                "version": __version__, "build": _build.BUILD, "commit": _build.COMMIT,
                "packaged": updates.is_packaged_app(),
                "initial_states": INITIAL_STATES, "speeds": list(SPEEDS),
                "models": models_dir() is not None,
                "has_token": updates.token() is not None,
            })
        elif p == "/api/update":
            self._json(self.server.check_update().to_dict())
        elif p.startswith("/models/"):
            root = models_dir()
            if root is None:
                self._send(404, b"models not available", "text/plain")
            else:
                self._file(root, p[len("/models/"):], cache=True)
        elif p in ("/", "/index.html"):
            self._file(STATIC_DIR, "index.html", cache=False)
        else:
            self._file(STATIC_DIR, p.lstrip("/"), cache=p.startswith("/vendor/"))

    def do_POST(self):
        p = urlparse(self.path).path
        # Pages from other origins must not drive the reactor or touch the token.
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers.get('Host')}":
            self._json({"ok": False, "error": "cross-origin request refused"}, 403)
            return
        try:
            body = self._body()
            if p == "/api/command":
                action = body.pop("action", None)
                if not isinstance(action, str):
                    raise CommandError("missing action")
                self._json(self.server.session.command(action, **body))
            elif p == "/api/update/token":
                updates.set_token(body.get("token") or None)
                self.server.last_update = None
                self._json({"ok": True, "has_token": updates.token() is not None})
            elif p == "/api/update/install":
                info = self.server.check_update(force=True)
                if not info.to_dict()["can_install"]:
                    raise CommandError(info.message or "no update to install")
                updates.install_and_relaunch(info)
                self._json({"ok": True})
                if self.server.on_quit:
                    threading.Timer(0.5, self.server.on_quit).start()
            else:
                self._json({"ok": False, "error": "not found"}, 404)
        except (CommandError, KeyError, TypeError, ValueError) as e:
            msg = f"missing field {e}" if isinstance(e, KeyError) else str(e)
            self._json({"ok": False, "error": msg}, 400)
        except Exception as e:  # keep the server alive; report to the page
            self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)


class ControlRoomServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, session: SimSession, port: int = 0, verbose: bool = False):
        super().__init__(("127.0.0.1", port), _Handler)
        self.session = session
        self.verbose = verbose
        self.on_quit = None  # set by the desktop shell so an update can close the window
        self.last_update: updates.UpdateInfo | None = None
        self._update_lock = threading.Lock()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/"

    def check_update(self, force: bool = False) -> updates.UpdateInfo:
        with self._update_lock:
            if force or self.last_update is None:
                self.last_update = updates.check()
            return self.last_update

    def start_background(self) -> threading.Thread:
        t = threading.Thread(target=self.serve_forever, name="reactorsim-http", daemon=True)
        t.start()
        return t
