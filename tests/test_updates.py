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

    def fake_run(cmd, timeout=None, **kwargs):
        ran.setdefault("cmd", cmd)

        class R:
            returncode = 0
            stdout = ""

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
    monkeypatch.setattr(updates, "run_update", lambda target="": ran.append(target) or True)
    updates.notify_or_autoupdate()
    assert ran == ["99.0.0"]


def test_profiles_applied_by_an_older_version_are_flagged(tmp_path, monkeypatch):
    """Updating the binary is not enough: profiles need a re-apply."""
    from aparta.apply import stale_profiles
    from aparta.fsutil import SafeWriter
    from aparta.profiles import Profile, save_profiles

    old = Profile(name="legacy", root="~/a", git_email="a@b.c", applied_with="0.4.0")
    current = Profile(name="fresh", root="~/b", git_email="a@b.c", applied_with=updates.__version__)
    never = Profile(name="never", root="~/c", git_email="a@b.c")
    save_profiles({"legacy": old, "fresh": current, "never": never}, SafeWriter())

    assert sorted(stale_profiles()) == ["legacy", "never"]


def test_update_says_so_when_nothing_changed(monkeypatch, capsys):
    """The upgrade command exits 0 even with nothing to do; do not claim more."""
    monkeypatch.setattr(updates, "detect_install_method", lambda: "uv-tool")
    monkeypatch.setattr(updates, "installed_version", lambda: updates.__version__)
    monkeypatch.setattr(
        updates.subprocess, "run", lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": ""})()
    )
    assert updates.run_update() is True
    assert "already on the latest version" in capsys.readouterr().out


def test_update_reports_the_new_version(monkeypatch, capsys):
    monkeypatch.setattr(updates, "detect_install_method", lambda: "uv-tool")
    monkeypatch.setattr(updates, "installed_version", lambda: "99.0.0")
    monkeypatch.setattr(
        updates.subprocess, "run", lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": ""})()
    )
    assert updates.run_update() is True
    assert "99.0.0" in capsys.readouterr().out


def test_installed_version_parses_the_binary_output(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/aparta")
    monkeypatch.setattr(
        updates.subprocess,
        "run",
        lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": "aparta 1.2.3\n"})(),
    )
    assert updates.installed_version() == "1.2.3"


def test_update_flags_a_release_the_index_has_not_published(monkeypatch, capsys):
    """PyPI's JSON announces a version before installers can fetch it."""
    monkeypatch.setattr(updates, "detect_install_method", lambda: "uv-tool")
    monkeypatch.setattr(updates, "installed_version", lambda: updates.__version__)
    monkeypatch.setattr(
        updates.subprocess, "run", lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": ""})()
    )
    assert updates.run_update("99.0.0") is False
    assert "not installable yet" in capsys.readouterr().out
