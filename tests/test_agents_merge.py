"""Merging of settings.local.json (Claude Code), .codex/config.toml and .envrc."""

import json
from pathlib import Path

from aparta.agents.claude_code import ClaudeCodeAdapter, merge_settings_env
from aparta.agents.codex import merge_codex_env
from aparta.agents.direnv import merge_envrc
from aparta.fsutil import SafeWriter

ENV = {"GH_CONFIG_DIR": "/home/x/.config/gh-pessoal", "CLOUDSDK_ACTIVE_CONFIG_NAME": "pessoal"}


def test_settings_merge_preserves_other_keys():
    existing = json.dumps(
        {"permissions": {"allow": ["Bash(ls:*)"]}, "env": {"FOO": "bar"}}
    )
    merged = json.loads(merge_settings_env(existing, ENV))
    assert merged["permissions"] == {"allow": ["Bash(ls:*)"]}
    assert merged["env"]["FOO"] == "bar"
    assert merged["env"]["GH_CONFIG_DIR"] == ENV["GH_CONFIG_DIR"]


def test_settings_merge_from_empty():
    merged = json.loads(merge_settings_env("", ENV))
    assert merged == {"env": ENV}


def test_settings_merge_overrides_stale_values():
    existing = json.dumps({"env": {"CLOUDSDK_ACTIVE_CONFIG_NAME": "antigo"}})
    merged = json.loads(merge_settings_env(existing, ENV))
    assert merged["env"]["CLOUDSDK_ACTIVE_CONFIG_NAME"] == "pessoal"


def test_claude_adapter_inject_and_validate(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.local.json").write_text(json.dumps({"model": "opus"}))

    adapter = ClaudeCodeAdapter()
    writer = SafeWriter(dry_run=False)
    assert adapter.inject(repo, ENV, writer) is True

    data = json.loads((repo / ".claude" / "settings.local.json").read_text())
    assert data["model"] == "opus"
    assert data["env"] == ENV
    ok, msg = adapter.validate(repo, ENV)
    assert ok, msg
    # backup created
    assert list((repo / ".claude").glob("settings.local.json.bak-aparta-*"))


def test_codex_merge_preserves_toml():
    existing = 'model = "gpt-5"\n\n[env]\nFOO = "bar"\n'
    merged = merge_codex_env(existing, ENV)
    assert 'model = "gpt-5"' in merged
    assert 'FOO = "bar"' in merged
    assert 'CLOUDSDK_ACTIVE_CONFIG_NAME = "pessoal"' in merged


def test_envrc_merge_appends_and_updates():
    existing = 'use flake\nexport GH_CONFIG_DIR="/velho"\n'
    merged = merge_envrc(existing, ENV)
    assert "use flake" in merged
    assert merged.count("GH_CONFIG_DIR") == 1
    assert 'export GH_CONFIG_DIR="/home/x/.config/gh-pessoal"' in merged
    assert 'export CLOUDSDK_ACTIVE_CONFIG_NAME="pessoal"' in merged
