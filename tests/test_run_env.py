"""aparta run / aparta env: the profile environment outside the agents."""

from __future__ import annotations

import subprocess

import pytest

from aparta import auth, runner
from aparta.profiles import Profile
from aparta.workspaces import Workspace, profile_for_path


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


def _profiles(tmp_path):
    return {
        "work": Profile(
            name="work",
            root=str(tmp_path / "projects" / "work"),
            git_email="w@x.y",
            gcloud_account="w@x.y",
            gcloud_isolated=True,
        ),
        "inner": Profile(
            name="inner",
            root=str(tmp_path / "projects" / "work" / "special"),
            git_email="i@x.y",
        ),
        "personal": Profile(
            name="personal",
            root=str(tmp_path / "personal"),
            git_email="p@x.y",
            adopted_repos=[str(tmp_path / "elsewhere" / "stray-repo")],
        ),
    }


def _create_adc(profile: Profile) -> None:
    path = profile.gcloud_config_dir / "application_default_credentials.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")


def test_profile_for_path_picks_the_deepest_root(tmp_path):
    profiles = _profiles(tmp_path)
    inside = tmp_path / "projects" / "work" / "special" / "repo"
    inside.mkdir(parents=True)
    assert profile_for_path(inside, profiles).name == "inner"
    outer = tmp_path / "projects" / "work" / "other"
    outer.mkdir()
    assert profile_for_path(outer, profiles).name == "work"


def test_profile_for_path_covers_adopted_repos(tmp_path):
    profiles = _profiles(tmp_path)
    adopted = tmp_path / "elsewhere" / "stray-repo" / "src"
    adopted.mkdir(parents=True)
    assert profile_for_path(adopted, profiles).name == "personal"


def test_profile_for_path_outside_everything_is_none(tmp_path):
    assert profile_for_path(tmp_path / "nowhere", _profiles(tmp_path)) is None


def test_run_layers_the_profile_env_over_the_current_one(tmp_path, monkeypatch):
    profile = _profiles(tmp_path)["work"]
    _create_adc(profile)
    seen = {}

    def fake_run(command, env=None, **kwargs):
        seen["command"] = command
        seen["env"] = env
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setenv("UNRELATED", "stays")
    assert runner.run_in_profile(profile, ["terraform", "apply"]) == 0
    assert seen["command"] == ["terraform", "apply"]
    assert seen["env"]["UNRELATED"] == "stays"
    assert seen["env"]["CLOUDSDK_CONFIG"] == str(profile.gcloud_config_dir)
    # the pinned name an inherited shell variable cannot override
    assert seen["env"]["CLOUDSDK_ACTIVE_CONFIG_NAME"] == "work"


def test_run_drops_managed_selectors_inherited_from_another_client(tmp_path, monkeypatch):
    """Layering over the shell must not retain a provider the workspace did not select."""
    profile = _profiles(tmp_path)["work"]
    _create_adc(profile)
    seen = {}

    def fake_run(command, env=None, **kwargs):
        seen["env"] = env
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setenv("GH_CONFIG_DIR", "/globex/gh")
    monkeypatch.setenv("GH_TOKEN", "globex-secret")
    monkeypatch.setenv("GH_ENTERPRISE_TOKEN", "globex-enterprise-secret")
    monkeypatch.setenv("GH_HOST", "github.globex.example")
    monkeypatch.setenv("AWS_PROFILE", "globex")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/globex/adc.json")
    monkeypatch.setenv("CLOUDSDK_AUTH_ACCESS_TOKEN", "globex-access-token")
    monkeypatch.setenv("CLOUDSDK_CORE_ACCOUNT", "admin@globex.com")
    monkeypatch.setenv("CLOUDSDK_CORE_PROJECT", "globex-prod")

    assert runner.run_in_profile(profile, ["terraform", "plan"]) == 0

    assert "GH_CONFIG_DIR" not in seen["env"]
    assert "GH_TOKEN" not in seen["env"]
    assert "GH_ENTERPRISE_TOKEN" not in seen["env"]
    assert "GH_HOST" not in seen["env"]
    assert "AWS_PROFILE" not in seen["env"]
    assert "CLOUDSDK_AUTH_ACCESS_TOKEN" not in seen["env"]
    assert seen["env"]["CLOUDSDK_CORE_ACCOUNT"] == profile.gcloud_account
    assert "CLOUDSDK_CORE_PROJECT" not in seen["env"]
    assert seen["env"]["GOOGLE_APPLICATION_CREDENTIALS"] == str(
        profile.gcloud_config_dir / "application_default_credentials.json"
    )


def test_clean_environment_preserves_unrelated_values_and_replaces_managed_ones():
    """Removing unrelated shell values would make automatic activation destructive."""
    clean = runner.clean_environment(
        {"PATH": "/bin", "GH_CONFIG_DIR": "/old", "AWS_PROFILE": "old"},
        {"GH_CONFIG_DIR": "/new"},
    )

    assert clean == {"PATH": "/bin", "GH_CONFIG_DIR": "/new"}


