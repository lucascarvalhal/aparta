"""Utilitários de escrita segura: backup, merge e dry-run com diff."""

from __future__ import annotations

import difflib
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

console = Console()


def backup_path(path: Path) -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.name}.bak-aparta-{ts}")


@dataclass
class SafeWriter:
    """Escreve arquivos com backup automático e suporte a --dry-run.

    Toda escrita em arquivo existente gera <arquivo>.bak-aparta-<timestamp>
    antes de alterar. Em dry-run nada é tocado; apenas o diff é exibido.
    """

    dry_run: bool = False
    changes: list[str] = field(default_factory=list)

    def write_text(self, path: Path, new_content: str, label: str | None = None) -> bool:
        """Escreve `new_content` em `path`. Retorna True se houve (ou haveria) mudança."""
        label = label or str(path)
        old_content = path.read_text() if path.exists() else None
        if old_content == new_content:
            return False

        if self.dry_run:
            self._show_diff(label, old_content or "", new_content)
            self.changes.append(f"[dry-run] {label}")
            return True

        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            bak = backup_path(path)
            shutil.copy2(path, bak)
            console.print(f"[dim]backup: {bak}[/dim]")
        path.write_text(new_content)
        self.changes.append(label)
        console.print(f"[green]escrito:[/green] {label}")
        return True

    def _show_diff(self, label: str, old: str, new: str) -> None:
        diff = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"{label} (atual)",
            tofile=f"{label} (proposto)",
        )
        text = "".join(diff) or "(sem diferenças)"
        console.print(f"[bold yellow]--dry-run — {label}[/bold yellow]")
        console.print(text, highlight=False, markup=False)
