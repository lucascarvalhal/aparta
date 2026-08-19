"""Agent adapter interface: detect, inject, validate.

Any concrete AgentAdapter subclass with a `name` registers itself; adding
an agent is just dropping a module in this package.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

from ..fsutil import SafeWriter

REGISTRY: dict[str, type["AgentAdapter"]] = {}


def merge_env_lines(existing_text: str, env: dict[str, str], template: str) -> str:
    """Update or append one line per variable, preserving the rest.

    `template` formats a line from (key, value), e.g. '{k}="{v}"' or
    'export {k}="{v}"'. Double quotes in values are escaped.
    """
    lines = existing_text.splitlines()
    out = list(lines)
    for key, value in env.items():
        value = value.replace('"', '\\"')
        rendered = template.format(k=key, v=value)
        pattern = re.compile(rf"^\s*(export\s+)?{re.escape(key)}=")
        for i, line in enumerate(out):
            if pattern.match(line):
                out[i] = rendered
                break
        else:
            out.append(rendered)
    return "\n".join(out) + "\n"


def parse_env_lines(text: str) -> dict[str, str]:
    """KEY=value pairs from dotenv-style text, unquoting values."""
    env: dict[str, str] = {}
    for m in re.finditer(r"^\s*(?:export\s+)?(\w+)=(.*)$", text, re.M):
        value = m.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env.setdefault(m.group(1), value)
    return env


def missing_keys(current: dict[str, str], expected: dict[str, str]) -> list[str]:
    """Expected variables absent or divergent in `current`."""
    return [k for k, v in expected.items() if current.get(k) != v]


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

    def read_env(self, repo: Path) -> dict[str, str]:
        """Env this agent's config already defines for the repo.

        Used by discovery to detect previous setups; {} when unknown.
        """
        return {}
