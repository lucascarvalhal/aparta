"""doctor.check_profile branches with subprocess mocked."""

from __future__ import annotations

import subprocess
from pathlib import Path

from aparta import doctor
from aparta.profiles import Profile


def _fake_run(responses: dict[str, tuple[int, str]]):
    """Map a command marker to (returncode, stdout); default success/empty."""

    def run(args, env=None, capture_output=True, text=True, timeout=None):
        joined = " ".join(args)
        for marker, (code, out) in responses.items():
            if marker in joined:
                return subprocess.CompletedProcess(args, code, stdout=out, stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    return run


def _repo(tmp_path: Path, name: str) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


def test_check_profile_git_email_ok_and_divergent(tmp_path, monkeypatch):
    _repo(tmp_path, "good")
    profile = Profile(name="x", root=str(tmp_path), git_email="a@b.c")
    monkeypatch.setattr(
        doctor.subprocess, "run", _fake_run({"config user.email": (0, "a@b.c\n")})
    )
    assert doctor.check_profile(profile) is True

    monkeypatch.setattr(
        doctor.subprocess, "run", _fake_run({"config user.email": (0, "wrong@x.y\n")})
    )
    assert doctor.check_profile(profile) is False


def test_check_profile_no_repos_is_inconclusive_not_failure(tmp_path):
    profile = Profile(name="x", root=str(tmp_path / "empty"), git_email="a@b.c")
    assert doctor.check_profile(profile) is False  # None row counts as not-ok


def test_check_profile_gh_dir_missing_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    _repo(tmp_path, "r")
    profile = Profile(
        name="x", root=str(tmp_path), git_email="a@b.c", gh_user="someone"
    )
    monkeypatch.setattr(
        doctor.subprocess, "run", _fake_run({"config user.email": (0, "a@b.c\n")})
    )
    assert doctor.check_profile(profile) is False


def test_check_profile_missing_binary_reports_failure(tmp_path, monkeypatch):
    _repo(tmp_path, "r")
    profile = Profile(name="x", root=str(tmp_path), git_email="a@b.c")

    def raise_missing(args, **kwargs):
        raise FileNotFoundError(args[0])

    monkeypatch.setattr(doctor.subprocess, "run", raise_missing)
    assert doctor.check_profile(profile) is False
