"""doctor --fix: repairs the deterministic, never the human-only."""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

from aparta import auth, doctor
from aparta.profiles import Profile


@pytest.fixture(autouse=True)
def offline_auth_checks(monkeypatch):
    """Credential probes are opt-in per test; the rest is doctor's own logic."""
    monkeypatch.setenv("APARTA_AUTH_CHECK", "off")


@pytest.fixture
def output(monkeypatch) -> io.StringIO:
    """Capture doctor's rich output at a width that never wraps assertions."""
    buffer = io.StringIO()
    monkeypatch.setattr(doctor, "console", Console(file=buffer, width=200, no_color=True))
    return buffer


def _recorder(responses: dict[str, tuple[int, str]], calls: list[list[str]]):
    """Fake subprocess.run: record every command, answer by marker."""

    def run(args, env=None, capture_output=True, text=True, timeout=None, stdin=None, **kwargs):
        calls.append(list(args))
        joined = " ".join(args)
        for marker, (code, out) in responses.items():
            if marker in joined:
                return subprocess.CompletedProcess(args, code, stdout=out, stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    return run


def _repo(tmp_path: Path, name: str = "r") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


def test_fix_repairs_a_divergent_gcloud_account(tmp_path, monkeypatch, output):
    _repo(tmp_path)
    profile = Profile(
        name="x",
        root=str(tmp_path),
        git_email="a@b.c",
        gcloud_account="right@x.com",
        agents=[],
    )
    calls: list[list[str]] = []
    state = {"account": "wrong@x.com"}

    def run(args, env=None, capture_output=True, text=True, timeout=None, stdin=None, **kwargs):
        calls.append(list(args))
        joined = " ".join(args)
        if "config user.email" in joined:
            return subprocess.CompletedProcess(args, 0, "a@b.c\n", "")
        if "config get account" in joined:
            return subprocess.CompletedProcess(args, 0, state["account"] + "\n", "")
        if "config set account" in joined:
            state["account"] = args[-1]  # the fix takes effect
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(doctor.subprocess, "run", run)

    assert doctor.check_profile(profile, fix=True) is True
    assert ["gcloud", "config", "set", "account", "right@x.com"] in calls
    assert "gcloud: account and project reasserted" in output.getvalue()


def test_fix_reinjects_missing_env_into_the_repo(tmp_path, monkeypatch, output):
    repo = _repo(tmp_path)
    profile = Profile(
        name="x",
        root=str(tmp_path),
        git_email="a@b.c",
        gcloud_account="me@x.com",
        agents=["direnv"],
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        doctor.subprocess,
        "run",
        _recorder(
            {"config user.email": (0, "a@b.c\n"), "config get account": (0, "me@x.com\n")},
            calls,
        ),
    )

    assert not (repo / ".envrc").exists()
    assert doctor.check_profile(profile, fix=True) is True
    assert 'export CLOUDSDK_ACTIVE_CONFIG_NAME="x"' in (repo / ".envrc").read_text()
    assert "agents: env reinjected" in output.getvalue()


def test_fix_honors_dry_run(tmp_path, monkeypatch, output):
    repo = _repo(tmp_path)
    profile = Profile(
        name="x",
        root=str(tmp_path),
        git_email="a@b.c",
        gcloud_account="me@x.com",
        agents=["direnv"],
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        doctor.subprocess,
        "run",
        _recorder(
            {"config user.email": (0, "a@b.c\n"), "config get account": (0, "me@x.com\n")},
            calls,
        ),
    )

    assert doctor.check_profile(profile, fix=True, dry_run=True) is False
    assert not (repo / ".envrc").exists()
    assert "--dry-run: nothing was changed" in output.getvalue()


def test_expired_credential_is_only_reported_never_fixed(tmp_path, monkeypatch, output):
    _repo(tmp_path)
    monkeypatch.delenv("APARTA_AUTH_CHECK", raising=False)
    profile = Profile(
        name="x", root=str(tmp_path), git_email="a@b.c", gcloud_account="me@x.com", agents=[]
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        doctor.subprocess,
        "run",
        _recorder(
            {"config user.email": (0, "a@b.c\n"), "config get account": (0, "me@x.com\n")},
            calls,
        ),
    )
    monkeypatch.setattr(
        auth,
        "cached_check",
        lambda p: [auth.AuthStatus("gcloud", auth.REAUTH, "credential revoked or expired")],
    )

    assert doctor.check_profile(profile, fix=True) is False
    text = output.getvalue()
    assert "Still needs you:" in text
    assert "aparta login x" in text
    assert not any("auth" in " ".join(c) for c in calls)  # no reauthentication attempt
