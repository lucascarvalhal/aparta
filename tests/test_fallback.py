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


@pytest.fixture(autouse=True)
def fake_global_adc(tmp_path, monkeypatch):
    """The global ADC probe must never touch the real home or the network."""
    path = tmp_path / "gcloud" / "application_default_credentials.json"
    monkeypatch.setattr(fallback, "global_adc_path", lambda: path)
    return path


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


def test_secure_creates_the_neutral_config_and_activates_it(monkeypatch):
    calls = []
    monkeypatch.setattr(fallback.subprocess, "run", _recorder(calls))
    assert fallback.make_secure(SafeWriter(), assume_yes=True) is True
    commands = [cmd for cmd, _env in calls]
    assert any(f"{CREATE} {fallback.NEUTRAL_CONFIG} --no-activate" in c for c in commands)
    assert any(f"{ACTIVATE} {fallback.NEUTRAL_CONFIG}" in c for c in commands)
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
    assert not fallback.previous_path().exists()


def test_secure_reports_a_failing_gcloud(monkeypatch):
    monkeypatch.setattr(fallback.subprocess, "run", _recorder([], rc=1))
    assert fallback.make_secure(SafeWriter(), assume_yes=True) is False


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


def test_state_probes_the_global_adc_like_a_library(monkeypatch, fake_global_adc):
    import urllib.request

    fake_global_adc.parent.mkdir(parents=True)
    fake_global_adc.write_text(
        '{"type": "authorized_user", "client_id": "c", "client_secret": "s", "refresh_token": "r"}'
    )
    monkeypatch.setattr(fallback.subprocess, "run", _recorder([]))

    import io
    import urllib.error

    def expired(req, timeout=None):
        raise urllib.error.HTTPError(
            "u", 400, "Bad Request", {}, io.BytesIO(b'{"error": "invalid_grant", "error_subtype": "invalid_rapt"}')
        )

    monkeypatch.setattr(urllib.request, "urlopen", expired)
    state = fallback.read_state()
    assert state.adc_present is True
    from aparta.auth import REAUTH

    assert state.adc_state == REAUTH


def test_secure_parks_the_global_adc(monkeypatch, fake_global_adc, config_dir):
    fake_global_adc.parent.mkdir(parents=True)
    fake_global_adc.write_text("{}")
    monkeypatch.setattr(fallback.subprocess, "run", _recorder([]))
    assert fallback.make_secure(SafeWriter(), assume_yes=True) is True
    assert not fake_global_adc.exists()
    assert fallback.parked_adc_path().exists()


def test_restore_puts_the_parked_adc_back(monkeypatch, fake_global_adc, config_dir):
    fake_global_adc.parent.mkdir(parents=True)
    fake_global_adc.write_text('{"marker": 1}')
    monkeypatch.setattr(fallback.subprocess, "run", _recorder([]))
    fallback.make_secure(SafeWriter(), assume_yes=True)
    assert fallback.restore(SafeWriter()) is True
    assert fake_global_adc.read_text() == '{"marker": 1}'
    assert not fallback.parked_adc_path().exists()


def test_secure_parks_the_adc_even_when_the_config_is_already_neutral(
    monkeypatch, fake_global_adc, config_dir
):
    """--secure run again after a new ADC appeared must not say "nothing to do"."""
    neutral = "aparta-none\ttrue\t\t\n"
    fake_global_adc.parent.mkdir(parents=True)
    fake_global_adc.write_text("{}")
    monkeypatch.setattr(fallback.subprocess, "run", _recorder([], listing=neutral))
    assert fallback.make_secure(SafeWriter(), assume_yes=True) is True
    assert not fake_global_adc.exists()
    assert fallback.parked_adc_path().exists()


def test_move_file_backs_up_the_destination(tmp_path):
    src = tmp_path / "a"
    dst = tmp_path / "b"
    src.write_text("new")
    dst.write_text("old")
    writer = SafeWriter()
    assert writer.move_file(src, dst) is True
    assert dst.read_text() == "new" and not src.exists()
    assert [p.read_text() for p in tmp_path.glob("b.bak-aparta-*")] == ["old"]
    assert writer.changes == [f"{src} -> {dst}"]
