"""Adapter Antigravity (IDE agent-first do Google).

O Antigravity é um fork do VS Code e lê as configurações de workspace em
.vscode/settings.json; o terminal integrado (usado também pelos agentes ao
executar comandos) honra "terminal.integrated.env.<plataforma>". Injetamos as
variáveis em terminal.integrated.env.osx e .linux, preservando o resto.

Limitação conhecida: não há (até o momento) um mecanismo documentado do
Antigravity para injetar env diretamente no processo do agente fora do
terminal integrado. Se os comandos do agente não herdarem essas variáveis na
sua versão, combine este adapter com o adapter `direnv` (.envrc) como
fallback — o direnv aplica o env a qualquer shell que entre na pasta.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..fsutil import SafeWriter
from .base import AgentAdapter

_PLATFORM_KEYS = ("terminal.integrated.env.osx", "terminal.integrated.env.linux")


def merge_vscode_settings(existing_text: str, env: dict[str, str]) -> str:
    """Faz merge do env em terminal.integrated.env.{osx,linux} preservando o resto."""
    data = json.loads(existing_text) if existing_text.strip() else {}
    if not isinstance(data, dict):
        raise ValueError(".vscode/settings.json não contém um objeto JSON")
    for key in _PLATFORM_KEYS:
        current = data.get(key, {})
        if not isinstance(current, dict):
            current = {}
        data[key] = {**current, **env}
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


class AntigravityAdapter(AgentAdapter):
    name = "antigravity"
    display_name = "Antigravity"

    def settings_path(self, repo: Path) -> Path:
        return repo / ".vscode" / "settings.json"

    def detect(self, repo: Path) -> bool:
        # Workspace settings valem para qualquer repo aberto no Antigravity.
        return True

    def inject(self, repo: Path, env: dict[str, str], writer: SafeWriter) -> bool:
        path = self.settings_path(repo)
        existing = path.read_text() if path.exists() else ""
        return writer.write_text(path, merge_vscode_settings(existing, env))

    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        path = self.settings_path(repo)
        if not path.exists():
            return False, ".vscode/settings.json ausente"
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return False, ".vscode/settings.json inválido"
        for key in _PLATFORM_KEYS:
            current = data.get(key, {})
            missing = [k for k, v in env.items() if current.get(k) != v]
            if missing:
                return False, f"{key} divergente: {', '.join(missing)}"
        return True, "env ok"
