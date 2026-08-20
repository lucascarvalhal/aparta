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


def test_codex_gets_a_session_start_hook(tmp_path: Path):
    import sys

    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pragma: no cover
        import tomli as tomllib

    from aparta.agents.codex import CodexAdapter

    adapter = CodexAdapter()
    adapter.inject(tmp_path, {"GH_CONFIG_DIR": "/x"}, SafeWriter())
    assert adapter.install_check(tmp_path, SafeWriter()) is True

    data = tomllib.loads((tmp_path / ".codex" / "config.toml").read_text())
    hook = data["hooks"]["SessionStart"][0]
    assert hook["hooks"][0]["command"] == CHECK_COMMAND
    assert data["env"]["GH_CONFIG_DIR"] == "/x"  # env survives
    assert adapter.install_check(tmp_path, SafeWriter()) is False

    adapter.uninstall_check(tmp_path, SafeWriter())
    assert "SessionStart" not in (tmp_path / ".codex" / "config.toml").read_text()


def test_gemini_hook_uses_the_json_contract(tmp_path: Path):
    from aparta.agents.base import CHECK_JSON_COMMAND
    from aparta.agents.gemini import GeminiAdapter

    adapter = GeminiAdapter()
    assert adapter.install_check(tmp_path, SafeWriter()) is True

    data = json.loads((tmp_path / ".gemini" / "settings.json").read_text())
    command = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    # Gemini refuses anything but JSON on stdout, so the hook asks for JSON
    assert command == CHECK_JSON_COMMAND
    assert "--json" in command

    adapter.uninstall_check(tmp_path, SafeWriter())
    assert not (tmp_path / ".gemini" / "settings.json").exists()


def test_opencode_plugin_keeps_env_and_gains_the_check(tmp_path: Path):
    from aparta.agents.opencode import OpencodeAdapter

    adapter = OpencodeAdapter()
    adapter.inject(tmp_path, {"GH_CONFIG_DIR": "/x"}, SafeWriter())
    assert adapter.install_check(tmp_path, SafeWriter()) is True

    plugin = (tmp_path / ".opencode" / "plugins" / "aparta-env.js").read_text()
    assert CHECK_COMMAND in plugin
    assert 'output.env["GH_CONFIG_DIR"] = "/x"' in plugin
    assert "session.created" in plugin
    assert adapter.read_env(tmp_path) == {"GH_CONFIG_DIR": "/x"}

    # re-injecting env must not drop the check
    adapter.inject(tmp_path, {"OTHER": "y"}, SafeWriter())
    plugin = (tmp_path / ".opencode" / "plugins" / "aparta-env.js").read_text()
    assert CHECK_COMMAND in plugin and "OTHER" in plugin

    adapter.uninstall_check(tmp_path, SafeWriter())
    plugin = (tmp_path / ".opencode" / "plugins" / "aparta-env.js").read_text()
    assert CHECK_COMMAND not in plugin
    assert 'output.env["GH_CONFIG_DIR"] = "/x"' in plugin


def test_generated_plugin_is_syntactically_valid(tmp_path: Path):
    """A broken plugin would take opencode down, so check it parses."""
    import shutil
    import subprocess

    from aparta.agents.opencode import render_plugin

    node = shutil.which("node")
    if not node:  # pragma: no cover - node is not required to develop aparta
        return
    plugin = tmp_path / "aparta-env.mjs"
    plugin.write_text(render_plugin({"A": "1", "B": 'quote"inside'}, with_check=True))
    result = subprocess.run([node, "--check", str(plugin)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
