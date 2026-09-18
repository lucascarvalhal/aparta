"""Contextual add, login, and status command contracts."""

from __future__ import annotations

import subprocess
import json
import sys
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
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    repo = _git_init(tmp_path / "clients" / "acme" / "api")
    profile = Profile(
        name="acme",
        root=str(tmp_path / "clients" / "acme"),
        git_email="dev@acme.com",
        gcloud_account="dev@acme.com",
        gcloud_isolated=True,
        aws_profile="acme",
    )
    save_profiles({profile.name: profile}, SafeWriter())
    return repo, profile


def test_add_one_argument_targets_the_current_worktree(configured, monkeypatch):
    """Treating one argument as a workspace would break the contextual shorthand."""
    repo, _profile = configured
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["add", "aws"])

    assert result.exit_code == 0, result.output
    saved = load_workspaces()
    assert len(saved) == 1
    workspace = next(iter(saved.values()))
    assert workspace.root_path == repo.resolve()
    assert "aws" in workspace.providers


def test_add_materializes_legacy_workspace_without_inheriting_optional_providers(
    configured, monkeypatch
):
    """The first explicit provider choice must not retain profile-wide cloud access."""
    repo, _profile = configured
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["add", "aws"])

    assert result.exit_code == 0, result.output
    workspace = next(iter(load_workspaces().values()))
    assert workspace.providers == ["git", "aws"]


def test_add_git_materializes_a_git_only_legacy_workspace(configured, monkeypatch):
    """A legacy repo needs a way to opt out of inherited cloud providers."""
    repo, _profile = configured
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["add", "git"])

    assert result.exit_code == 0, result.output
    workspace = next(iter(load_workspaces().values()))
    assert workspace.providers == ["git"]

    activated = runner.invoke(app, ["env", "--activate"])
    assert activated.exit_code == 0, activated.output
    assert "export CLOUDSDK_CONFIG=" not in activated.output
    assert "export GOOGLE_APPLICATION_CREDENTIALS=" not in activated.output


def test_add_two_arguments_targets_a_named_workspace(configured, tmp_path):
    """Explicit targeting must work without changing the caller's directory."""
    repo, profile = configured
    workspace = Workspace("acme-api", str(repo), profile.name, ["git"])
    save_workspaces({workspace.name: workspace}, SafeWriter())

    result = runner.invoke(app, ["add", "acme-api", "aws"])

    assert result.exit_code == 0, result.output
    assert load_workspaces()[workspace.name].providers == ["git", "aws"]


def test_add_two_arguments_finds_an_unmaterialized_repo_by_name(
    configured, tmp_path, monkeypatch
):
    """The explicit repo form must work before the first workspace record exists."""
    repo, _profile = configured
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["add", repo.name, "aws"])

    assert result.exit_code == 0, result.output
    workspace = next(iter(load_workspaces().values()))
    assert workspace.root_path == repo.resolve()
    assert "aws" in workspace.providers


def test_add_is_idempotent(configured, monkeypatch):
    """Repeated setup must not duplicate provider state."""
    repo, _profile = configured
    monkeypatch.chdir(repo)

    first = runner.invoke(app, ["add", "aws"])
    second = runner.invoke(app, ["add", "aws"])

    assert first.exit_code == second.exit_code == 0
    workspace = next(iter(load_workspaces().values()))
    assert workspace.providers.count("aws") == 1
    assert "already" in second.output.lower()


def test_add_immediately_reconciles_agent_environment(configured):
    """Requiring a second apply would leave newly added providers inactive in agents."""
    import json

    repo, profile = configured
    profile.gh_user = "acme-gh"
    profile.agents = ["claude-code"]
    save_profiles({profile.name: profile}, SafeWriter())
    workspace = Workspace("acme-api", str(repo), profile.name, ["git"])
    save_workspaces({workspace.name: workspace}, SafeWriter())

    result = runner.invoke(app, ["add", "acme-api", "github"])

    assert result.exit_code == 0, result.output
    settings = json.loads((repo / ".claude" / "settings.local.json").read_text())
    assert settings["env"]["GH_CONFIG_DIR"] == str(profile.gh_config_dir)


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

    result = runner.invoke(app, ["login", "acme"])

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
    assert "acme" in result.output
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


