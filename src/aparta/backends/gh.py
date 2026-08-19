"""GitHub CLI backend: parallel config directory ~/.config/gh-<profile>.

Tokens live in the OS keyring, so copying ~/.config/gh and switching the
active user inside the copy (via GH_CONFIG_DIR) needs no re-login.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from rich.console import Console

from ..fsutil import SafeWriter
from ..profiles import Profile

console = Console()


def apply_gh(profile: Profile, writer: SafeWriter, home: Path | None = None) -> None:
    if not profile.gh_user:
        return
    home = home or Path.home()
    src = home / ".config" / "gh"
    dst = home / ".config" / f"gh-{profile.name}"

    # an existing dst (e.g. wizard logged in straight into the profile dir)
    # needs no copy; the global config is only used to clone a session
    if not dst.exists() and not src.exists():
        console.print("[yellow]aviso:[/yellow] ~/.config/gh não existe — rode `gh auth login` antes.")
        return

    if writer.dry_run:
        if not dst.exists():
            console.print(f"[yellow]--dry-run[/yellow] copiaria {src} -> {dst}")
        console.print(
            f"[yellow]--dry-run[/yellow] GH_CONFIG_DIR={dst} gh auth switch --user {profile.gh_user}"
        )
        return

    if not dst.exists():
        shutil.copytree(src, dst)
        console.print(f"[green]criado:[/green] {dst}")

    result = subprocess.run(
        ["gh", "auth", "switch", "--user", profile.gh_user],
        env=dict(os.environ, GH_CONFIG_DIR=str(dst)),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print(f"[red]gh auth switch falhou:[/red] {result.stderr.strip()}")
    else:
        console.print(f"[green]gh:[/green] usuário ativo em {dst.name}: {profile.gh_user}")
