"""The control-room app: live session, local HTTP API and update checks."""

import json
from pathlib import Path
import urllib.error
import urllib.request

import pytest

from reactorsim.app import updates
from reactorsim.app.server import ControlRoomServer
from reactorsim.app.session import CommandError, SimSession


def test_state_is_strict_json_from_cold():
    s = SimSession("cold", seed=1)
    s.advance(2.0)
    st = s.state()
    json.dumps(st, allow_nan=False)  # infinite periods must not leak out as Infinity
    assert st["source_inserted"] and not st["scrammed"]
    assert set(st["rods"]) == {"SS1", "SS2", "RR"}
    assert st["trend"] and st["events"][0]["kind"] == "operator"


def test_operator_can_withdraw_a_rod_and_scram():
    s = SimSession("cold", seed=1)
    s.command("drive", rod="SS1", direction="out")
    s.advance(20.0)
    s.command("drive", rod="SS1", direction="stop")
    pos = s.state()["rods"]["SS1"]["position_cm"]
    assert pos == pytest.approx(20 * 11.0 / 60, rel=0.05)
    s.command("scram")
    s.advance(2.0)
    st = s.state()
    assert st["scrammed"] and st["rods"]["SS1"]["position_cm"] == 0.0
    assert not st["rods"]["SS1"]["latched"]


def test_servo_owns_the_regulating_rod():
    s = SimSession("power_10kw", seed=1)
    with pytest.raises(CommandError):
        s.command("drive", rod="RR", direction="out")
    s.advance(30.0)
    assert s.state()["true"]["power_w"] == pytest.approx(10_000, rel=0.02)


def test_instructor_experiment_and_bad_commands():
    s = SimSession("power_10kw", seed=1)
    s.command("experiment", dollars=0.38)
    s.advance(60.0)
    assert s.state()["scrammed"] is False or s.state()["scram_causes"]
    with pytest.raises(CommandError):
        s.command("experiment", dollars=50)
    with pytest.raises(CommandError):
        s.command("warp_drive")
    with pytest.raises(CommandError):
        s.command("speed", speed=7)


def test_events_and_trend_are_incremental():
    s = SimSession("cold", seed=1)
    s.advance(5.0)
    first = s.state()
    s.command("source", inserted=False)
    s.advance(1.0)
    later = s.state(events_after=first["event_count"], trend_after=first["trend"][-1][0])
    assert later["events"][0]["message"] == "Source withdrawn"
    assert all(e["i"] >= first["event_count"] for e in later["events"])
    assert all(p[0] > first["trend"][-1][0] for p in later["trend"])


@pytest.fixture
def server():
    session = SimSession("cold", seed=1)
    srv = ControlRoomServer(session)
    srv.start_background()
    yield srv
    srv.shutdown()


def _get(srv, path):
    with urllib.request.urlopen(srv.url.rstrip("/") + path, timeout=5) as r:
        return r.status, r.headers.get("Content-Type"), r.read()


def _post(srv, path, body, headers=None):
    req = urllib.request.Request(srv.url.rstrip("/") + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_http_api(server):
    code, ctype, body = _get(server, "/")
    assert code == 200 and "text/html" in ctype and b"PUR-1" in body
    code, ctype, _ = _get(server, "/app.js")
    assert "javascript" in ctype
    code, _, body = _get(server, "/api/state")
    assert json.loads(body)["reactor"]["key"] == "pur1"
    assert _post(server, "/api/command", {"action": "drive", "rod": "SS2", "direction": "out"}) == (200, {"ok": True})
    code, data = _post(server, "/api/command", {"action": "drive", "rod": "XX", "direction": "out"})
    assert code == 400 and "unknown rod" in data["error"]
    code, data = _post(server, "/api/command", {"action": "scram"}, {"Origin": "http://evil.example"})
    assert code == 403


def test_fullscreen_goes_through_the_native_window(server):
    """In a browser there is no app window: the page is told so and the route refuses. With the
    desktop shell's hook set, the route toggles the native window's full screen."""
    assert json.loads(_get(server, "/api/info")[2])["native_window"] is False
    code, data = _post(server, "/api/window/fullscreen", {})
    assert code == 400 and "no app window" in data["error"]
    calls = []
    server.on_fullscreen = lambda: calls.append(1)
    try:
        assert json.loads(_get(server, "/api/info")[2])["native_window"] is True
        assert _post(server, "/api/window/fullscreen", {}) == (200, {"ok": True})
        assert calls == [1]
    finally:
        server.on_fullscreen = None


def test_static_files_cannot_escape(server):
    for path in ("/../pyproject.toml", "/%2e%2e/pyproject.toml", "/models/../../pyproject.toml"):
        with pytest.raises(urllib.error.HTTPError) as e:
            _get(server, path)
        assert e.value.code == 404


def test_models_are_served(server):
    code, ctype, body = _get(server, "/models/pur1_core.glb")
    assert code == 200 and body[:4] == b"glTF"


def test_update_check_from_source_is_dev():
    assert updates.check().status == "dev"


def test_release_parsing():
    rel = {"tag_name": "build-12", "body": "notes", "published_at": "2026-10-09T00:00:00Z",
           "assets": [{"name": updates.ASSET_NAME, "url": "https://api.github.com/x/assets/1"}]}
    info = updates.info_from_release(rel, current=11)
    assert info.status == "available" and info.latest == 12 and info.asset_url
    assert updates.info_from_release(rel, current=12).status == "up_to_date"
    assert updates.parse_build("v1.0") is None


def test_token_storage_is_private(tmp_path, monkeypatch):
    monkeypatch.setattr(updates, "settings_dir", lambda: tmp_path)
    monkeypatch.delenv("REACTORSIM_GITHUB_TOKEN", raising=False)
    updates.set_token("  github_pat_abc  ")
    assert updates.token() == "github_pat_abc"
    assert (tmp_path / "settings.json").stat().st_mode & 0o077 == 0
    updates.set_token(None)
    assert updates.token() is None


def test_update_check_needs_no_token(monkeypatch):
    """The repository is public: the API request carries no Authorization header unless a token is set."""
    monkeypatch.delenv("REACTORSIM_GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(updates, "load_settings", lambda: {})
    req = updates._request("https://api.github.com/x", updates.token())
    assert not req.has_header("Authorization")
    assert updates._request("https://api.github.com/x", "tok").get_header("Authorization") == "Bearer tok"
    # download() no longer refuses to run without a token (only without an asset).
    info = updates.UpdateInfo("available", 1, latest=2, asset_url=None)
    with pytest.raises(RuntimeError, match="no update asset"):
        updates.download(info, Path("/nonexistent"))
