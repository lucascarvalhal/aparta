"""Safe file writing: automatic backups, merges and dry-run diffs."""

from __future__ import annotations

import difflib
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .i18n import _
from rich.console import Console

console = Console()


def tilde(path: Path | str) -> str:
    """Render a path with ~ when it lives under the user's home."""
    p = Path(path)
    home = Path.home()
    if p == home:
        return "~"
    try:
        return "~/" + str(p.relative_to(home))
    except ValueError:
        return str(p)


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
    verbose: bool = False
    changes: list[str] = field(default_factory=list)

    def write_text(self, path: Path, new_content: str, label: str | None = None) -> bool:
        """Write `new_content` to `path`; True if anything changed (or would)."""
        label = label or str(path)
        old_content = path.read_text() if path.exists() else None
        if old_content == new_content:
            return False

        if self.dry_run:
            if self.verbose:
                self._show_diff(label, old_content or "", new_content)
            self.changes.append(f"[dry-run] {label}")
            return True

        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            bak = backup_path(path)
            shutil.copy2(path, bak)
            if self.verbose:
                console.print(f"[dim]{_('backup:')} {bak}[/dim]")
        path.write_text(new_content)
        self.changes.append(label)
        if self.verbose:
            console.print(f"[green]{_('written:')}[/green] {label}")
        return True

    def remove_file(self, path: Path, label: str | None = None) -> bool:
        """Remove a file, keeping a backup copy. True if removed (or would)."""
        label = label or str(path)
        if not path.exists():
            return False
        if self.dry_run:
            if self.verbose:
                console.print(f"[yellow]--dry-run[/yellow] rm {label}")
            self.changes.append(f"[dry-run] rm {label}")
            return True
        bak = backup_path(path)
        shutil.copy2(path, bak)
        if self.verbose:
            console.print(f"[dim]{_('backup:')} {bak}[/dim]")
        path.unlink()
        self.changes.append(label)
        if self.verbose:
            console.print(f"[red]{_('removed:')}[/red] {label}")
        return True

    def remove_dir(self, path: Path, label: str | None = None) -> bool:
        """Remove a directory by renaming it to a backup. True if removed."""
        label = label or str(path)
        if not path.exists():
            return False
        if self.dry_run:
            if self.verbose:
                console.print(f"[yellow]--dry-run[/yellow] rm -r {label}")
            self.changes.append(f"[dry-run] rm -r {label}")
            return True
        bak = backup_path(path)
        path.rename(bak)
        if self.verbose:
            console.print(f"[dim]{_('backup:')} {bak}[/dim]")
        self.changes.append(label)
        if self.verbose:
            console.print(f"[red]{_('removed:')}[/red] {label}")
        return True

    def _show_diff(self, label: str, old: str, new: str) -> None:
        diff = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"{label} ({_('current')})",
            tofile=f"{label} ({_('proposed')})",
        )
        text = "".join(diff) or _("(no differences)")
        console.print(f"[bold yellow]--dry-run: {label}[/bold yellow]")
        console.print(text, highlight=False, markup=False)
