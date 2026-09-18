"""English canonical strings with translation catalogs loaded from locales/*.json."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

LANGUAGES = ("en", "pt")
LOCALES = Path(__file__).parent / "locales"

_saved_cache: tuple[object, str] | None = None


@lru_cache(maxsize=None)
def catalog(lang: str) -> dict[str, str]:
    """Translation table for a language; English is the identity."""
    path = LOCALES / f"{lang}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(value: str) -> str:
    return "pt" if value.lower().startswith("pt") else "en"


def saved_language() -> str:
    """Language persisted by the wizard's first-run question ('' if none)."""
    global _saved_cache
    from .profiles import config_dir

    d = config_dir()
    if _saved_cache is None or _saved_cache[0] != d:
        try:
            value = (d / "language").read_text().strip()
        except OSError:
            value = ""
        _saved_cache = (d, value if value in LANGUAGES else "")
    return _saved_cache[1]


def set_language(lang: str) -> None:
    """Persist the chosen language in aparta's config directory."""
    global _saved_cache
    from .profiles import config_dir

    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "language").write_text(lang + "\n")
    _saved_cache = (d, lang)


def resolve_lang() -> str:
    """APARTA_LANG, then the saved choice, then LC_ALL, LC_MESSAGES and LANG."""
    env = os.environ.get("APARTA_LANG")
    if env:
        return _normalize(env)
    saved = saved_language()
    if saved:
        return saved
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return _normalize(value)
    return "en"


def _(text: str, **kwargs) -> str:
    """Translate a canonical English string and format its placeholders."""
    translated = catalog(resolve_lang()).get(text, text)
    return translated.format(**kwargs) if kwargs else translated
