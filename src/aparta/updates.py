"""Update checks and self-update."""

from __future__ import annotations

import json
import shutil
import re
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from rich.console import Console

from . import __version__
from .i18n import _
from .config import read_json, read_setting, setting_path, write_json, write_setting
from .profiles import load_profiles

console = Console()

CHECK_INTERVAL_SECONDS = 24 * 60 * 60
PYPI_URL = "https://pypi.org/pypi/aparta/json"
UPDATE_MODES = ("auto", "manual", "off")


def update_mode() -> str:
    """'auto', 'manual' (default) or 'off'."""
    env = os.environ.get("APARTA_UPDATES")
    if env in UPDATE_MODES:
        return env
    return read_setting("updates", allowed=UPDATE_MODES, default="manual")


def set_update_mode(mode: str) -> None:
    write_setting("updates", mode)


def update_mode_saved() -> bool:
    return setting_path("updates").exists()


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
    now = time.time()
    data = {} if force else read_json("update-check.json")
    if now - data.get("checked_at", 0) < CHECK_INTERVAL_SECONDS:
        latest = data.get("latest", "")
        return latest if _is_newer(latest, __version__) else ""
    latest = fetch_latest_version()
    write_json("update-check.json", {"checked_at": now, "latest": latest})
    return latest if _is_newer(latest, __version__) else ""


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


def installed_version() -> str:
    """Version of the aparta on PATH, which after an upgrade is the new one."""

    binary = shutil.which("aparta")
    if not binary:
        return ""
    try:
        r = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "APARTA_UPDATES": "off"},
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    match = re.search(r"\d+\.\d+\.\d+", r.stdout)
    return match.group(0) if match else ""


def run_update(target: str = "") -> bool:
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
        now = installed_version()
        if now and now == __version__:
            if target and target != now:
                console.print(_(
                    "[yellow]{target} is announced but not installable yet; PyPI's index "
                    "takes a few minutes to catch up. Try again shortly.[/yellow]",
                    target=target,
                ))
                return False
            console.print(_("[green]You are already on the latest version ({current}).[/green]", current=now))
            return True
        if now:
            console.print(_("[green]aparta updated to {version}. It applies on the next run.[/green]", version=now))
        else:
            console.print(_("[green]aparta updated. The new version applies on the next run.[/green]"))
        try:

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
        run_update(latest)
    else:
        console.print(_(
            "[yellow]aparta {latest} is available (you have {current}). Run [bold]aparta update[/bold].[/yellow]",
            latest=latest,
            current=__version__,
        ))
