"""Agent adapters: one file format strategy each, one merge algorithm for all."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .. import _toml
from ..fsutil import SafeWriter
from ..i18n import _

ADAPTERS: dict[str, type["AgentAdapter"]] = {}

CHECK_COMMAND = "aparta check --quiet"
CHECK_JSON_COMMAND = "aparta check --quiet --json"


class FileFormat(ABC):
    """Parses a config file into a document and renders it back."""

    @abstractmethod
    def load(self, text: str) -> Any:
        """Document for the text; ValueError when the text is not this format."""

    @abstractmethod
    def dump(self, doc: Any) -> str:
        """Text for the document."""


class JsonFormat(FileFormat):
    def load(self, text: str) -> dict:
        if not text.strip():
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(str(exc)) from exc
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
        return data

    def dump(self, doc: dict) -> str:
        return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


class TomlFormat(FileFormat):
    def load(self, text: str) -> dict:
        if not text.strip():
            return {}
        try:
            return _toml.loads(text)
        except _toml.TOMLDecodeError as exc:
            raise ValueError(str(exc)) from exc

    def dump(self, doc: dict) -> str:
        return _toml.dumps(doc)


class DotenvDoc:
    """Dotenv text kept verbatim, so unrelated lines survive every merge."""

    def __init__(self, text: str) -> None:
        self.text = text


class DotenvFormat(FileFormat):
    def __init__(self, template: str) -> None:
        self.template = template

    def load(self, text: str) -> DotenvDoc:
        return DotenvDoc(text)

    def dump(self, doc: DotenvDoc) -> str:
        return doc.text


def merge_env_lines(existing_text: str, env: dict[str, str], template: str) -> str:
    """Update or append one line per variable, preserving the rest."""
    out = existing_text.splitlines()
    for key, value in env.items():
        rendered = template.format(k=key, v=value.replace('"', '\\"'))
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


def remove_env_lines(existing_text: str, keys: list[str]) -> str:
    """Drop the lines that define any of the given variables."""
    pattern = re.compile(rf"^\s*(export\s+)?({'|'.join(re.escape(k) for k in keys)})=")
    lines = [line for line in existing_text.splitlines() if not pattern.match(line)]
    return "\n".join(lines) + ("\n" if lines else "")


def missing_keys(current: dict[str, str], expected: dict[str, str]) -> list[str]:
    """Expected variables absent or divergent in `current`."""
    return [k for k, v in expected.items() if current.get(k) != v]


def _mentions(entry: Any, command: str) -> bool:
    return command in json.dumps(entry, default=str)


def _entries(doc: dict, key: tuple[str, ...], create: bool) -> list | None:
    node: Any = doc
    for part in key[:-1]:
        child = node.get(part) if isinstance(node, dict) else None
        if child is None and create:
            child = node[part] = {}
        if not isinstance(child, dict):
            return None
        node = child
    entries = node.get(key[-1]) if isinstance(node, dict) else None
    if entries is None and create:
        entries = node[key[-1]] = []
    return entries if isinstance(entries, list) else None


def _set_entries(doc: dict, key: tuple[str, ...], entries: list) -> None:
    chain = [doc]
    for part in key[:-1]:
        chain.append(chain[-1][part])
    if entries:
        chain[-1][key[-1]] = entries
        return
    chain[-1].pop(key[-1], None)
    for parent, part in zip(reversed(chain[:-1]), reversed(key[:-1])):
        if parent[part]:
            break
        parent.pop(part)


class AgentAdapter(ABC):
    """Injects per-profile environment variables into one agent's config."""

    name: str = ""
    display_name: str = ""
    format: FileFormat
    hook_key: tuple[str, ...] = ()
    hook_command: str = CHECK_COMMAND
    hook_defaults: dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if cls.name:
            cls.display_name = cls.display_name or cls.name
            ADAPTERS[cls.name] = cls

    @abstractmethod
    def env_path(self, repo: Path) -> Path:
        """The file that carries the environment for this repo."""

    @abstractmethod
    def env_of(self, doc: Any) -> dict[str, str]:
        """The variables the document currently defines."""

    @abstractmethod
    def set_env(self, doc: Any, env: dict[str, str]) -> None:
        """Make `env` the complete set of variables in the document."""

    def is_empty(self, doc: Any) -> bool:
        return not doc

    def hook_path(self, repo: Path) -> Path:
        return self.env_path(repo)

    def hook_format(self) -> FileFormat:
        return self.format

    def hook_entry(self) -> dict:
        raise NotImplementedError

    def hook_is_empty(self, doc: Any) -> bool:
        return not doc

    def _load(self, path: Path, fmt: FileFormat | None = None) -> Any:
        text = path.read_text() if path.exists() else ""
        try:
            return (fmt or self.format).load(text)
        except ValueError as exc:
            raise ValueError(_("{file} is invalid", file=path.name)) from exc

    def read_env(self, repo: Path) -> dict[str, str]:
        try:
            return dict(self.env_of(self._load(self.env_path(repo))))
        except ValueError:
            return {}

    def inject(self, repo: Path, env: dict[str, str], writer: SafeWriter) -> bool:
        """Merge `env` into the agent's config file; True if anything changed."""
        path = self.env_path(repo)
        doc = self._load(path)
        self.set_env(doc, {**self.env_of(doc), **env})
        return writer.write_text(path, self.format.dump(doc))

    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        """(ok, message): are the expected variables in place?"""
        path = self.env_path(repo)
        if not path.exists():
            return False, _("{file} missing", file=path.name)
        try:
            current = self.env_of(self._load(path))
        except ValueError as exc:
            return False, str(exc)
        missing = missing_keys(current, env)
        if missing:
            return False, _("env mismatch: {keys}", keys=", ".join(missing))
        return True, _("env ok")

    def remove_env(self, repo: Path, keys: list[str], writer: SafeWriter) -> bool:
        """Remove the given variables from the agent's config; True if changed."""
        path = self.env_path(repo)
        if not path.exists():
            return False
        try:
            doc = self._load(path)
        except ValueError:
            return False
        current = self.env_of(doc)
        if not any(key in current for key in keys):
            return False
        self.set_env(doc, {k: v for k, v in current.items() if k not in keys})
        if self.is_empty(doc):
            return writer.remove_file(path)
        return writer.write_text(path, self.format.dump(doc))

    def install_check(self, repo: Path, writer: SafeWriter) -> bool:
        """Make the agent run the credential check when a session starts."""
        if not self.hook_key:
            return False
        path = self.hook_path(repo)
        try:
            doc = self._load(path, self.hook_format())
        except ValueError:
            return False
        entries = _entries(doc, self.hook_key, create=True)
        if entries is None or any(_mentions(e, self.hook_command) for e in entries):
            return False
        for key, value in self.hook_defaults.items():
            doc.setdefault(key, value)
        entries.append(self.hook_entry())
        return writer.write_text(path, self.hook_format().dump(doc))

    def uninstall_check(self, repo: Path, writer: SafeWriter) -> bool:
        """Remove the startup check this adapter installed."""
        if not self.hook_key:
            return False
        path = self.hook_path(repo)
        if not path.exists():
            return False
        try:
            doc = self._load(path, self.hook_format())
        except ValueError:
            return False
        entries = _entries(doc, self.hook_key, create=False)
        if not entries:
            return False
        remaining = [e for e in entries if not _mentions(e, self.hook_command)]
        if len(remaining) == len(entries):
            return False
        _set_entries(doc, self.hook_key, remaining)
        if self.hook_is_empty(doc):
            return writer.remove_file(path)
        return writer.write_text(path, self.hook_format().dump(doc))


class DotenvAdapter(AgentAdapter):
    """Adapters whose environment is a dotenv file with a per-agent line template."""

    def env_of(self, doc: DotenvDoc) -> dict[str, str]:
        return parse_env_lines(doc.text)

    def set_env(self, doc: DotenvDoc, env: dict[str, str]) -> None:
        stale = [key for key in parse_env_lines(doc.text) if key not in env]
        text = remove_env_lines(doc.text, stale) if stale else doc.text
        doc.text = merge_env_lines(text, env, self.format.template) if env else text

    def is_empty(self, doc: DotenvDoc) -> bool:
        return not doc.text.strip()
