"""Application layer: apply a profile across backends and agent adapters."""

from __future__ import annotations

from typing import Callable

from rich.console import Console

from .agents import get_adapters
from .backends import Note
from .backends.aws import apply_aws
from .backends.gcloud import apply_gcloud
from .backends.gh import apply_gh
from .fsutil import SafeWriter
from .i18n import _
from . import __version__
from .profiles import MANAGED_ENV_KEYS, Profile, load_profiles, save_profiles
from .providers import workspace_env
from .workspaces import Workspace, load_workspaces, nested_profile_roots, profile_repos, workspace_for_path

console = Console()

BACKENDS: list[tuple[str, Callable[[Profile, SafeWriter], list[Note]]]] = [
    ("gh", apply_gh),
    ("gcloud", apply_gcloud),
    ("aws", apply_aws),
]


def apply_workspace_agents(
    profile: Profile,
    workspace: Workspace,
    writer: SafeWriter,
) -> int:
    """Reconcile selected agent files for one exact workspace."""
    from .backends.git import render_workspace_gitconfig, workspace_gitconfig_path

    env = workspace_env(workspace, profile)
    before = len(writer.changes)
    if set(workspace.providers).intersection({"git", "ssh"}):
        writer.write_text(
            workspace_gitconfig_path(workspace),
            render_workspace_gitconfig(profile, workspace),
        )
    for adapter in get_adapters(profile.agents):
        try:
            if env:
                adapter.inject(workspace.root_path, env, writer)
            stale = [
                key
                for key in MANAGED_ENV_KEYS
                if key not in env and key in adapter.read_env(workspace.root_path)
            ]
            if stale:
                adapter.remove_env(workspace.root_path, stale, writer)
            if env:
                adapter.install_check(workspace.root_path, writer)
        except ValueError as exc:
            console.print(
                _(
                    "[yellow]warning:[/yellow] {adapter} in {repo}: {error}; skipping.",
                    adapter=adapter.name,
                    repo=workspace.root_path.name,
                    error=exc,
                )
            )
    return len(set(writer.changes[before:]))


def apply_profile(
    profile: Profile,
    writer: SafeWriter,
    siblings: dict[str, Profile] | None = None,
) -> None:
    """Apply every backend, then inject env into the profile's repos."""
    console.print(_("[bold]Applying profile '{name}'[/bold] (root: {root})", name=profile.name, root=profile.root_path))

    ownership_profiles = siblings or load_profiles()
    ownership_profiles.setdefault(profile.name, profile)
    nested = nested_profile_roots(profile, ownership_profiles)
    if nested:
        console.print(
            _(
                "[dim]Skipping repos owned by more specific profiles: {roots}[/dim]",
                roots=", ".join(str(n) for n in nested),
            )
        )

    saved_workspaces = load_workspaces()

    for label, backend in BACKENDS:
        before = len(writer.changes)
        notes = backend(profile, writer)
        for note in notes:
            if note.level != "info" or writer.verbose:
                console.print(note.text)
        if len(writer.changes) > before or any(n.level == "info" for n in notes):
            console.print(_("  [green]OK[/green] {area}", area=label))

    from .backends.git import reconcile_workspace_git

    reconcile_workspace_git(ownership_profiles, saved_workspaces, writer)

    default_env = profile.env()
    if not default_env:
        console.print(_("[dim]Profile has no gh/gcloud: no env to inject into agents.[/dim]"))
    repos = profile_repos(profile, ownership_profiles)
    if not repos:
        console.print(_("[yellow]No git repository found in {root}.[/yellow]", root=profile.root_path))
    before = len(writer.changes)
    adapters = get_adapters(profile.agents)
    for repo in repos:
        workspace = workspace_for_path(repo, ownership_profiles, saved_workspaces)
        if workspace is not None and workspace.profile != profile.name:
            continue
        env = workspace_env(workspace, profile) if workspace is not None else default_env
        for adapter in adapters:
            try:
                if env:
                    adapter.inject(repo, env, writer)
                stale = [
                    key
                    for key in MANAGED_ENV_KEYS
                    if key not in env and key in adapter.read_env(repo)
                ]
                if stale:
                    adapter.remove_env(repo, stale, writer)
                if env:
                    adapter.install_check(repo, writer)
            except ValueError as exc:
                console.print(
                    _("[yellow]warning:[/yellow] {adapter} in {repo}: {error}; skipping.", adapter=adapter.name, repo=repo.name, error=exc)
                )
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
