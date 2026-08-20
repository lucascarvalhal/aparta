"""Safe fallback: state outside a profile, neutral global default and undo."""

from __future__ import annotations

import subprocess

import pytest

from aparta import fallback
from aparta.fsutil import SafeWriter

LIST = "config configurations list"
CREATE = "config configurations create"
ACTIVATE = "config configurations activate"

CONFIGS = "default\tFalse\tme@gmail.com\t\nclient\tTrue\tme@client.com\tclient-prod\n"
NEUTRAL = f"default\tFalse\tme@gmail.com\t\n{fallback.NEUTRAL_CONFIG}\tTrue\t\t\n"
GH_JSON = '{"hosts":{"github.com":[{"active":true,"login":"octocat"}]}}'


@pytest.fixture(autouse=True)
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr(fallback.shutil, "which", lambda name: f"/usr/bin/{name}")
    return tmp_path / "cfg"


def _recorder(calls, listing=CONFIGS, gh_out=GH_JSON, rc=0):
    def run(args, env=None, capture_output=True, text=True, timeout=None):
        joined = " ".join(args)
        calls.append((joined, env or {}))
        if args[0] == "gh":
            return subprocess.CompletedProcess(args, 0, stdout=gh_out, stderr="")
        if LIST in joined:
            return subprocess.CompletedProcess(args, 0, stdout=listing, stderr="")
        return subprocess.CompletedProcess(args, rc, stdout="", stderr="boom")

    return run


# ---- reading the current state ----


def test_state_reports_the_global_identity_of_each_tool(monkeypatch):
    monkeypatch.setattr(fallback.subprocess, "run", _recorder([]))
    state = fallback.read_state()
    assert state.gcloud_active.name == "client"
    assert state.gcloud_active.account == "me@client.com"
    assert state.gcloud_active.project == "client-prod"
    assert state.gh_user == "octocat"
    assert state.secure is False


def test_state_probes_without_the_profile_env(monkeypatch):
    calls = []
    monkeypatch.setattr(fallback.subprocess, "run", _recorder(calls))
    monkeypatch.setenv("CLOUDSDK_ACTIVE_CONFIG_NAME", "personal")
    monkeypatch.setenv("GH_CONFIG_DIR", "/somewhere/gh-personal")
    fallback.read_state()
    assert calls and all(
        "CLOUDSDK_ACTIVE_CONFIG_NAME" not in env and "GH_CONFIG_DIR" not in env
        for _cmd, env in calls
    )


def test_show_state_changes_nothing(monkeypatch, config_dir):
    calls = []
    monkeypatch.setattr(fallback.subprocess, "run", _recorder(calls))
    state = fallback.show_state()
    assert state.gcloud_active.name == "client"
    assert not any(CREATE in cmd or ACTIVATE in cmd for cmd, _env in calls)
    assert not fallback.previous_path().exists()


def test_missing_binaries_degrade_gracefully(monkeypatch):
    monkeypatch.setattr(fallback.shutil, "which", lambda name: None)

    def explode(*a, **kw):  # pragma: no cover - must not be called
        raise AssertionError("no subprocess when the CLI is absent")

    monkeypatch.setattr(fallback.subprocess, "run", explode)
    state = fallback.show_state()
    assert state.gcloud_installed is False and state.gh_installed is False
    assert fallback.make_secure(SafeWriter(), assume_yes=True) is False


# ---- securing ----


def test_secure_creates_the_neutral_config_and_activates_it(monkeypatch):
    calls = []
    monkeypatch.setattr(fallback.subprocess, "run", _recorder(calls))
    assert fallback.make_secure(SafeWriter(), assume_yes=True) is True
    commands = [cmd for cmd, _env in calls]
    assert any(f"{CREATE} {fallback.NEUTRAL_CONFIG} --no-activate" in c for c in commands)
    assert any(f"{ACTIVATE} {fallback.NEUTRAL_CONFIG}" in c for c in commands)
    # no existing configuration is touched
    assert not any("client" in c or "delete" in c for c in commands)


