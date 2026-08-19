"""GitHub CLI backend: parallel config directory ~/.config/gh-<profile>.

Tokens live in the OS keyring, so copying ~/.config/gh and switching the
active user inside the copy (via GH_CONFIG_DIR) needs no re-login.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ..i18n import _
from rich.console import Console

from ..fsutil import SafeWriter
from ..profiles import Profile, gh_config_dir

console = Console()


def apply_gh(profile: Profile, writer: SafeWriter, home: Path | None = None) -> None:
    if not profile.gh_user:
        return
    home = home or Path.home()
    src = home / ".config" / "gh"
    dst = gh_config_dir(profile.name, home / ".config")

    # an existing dst (e.g. wizard logged in straight into the profile dir)
    # needs no copy; the global config is only used to clone a session
    if not dst.exists() and not src.exists():
        console.print(_("[yellow]warning:[/yellow] ~/.config/gh does not exist, run `gh auth login` first."))
        return

    if writer.dry_run:
        if not dst.exists():
            console.print(_("[yellow]--dry-run[/yellow] would copy {src} -> {dst}", src=src, dst=dst))
        console.print(
            f"[yellow]--dry-run[/yellow] GH_CONFIG_DIR={dst} gh auth switch --user {profile.gh_user}"
        )
        return

    if not dst.exists():
        shutil.copytree(src, dst)
        console.print(_("[green]created:[/green] {dst}", dst=dst))

    result = subprocess.run(
        ["gh", "auth", "switch", "--user", profile.gh_user],
        env=dict(os.environ, GH_CONFIG_DIR=str(dst)),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        console.print(_("[red]gh auth switch failed:[/red] {error}", error=result.stderr.strip()))
    else:
        console.print(_("[green]gh:[/green] active user in {dst}: {user}", dst=dst.name, user=profile.gh_user))
