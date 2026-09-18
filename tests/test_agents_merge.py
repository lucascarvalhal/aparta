"""Merging of settings.local.json (Claude Code), .codex/config.toml and .envrc."""

import json
from pathlib import Path

from aparta import _toml
from aparta.agents.claude_code import ClaudeCodeAdapter
from aparta.agents.codex import CodexAdapter
from aparta.agents.direnv import DirenvAdapter
from aparta.fsutil import SafeWriter

ENV = {"GH_CONFIG_DIR": "/home/x/.config/gh-pessoal", "CLOUDSDK_ACTIVE_CONFIG_NAME": "pessoal"}


def _inject(adapter, repo: Path, existing: str | None) -> str:
    path = adapter.env_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    if existing is not None:
        path.write_text(existing)
    adapter.inject(repo, ENV, SafeWriter())
    return path.read_text()


def test_settings_merge_preserves_other_keys(tmp_path: Path):
    existing = json.dumps({"permissions": {"allow": ["Bash(ls:*)"]}, "env": {"FOO": "bar"}})
    merged = json.loads(_inject(ClaudeCodeAdapter(), tmp_path, existing))
    assert merged["permissions"] == {"allow": ["Bash(ls:*)"]}
    assert merged["env"]["FOO"] == "bar"
    assert merged["env"]["GH_CONFIG_DIR"] == ENV["GH_CONFIG_DIR"]


def test_settings_merge_from_nothing(tmp_path: Path):
    assert json.loads(_inject(ClaudeCodeAdapter(), tmp_path, None)) == {"env": ENV}


def test_settings_merge_overrides_stale_values(tmp_path: Path):
    existing = json.dumps({"env": {"CLOUDSDK_ACTIVE_CONFIG_NAME": "antigo"}})
    merged = json.loads(_inject(ClaudeCodeAdapter(), tmp_path, existing))
    assert merged["env"]["CLOUDSDK_ACTIVE_CONFIG_NAME"] == "pessoal"


def test_claude_adapter_inject_and_validate(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.local.json").write_text(json.dumps({"model": "opus"}))

    adapter = ClaudeCodeAdapter()
    assert adapter.inject(repo, ENV, SafeWriter()) is True

    data = json.loads((repo / ".claude" / "settings.local.json").read_text())
    assert data["model"] == "opus"
    assert data["env"] == ENV
    ok, msg = adapter.validate(repo, ENV)
    assert ok, msg
    assert list((repo / ".claude").glob("settings.local.json.bak-aparta-*"))


def test_invalid_json_is_reported_not_overwritten(tmp_path: Path):
    adapter = ClaudeCodeAdapter()
    path = adapter.env_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not json")
    try:
        adapter.inject(tmp_path, ENV, SafeWriter())
    except ValueError as exc:
        assert "settings.local.json" in str(exc)
    else:
        raise AssertionError("invalid config must not be overwritten")
    assert path.read_text() == "{not json"
    assert adapter.validate(tmp_path, ENV) == (False, "settings.local.json is invalid")


def test_codex_merge_preserves_toml_and_migrates_the_legacy_env_table(tmp_path: Path):
    existing = (
        'model = "gpt-5"\n\n'
        '[env]\nFOO = "bar"\nGH_CONFIG_DIR = "/old"\n\n'
        '[shell_environment_policy.set]\nOTHER = "keep"\n'
    )
    data = _toml.loads(_inject(CodexAdapter(), tmp_path, existing))
    assert data["model"] == "gpt-5"
    assert data["env"] == {"FOO": "bar"}
    assert data["shell_environment_policy"]["set"] == {"OTHER": "keep", **ENV}


def test_codex_adapter_applies_without_preexisting_codex_directory(tmp_path: Path):
    assert CodexAdapter().inject(tmp_path, ENV, SafeWriter()) is True
    assert (tmp_path / ".codex" / "config.toml").exists()


def test_envrc_merge_appends_and_updates(tmp_path: Path):
    merged = _inject(DirenvAdapter(), tmp_path, 'use flake\nexport GH_CONFIG_DIR="/velho"\n')
    assert "use flake" in merged
    assert merged.count("GH_CONFIG_DIR") == 1
    assert 'export GH_CONFIG_DIR="/home/x/.config/gh-pessoal"' in merged
    assert 'export CLOUDSDK_ACTIVE_CONFIG_NAME="pessoal"' in merged


def test_removing_the_last_variables_removes_the_file(tmp_path: Path):
    adapter = ClaudeCodeAdapter()
    adapter.inject(tmp_path, ENV, SafeWriter())
    assert adapter.remove_env(tmp_path, list(ENV), SafeWriter()) is True
    assert not adapter.env_path(tmp_path).exists()
