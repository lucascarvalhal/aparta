"""Backends configure external tools; they report through Note values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Level = Literal["info", "warn", "error"]


@dataclass
class Note:
    level: Level
    text: str


def print_notes(notes: list[Note], console, verbose: bool) -> None:
    """Warnings and errors always; informational notes only when verbose."""
    for note in notes:
        if note.level != "info" or verbose:
            console.print(note.text)
