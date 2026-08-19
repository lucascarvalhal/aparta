"""Application layer: apply a profile across backends and agent adapters.

Lives between the UI layers (cli, wizard) and the backends so neither UI
imports the other. New backends only need to be added to BACKENDS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .i18n import _
from rich.console import Console

from .agents import get_adapters
from .backends import Note
from .backends.gcloud import apply_gcloud
from .backends.gh import apply_gh
from .backends.git import apply_git
from .discovery import find_repos
from .fsutil import SafeWriter
from .profiles import Profile

console = Console()

BACKENDS: list[Callable[[Profile, SafeWriter], "list[Note]"]] = [
    apply_git,
    apply_gh,
    apply_gcloud,
]


def apply_profile(profile: Profile, writer: SafeWriter) -> None:
    """Apply every backend, then inject env into the profile's repos."""
    console.print(_("[bold]Applying profile '{name}'[/bold] (root: {root})", name=profile.name, root=profile.root_path) + "\n")

    for backend in BACKENDS:
        for note in backend(profile, writer):
            console.print(note.text)

    env = profile.env()
    if not env:
        console.print(_("[dim]Profile has no gh/gcloud: no env to inject into agents.[/dim]"))
    else:
        repos = find_repos(profile.root_path) + [
            Path(r).expanduser() for r in profile.adopted_repos
        ]
        if not repos:
            console.print(_("[yellow]No git repository found in {root}.[/yellow]", root=profile.root_path))
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
                        _("[yellow]warning:[/yellow] {adapter} in {repo}: {error}; skipping.", adapter=adapter.name, repo=repo.name, error=exc)
                    )

    if writer.dry_run:
        console.print("\n" + _("[yellow]--dry-run: {n} planned change(s); nothing was modified.[/yellow]", n=len(writer.changes)))
    elif not writer.changes:
        console.print("\n" + _("[green]Everything was already applied; nothing to change.[/green]"))
    else:
        console.print("\n" + _("[green]Done: {n} file(s) updated.[/green]", n=len(writer.changes)))
