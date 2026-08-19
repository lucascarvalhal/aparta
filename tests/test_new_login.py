"""New-account login in the wizard and apply_gh with a pre-existing dir."""

from __future__ import annotations

import subprocess
from pathlib import Path

from aparta import wizard
from aparta.backends import gh
from aparta.fsutil import SafeWriter
from aparta.profiles import Profile


def test_login_gh_dry_run_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert wizard.login_new_gh_account("novo", dry_run=True) == ""
    assert not (tmp_path / ".config" / "gh-novo").exists()


def test_login_gcloud_dry_run_runs_nothing(monkeypatch):
    def explode(*a, **kw):  # pragma: no cover - must not be called
        raise AssertionError("subprocess não deveria rodar em dry-run")

    monkeypatch.setattr(wizard.subprocess, "run", explode)
    assert wizard.login_new_gcloud_account("novo", dry_run=True) == ""


def test_login_gh_creates_profile_dir_and_returns_user(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs.get("env", {}).get("GH_CONFIG_DIR", "")))
        if args == ["gh", "auth", "login"]:
            return subprocess.CompletedProcess(args, 0)
        return subprocess.CompletedProcess(
            args, 0, stdout="✓ Logged in to github.com account fulano (keyring)", stderr=""
        )

    monkeypatch.setattr(wizard.subprocess, "run", fake_run)
    user = wizard.login_new_gh_account("novo")
    assert user == "fulano"
    dst = str(tmp_path / ".config" / "gh-novo")
    assert (tmp_path / ".config" / "gh-novo").is_dir()
    # login and status ran with the profile's GH_CONFIG_DIR (isolated)
    assert all(env == dst for _, env in calls)


def test_login_gh_failure_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        wizard.subprocess,
        "run",
        lambda args, **kw: subprocess.CompletedProcess(args, 1, stdout="", stderr=""),
    )
    assert wizard.login_new_gh_account("novo") == ""


def test_login_gcloud_uses_named_config(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs.get("env", {}).get("CLOUDSDK_ACTIVE_CONFIG_NAME", "")))
        out = "nova@conta.com\n" if args[-1] == "account" else ""
        return subprocess.CompletedProcess(args, 0, stdout=out, stderr="")

    monkeypatch.setattr(wizard.subprocess, "run", fake_run)
    assert wizard.login_new_gcloud_account("novo") == "nova@conta.com"
    assert calls[0][0][:4] == ["gcloud", "config", "configurations", "create"]
    login_call = next(c for c in calls if c[0] == ["gcloud", "auth", "login"])
    assert login_call[1] == "novo"  # login pinned to the profile's config


def test_generate_ssh_key_dry_run_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert wizard.generate_ssh_key("novo", dry_run=True) == ""
    assert not (tmp_path / ".ssh" / "id_ed25519_novo").exists()


def test_generate_ssh_key_creates_key_pair(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key = wizard.generate_ssh_key("novo")
    assert key == str(tmp_path / ".ssh" / "id_ed25519_novo")
    assert Path(key).exists() and Path(key + ".pub").exists()


def test_generate_ssh_key_reuses_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir(mode=0o700)
    (ssh_dir / "id_ed25519_novo").write_text("chave existente")
    assert wizard.generate_ssh_key("novo") == str(ssh_dir / "id_ed25519_novo")
    assert (ssh_dir / "id_ed25519_novo").read_text() == "chave existente"


def test_apply_gh_with_existing_dir_and_no_global_config(tmp_path, monkeypatch):
    """Wizard login creates gh-<profile>; apply must not require ~/.config/gh."""
    dst = tmp_path / ".config" / "gh-novo"
    dst.mkdir(parents=True)
    switches = []
    monkeypatch.setattr(
        gh.subprocess,
        "run",
        lambda args, **kw: switches.append(args)
        or subprocess.CompletedProcess(args, 0, stdout="", stderr=""),
    )
    profile = Profile(name="novo", root="~/novo", git_email="a@b.c", gh_user="fulano")
    gh.apply_gh(profile, SafeWriter(), home=tmp_path)
    assert switches == [["gh", "auth", "switch", "--user", "fulano"]]


def test_apply_gh_with_nothing_yet_warns_without_raising(tmp_path, capsys):
    profile = Profile(name="novo", root="~/novo", git_email="a@b.c", gh_user="fulano")
    gh.apply_gh(profile, SafeWriter(), home=tmp_path)  # neither global nor dst exists
