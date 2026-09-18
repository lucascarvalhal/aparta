"""Stray-repo adoption: adopted_repos plus the local include.path."""

from __future__ import annotations

import subprocess
from pathlib import Path

import os

from aparta.backends.git import reconcile_workspace_git
from aparta.discovery import loose_repos
from aparta.fsutil import SafeWriter
from aparta.profiles import Profile, load_profiles, save_profiles


def _make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def test_loose_repos_skips_profile_covered_ones(tmp_path: Path):
    _make_repo(tmp_path / "projects" / "acme" / "api")
    solto = _make_repo(tmp_path / "projects" / "avulso")
    result = loose_repos(
        [tmp_path / "projects" / "acme"], scan_roots=[str(tmp_path / "projects")]
    )
    assert result == [solto]


def test_adopted_repos_roundtrip_in_toml(tmp_path: Path):
    path = tmp_path / "profiles.toml"
    p = Profile(name="x", root="~/x", git_email="a@b.c", adopted_repos=["~/projects/avulso"])
    save_profiles({"x": p}, SafeWriter(), path)
    loaded = load_profiles(path)
    assert loaded["x"].adopted_repos == ["~/projects/avulso"]


def test_adopted_repo_gets_the_profile_identity(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path / "cfg"))
    home = tmp_path / "home"
    home.mkdir()
    repo = _make_repo(tmp_path / "elsewhere" / "avulso")
    p = Profile(name="acme", root=str(home / "acme"), git_email="a@b.c", adopted_repos=[str(repo)])

    reconcile_workspace_git({p.name: p}, {}, SafeWriter(), home=home)

    query_env = {**os.environ, "GIT_CONFIG_GLOBAL": str(home / ".gitconfig")}
    r = subprocess.run(
        ["git", "-C", str(repo), "config", "user.email"], env=query_env, capture_output=True, text=True
    )
    assert r.stdout.strip() == "a@b.c"


def test_missing_adopted_repo_is_skipped(tmp_path: Path):
    from aparta.workspaces import profile_repos

    p = Profile(name="x", root=str(tmp_path / "x"), git_email="a@b.c", adopted_repos=[str(tmp_path / "gone")])
    assert profile_repos(p, {p.name: p}) == []
