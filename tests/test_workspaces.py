"""Exact workspace persistence and resolution."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aparta.fsutil import SafeWriter
from aparta.profiles import Profile
from aparta.workspaces import (
    Workspace,
    WorkspaceResolutionError,
    git_workspace_root,
    load_workspaces,
    resolve_workspace,
    save_workspaces,
    workspace_for_path,
)


def _git_init(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def test_workspace_roundtrip_preserves_exact_path_and_providers(tmp_path):
    """Dropping provider fields while saving would erase workspace isolation."""
    path = tmp_path / "workspaces.toml"
    workspace = Workspace(
        name="eneva-api",
        path=str(tmp_path / "eneva-api"),
        profile="eneva",
        providers=["git", "gcloud"],
    )

    save_workspaces({workspace.name: workspace}, SafeWriter(), path)

    assert load_workspaces(path) == {workspace.name: workspace}


def test_git_workspace_root_finds_top_level_from_a_nested_directory(tmp_path):
    """Using cwd directly would create separate records for repository subfolders."""
    repo = _git_init(tmp_path / "repo")
    nested = repo / "src" / "feature"
    nested.mkdir(parents=True)

    assert git_workspace_root(nested) == repo.resolve()


def test_explicit_worktree_record_beats_broad_profile_root(tmp_path):
    """Falling back to a broad root would lose the worktree-specific providers."""
    repo = _git_init(tmp_path / "clients" / "eneva" / "api")
    nested = repo / "src"
    nested.mkdir()
    profile = Profile(
        name="eneva",
        root=str(tmp_path / "clients" / "eneva"),
        git_email="dev@eneva.com",
    )
    explicit = Workspace(
        name="eneva-api",
        path=str(repo),
        profile="eneva",
        providers=["git", "bitbucket"],
    )

    resolved = workspace_for_path(
        nested,
        {profile.name: profile},
        {explicit.name: explicit},
    )

    assert resolved == explicit


def test_profile_owned_repository_has_backward_compatible_implicit_workspace(tmp_path):
    """Existing profile installations must activate before explicit migration."""
    repo = _git_init(tmp_path / "clients" / "whirlpool" / "trade")
    profile = Profile(
        name="whirlpool",
        root=str(tmp_path / "clients" / "whirlpool"),
        git_email="dev@whirlpool.com",
        gcloud_account="dev@whirlpool.com",
        gcloud_isolated=True,
    )

    resolved = workspace_for_path(repo, {profile.name: profile}, {})

    assert resolved is not None
    assert resolved.path == str(repo.resolve())
    assert resolved.profile == "whirlpool"
    assert {"git", "gcloud", "adc"}.issubset(resolved.providers)


def test_resolve_workspace_rejects_ambiguous_directory_names(tmp_path):
    """Choosing the first matching basename could activate the wrong client."""
    left = Workspace("client-a-api", str(tmp_path / "client-a" / "api"), "client-a", ["git"])
    right = Workspace("client-b-api", str(tmp_path / "client-b" / "api"), "client-b", ["git"])

    with pytest.raises(WorkspaceResolutionError, match="ambiguous"):
        resolve_workspace("api", tmp_path, {}, {left.name: left, right.name: right})