def test_secure_saves_the_previous_configuration_before_switching(monkeypatch):
    calls = []
    monkeypatch.setattr(fallback.subprocess, "run", _recorder(calls))
    fallback.make_secure(SafeWriter(), assume_yes=True)
    assert fallback.read_previous() == "client"


def test_secure_asks_before_changing_anything(monkeypatch):
    calls = []
    monkeypatch.setattr(fallback.subprocess, "run", _recorder(calls))
    monkeypatch.setattr(fallback, "_ask", lambda question: False)
    assert fallback.make_secure(SafeWriter()) is False
    assert not any(ACTIVATE in cmd for cmd, _env in calls)
    assert not fallback.previous_path().exists()


def test_secure_skips_creation_when_the_neutral_config_exists(monkeypatch):
    calls = []
    listing = f"client\tTrue\tme@client.com\t\n{fallback.NEUTRAL_CONFIG}\tFalse\t\t\n"
    monkeypatch.setattr(fallback.subprocess, "run", _recorder(calls, listing=listing))
    fallback.make_secure(SafeWriter(), assume_yes=True)
    commands = [cmd for cmd, _env in calls]
    assert not any(CREATE in c for c in commands)
    assert any(f"{ACTIVATE} {fallback.NEUTRAL_CONFIG}" in c for c in commands)


def test_secure_is_idempotent(monkeypatch):
    calls = []
    monkeypatch.setattr(fallback.subprocess, "run", _recorder(calls, listing=NEUTRAL))
    assert fallback.make_secure(SafeWriter(), assume_yes=True) is True
    assert not any(ACTIVATE in cmd for cmd, _env in calls)
    # the memory of a real previous configuration is not overwritten
    assert not fallback.previous_path().exists()


def test_secure_reports_a_failing_gcloud(monkeypatch):
    monkeypatch.setattr(fallback.subprocess, "run", _recorder([], rc=1))
    assert fallback.make_secure(SafeWriter(), assume_yes=True) is False


# ---- dry run ----


def test_dry_run_runs_no_command_and_writes_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(fallback.subprocess, "run", _recorder(calls))
    monkeypatch.setattr(fallback, "_ask", lambda question: pytest.fail("no prompt in dry-run"))
    assert fallback.make_secure(SafeWriter(dry_run=True)) is True
    assert not any(CREATE in cmd or ACTIVATE in cmd for cmd, _env in calls)
    assert not fallback.previous_path().exists()


def test_dry_run_restore_activates_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(fallback.subprocess, "run", _recorder(calls))
    fallback.make_secure(SafeWriter(), assume_yes=True)
    calls.clear()
    assert fallback.restore(SafeWriter(dry_run=True)) is True
    assert not any(ACTIVATE in cmd for cmd, _env in calls)
    assert fallback.read_previous() == "client"


# ---- restoring ----


def test_restore_reactivates_the_saved_configuration(monkeypatch):
    calls = []
    monkeypatch.setattr(fallback.subprocess, "run", _recorder(calls))
    fallback.make_secure(SafeWriter(), assume_yes=True)
    calls.clear()
    assert fallback.restore(SafeWriter()) is True
    assert any(f"{ACTIVATE} client" in cmd for cmd, _env in calls)
    assert fallback.read_previous() == ""


def test_restore_without_a_saved_state_does_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(fallback.subprocess, "run", _recorder(calls))
    assert fallback.restore(SafeWriter()) is False
    assert calls == []


def test_restore_keeps_the_saved_state_when_gcloud_fails(monkeypatch):
    monkeypatch.setattr(fallback.subprocess, "run", _recorder([]))
    fallback.make_secure(SafeWriter(), assume_yes=True)
    monkeypatch.setattr(fallback.subprocess, "run", _recorder([], rc=1))
    assert fallback.restore(SafeWriter()) is False
    assert fallback.read_previous() == "client"