def test_shell_status_never_starts_a_network_probe(configured, monkeypatch):
    """Rendering every prompt must stay instant even when the cache is empty."""
    repo, profile = configured
    monkeypatch.chdir(repo)
    adc = profile.gcloud_config_dir / "application_default_credentials.json"
    adc.parent.mkdir(parents=True)
    adc.write_text("{}")

    def explode(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("the prompt must never probe providers synchronously")

    monkeypatch.setattr(auth, "check_profile", explode)

    result = runner.invoke(app, ["status", "--shell"])

    assert result.exit_code == 0, result.output
    assert "aparta:api" in result.output
    assert "unknown" in result.output


def test_status_blocks_when_a_selected_isolated_adc_file_is_missing(
    configured, monkeypatch
):
    """No cache entry must not turn a missing selected ADC into a green status."""
    repo, _profile = configured
    monkeypatch.chdir(repo)
    monkeypatch.setattr(auth, "cached_check", lambda profile, force=False: [])

    result = runner.invoke(app, ["status", "--shell"])

    assert result.exit_code == 0, result.output
    assert "reauth needed" in result.output
    assert "blocked" not in result.output


def test_shell_status_speaks_the_saved_language(configured, monkeypatch):
    """The prompt segment is read by a human; "blocked" told them nothing."""
    repo, _profile = configured
    monkeypatch.chdir(repo)
    monkeypatch.setattr(auth, "cached_check", lambda profile, force=False: [])
    monkeypatch.setenv("APARTA_LANG", "pt")

    result = runner.invoke(app, ["status", "--shell"])

    assert result.exit_code == 0, result.output
    assert "reautenticar" in result.output


def test_shell_status_sanitizes_workspace_name_for_prompt_expansion(configured, monkeypatch):
    """A workspace label must never become executable zsh prompt syntax."""
    repo, profile = configured
    workspace = Workspace("bad$(touch_x)", str(repo), profile.name, ["git"])
    save_workspaces({workspace.name: workspace}, SafeWriter())
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["status", "--shell"])

    assert result.exit_code == 0, result.output
    assert "$(" not in result.output
    assert "bad??touch_x?" in result.output


def test_env_activate_emits_unsets_and_current_workspace_exports(configured, monkeypatch):
    """The shell hook needs one eval-safe transition, not additive exports."""
    repo, profile = configured
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GH_CONFIG_DIR", "/globex/gh")

    result = runner.invoke(app, ["env", "--activate"])

    assert result.exit_code == 0, result.output
    assert "unset " in result.output
    assert "GH_CONFIG_DIR" in result.output
    assert f"export APARTA_PROFILE={profile.name}" in result.output
    assert f"export CLOUDSDK_CONFIG={profile.gcloud_config_dir}" in result.output


def test_run_uses_only_the_current_worktree_providers(configured, monkeypatch):
    """A shared profile's extra providers must not leak into a restricted worktree."""
    repo, profile = configured
    profile.gh_user = "acme-gh"
    save_profiles({profile.name: profile}, SafeWriter())
    workspace = Workspace("acme-api", str(repo), profile.name, ["gcloud"])
    save_workspaces({workspace.name: workspace}, SafeWriter())
    monkeypatch.chdir(repo)
    output = repo / "received-env.json"
    code = (
        "import json, os, pathlib; "
        f"pathlib.Path({str(output)!r}).write_text(json.dumps(dict(os.environ)))"
    )

    result = runner.invoke(app, ["run", "--", sys.executable, "-c", code])

    assert result.exit_code == 0, result.output
    received = json.loads(output.read_text())
    assert received["CLOUDSDK_CONFIG"] == str(profile.gcloud_config_dir)
    assert received["GOOGLE_APPLICATION_CREDENTIALS"] == str(
        profile.gcloud_config_dir / "application_default_credentials.json"
    )
    assert "GH_CONFIG_DIR" not in received


def test_env_with_an_explicit_profile_prints_its_exports(configured, monkeypatch):
    repo, profile = configured
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["env", profile.name])

    assert result.exit_code == 0, result.output
    assert "CLOUDSDK_CONFIG" in result.output


def test_run_with_an_explicit_profile_executes_the_command(configured, monkeypatch):
    repo, profile = configured
    monkeypatch.chdir(repo)
    profile.gcloud_config_dir.mkdir(parents=True, exist_ok=True)
    (profile.gcloud_config_dir / "application_default_credentials.json").write_text("{}")
    monkeypatch.setattr(auth, "cached_check", lambda p, force=False: [])

    result = runner.invoke(app, ["run", "--profile", profile.name, "--", "true"])

    assert result.exit_code == 0, result.output
