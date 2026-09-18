"""Application layer: remove a profile and undo what it applied."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

from .agents import get_adapters
from .backends.gcloud import configuration_exists
from .backends.git import context_gitconfig_path, gitdir_pattern, remove_includeif
from .discovery import find_repos
from .fsutil import SafeWriter
from .i18n import _
from .profiles import Profile, is_managed_env_key, load_profiles

console = Console()


def remove_profile(profile: Profile, writer: SafeWriter, home: Path | None = None) -> None:
    """Undo everything the profile applied: agent env, git includes, gh dir and gcloud config."""
    home = home or Path.home()
    console.print(_("[bold]Removing profile '{name}'[/bold]", name=profile.name) + "\n")

    repos = find_repos(profile.root_path) + [
        Path(r).expanduser() for r in profile.adopted_repos
    ]
    for repo in repos:
        for adapter in get_adapters(profile.agents):
            try:
                keys = [key for key in adapter.read_env(repo) if is_managed_env_key(key)]
                if keys:
                    adapter.remove_env(repo, keys, writer)
                adapter.uninstall_check(repo, writer)
            except ValueError:
                continue

    from .backends.git import reconcile_workspace_git, workspace_gitconfig_path
    from .workspaces import (
        Workspace,
        default_providers,
        git_workspace_root,
        load_workspaces,
        save_workspaces,
    )

    profiles = load_profiles()
    profiles.pop(profile.name, None)
    workspaces = load_workspaces()
    removed_workspaces = [
        workspace for workspace in workspaces.values() if workspace.profile == profile.name
    ]
    remaining_workspaces = {
        name: workspace
        for name, workspace in workspaces.items()
        if workspace.profile != profile.name
    }
    if len(remaining_workspaces) != len(workspaces):
        save_workspaces(remaining_workspaces, writer)
    reconcile_workspace_git(profiles, remaining_workspaces, writer, home=home)
    implicit_removed = []
    for repo in repos:
        root = git_workspace_root(repo)
        if root is not None:
            implicit_removed.append(
                Workspace(
                    root.name,
                    str(root),
                    profile.name,
                    default_providers(profile),
                )
            )
    for workspace in [*removed_workspaces, *implicit_removed]:
        writer.remove_file(workspace_gitconfig_path(workspace))

    include = str(context_gitconfig_path(profile, home))
    for raw in profile.adopted_repos:
        repo = Path(raw).expanduser()
        if not (repo / ".git").exists():
            continue
        if writer.dry_run:
            console.print(
                f"[yellow]--dry-run[/yellow] git -C {repo} config --local "
                f"--unset-all include.path {include}"
            )
            continue
        subprocess.run(
            ["git", "-C", str(repo), "config", "--local", "--unset-all",
             "include.path", include],
            capture_output=True,
            text=True,
            timeout=30,
        )

    gitconfig = home / ".gitconfig"
    if gitconfig.exists():
        cleaned = remove_includeif(gitconfig.read_text(), gitdir_pattern(profile))
        if cleaned != gitconfig.read_text():
            writer.write_text(gitconfig, cleaned)
    writer.remove_file(context_gitconfig_path(profile, home))

    writer.remove_dir(profile.gh_config_dir)

    if profile.gcloud_isolated:
        writer.remove_dir(profile.gcloud_config_dir)
    elif profile.gcloud_account or profile.gcloud_project:
        if writer.dry_run:
            console.print(
                f"[yellow]--dry-run[/yellow] gcloud config configurations delete "
                f"{profile.name} --quiet"
            )
        elif configuration_exists(profile.name):
            r = subprocess.run(
                ["gcloud", "config", "configurations", "delete", profile.name, "--quiet"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode != 0:
                console.print(_("[red]{cmd} failed:[/red] {error}",
                                cmd="gcloud configurations delete", error=r.stderr.strip()))

    if writer.dry_run:
        console.print("\n" + _("[yellow]--dry-run: {n} planned change(s); nothing was modified.[/yellow]", n=len(writer.changes)))
    else:
        console.print("\n" + _("[green]Profile '{name}' removed. Backups were kept for every touched file.[/green]", name=profile.name))
