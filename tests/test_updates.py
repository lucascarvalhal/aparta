"""Update checks: caching, mode persistence, comparison and self-update."""

from __future__ import annotations

import json

import pytest

from aparta import updates


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv("APARTA_UPDATES", raising=False)


def test_default_mode_is_manual():
    assert updates.update_mode() == "manual"


def test_mode_persists(tmp_path):
    updates.set_update_mode("auto")
    assert updates.update_mode() == "auto"
    assert updates.update_mode_saved() is True


def test_env_overrides_saved_mode(monkeypatch):
    updates.set_update_mode("auto")
    monkeypatch.setenv("APARTA_UPDATES", "off")
    assert updates.update_mode() == "off"


def test_check_reports_newer_version(monkeypatch):
    monkeypatch.setattr(updates, "fetch_latest_version", lambda timeout=2.0: "99.0.0")
    assert updates.check_for_update() == "99.0.0"


def test_check_ignores_older_or_equal(monkeypatch):
    monkeypatch.setattr(updates, "fetch_latest_version", lambda timeout=2.0: updates.__version__)
    assert updates.check_for_update() == ""


def test_check_is_cached_daily(monkeypatch):
    calls = []

    def fake_fetch(timeout=2.0):
        calls.append(1)
        return "99.0.0"

    monkeypatch.setattr(updates, "fetch_latest_version", fake_fetch)
    assert updates.check_for_update() == "99.0.0"
    assert updates.check_for_update() == "99.0.0"  # served from cache
    assert len(calls) == 1


def test_check_off_mode_skips_network(monkeypatch):
    monkeypatch.setenv("APARTA_UPDATES", "off")

    def explode(timeout=2.0):  # pragma: no cover - must not be called
        raise AssertionError("network call in off mode")

    monkeypatch.setattr(updates, "fetch_latest_version", explode)
    assert updates.check_for_update() == ""


def test_check_survives_corrupt_cache(monkeypatch):
    from aparta.profiles import config_dir

    config_dir().mkdir(parents=True, exist_ok=True)
    (config_dir() / "update-check.json").write_text("{broken")
    monkeypatch.setattr(updates, "fetch_latest_version", lambda timeout=2.0: "99.0.0")
    assert updates.check_for_update() == "99.0.0"


def test_run_update_uses_detected_method(monkeypatch):
    ran = {}
    monkeypatch.setattr(updates, "detect_install_method", lambda: "uv-tool")

    def fake_run(cmd, timeout=None):
        ran["cmd"] = cmd

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(updates.subprocess, "run", fake_run)
    assert updates.run_update() is True
    assert ran["cmd"] == ["uv", "tool", "upgrade", "aparta"]


def test_run_update_ephemeral_is_a_noop(monkeypatch):
    monkeypatch.setattr(updates, "detect_install_method", lambda: "ephemeral")

    def explode(*a, **kw):  # pragma: no cover - must not be called
        raise AssertionError("no subprocess for ephemeral installs")

    monkeypatch.setattr(updates.subprocess, "run", explode)
    assert updates.run_update() is True


def test_notify_in_manual_mode_does_not_update(monkeypatch, capsys):
    monkeypatch.setattr(updates, "check_for_update", lambda force=False: "99.0.0")

    def explode():  # pragma: no cover - must not be called
        raise AssertionError("auto update in manual mode")

    monkeypatch.setattr(updates, "run_update", explode)
    updates.notify_or_autoupdate()


def test_autoupdate_runs_in_auto_mode(monkeypatch):
    updates.set_update_mode("auto")
    monkeypatch.setattr(updates, "check_for_update", lambda force=False: "99.0.0")
    ran = []
    monkeypatch.setattr(updates, "run_update", lambda: ran.append(1) or True)
    updates.notify_or_autoupdate()
    assert ran == [1]
