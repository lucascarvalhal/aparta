"""Stray-repo adoption: adopted_repos plus the local include.path."""

from __future__ import annotations

import subprocess
from pathlib import Path

from aparta.backends.git import apply_adopted_git, context_gitconfig_path
from aparta.discovery import loose_repos
from aparta.fsutil import SafeWriter
from aparta.profiles import Profile, load_profiles, save_profiles


def _make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def test_loose_repos_skips_profile_covered_ones(tmp_path: Path):
    _make_repo(tmp_path / "projects" / "eneva" / "api")  # covered
    solto = _make_repo(tmp_path / "projects" / "avulso")  # stray
    result = loose_repos(
        [tmp_path / "projects" / "eneva"], scan_roots=[str(tmp_path / "projects")]
    )
    assert result == [solto]


def test_adopted_repos_roundtrip_in_toml(tmp_path: Path):
    path = tmp_path / "profiles.toml"
    p = Profile(name="x", root="~/x", git_email="a@b.c", adopted_repos=["~/projects/avulso"])
    save_profiles({"x": p}, SafeWriter(), path)
    loaded = load_profiles(path)
    assert loaded["x"].adopted_repos == ["~/projects/avulso"]


def test_apply_adopted_adds_local_include(tmp_path: Path):
    repo = _make_repo(tmp_path / "avulso")
    p = Profile(name="eneva", root="~/x", git_email="a@b.c", adopted_repos=[str(repo)])
    (tmp_path / ".gitconfig-eneva").write_text("[user]\n\temail = a@b.c\n")

    apply_adopted_git(p, SafeWriter(), home=tmp_path)

    include = str(context_gitconfig_path(p, tmp_path))
    r = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "--get-all", "include.path"],
        capture_output=True,
        text=True,
    )
    assert include in r.stdout.splitlines()
    # e-mail inherited from the profile's gitconfig
    r = subprocess.run(
        ["git", "-C", str(repo), "config", "user.email"], capture_output=True, text=True
    )
    assert r.stdout.strip() == "a@b.c"


def test_apply_adopted_is_idempotent(tmp_path: Path):
    repo = _make_repo(tmp_path / "avulso")
    p = Profile(name="x", root="~/x", git_email="a@b.c", adopted_repos=[str(repo)])
    apply_adopted_git(p, SafeWriter(), home=tmp_path)
    apply_adopted_git(p, SafeWriter(), home=tmp_path)
    r = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "--get-all", "include.path"],
        capture_output=True,
        text=True,
    )
    assert len(r.stdout.splitlines()) == 1


def test_apply_adopted_dry_run_writes_nothing(tmp_path: Path):
    repo = _make_repo(tmp_path / "avulso")
    p = Profile(name="x", root="~/x", git_email="a@b.c", adopted_repos=[str(repo)])
    apply_adopted_git(p, SafeWriter(dry_run=True), home=tmp_path)
    r = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "--get-all", "include.path"],
        capture_output=True,
        text=True,
    )
    assert r.stdout.strip() == ""


def test_apply_adopted_warns_on_non_git_dir(tmp_path: Path):
    (tmp_path / "nao-repo").mkdir()
    p = Profile(name="x", root="~/x", git_email="a@b.c", adopted_repos=[str(tmp_path / "nao-repo")])
    apply_adopted_git(p, SafeWriter(), home=tmp_path)  # must not raise
