"""Update checks and self-update.

The check hits PyPI at most once a day (cached in the config dir), never
blocks for more than two seconds and can be disabled with APARTA_UPDATES=off.
The update itself detects how aparta was installed and runs the matching
upgrade command.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from rich.console import Console

from . import __version__
from .i18n import _
from .profiles import config_dir

console = Console()

CHECK_INTERVAL_SECONDS = 24 * 60 * 60
PYPI_URL = "https://pypi.org/pypi/aparta/json"


# ------------------------------------------------------------- update mode

def update_mode() -> str:
    """'auto', 'manual' (default) or 'off'."""
    import os

    env = os.environ.get("APARTA_UPDATES")
    if env in ("auto", "manual", "off"):
        return env
    try:
        value = (config_dir() / "updates").read_text().strip()
    except OSError:
        return "manual"
    return value if value in ("auto", "manual", "off") else "manual"


def set_update_mode(mode: str) -> None:
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "updates").write_text(mode + "\n")


def update_mode_saved() -> bool:
    return (config_dir() / "updates").exists()


# ------------------------------------------------------------ version check

def fetch_latest_version(timeout: float = 2.0) -> str:
    try:
        with urllib.request.urlopen(PYPI_URL, timeout=timeout) as response:
            return json.load(response)["info"]["version"]
    except Exception:
        return ""


def _is_newer(latest: str, current: str) -> bool:
    def parse(v: str) -> tuple:
        try:
            return tuple(int(x) for x in v.split("."))
        except ValueError:
            return ()

    return bool(parse(latest)) and parse(latest) > parse(current)


def check_for_update(force: bool = False) -> str:
    """Newest version when an update exists, '' otherwise. Cached daily."""
    if update_mode() == "off" and not force:
        return ""
    cache = config_dir() / "update-check.json"
    now = time.time()
    if not force and cache.exists():
        try:
            data = json.loads(cache.read_text())
            if now - data.get("checked_at", 0) < CHECK_INTERVAL_SECONDS:
                latest = data.get("latest", "")
                return latest if _is_newer(latest, __version__) else ""
        except (json.JSONDecodeError, OSError):
            pass
    latest = fetch_latest_version()
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"checked_at": now, "latest": latest}))
    except OSError:
        pass
    return latest if _is_newer(latest, __version__) else ""


# -------------------------------------------------------------- self-update

def detect_install_method() -> str:
    """'uv-tool', 'pipx', 'ephemeral' (uvx/npx cache) or 'pip'."""
    location = str(Path(__file__).resolve())
    if "/uv/tools/" in location or "\\uv\\tools\\" in location:
        return "uv-tool"
    if "pipx" in location:
        return "pipx"
    if "/uv/" in location and ("archive-v" in location or "environments-v" in location):
        return "ephemeral"
    return "pip"


def run_update() -> bool:
    """Upgrade aparta in place; True when the upgrade command succeeded."""
    method = detect_install_method()
    commands = {
        "uv-tool": ["uv", "tool", "upgrade", "aparta"],
        "pipx": ["pipx", "upgrade", "aparta"],
        "pip": [sys.executable, "-m", "pip", "install", "--upgrade", "aparta"],
    }
    if method == "ephemeral":
        console.print(_(
            "You run aparta through uvx/npx, so every run already resolves the "
            "latest release; there is nothing to update in place."
        ))
        return True
    command = commands[method]
    console.print(_("Updating with: {cmd}", cmd=" ".join(command)))
    try:
        result = subprocess.run(command, timeout=300)
    except FileNotFoundError:
        console.print(_("[red]{cmd} not found in PATH.[/red]", cmd=command[0]))
        return False
    if result.returncode == 0:
        console.print(_("[green]aparta updated. The new version applies on the next run.[/green]"))
        try:
            from .profiles import load_profiles

            if load_profiles():
                console.print(
                    _("[dim]Run `aparta apply <profile>` to bring your profiles to the new behaviour.[/dim]")
                )
        except Exception:
            pass
        return True
    console.print(_("[red]The update command failed; try it manually.[/red]"))
    return False


def notify_or_autoupdate() -> None:
    """Startup hook: warn about a new version, or apply it in auto mode."""
    latest = check_for_update()
    if not latest:
        return
    if update_mode() == "auto":
        console.print(_("[dim]aparta {latest} is out, updating automatically...[/dim]", latest=latest))
        run_update()
    else:
        console.print(_(
            "[yellow]aparta {latest} is available (you have {current}). Run [bold]aparta update[/bold].[/yellow]",
            latest=latest,
            current=__version__,
        ))
