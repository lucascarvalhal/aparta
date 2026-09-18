"""GitHub CLI backend: parallel config directory ~/.config/gh-<profile>."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from ..i18n import _
from . import Note

from ..fsutil import SafeWriter
from ..config import config_home
from ..profiles import Profile


def apply_gh(profile: Profile, writer: SafeWriter) -> list[Note]:
    notes: list[Note] = []
    if not profile.gh_user:
        return notes
    src = config_home() / "gh"
    dst = profile.gh_config_dir

    if not dst.exists() and not src.exists():
        notes.append(Note("warn", _("[yellow]warning:[/yellow] ~/.config/gh does not exist, run `gh auth login` first.")))
        return notes

    if writer.dry_run:
        if not dst.exists():
            notes.append(Note("info", _("[yellow]--dry-run[/yellow] would copy {src} -> {dst}", src=src, dst=dst)))
        notes.append(Note(
            "info",
            f"[yellow]--dry-run[/yellow] GH_CONFIG_DIR={dst} gh auth switch --user {profile.gh_user}",
        ))
        return notes

    if not dst.exists():
        shutil.copytree(src, dst)
        notes.append(Note("info", _("[green]created:[/green] {dst}", dst=dst)))

    result = subprocess.run(
        ["gh", "auth", "switch", "--user", profile.gh_user],
        env=dict(os.environ, GH_CONFIG_DIR=str(dst)),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        notes.append(Note("error", _("[red]gh auth switch failed:[/red] {error}", error=result.stderr.strip())))
    else:
        notes.append(Note("info", _("[green]gh:[/green] active user in {dst}: {user}", dst=dst.name, user=profile.gh_user)))
    return notes


def parse_gh_accounts(status_output: str) -> list[str]:
    """Logged-in users from `gh auth status` output (every account)."""
    return list(dict.fromkeys(re.findall(r"Logged in to \S+ account (\S+)", status_output)))


def list_gh_accounts() -> list[str]:
    try:
        r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return parse_gh_accounts(r.stdout + r.stderr)


def login_gh(config_dir: Path) -> tuple[str, str]:
    """Interactive `gh auth login` inside a config dir: (user, error)."""
    config_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GH_CONFIG_DIR=str(config_dir))
    try:
        r = subprocess.run(["gh", "auth", "login"], env=env)
    except FileNotFoundError:
        return "", _("[red]gh not found in PATH.[/red]")
    if r.returncode != 0:
        return "", _("[yellow]Login cancelled or failed; skipping gh.[/yellow]")
    status = subprocess.run(["gh", "auth", "status"], env=env, capture_output=True, text=True, timeout=30)
    accounts = parse_gh_accounts(status.stdout + status.stderr)
    return (accounts[0], "") if accounts else ("", "")
