"""Exact Git checkout bindings persisted outside product repositories."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import config_dir, load_table, save_table
from .fsutil import SafeWriter
from .profiles import Profile

IGNORED_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "target",
    "vendor",
    "Pods",
    "DerivedData",
    "site-packages",
}

SYSTEM_DIRS = {
    "Library",
    "Applications",
    "Movies",
    "Music",
    "Pictures",
    "Public",
    "AppData",
}

DEFAULT_SCAN_DEPTH = 4


class WorkspaceResolutionError(ValueError):
    """A workspace selector is missing, unknown, or ambiguous."""


@dataclass(eq=True)
class Workspace:
    """One exact main checkout or linked Git worktree."""

    name: str
    path: str
    profile: str
    providers: list[str] = field(default_factory=list)

    @property
    def root_path(self) -> Path:
        return Path(self.path).expanduser().resolve()


def workspaces_path() -> Path:
    return config_dir() / "workspaces.toml"


def load_workspaces(path: Path | None = None) -> dict[str, Workspace]:
    result: dict[str, Workspace] = {}
    for name, raw in load_table(path or workspaces_path(), "workspaces").items():
        result[name] = Workspace(
            name=name,
            path=str(raw.get("path", "")),
            profile=str(raw.get("profile", "")),
            providers=list(dict.fromkeys(raw.get("providers", []))),
        )
    return result


def save_workspaces(
    workspaces: dict[str, Workspace],
    writer: SafeWriter,
    path: Path | None = None,
) -> None:
    rows = {
        name: {key: value for key, value in asdict(workspace).items() if key != "name"}
        for name, workspace in sorted(workspaces.items())
    }
    save_table(path or workspaces_path(), "workspaces", rows, writer)


def git_env() -> dict[str, str]:
    """The caller's environment without any redirection of which repository git sees."""
    env = dict(os.environ)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"):
        env.pop(key, None)
    return env


def git_workspace_root(path: Path) -> Path | None:
    """Return Git's exact top-level for a directory, including linked worktrees."""
    candidate = path.expanduser()
    if not candidate.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
            env=git_env(),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).expanduser().resolve()


