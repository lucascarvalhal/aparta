"""Adapter Gemini CLI: variáveis em <repo>/.gemini/.env (mecanismo nativo).

O Gemini CLI carrega automaticamente variáveis de ambiente de arquivos .env,
procurando primeiro <projeto>/.gemini/.env, depois <projeto>/.env, subindo
até a raiz do projeto (.git) ou a home. Usamos .gemini/.env porque é o local
específico do Gemini (não interfere no .env da aplicação) e porque algumas
variáveis só são lidas de lá.
Ref.: google-gemini/gemini-cli docs/reference/configuration.md
"""

from __future__ import annotations

import re
from pathlib import Path

from ..fsutil import SafeWriter
from .base import AgentAdapter


def merge_dotenv(existing_text: str, env: dict[str, str]) -> str:
    """Atualiza/adiciona linhas KEY="value" preservando o resto do arquivo."""
    lines = existing_text.splitlines()
    out = list(lines)
    for key, value in env.items():
        pattern = re.compile(rf"^\s*(export\s+)?{re.escape(key)}=")
        replaced = False
        for i, line in enumerate(out):
            if pattern.match(line):
                out[i] = f'{key}="{value}"'
                replaced = True
                break
        if not replaced:
            out.append(f'{key}="{value}"')
    return "\n".join(out) + "\n"


class GeminiAdapter(AgentAdapter):
    name = "gemini"
    display_name = "Gemini CLI"

    def env_path(self, repo: Path) -> Path:
        return repo / ".gemini" / ".env"

    def detect(self, repo: Path) -> bool:
        # O Gemini CLI cria .gemini/ sob demanda; o adapter é sempre aplicável.
        return True

    def inject(self, repo: Path, env: dict[str, str], writer: SafeWriter) -> bool:
        path = self.env_path(repo)
        existing = path.read_text() if path.exists() else ""
        return writer.write_text(path, merge_dotenv(existing, env))

    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        path = self.env_path(repo)
        if not path.exists():
            return False, ".gemini/.env ausente"
        text = path.read_text()
        missing = [k for k, v in env.items() if f'{k}="{v}"' not in text]
        return (not missing, "env ok" if not missing else f"faltando: {', '.join(missing)}")
