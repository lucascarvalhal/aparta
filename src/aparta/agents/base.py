"""Interface comum dos adapters de agentes: detect, inject, validate.

Registry central: qualquer subclasse concreta de AgentAdapter com `name`
definido é registrada automaticamente. Adicionar um agente novo = criar um
arquivo neste pacote (os módulos são importados por aparta.agents).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..fsutil import SafeWriter

REGISTRY: dict[str, type["AgentAdapter"]] = {}


class AgentAdapter(ABC):
    """Um adapter sabe injetar variáveis de ambiente em um agente para um repo."""

    name: str = ""
    display_name: str = ""

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if cls.name:
            cls.display_name = cls.display_name or cls.name
            REGISTRY[cls.name] = cls

    @abstractmethod
    def detect(self, repo: Path) -> bool:
        """True se o agente é usado (ou faz sentido) neste repositório."""

    @abstractmethod
    def inject(self, repo: Path, env: dict[str, str], writer: SafeWriter) -> bool:
        """Faz merge das variáveis no arquivo de config do agente. True se mudou algo."""

    @abstractmethod
    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        """(ok, mensagem) — as variáveis esperadas estão presentes?"""