def test_isolated_adc_path_is_exported_before_the_file_exists(tmp_path):
    """Omitting the selector lets Google libraries fall through to the global ADC."""
    profile = _profiles(tmp_path)["work"]
    env = runner.profile_env(profile)
    assert env["GOOGLE_APPLICATION_CREDENTIALS"] == str(
        profile.gcloud_config_dir / "application_default_credentials.json"
    )


def test_gh_token_is_strictly_opt_in(tmp_path, monkeypatch):
    profile = Profile(name="w", root=str(tmp_path), git_email="a@b.c", gh_user="w-user")
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 0, stdout="ghp_secret\n", stderr=""),
    )
    assert "GITHUB_TOKEN" not in runner.profile_env(profile)
    assert runner.profile_env(profile, with_gh_token=True)["GITHUB_TOKEN"] == "ghp_secret"


def test_gh_token_reads_from_the_profile_scope(tmp_path, monkeypatch):
    profile = Profile(name="w", root=str(tmp_path), git_email="a@b.c", gh_user="w-user")
    seen = {}

    def fake_run(args, env=None, **kwargs):
        seen["config_dir"] = (env or {}).get("GH_CONFIG_DIR")
        seen["inherited_token"] = (env or {}).get("GH_TOKEN")
        return subprocess.CompletedProcess(args, 0, stdout="tok", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setenv("GH_TOKEN", "another-client")
    runner.gh_token(profile)
    assert seen["config_dir"] == str(profile.gh_config_dir)
    assert seen["inherited_token"] is None


def test_export_lines_are_shell_safe():
    lines = runner.export_lines({"A": "plain", "B": "with space and 'quote'"})
    assert "export A=plain" in lines
    assert "export B=" in lines and "with space" in lines
    # eval must reproduce the exact value
    import subprocess as sp

    out = sp.run(
        ["bash", "-c", f'{lines}\nprintf "%s" "$B"'], capture_output=True, text=True
    )
    assert out.stdout == "with space and 'quote'"


def test_missing_command_returns_127(tmp_path):
    profile = _profiles(tmp_path)["work"]
    _create_adc(profile)
    assert runner.run_in_profile(profile, ["definitely-not-a-binary-xyz"]) == 127


def test_workspace_run_blocks_a_cached_expired_selected_provider(tmp_path, monkeypatch):
    profile = _profiles(tmp_path)["work"]
    workspace = Workspace(
        name="initech",
        path=str(tmp_path / "initech"),
        profile="work",
        providers=["gcloud", "adc"],
    )
    monkeypatch.setattr(
        auth,
        "read_cached_status",
        lambda selected: [auth.AuthStatus("ADC", auth.REAUTH, "session expired")],
    )
    monkeypatch.setattr(
        auth,
        "cached_check",
        lambda selected, force=False: [
            auth.AuthStatus("ADC", auth.REAUTH, "session expired")
        ],
    )

    def must_not_run(*args, **kwargs):
        raise AssertionError("expired credentials must block the protected process")

    monkeypatch.setattr(runner.subprocess, "run", must_not_run)

    assert runner.run_in_workspace(profile, workspace, ["terraform", "plan"]) == 1


def test_workspace_run_blocks_a_selected_adc_before_login(tmp_path, monkeypatch):
    profile = _profiles(tmp_path)["work"]
    workspace = Workspace(
        name="initech",
        path=str(tmp_path / "initech"),
        profile="work",
        providers=["gcloud", "adc"],
    )
    monkeypatch.setattr(auth, "read_cached_status", lambda selected: [])

    def must_not_run(*args, **kwargs):
        raise AssertionError("a missing selected ADC must block the protected process")

    monkeypatch.setattr(runner.subprocess, "run", must_not_run)

    assert runner.run_in_workspace(profile, workspace, ["terraform", "plan"]) == 1


def test_explicit_profile_run_keeps_the_same_missing_adc_boundary(tmp_path, monkeypatch):
    """The --profile escape hatch must not weaken the fail-closed run contract."""
    profile = _profiles(tmp_path)["work"]
    monkeypatch.setattr(auth, "read_cached_status", lambda selected: [])

    def must_not_run(*args, **kwargs):
        raise AssertionError("explicit profile runs must still enforce selected credentials")

    monkeypatch.setattr(runner.subprocess, "run", must_not_run)

    assert runner.run_in_profile(profile, ["terraform", "plan"]) == 1


def test_workspace_run_ignores_an_expired_provider_not_enabled_here(tmp_path, monkeypatch):
    profile = _profiles(tmp_path)["work"]
    workspace = Workspace(
        name="local-only",
        path=str(tmp_path / "local-only"),
        profile="work",
        providers=["git"],
    )
    monkeypatch.setattr(
        auth,
        "read_cached_status",
        lambda selected: [auth.AuthStatus("ADC", auth.REAUTH, "session expired")],
    )
    called = {}

    def fake_run(command, **kwargs):
        called["command"] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner.run_in_workspace(profile, workspace, ["git", "status"]) == 0
    assert called["command"] == ["git", "status"]
