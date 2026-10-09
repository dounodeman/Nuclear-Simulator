"""Self-updating for the packaged Mac app.

Every merge to main that touches the simulator builds the app on GitHub
Actions and publishes it as a GitHub Release tagged ``build-<n>``. On launch
the app asks GitHub for the latest release; when its build number is higher
than the running one it offers the update, downloads the zipped ``.app``,
swaps it in place of the running bundle once the app quits, and relaunches.

The repository is private, so the GitHub API needs a token with read access to
its contents. The user pastes one once in the app; it is kept in a settings
file readable only by them.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from reactorsim import _build

REPO = "dounodeman/nuclear-simulator"
API = f"https://api.github.com/repos/{REPO}"
ASSET_NAME = "PUR-1-Simulator-macOS.zip"
APP_NAME = "PUR-1 Simulator"


def settings_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME


def _settings_path() -> Path:
    return settings_dir() / "settings.json"


def load_settings() -> dict:
    try:
        return json.loads(_settings_path().read_text())
    except (OSError, ValueError):
        return {}


def save_settings(settings: dict) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp, path)


def token() -> str | None:
    return os.environ.get("REACTORSIM_GITHUB_TOKEN") or load_settings().get("github_token") or None


def set_token(value: str | None) -> None:
    s = load_settings()
    if value:
        s["github_token"] = value.strip()
    else:
        s.pop("github_token", None)
    save_settings(s)


def running_build() -> int:
    return int(_build.BUILD)


def is_packaged_app() -> bool:
    return bool(getattr(sys, "frozen", False)) and sys.platform == "darwin"


def app_bundle() -> Path | None:
    """The running .app bundle (…/X.app/Contents/MacOS/X → …/X.app)."""
    if not is_packaged_app():
        return None
    p = Path(sys.executable).resolve()
    for parent in p.parents:
        if parent.suffix == ".app":
            return parent
    return None


@dataclass
class UpdateInfo:
    status: str  # "dev", "no_token", "up_to_date", "available", "error"
    current: int
    latest: int | None = None
    notes: str = ""
    published: str = ""
    asset_url: str | None = None
    message: str = ""

    def to_dict(self) -> dict:
        d = dict(vars(self))
        d.pop("asset_url")
        d["can_install"] = self.status == "available" and self.asset_url is not None and is_packaged_app()
        return d


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request(url: str, tok: str, accept: str = "application/vnd.github+json") -> urllib.request.Request:
    return urllib.request.Request(url, headers={
        "Accept": accept,
        "Authorization": f"Bearer {tok}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "reactorsim-updater",
    })


def parse_build(tag: str) -> int | None:
    m = re.fullmatch(r"build-(\d+)", tag or "")
    return int(m.group(1)) if m else None


def check(timeout: float = 10.0) -> UpdateInfo:
    current = running_build()
    if not is_packaged_app():
        return UpdateInfo("dev", current, message="Running from source: update with git pull.")
    tok = token()
    if not tok:
        return UpdateInfo("no_token", current,
                          message="Add a GitHub token to check for updates (the repository is private).")
    try:
        with urllib.request.urlopen(_request(f"{API}/releases/latest", tok), timeout=timeout) as resp:
            rel = json.load(resp)
    except urllib.error.HTTPError as e:
        hint = {401: "the token was rejected", 403: "the token lacks access",
                404: "no release found, or the token cannot see the repository"}.get(e.code, f"HTTP {e.code}")
        return UpdateInfo("error", current, message=f"Update check failed: {hint}.")
    except (urllib.error.URLError, OSError, ValueError) as e:
        return UpdateInfo("error", current, message=f"Update check failed: {e}")
    return info_from_release(rel, current)


def info_from_release(rel: dict, current: int) -> UpdateInfo:
    latest = parse_build(rel.get("tag_name", ""))
    asset = next((a for a in rel.get("assets", []) if a.get("name") == ASSET_NAME), None)
    info = UpdateInfo("up_to_date", current, latest=latest, notes=(rel.get("body") or "")[:4000],
                      published=rel.get("published_at") or "",
                      asset_url=asset.get("url") if asset else None)
    if latest is not None and latest > current:
        info.status = "available"
        info.message = f"Build {latest} is available (you have build {current})."
    else:
        info.message = f"Up to date (build {current})."
    return info


def download(info: UpdateInfo, dest_dir: Path, timeout: float = 120.0) -> Path:
    """Download the release zip. GitHub answers the asset API with a redirect to a signed
    storage URL that must be fetched without the token, so the redirect is followed by hand."""
    tok = token()
    if not (tok and info.asset_url):
        raise RuntimeError("no update asset to download")
    opener = urllib.request.build_opener(_NoRedirect)
    req = _request(info.asset_url, tok, accept="application/octet-stream")
    try:
        resp = opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            raise
        resp = urllib.request.urlopen(urllib.request.Request(
            e.headers["Location"], headers={"User-Agent": "reactorsim-updater"}), timeout=timeout)
    out = dest_dir / ASSET_NAME
    with resp, open(out, "wb") as f:
        shutil.copyfileobj(resp, f)
    return out


def install_and_relaunch(info: UpdateInfo) -> None:
    """Unpack the new app beside the old one, then hand off to a small shell script that waits
    for this process to exit, swaps the bundles and opens the new app."""
    bundle = app_bundle()
    if bundle is None:
        raise RuntimeError("self-update only works in the packaged Mac app")
    work = Path(tempfile.mkdtemp(prefix="reactorsim-update-"))
    zip_path = download(info, work)
    unpacked = work / "unpacked"
    subprocess.run(["/usr/bin/ditto", "-x", "-k", str(zip_path), str(unpacked)], check=True)
    new_app = next(unpacked.glob("*.app"), None)
    if new_app is None:
        raise RuntimeError("the downloaded update does not contain an app")
    script = work / "swap.sh"
    script.write_text(_SWAP_SCRIPT)
    script.chmod(0o700)
    subprocess.Popen(["/bin/sh", str(script), str(os.getpid()), str(new_app), str(bundle), str(work)],
                     start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


_SWAP_SCRIPT = r"""#!/bin/sh
# swap.sh PID NEW_APP OLD_APP WORKDIR
pid="$1"; new="$2"; old="$3"; work="$4"
while kill -0 "$pid" 2>/dev/null; do sleep 0.3; done
backup="$old.previous"
rm -rf "$backup"
mv "$old" "$backup" && mv "$new" "$old" || { mv "$backup" "$old" 2>/dev/null; open "$old"; exit 1; }
xattr -dr com.apple.quarantine "$old" 2>/dev/null
rm -rf "$backup" "$work"
open "$old"
"""
