"""Adapter registry: auto-registration and display_name."""

from pathlib import Path

from aparta.agents import ADAPTERS, get_adapters
from aparta.agents.base import AgentAdapter


def test_all_builtin_adapters_registered():
    assert set(ADAPTERS) >= {"claude-code", "codex", "gemini", "antigravity", "direnv"}


def test_adapters_declare_display_name():
    for name, cls in ADAPTERS.items():
        assert cls.name == name
        assert cls.display_name, f"{name} sem display_name"
    assert ADAPTERS["claude-code"].display_name == "Claude Code"
    assert ADAPTERS["gemini"].display_name == "Gemini CLI"
    assert ADAPTERS["antigravity"].display_name == "Antigravity"


def test_new_adapter_file_registers_itself():
    class FakeAdapter(AgentAdapter):
        name = "fake-test-adapter"

        def env_path(self, repo: Path) -> Path:  # pragma: no cover
            return repo / "fake.json"

        def env_of(self, doc):  # pragma: no cover
            return {}

        def set_env(self, doc, env) -> None:  # pragma: no cover
            pass

    try:
        assert ADAPTERS["fake-test-adapter"] is FakeAdapter
        assert FakeAdapter.display_name == "fake-test-adapter"
        assert isinstance(get_adapters(["fake-test-adapter"])[0], FakeAdapter)
    finally:
        del ADAPTERS["fake-test-adapter"]


def test_get_adapters_ignores_unknown():
    assert get_adapters(["nao-existe"]) == []
