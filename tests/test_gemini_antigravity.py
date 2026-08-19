"""Gemini CLI (.gemini/.env) and Antigravity (.vscode/settings.json) adapters."""

import json
from pathlib import Path

from aparta.agents.antigravity import AntigravityAdapter, merge_vscode_settings
from aparta.agents.gemini import GeminiAdapter, merge_dotenv
from aparta.fsutil import SafeWriter

ENV = {"GH_CONFIG_DIR": "/home/x/.config/gh-pessoal", "CLOUDSDK_ACTIVE_CONFIG_NAME": "pessoal"}


def test_merge_dotenv_appends_and_updates():
    existing = 'GEMINI_API_KEY="abc"\nCLOUDSDK_ACTIVE_CONFIG_NAME="velho"\n'
    merged = merge_dotenv(existing, ENV)
    assert 'GEMINI_API_KEY="abc"' in merged
    assert merged.count("CLOUDSDK_ACTIVE_CONFIG_NAME") == 1
    assert 'CLOUDSDK_ACTIVE_CONFIG_NAME="pessoal"' in merged
    assert 'GH_CONFIG_DIR="/home/x/.config/gh-pessoal"' in merged


def test_gemini_inject_and_validate(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    adapter = GeminiAdapter()
    assert adapter.inject(repo, ENV, SafeWriter()) is True
    assert (repo / ".gemini" / ".env").exists()
    ok, msg = adapter.validate(repo, ENV)
    assert ok, msg


def test_vscode_merge_preserves_settings():
    existing = json.dumps(
        {
            "editor.fontSize": 14,
            "terminal.integrated.env.osx": {"FOO": "bar"},
        }
    )
    merged = json.loads(merge_vscode_settings(existing, ENV))
    assert merged["editor.fontSize"] == 14
    assert merged["terminal.integrated.env.osx"]["FOO"] == "bar"
    assert merged["terminal.integrated.env.osx"]["CLOUDSDK_ACTIVE_CONFIG_NAME"] == "pessoal"
    assert merged["terminal.integrated.env.linux"]["GH_CONFIG_DIR"] == ENV["GH_CONFIG_DIR"]


def test_antigravity_inject_validate_and_backup(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".vscode").mkdir(parents=True)
    settings = repo / ".vscode" / "settings.json"
    settings.write_text(json.dumps({"files.exclude": {"**/.git": True}}))

    adapter = AntigravityAdapter()
    assert adapter.inject(repo, ENV, SafeWriter()) is True

    data = json.loads(settings.read_text())
    assert data["files.exclude"] == {"**/.git": True}
    ok, msg = adapter.validate(repo, ENV)
    assert ok, msg
    assert list((repo / ".vscode").glob("settings.json.bak-aparta-*"))


def test_antigravity_validate_detects_divergence(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".vscode").mkdir(parents=True)
    (repo / ".vscode" / "settings.json").write_text(
        json.dumps({"terminal.integrated.env.osx": {"CLOUDSDK_ACTIVE_CONFIG_NAME": "outro"}})
    )
    ok, msg = AntigravityAdapter().validate(repo, ENV)
    assert not ok
    assert "divergente" in msg
