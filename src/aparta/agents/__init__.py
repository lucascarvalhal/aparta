"""Adapters de agentes de IA de terminal."""

from __future__ import annotations

from .base import AgentAdapter
from .claude_code import ClaudeCodeAdapter
from .codex import CodexAdapter
from .direnv import DirenvAdapter

ADAPTERS: dict[str, type[AgentAdapter]] = {
    ClaudeCodeAdapter.name: ClaudeCodeAdapter,
    CodexAdapter.name: CodexAdapter,
    DirenvAdapter.name: DirenvAdapter,
}


def get_adapters(names: list[str]) -> list[AgentAdapter]:
    return [ADAPTERS[n]() for n in names if n in ADAPTERS]
