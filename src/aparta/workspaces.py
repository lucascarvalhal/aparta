"""Exact Git checkout bindings persisted outside product repositories."""

from __future__ import annotations

from . import _toml

import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path



from .fsutil import SafeWriter
from .profiles import Profile, config_dir


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
    path = path or workspaces_path()
    if not path.exists():
        return {}
    data = _toml.loads(path.read_text())
    result: dict[str, Workspace] = {}
    for name, raw in data.get("workspaces", {}).items():
        fields = {key: value for key, value in raw.items() if key in Workspace.__dataclass_fields__}
        providers = list(dict.fromkeys(fields.get("providers", [])))
        result[name] = Workspace(
            name=name,
            path=str(fields.get("path", "")),
            profile=str(fields.get("profile", "")),
            providers=providers,
        )
    return result


def save_workspaces(
    workspaces: dict[str, Workspace],
    writer: SafeWriter,
    path: Path | None = None,
) -> None:
    path = path or workspaces_path()
    doc = {
        "workspaces": {
            name: {key: value for key, value in asdict(workspace).items() if key != "name"}
            for name, workspace in sorted(workspaces.items())
        }
    }
    writer.write_text(path, _toml.dumps(doc), label=str(path))


def git_workspace_root(path: Path) -> Path | None:
    """Return Git's exact top-level for a directory, including linked worktrees."""
    candidate = path.expanduser()
    if candidate.is_file():
        candidate = candidate.parent
    env = dict(os.environ)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"):
        env.pop(key, None)
    try:
        result = subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).expanduser().resolve()


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


def _implicit_workspaces_named(
    name: str,
    profiles: dict[str, Profile],
) -> list[Workspace]:
    """Find legacy profile-owned repos by basename before first materialization."""
    from .discovery import find_repos

    matches: dict[Path, Workspace] = {}
    for profile in profiles.values():
        repos = find_repos(profile.root_path) + [
            Path(raw).expanduser() for raw in profile.adopted_repos
        ]
        for repo in repos:
            root = git_workspace_root(repo)
            if root is None or root.name != name:
                continue
            owner = profile_for_path(root, profiles)
            if owner is not None:
                matches[root] = implicit_workspace(root, owner)
    return list(matches.values())


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

    implicit_matches = _implicit_workspaces_named(selector, profiles)
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
