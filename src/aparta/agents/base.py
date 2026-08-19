"""Agent adapter interface: detect, inject, validate.

Any concrete AgentAdapter subclass with a `name` registers itself; adding
an agent is just dropping a module in this package.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..fsutil import SafeWriter

REGISTRY: dict[str, type["AgentAdapter"]] = {}


class AgentAdapter(ABC):
    """Injects per-profile environment variables into one agent's config."""

    name: str = ""
    display_name: str = ""

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if cls.name:
            cls.display_name = cls.display_name or cls.name
            REGISTRY[cls.name] = cls

    @abstractmethod
    def detect(self, repo: Path) -> bool:
        """Whether this agent applies to the given repo."""

    @abstractmethod
    def inject(self, repo: Path, env: dict[str, str], writer: SafeWriter) -> bool:
        """Merge `env` into the agent's config file; True if anything changed."""

    @abstractmethod
    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        """Return (ok, message): are the expected variables in place?"""
