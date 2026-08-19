"""Safe file writing: automatic backups, merges and dry-run diffs."""

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
    """Writes files with automatic backups and --dry-run support.

    Existing files are copied to <file>.bak-aparta-<timestamp> before any
    change. In dry-run mode nothing is touched; only the diff is shown.
    """

    dry_run: bool = False
    changes: list[str] = field(default_factory=list)

    def write_text(self, path: Path, new_content: str, label: str | None = None) -> bool:
        """Write `new_content` to `path`; True if anything changed (or would)."""
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
