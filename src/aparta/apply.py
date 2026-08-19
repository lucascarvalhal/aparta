"""Application layer: apply a profile across backends and agent adapters.

Lives between the UI layers (cli, wizard) and the backends so neither UI
imports the other. New backends only need to be added to BACKENDS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from rich.console import Console

from .agents import get_adapters
from .backends.gcloud import apply_gcloud
from .backends.gh import apply_gh
from .backends.git import apply_git
from .discovery import find_repos
from .fsutil import SafeWriter
from .profiles import Profile

console = Console()

BACKENDS: list[Callable[[Profile, SafeWriter], None]] = [
    apply_git,
    apply_gh,
    apply_gcloud,
]


def apply_profile(profile: Profile, writer: SafeWriter) -> None:
    """Apply every backend, then inject env into the profile's repos."""
    console.print(f"[bold]Aplicando perfil '{profile.name}'[/bold] (raiz: {profile.root_path})\n")

    for backend in BACKENDS:
        backend(profile, writer)

    env = profile.env()
    if not env:
        console.print("[dim]Perfil sem gh/gcloud: nada de env para injetar nos agentes.[/dim]")
    else:
        repos = find_repos(profile.root_path) + [
            Path(r).expanduser() for r in profile.adopted_repos
        ]
        if not repos:
            console.print(f"[yellow]Nenhum repositório git encontrado em {profile.root_path}.[/yellow]")
        adapters = get_adapters(profile.agents)
        for repo in repos:
            for adapter in adapters:
                if not adapter.detect(repo):
                    continue
                try:
                    adapter.inject(repo, env, writer)
                except ValueError as exc:
                    # one repo with a broken config file must not stop the apply
                    console.print(
                        f"[yellow]aviso:[/yellow] {adapter.name} em {repo.name}: {exc}; pulando."
                    )

    if writer.dry_run:
        console.print(f"\n[yellow]--dry-run: {len(writer.changes)} mudança(s) prevista(s); nada foi alterado.[/yellow]")
    elif not writer.changes:
        console.print("\n[green]Tudo já estava aplicado; nada a mudar.[/green]")
    else:
        console.print(f"\n[green]Pronto: {len(writer.changes)} arquivo(s) atualizado(s).[/green]")
