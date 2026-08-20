"""Startup checks: each agent gets the warning through its own mechanism."""

from __future__ import annotations

import json
from pathlib import Path

from aparta.agents.antigravity import AntigravityAdapter
from aparta.agents.base import CHECK_COMMAND
from aparta.agents.claude_code import ClaudeCodeAdapter
from aparta.agents.direnv import DirenvAdapter
from aparta.fsutil import SafeWriter


def test_claude_code_gets_a_session_start_hook(tmp_path: Path):
    adapter = ClaudeCodeAdapter()
    adapter.inject(tmp_path, {"GH_CONFIG_DIR": "/x"}, SafeWriter())
    assert adapter.install_check(tmp_path, SafeWriter()) is True

    data = json.loads((tmp_path / ".claude" / "settings.local.json").read_text())
    assert CHECK_COMMAND in json.dumps(data["hooks"]["SessionStart"])
    # the env it already had survives
    assert data["env"]["GH_CONFIG_DIR"] == "/x"


def test_claude_code_hook_is_not_duplicated(tmp_path: Path):
    adapter = ClaudeCodeAdapter()
    adapter.install_check(tmp_path, SafeWriter())
    assert adapter.install_check(tmp_path, SafeWriter()) is False


def test_claude_code_hook_can_be_removed(tmp_path: Path):
    adapter = ClaudeCodeAdapter()
    adapter.install_check(tmp_path, SafeWriter())
    assert adapter.uninstall_check(tmp_path, SafeWriter()) is True
    data = json.loads((tmp_path / ".claude" / "settings.local.json").read_text())
    assert "SessionStart" not in json.dumps(data)


def test_claude_code_keeps_other_session_hooks(tmp_path: Path):
    path = tmp_path / ".claude" / "settings.local.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "mine"}]}]}}))
    adapter = ClaudeCodeAdapter()
    adapter.install_check(tmp_path, SafeWriter())
    adapter.uninstall_check(tmp_path, SafeWriter())
    data = json.loads(path.read_text())
    assert "mine" in json.dumps(data["hooks"]["SessionStart"])


def test_direnv_appends_the_check_to_envrc(tmp_path: Path):
    adapter = DirenvAdapter()
    adapter.inject(tmp_path, {"GH_CONFIG_DIR": "/x"}, SafeWriter())
    assert adapter.install_check(tmp_path, SafeWriter()) is True

    text = (tmp_path / ".envrc").read_text()
    assert CHECK_COMMAND in text
    assert 'export GH_CONFIG_DIR="/x"' in text  # the env line is untouched
    assert adapter.install_check(tmp_path, SafeWriter()) is False  # idempotent

    adapter.uninstall_check(tmp_path, SafeWriter())
    assert CHECK_COMMAND not in (tmp_path / ".envrc").read_text()


def test_antigravity_uses_a_folder_open_task(tmp_path: Path):
    adapter = AntigravityAdapter()
    assert adapter.install_check(tmp_path, SafeWriter()) is True

    data = json.loads((tmp_path / ".vscode" / "tasks.json").read_text())
    task = data["tasks"][0]
    assert task["command"] == CHECK_COMMAND
    assert task["runOptions"]["runOn"] == "folderOpen"
    assert adapter.install_check(tmp_path, SafeWriter()) is False


def test_antigravity_keeps_existing_tasks(tmp_path: Path):
    path = tmp_path / ".vscode" / "tasks.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"version": "2.0.0", "tasks": [{"label": "build"}]}))
    adapter = AntigravityAdapter()
    adapter.install_check(tmp_path, SafeWriter())
    adapter.uninstall_check(tmp_path, SafeWriter())
    data = json.loads(path.read_text())
    assert [t["label"] for t in data["tasks"]] == ["build"]


def test_broken_config_never_raises(tmp_path: Path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.local.json").write_text("{broken")
    assert ClaudeCodeAdapter().install_check(tmp_path, SafeWriter()) is False
