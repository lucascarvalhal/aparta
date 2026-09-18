"""Backends configure external tools; they report through Note values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Note:
    level: str
    text: str
