"""Backend GitHub CLI: diretório de config paralelo ~/.config/gh-<contexto>.

Os tokens ficam no keyring do macOS, então copiar ~/.config/gh e trocar o
usuário ativo com GH_CONFIG_DIR apontando para a cópia funciona sem novo login.
"""

from __future__ import annotations

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

    # dst já existente (ex.: login feito pelo wizard direto no dir do perfil)
    # dispensa a cópia; a config global só é necessária para clonar a sessão.
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
        env={"GH_CONFIG_DIR": str(dst), "PATH": _path_env()},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print(f"[red]gh auth switch falhou:[/red] {result.stderr.strip()}")
    else:
        console.print(f"[green]gh:[/green] usuário ativo em {dst.name}: {profile.gh_user}")


def _path_env() -> str:
    import os

    return os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin")
