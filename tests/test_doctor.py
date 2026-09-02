"""doctor.check_profile branches with subprocess mocked."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aparta import doctor
from aparta.profiles import Profile


@pytest.fixture(autouse=True)
def offline_auth_checks(monkeypatch):
    """These tests exercise doctor's own logic, not the credential probes."""
    monkeypatch.setenv("APARTA_AUTH_CHECK", "off")


def _fake_run(responses: dict[str, tuple[int, str]]):
    """Map a command marker to (returncode, stdout); default success/empty."""

    def run(args, env=None, capture_output=True, text=True, timeout=None, stdin=None):
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
    profile = Profile(name="x", root=str(tmp_path), git_email="a@b.c", agents=[])
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


def test_doctor_provider_commands_clear_inherited_credentials(monkeypatch):
    """A doctor probe must observe the same clean environment as the real command."""
    seen = {}
    monkeypatch.setenv("GH_TOKEN", "other-client")

    def run(args, env=None, **kwargs):
        seen["env"] = env
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(doctor.subprocess, "run", run)
    doctor._run(["gh", "auth", "status"], {"GH_CONFIG_DIR": "/client/gh"})

    assert "GH_TOKEN" not in seen["env"]
    assert seen["env"]["GH_CONFIG_DIR"] == "/client/gh"


def test_doctor_validates_agent_env_against_each_workspace_providers(tmp_path, monkeypatch):
    """Comparing every repo with the full profile env creates false failures."""
    from aparta.agents.claude_code import ClaudeCodeAdapter
    from aparta.fsutil import SafeWriter
    from aparta.providers import workspace_env
    from aparta.workspaces import Workspace, save_workspaces

    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    github_repo = _repo(tmp_path, "github-app")
    cloud_repo = _repo(tmp_path, "cloud-app")
    for repo in (github_repo, cloud_repo):
        (repo / ".git").rmdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
    profile = Profile(
        name="client",
        root=str(tmp_path),
        git_email="dev@client.com",
        gh_user="client-gh",
        gcloud_account="dev@client.com",
        gcloud_isolated=True,
        agents=["claude-code"],
    )
    profile.gh_config_dir.mkdir(parents=True)
    profile.gcloud_config_dir.mkdir(parents=True)
    workspaces = {
        "github-app": Workspace("github-app", str(github_repo), profile.name, ["github"]),
        "cloud-app": Workspace("cloud-app", str(cloud_repo), profile.name, ["gcloud"]),
    }
    save_workspaces(workspaces, SafeWriter())
    adapter = ClaudeCodeAdapter()
    for workspace in workspaces.values():
        adapter.inject(
            workspace.root_path,
            workspace_env(workspace, profile),
            SafeWriter(),
        )

    def fake_run(args, extra_env=None):
        joined = " ".join(args)
        if "user.email" in joined:
            output = profile.git_email + "\n"
        elif args[:3] == ["gh", "auth", "status"]:
            output = profile.gh_user + "\n"
        elif args[-1] == "account":
            output = profile.gcloud_account + "\n"
        else:
            output = ""
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

    monkeypatch.setattr(doctor, "_run", fake_run)

    rows, _all_ok, _issues = doctor._diagnose(profile)
    agent_rows = [row for row in rows if row[0] == "claude-code"]
    assert len(agent_rows) == 2
    assert all(row[2] is True for row in agent_rows)
