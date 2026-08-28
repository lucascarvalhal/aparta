"""aparta run / aparta env: the profile environment outside the agents."""

from __future__ import annotations

import subprocess

import pytest

from aparta import runner
from aparta.profiles import Profile


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


def test_profile_for_path_picks_the_deepest_root(tmp_path):
    profiles = _profiles(tmp_path)
    inside = tmp_path / "projects" / "work" / "special" / "repo"
    inside.mkdir(parents=True)
    assert runner.profile_for_path(inside, profiles).name == "inner"
    outer = tmp_path / "projects" / "work" / "other"
    outer.mkdir()
    assert runner.profile_for_path(outer, profiles).name == "work"


def test_profile_for_path_covers_adopted_repos(tmp_path):
    profiles = _profiles(tmp_path)
    adopted = tmp_path / "elsewhere" / "stray-repo" / "src"
    adopted.mkdir(parents=True)
    assert runner.profile_for_path(adopted, profiles).name == "personal"


def test_profile_for_path_outside_everything_is_none(tmp_path):
    assert runner.profile_for_path(tmp_path / "nowhere", _profiles(tmp_path)) is None


def test_run_layers_the_profile_env_over_the_current_one(tmp_path, monkeypatch):
    profile = _profiles(tmp_path)["work"]
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


def test_adc_is_only_exported_when_the_file_exists(tmp_path):
    profile = _profiles(tmp_path)["work"]
    env = runner.profile_env(profile)
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in env
    profile.gcloud_config_dir.mkdir(parents=True)
    (profile.gcloud_config_dir / "application_default_credentials.json").write_text("{}")
    env = runner.profile_env(profile)
    assert env["GOOGLE_APPLICATION_CREDENTIALS"].endswith("application_default_credentials.json")


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
        return subprocess.CompletedProcess(args, 0, stdout="tok", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.gh_token(profile)
    assert seen["config_dir"] == str(profile.gh_config_dir)


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
    assert runner.run_in_profile(profile, ["definitely-not-a-binary-xyz"]) == 127
