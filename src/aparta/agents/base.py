"""Interface comum dos adapters de agentes: detect, inject, validate."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..fsutil import SafeWriter


class AgentAdapter(ABC):
    """Um adapter sabe injetar variáveis de ambiente em um agente para um repo."""

    name: str = ""

    @abstractmethod
    def detect(self, repo: Path) -> bool:
        """True se o agente é usado (ou faz sentido) neste repositório."""

    @abstractmethod
    def inject(self, repo: Path, env: dict[str, str], writer: SafeWriter) -> bool:
        """Faz merge das variáveis no arquivo de config do agente. True se mudou algo."""

    @abstractmethod
    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        """(ok, mensagem) — as variáveis esperadas estão presentes?"""
