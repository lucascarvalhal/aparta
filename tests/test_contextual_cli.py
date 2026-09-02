"""Contextual add, login, and status command contracts."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aparta import auth
from aparta.cli import app
from aparta.fsutil import SafeWriter
from aparta.profiles import Profile, save_profiles
from aparta.workspaces import Workspace, load_workspaces, save_workspaces


runner = CliRunner()


def _git_init(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


@pytest.fixture()
def configured(tmp_path, monkeypatch):
    config = tmp_path / "config"
    monkeypatch.setenv("APARTA_CONFIG_DIR", str(config))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    repo = _git_init(tmp_path / "clients" / "eneva" / "api")
    profile = Profile(
        name="eneva",
        root=str(tmp_path / "clients" / "eneva"),
        git_email="dev@eneva.com",
        gcloud_account="dev@eneva.com",
        gcloud_isolated=True,
    )
    save_profiles({profile.name: profile}, SafeWriter())
    return repo, profile


def test_add_one_argument_targets_the_current_worktree(configured, monkeypatch):
    """Treating one argument as a workspace would break the contextual shorthand."""
    repo, _profile = configured
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["add", "bitbucket"])

    assert result.exit_code == 0, result.output
    saved = load_workspaces()
    assert len(saved) == 1
    workspace = next(iter(saved.values()))
    assert workspace.root_path == repo.resolve()
    assert "bitbucket" in workspace.providers


def test_add_two_arguments_targets_a_named_workspace(configured, tmp_path):
    """Explicit targeting must work without changing the caller's directory."""
    repo, profile = configured
    workspace = Workspace("eneva-api", str(repo), profile.name, ["git"])
    save_workspaces({workspace.name: workspace}, SafeWriter())

    result = runner.invoke(app, ["add", "eneva-api", "bitbucket"])

    assert result.exit_code == 0, result.output
    assert load_workspaces()[workspace.name].providers == ["git", "bitbucket"]


def test_add_is_idempotent(configured, monkeypatch):
    """Repeated setup must not duplicate provider state."""
    repo, _profile = configured
    monkeypatch.chdir(repo)

    first = runner.invoke(app, ["add", "bitbucket"])
    second = runner.invoke(app, ["add", "bitbucket"])

    assert first.exit_code == second.exit_code == 0
    workspace = next(iter(load_workspaces().values()))
    assert workspace.providers.count("bitbucket") == 1
    assert "already" in second.output.lower()


def test_add_rejects_global_gcloud_mode(configured, monkeypatch):
    """Enabling light gcloud would claim isolation while libraries still use global ADC."""
    repo, profile = configured
    profile.gcloud_isolated = False
    save_profiles({profile.name: profile}, SafeWriter())
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["add", "gcloud"])

    assert result.exit_code == 1
    assert "isolated" in result.output.lower()
    assert load_workspaces() == {}


def test_login_without_argument_uses_the_current_worktree(configured, monkeypatch):
    """Requiring a profile name would defeat directory-driven login."""
    repo, profile = configured
    monkeypatch.chdir(repo)
    seen = {}

    def fake_login(selected, provider="", enabled_providers=None):
        seen["profile"] = selected.name
        seen["providers"] = enabled_providers
        return True

    monkeypatch.setattr(auth, "login_profile", fake_login)

    result = runner.invoke(app, ["login"])

    assert result.exit_code == 0, result.output
    assert seen["profile"] == profile.name
    assert {"gcloud", "adc"}.issubset(seen["providers"])


def test_login_keeps_explicit_profile_form(configured, monkeypatch):
    """Contextual login must not remove the existing from-anywhere workflow."""
    _repo, profile = configured
    seen = {}
    monkeypatch.setattr(
        auth,
        "login_profile",
        lambda selected, provider="", enabled_providers=None: seen.setdefault("name", selected.name) == selected.name,
    )

    result = runner.invoke(app, ["login", "eneva"])

    assert result.exit_code == 0, result.output
    assert seen["name"] == profile.name


def test_status_shows_known_expiry_inside_warning_window(configured, monkeypatch):
    """A known imminent expiry must be visible before a protected operation starts."""
    repo, _profile = configured
    monkeypatch.chdir(repo)
    monkeypatch.setattr(
        auth,
        "cached_check",
        lambda profile, force=False: [
            auth.AuthStatus("gcloud", auth.OK, expires_at=time.time() + 20 * 60)
        ],
    )

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.output
    assert "api" in result.output
    assert "eneva" in result.output
    assert "20m" in result.output


def test_status_hides_long_or_renewable_expiry_countdown(configured, monkeypatch):
    """Renewable access-token churn must not look like an impending logout."""
    repo, _profile = configured
    monkeypatch.chdir(repo)
    monkeypatch.setattr(
        auth,
        "cached_check",
        lambda profile, force=False: [
            auth.AuthStatus(
                "gcloud", auth.OK, expires_at=time.time() + 10 * 60, renewable=True
            )
        ],
    )

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.output
    assert "10m" not in result.output
    assert "renewable" in result.output.lower()
