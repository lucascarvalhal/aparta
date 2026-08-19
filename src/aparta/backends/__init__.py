"""Backends configure external tools; they report through Note values.

Backends never print: each apply function returns a list of Notes and the
application layer decides how to render them. `text` is localized and may
contain rich markup; `level` enables non-interactive frontends later.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Note:
    level: str  # "info", "warn" or "error"
    text: str