def find_repos(root: Path, max_depth: int = 3) -> list[Path]:
    """git repos under root, depth-limited, skipping non-project directories."""
    repos: list[Path] = []
    if not root.exists():
        return repos
    if (root / ".git").exists():
        return [root]

    def walk(d: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            children = sorted(
                p
                for p in d.iterdir()
                if p.is_dir()
                and not p.is_symlink()
                and not p.name.startswith(".")
                and p.name not in IGNORED_DIRS
                and p.name not in SYSTEM_DIRS
            )
        except PermissionError:
            return
        for child in children:
            if (child / ".git").exists():
                repos.append(child)
            else:
                walk(child, depth + 1)

    walk(root, 1)
    return repos


def nested_profile_roots(profile: Profile, profiles: Mapping[str, Profile]) -> list[Path]:
    """Roots of other profiles that live inside this profile's root."""
    root = profile.root_path
    return [
        other.root_path
        for other in profiles.values()
        if other.name != profile.name and other.root_path != root and root in other.root_path.parents
    ]


def profile_repos(profile: Profile, profiles: Mapping[str, Profile]) -> list[Path]:
    """The profile's checkouts: its root scan minus nested profiles, plus adopted repos that exist."""
    nested = nested_profile_roots(profile, profiles)
    repos = [r for r in find_repos(profile.root_path) if not any(r == n or n in r.parents for n in nested)]
    adopted = (Path(raw).expanduser() for raw in profile.adopted_repos)
    return repos + [repo for repo in adopted if repo.exists()]


def profile_for_path(path: Path, profiles: dict[str, Profile]) -> Profile | None:
    """Return the profile owning a path, with the deepest configured root winning."""
    path = path.expanduser().resolve()
    best: Profile | None = None
    best_depth = -1
    for profile in profiles.values():
        candidates = [profile.root_path] + [Path(raw).expanduser() for raw in profile.adopted_repos]
        for root in candidates:
            root = root.resolve()
            if path == root or root in path.parents:
                depth = len(root.parts)
                if depth > best_depth:
                    best, best_depth = profile, depth
    return best


def default_providers(profile: Profile) -> list[str]:
    """Providers represented by a legacy profile before workspace records existed."""
    providers = ["git"]
    if profile.ssh_key or profile.ssh_alias:
        providers.append("ssh")
    if profile.gh_user:
        providers.append("github")
    if profile.gcloud_account or profile.gcloud_project:
        providers.append("gcloud")
        if profile.gcloud_isolated:
            providers.append("adc")
    if profile.aws_profile:
        providers.append("aws")
    return providers


def implicit_workspace(root: Path, profile: Profile) -> Workspace:
    return Workspace(
        name=root.name,
        path=str(root.resolve()),
        profile=profile.name,
        providers=default_providers(profile),
    )


def implicit_workspaces(profiles: Mapping[str, Profile]) -> dict[Path, Workspace]:
    """Every checkout the profiles own, keyed by exact git root, the deepest owner winning."""
    found: dict[Path, Workspace] = {}
    for profile in profiles.values():
        for repo in profile_repos(profile, profiles):
            root = git_workspace_root(repo)
            owner = profile_for_path(root, profiles) if root is not None else None
            if root is not None and owner is not None:
                found[root] = implicit_workspace(root, owner)
    return found


def known_workspaces(
    profiles: Mapping[str, Profile], workspaces: Mapping[str, Workspace]
) -> dict[Path, Workspace]:
    """Implicit checkouts with the explicit records laid over them."""
    candidates = implicit_workspaces(profiles)
    for workspace in workspaces.values():
        root = git_workspace_root(workspace.root_path)
        if root is not None and workspace.profile in profiles:
            candidates[root] = Workspace(workspace.name, str(root), workspace.profile, list(workspace.providers))
    return candidates


def workspace_for_path(
    path: Path,
    profiles: dict[str, Profile],
    workspaces: dict[str, Workspace],
) -> Workspace | None:
    """Resolve the exact checkout first, then the legacy owning profile."""
    root = git_workspace_root(path)
    if root is None:
        return None
    explicit = [workspace for workspace in workspaces.values() if workspace.root_path == root]
    if len(explicit) > 1:
        names = ", ".join(sorted(workspace.name for workspace in explicit))
        raise WorkspaceResolutionError(f"workspace path is ambiguous: {names}")
    if explicit:
        return explicit[0]
    profile = profile_for_path(root, profiles)
    return implicit_workspace(root, profile) if profile else None


def resolve_workspace(
    selector: str,
    cwd: Path,
    profiles: dict[str, Profile],
    workspaces: dict[str, Workspace],
) -> Workspace:
    """Resolve a contextual or explicit workspace selector without guessing."""
    if not selector:
        current = workspace_for_path(cwd, profiles, workspaces)
        if current is None:
            raise WorkspaceResolutionError("this folder belongs to no registered workspace")
        return current

    if selector in workspaces:
        return workspaces[selector]

    candidate_path = Path(selector).expanduser()
    if candidate_path.exists():
        selected = workspace_for_path(candidate_path, profiles, workspaces)
        if selected is not None:
            return selected

    by_basename = [workspace for workspace in workspaces.values() if workspace.root_path.name == selector]
    if len(by_basename) == 1:
        return by_basename[0]
    if len(by_basename) > 1:
        names = ", ".join(sorted(workspace.name for workspace in by_basename))
        raise WorkspaceResolutionError(f"workspace selector is ambiguous: {names}")

    implicit_matches = [w for root, w in implicit_workspaces(profiles).items() if root.name == selector]
    if len(implicit_matches) == 1:
        return implicit_matches[0]
    if len(implicit_matches) > 1:
        paths = ", ".join(sorted(str(workspace.root_path) for workspace in implicit_matches))
        raise WorkspaceResolutionError(f"workspace selector is ambiguous: {paths}")

    if selector in profiles:
        current = workspace_for_path(cwd, profiles, workspaces)
        if current is not None and current.profile == selector:
            return current
        matches = [workspace for workspace in workspaces.values() if workspace.profile == selector]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            names = ", ".join(sorted(workspace.name for workspace in matches))
            raise WorkspaceResolutionError(f"profile has multiple workspaces: {names}")

    raise WorkspaceResolutionError(f"workspace '{selector}' not found")


def resolve_target(
    selector: str,
    cwd: Path,
    profiles: dict[str, Profile],
    workspaces: dict[str, Workspace],
) -> tuple[Profile, Workspace | None]:
    """A profile named outright, or the workspace a selector resolves to and its profile."""
    if selector and selector in profiles:
        return profiles[selector], None
    workspace = resolve_workspace(selector, cwd, profiles, workspaces)
    profile = profiles.get(workspace.profile)
    if profile is None:
        raise WorkspaceResolutionError(
            f"workspace '{workspace.name}' points to unknown profile '{workspace.profile}'"
        )
    return profile, workspace


def enable_provider(
    workspaces: dict[str, Workspace], workspace: Workspace, provider: str
) -> tuple[Workspace, bool]:
    """Record a provider on the exact checkout; a first record starts from git alone."""
    existing = next(
        (name for name, saved in workspaces.items() if saved.root_path == workspace.root_path), ""
    )
    if existing and provider in workspace.providers:
        return workspaces[existing], True
    base_providers = workspace.providers if existing else ["git"]
    record = Workspace(
        existing or _unique_name(workspaces, workspace),
        str(workspace.root_path),
        workspace.profile,
        list(dict.fromkeys([*base_providers, provider])),
    )
    workspaces[record.name] = record
    return record, False


def _unique_name(workspaces: dict[str, Workspace], workspace: Workspace) -> str:
    taken = workspace.name in workspaces and workspaces[workspace.name].root_path != workspace.root_path
    if not taken:
        return workspace.name
    base = f"{workspace.profile}-{workspace.name}"
    name, suffix = base, 2
    while name in workspaces:
        name = f"{base}-{suffix}"
        suffix += 1
    return name
