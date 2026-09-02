"""Automatic zsh activation and reversible startup installation."""

from __future__ import annotations

import os
import subprocess

from aparta.fsutil import SafeWriter
from aparta.profiles import Profile
from aparta.shell import (
    activation_lines,
    install_for_current_shell,
    install_zsh_hook,
    merge_zshrc,
    render_zsh_hook,
)
from aparta.workspaces import Workspace


def _context(tmp_path):
    profile = Profile(
        name="eneva",
        root=str(tmp_path),
        git_email="dev@eneva.com",
        gcloud_account="dev@eneva.com",
        gcloud_isolated=True,
    )
    workspace = Workspace("eneva-api", str(tmp_path), profile.name, ["gcloud", "adc"])
    return workspace, profile


def test_activation_clears_foreign_selectors_before_exporting_workspace(tmp_path):
    """Appending exports without unsets is the cross-client leak being fixed."""
    workspace, profile = _context(tmp_path)
    inherited = {
        "GH_CONFIG_DIR": "/effektra/gh",
        "AWS_PROFILE": "effektra",
        "GIT_CONFIG_KEY_0": "user.email",
    }
    script = activation_lines(
        workspace,
        profile,
        current_env=inherited,
    )
    command = (
        script
        + "\n"
        + "print -r -- ${GH_CONFIG_DIR-unset}:${AWS_PROFILE-unset}:${GIT_CONFIG_KEY_0-unset}:$APARTA_PROFILE:$APARTA_WORKSPACE:$CLOUDSDK_CONFIG"
    )

    result = subprocess.run(
        ["zsh", "-c", command],
        env={**os.environ, **inherited},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        f"unset:unset:unset:eneva:eneva-api:{profile.gcloud_config_dir}"
    )


def test_unregistered_folder_deactivates_every_aparta_value():
    """Leaving a workspace must not carry its identity into the next folder."""
    inherited = {"GH_CONFIG_DIR": "/eneva/gh", "APARTA_WORKSPACE": "eneva"}
    script = activation_lines(
        None,
        None,
        current_env=inherited,
    )
    command = script + "\nprint -r -- ${GH_CONFIG_DIR-unset}:${APARTA_WORKSPACE-unset}"

    result = subprocess.run(
        ["zsh", "-c", command],
        env={**os.environ, **inherited},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "unset:unset"


def test_generated_zsh_hook_is_syntactically_valid(tmp_path):
    """A syntax error in .zshrc would break every new terminal."""
    hook = tmp_path / "hook.zsh"
    hook.write_text(render_zsh_hook())

    result = subprocess.run(["zsh", "-n", str(hook)], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_zshrc_merge_preserves_user_content_and_is_idempotent():
    """Repeated setup must not duplicate hooks or replace shell customization."""
    existing = "export EDITOR=nvim\n"
    once = merge_zshrc(existing)
    twice = merge_zshrc(once)

    assert "export EDITOR=nvim" in once
    assert once == twice
    assert once.count('eval "$(aparta hook zsh)"') == 1


def test_install_zsh_hook_honors_dry_run(tmp_path):
    """Preview mode must never create or modify a startup file."""
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("export EDITOR=vim\n")

    changed = install_zsh_hook(SafeWriter(dry_run=True), zshrc)

    assert changed is True
    assert zshrc.read_text() == "export EDITOR=vim\n"
    assert not list(tmp_path.glob(".zshrc.bak-aparta-*"))


def test_install_for_current_shell_uses_zdotdir(tmp_path, monkeypatch):
    """A zsh setup must honor the user's configured startup directory."""
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.setenv("ZDOTDIR", str(tmp_path))

    assert install_for_current_shell(SafeWriter()) is True
    assert 'eval "$(aparta hook zsh)"' in (tmp_path / ".zshrc").read_text()


def test_install_for_current_shell_leaves_unsupported_shells_untouched(tmp_path, monkeypatch):
    """Aparta must not write zsh configuration for a different active shell."""
    monkeypatch.setenv("SHELL", "/bin/bash")
    monkeypatch.setenv("ZDOTDIR", str(tmp_path))

    assert install_for_current_shell(SafeWriter()) is False
    assert not (tmp_path / ".zshrc").exists()
