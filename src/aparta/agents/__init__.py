"""Terminal AI agent adapters."""

from __future__ import annotations

import importlib
import pkgutil

from .base import REGISTRY, AgentAdapter

for _mod in pkgutil.iter_modules(__path__):
    if _mod.name != "base":
        importlib.import_module(f"{__name__}.{_mod.name}")

ADAPTERS: dict[str, type[AgentAdapter]] = REGISTRY


def get_adapters(names: list[str]) -> list[AgentAdapter]:
    return [ADAPTERS[n]() for n in names if n in ADAPTERS]
