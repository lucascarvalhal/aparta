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
        name="acme-api",
        path=str(tmp_path / "acme-api"),
        profile="acme",
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


def test_git_workspace_root_ignores_inherited_repository_redirection(tmp_path, monkeypatch):
    """GIT_DIR from another client must not redirect contextual resolution."""
    expected = _git_init(tmp_path / "expected")
    foreign = _git_init(tmp_path / "foreign")
    monkeypatch.setenv("GIT_DIR", str(foreign / ".git"))

    assert git_workspace_root(expected) == expected.resolve()


def test_explicit_worktree_record_beats_broad_profile_root(tmp_path):
    """Falling back to a broad root would lose the worktree-specific providers."""
    repo = _git_init(tmp_path / "clients" / "acme" / "api")
    nested = repo / "src"
    nested.mkdir()
    profile = Profile(
        name="acme",
        root=str(tmp_path / "clients" / "acme"),
        git_email="dev@acme.com",
    )
    explicit = Workspace(
        name="acme-api",
        path=str(repo),
        profile="acme",
        providers=["git", "ssh"],
    )

    resolved = workspace_for_path(
        nested,
        {profile.name: profile},
        {explicit.name: explicit},
    )

    assert resolved == explicit


def test_profile_owned_repository_has_backward_compatible_implicit_workspace(tmp_path):
    """Existing profile installations must activate before explicit migration."""
    repo = _git_init(tmp_path / "clients" / "initech" / "trade")
    profile = Profile(
        name="initech",
        root=str(tmp_path / "clients" / "initech"),
        git_email="dev@initech.com",
        gcloud_account="dev@initech.com",
        gcloud_isolated=True,
    )

    resolved = workspace_for_path(repo, {profile.name: profile}, {})

    assert resolved is not None
    assert resolved.path == str(repo.resolve())
    assert resolved.profile == "initech"
    assert {"git", "gcloud", "adc"}.issubset(resolved.providers)


def test_resolve_workspace_rejects_ambiguous_directory_names(tmp_path):
    """Choosing the first matching basename could activate the wrong client."""
    left = Workspace("client-a-api", str(tmp_path / "client-a" / "api"), "client-a", ["git"])
    right = Workspace("client-b-api", str(tmp_path / "client-b" / "api"), "client-b", ["git"])

    with pytest.raises(WorkspaceResolutionError, match="ambiguous"):
        resolve_workspace("api", tmp_path, {}, {left.name: left, right.name: right})


def test_resolve_workspace_rejects_ambiguous_implicit_repo_names(tmp_path):
    """Legacy profile repos with the same basename must never be guessed."""
    left_repo = _git_init(tmp_path / "client-a" / "api")
    right_repo = _git_init(tmp_path / "client-b" / "api")
    profiles = {
        "client-a": Profile("client-a", str(left_repo.parent), "a@example.com"),
        "client-b": Profile("client-b", str(right_repo.parent), "b@example.com"),
    }

    with pytest.raises(WorkspaceResolutionError, match="ambiguous") as exc:
        resolve_workspace("api", tmp_path, profiles, {})

    assert str(left_repo.resolve()) in str(exc.value)
    assert str(right_repo.resolve()) in str(exc.value)
