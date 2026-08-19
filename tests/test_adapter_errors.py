"""Adapters must survive broken config files instead of crashing apply/doctor."""

from __future__ import annotations

from pathlib import Path

import pytest

from aparta.agents.antigravity import AntigravityAdapter
from aparta.agents.claude_code import ClaudeCodeAdapter
from aparta.agents.codex import CodexAdapter
from aparta.apply import apply_profile
from aparta.fsutil import SafeWriter
from aparta.profiles import Profile

ENV = {"GH_CONFIG_DIR": "/x/gh-acme"}


def test_claude_validate_invalid_json(tmp_path: Path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.local.json").write_text("{broken")
    ok, msg = ClaudeCodeAdapter().validate(tmp_path, ENV)
    assert ok is False and "inválido" in msg


def test_codex_validate_invalid_toml(tmp_path: Path):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text("[env\nbroken")
    ok, msg = CodexAdapter().validate(tmp_path, ENV)
    assert ok is False and "inválido" in msg


@pytest.mark.parametrize(
    ("adapter", "path", "content"),
    [
        (ClaudeCodeAdapter(), ".claude/settings.local.json", "{broken"),
        (CodexAdapter(), ".codex/config.toml", "[env\nbroken"),
        (AntigravityAdapter(), ".vscode/settings.json", "not json"),
    ],
)
def test_inject_on_broken_file_raises_value_error(tmp_path, adapter, path, content):
    target = tmp_path / path
    target.parent.mkdir(parents=True)
    target.write_text(content)
    with pytest.raises(ValueError):
        adapter.inject(tmp_path, ENV, SafeWriter())


def test_apply_profile_survives_one_broken_repo(tmp_path, monkeypatch):
    """A repo with an invalid agent config is skipped, the others still get env."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    root = tmp_path / "work"
    good, bad = root / "good", root / "bad"
    for repo in (good, bad):
        repo.mkdir(parents=True)
        (repo / ".git").mkdir()
    (bad / ".claude").mkdir()
    (bad / ".claude" / "settings.local.json").write_text("{broken")

    profile = Profile(
        name="acme",
        root=str(root),
        git_email="a@b.c",
        gh_user="someone",
        agents=["claude-code"],
    )
    # backends run against fakes; only the adapter injection matters here
    monkeypatch.setattr("aparta.apply.BACKENDS", [])
    apply_profile(profile, SafeWriter())

    assert (good / ".claude" / "settings.local.json").exists()
    assert (bad / ".claude" / "settings.local.json").read_text() == "{broken"
