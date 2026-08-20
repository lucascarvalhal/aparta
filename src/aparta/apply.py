"""Application layer: apply a profile across backends and agent adapters.

Lives between the UI layers (cli, wizard) and the backends so neither UI
imports the other. Output is one compact line per area; SafeWriter in
verbose mode adds the per-file detail and dry-run diffs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from rich.console import Console

from .agents import get_adapters
from .backends import Note
from .backends.aws import apply_aws
from .backends.gcloud import apply_gcloud
from .backends.gh import apply_gh
from .backends.git import apply_git
from .discovery import find_repos
from .fsutil import SafeWriter
from .i18n import _
from . import __version__
from .profiles import Profile, load_profiles, save_profiles

console = Console()

BACKENDS: list[tuple[str, Callable[[Profile, SafeWriter], "list[Note]"]]] = [
    ("git", apply_git),
    ("gh", apply_gh),
    ("gcloud", apply_gcloud),
    ("aws", apply_aws),
]


def _nested_profile_roots(
    profile: Profile, siblings: dict[str, Profile] | None = None
) -> list[Path]:
    """Roots of sibling profiles nested inside this profile's root.

    `siblings` allows callers holding unsaved profiles (wizard dry-run) to
    pass them in; otherwise the saved profiles are loaded.
    """
    root = profile.root_path
    return [
        p.root_path
        for p in (siblings or load_profiles()).values()
        if p.name != profile.name and p.root_path != root and root in p.root_path.parents
    ]


def profile_repos(profile: Profile, siblings: dict[str, Profile] | None = None) -> list[Path]:
    """The profile's repos: root scan minus nested sibling profiles, plus adopted.

    A repo under a more specific profile's root belongs to that profile, so
    a broad profile (e.g. ~/projects) never overwrites a nested one's env.
    """
    nested = _nested_profile_roots(profile, siblings)
    repos = [
        r
        for r in find_repos(profile.root_path)
        if not any(r == n or n in r.parents for n in nested)
    ]
    return repos + [Path(r).expanduser() for r in profile.adopted_repos]


def apply_profile(
    profile: Profile,
    writer: SafeWriter,
    siblings: dict[str, Profile] | None = None,
) -> None:
    """Apply every backend, then inject env into the profile's repos."""
    console.print(_("[bold]Applying profile '{name}'[/bold] (root: {root})", name=profile.name, root=profile.root_path))

    nested = _nested_profile_roots(profile, siblings)
    if nested:
        console.print(
            _(
                "[dim]Skipping repos owned by more specific profiles: {roots}[/dim]",
                roots=", ".join(str(n) for n in nested),
            )
        )

    for label, backend in BACKENDS:
        before = len(writer.changes)
        notes = backend(profile, writer)
        for note in notes:
            if note.level != "info" or writer.verbose:
                console.print(note.text)
        if len(writer.changes) > before or any(n.level == "info" for n in notes):
            console.print(_("  [green]OK[/green] {area}", area=label))

    env = profile.env()
    if not env:
        console.print(_("[dim]Profile has no gh/gcloud: no env to inject into agents.[/dim]"))
    else:
        repos = profile_repos(profile, siblings)
        if not repos:
            console.print(_("[yellow]No git repository found in {root}.[/yellow]", root=profile.root_path))
        before = len(writer.changes)
        adapters = get_adapters(profile.agents)
        for repo in repos:
            for adapter in adapters:
                if not adapter.detect(repo):
                    continue
                try:
                    adapter.inject(repo, env, writer)
                    # the same agent should also warn when a credential dies
                    adapter.install_check(repo, writer)
                except ValueError as exc:
                    # one repo with a broken config file must not stop the apply
                    console.print(
                        _("[yellow]warning:[/yellow] {adapter} in {repo}: {error}; skipping.", adapter=adapter.name, repo=repo.name, error=exc)
                    )
        # env and the startup hook can land in the same file: count files, not writes
        touched = len(set(writer.changes[before:]))
        if repos:
            console.print(
                _("  [green]OK[/green] agents: {n} config file(s) updated across {total} repo(s)", n=touched, total=len(repos))
            )

    if not writer.dry_run:
        _stamp_version(profile, writer)

    if writer.dry_run:
        console.print(_("[yellow]--dry-run: {n} planned change(s); nothing was modified.[/yellow]", n=len(writer.changes)))
        if not writer.verbose and writer.changes:
            console.print(_("[dim]Use --verbose to see every file and diff.[/dim]"))
    elif not writer.changes:
        console.print(_("[green]Everything was already applied; nothing to change.[/green]"))
    else:
        console.print(_("[green]Done: {n} file(s) updated (backups kept).[/green]", n=len(writer.changes)))
    console.print()


def _stamp_version(profile: Profile, writer: SafeWriter) -> None:
    """Remember which version applied this profile, to spot stale setups."""
    profile.applied_with = __version__
    saved = load_profiles()
    if profile.name in saved:
        saved[profile.name].applied_with = __version__
        quiet = SafeWriter(dry_run=False, verbose=False)
        save_profiles(saved, quiet)


def stale_profiles() -> list[str]:
    """Profiles applied by an older aparta, so they may miss new behaviour."""
    return [
        name
        for name, profile in load_profiles().items()
        if profile.applied_with != __version__
    ]
