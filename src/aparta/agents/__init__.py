"""Terminal AI agent adapters, registered by importing every module here."""

from __future__ import annotations

import importlib
import pkgutil

from .base import ADAPTERS, AgentAdapter

for _mod in pkgutil.iter_modules(__path__):
    if _mod.name != "base":
        importlib.import_module(f"{__name__}.{_mod.name}")


def get_adapters(names: list[str]) -> list[AgentAdapter]:
    return [ADAPTERS[n]() for n in names if n in ADAPTERS]


__all__ = ["ADAPTERS", "AgentAdapter", "get_adapters"]
