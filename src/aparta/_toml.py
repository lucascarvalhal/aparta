"""TOML reading and writing with one import for every supported Python."""

from __future__ import annotations

import sys

import tomli_w

if sys.version_info >= (3, 11):
    from tomllib import TOMLDecodeError, loads
else:  # pragma: no cover
    from tomli import TOMLDecodeError, loads

dumps = tomli_w.dumps

__all__ = ["TOMLDecodeError", "dumps", "loads"]
