"""Reversible zsh hook and eval-safe workspace environment transitions."""

from __future__ import annotations

import os
import shlex
from collections.abc import Mapping
from pathlib import Path

from .fsutil import SafeWriter
from .profiles import MANAGED_ENV_KEYS, MANAGED_ENV_PREFIXES, Profile
from .providers import workspace_env
from .runner import export_lines
from .workspaces import Workspace


APARTA_METADATA_KEYS = (
    "APARTA_WORKSPACE",
    "APARTA_PROFILE",
    "APARTA_PROVIDERS",
)

ZSH_START = "# >>> aparta automatic workspace activation >>>"
ZSH_END = "# <<< aparta automatic workspace activation <<<"
ZSH_STARTUP_BLOCK = (
    f"{ZSH_START}\n"
    'eval "$(aparta hook zsh)"\n'
    f"{ZSH_END}\n"
)


def _keys_to_unset(current_env: Mapping[str, str]) -> list[str]:
    dynamic = [
        key
        for key in current_env
        if key.startswith(MANAGED_ENV_PREFIXES) or key in APARTA_METADATA_KEYS
    ]
    return list(dict.fromkeys([*MANAGED_ENV_KEYS, *dynamic, *APARTA_METADATA_KEYS]))


def activation_lines(
    workspace: Workspace | None,
    profile: Profile | None,
    current_env: Mapping[str, str] | None = None,
) -> str:
    """Render one atomic shell transition that first removes stale identity."""
    current_env = current_env or os.environ
    lines = ["unset " + " ".join(_keys_to_unset(current_env))]
    if workspace is None or profile is None:
        return "\n".join(lines)

    values = workspace_env(workspace, profile)
    values.update(
        {
            "APARTA_WORKSPACE": workspace.name,
            "APARTA_PROFILE": profile.name,
            "APARTA_PROVIDERS": ",".join(workspace.providers),
        }
    )
    exported = export_lines(values)
    if exported:
        lines.append(exported)
    return "\n".join(lines)


def render_zsh_hook() -> str:
    """Define additive chpwd/precmd hooks and activate the initial directory."""
    return r'''autoload -Uz add-zsh-hook

if (( ! ${+_APARTA_ORIGINAL_RPROMPT} )); then
  typeset -g _APARTA_ORIGINAL_RPROMPT="$RPROMPT"
fi
typeset -g _APARTA_PROMPT_SEGMENT=""

_aparta_activate_context() {
  local transition
  transition="$(command aparta env --activate 2>/dev/null)" || transition=""
  if [[ -n "$transition" ]]; then
    eval "$transition"
  fi
  if [[ -n "${APARTA_WORKSPACE:-}" ]]; then
    command aparta check --quiet >/dev/null 2>&1 &!
  fi
}

_aparta_refresh_prompt() {
  if [[ -n "${APARTA_WORKSPACE:-}" ]]; then
    _APARTA_PROMPT_SEGMENT="$(command aparta status --shell 2>/dev/null)"
  else
    _APARTA_PROMPT_SEGMENT=""
  fi
  if [[ -n "$_APARTA_PROMPT_SEGMENT" ]]; then
    RPROMPT="${_APARTA_PROMPT_SEGMENT}${_APARTA_ORIGINAL_RPROMPT:+ $_APARTA_ORIGINAL_RPROMPT}"
  else
    RPROMPT="$_APARTA_ORIGINAL_RPROMPT"
  fi
}

add-zsh-hook -d chpwd _aparta_activate_context 2>/dev/null || true
add-zsh-hook -d precmd _aparta_refresh_prompt 2>/dev/null || true
add-zsh-hook chpwd _aparta_activate_context
add-zsh-hook precmd _aparta_refresh_prompt
_aparta_activate_context
'''


def merge_zshrc(existing: str) -> str:
    """Add or replace Aparta's marked startup block without touching user code."""
    if ZSH_START in existing and ZSH_END in existing:
        before, rest = existing.split(ZSH_START, 1)
        _old, after = rest.split(ZSH_END, 1)
        return before.rstrip("\n") + "\n\n" + ZSH_STARTUP_BLOCK + after.lstrip("\n")
    prefix = existing.rstrip("\n")
    return prefix + ("\n\n" if prefix else "") + ZSH_STARTUP_BLOCK


def zshrc_path() -> Path:
    zdotdir = os.environ.get("ZDOTDIR")
    return Path(zdotdir).expanduser() / ".zshrc" if zdotdir else Path.home() / ".zshrc"


def install_zsh_hook(writer: SafeWriter, path: Path | None = None) -> bool:
    path = path or zshrc_path()
    existing = path.read_text() if path.exists() else ""
    return writer.write_text(path, merge_zshrc(existing), label=str(path))


def install_for_current_shell(writer: SafeWriter) -> bool:
    """Install activation only when the user's configured shell is supported."""
    if Path(os.environ.get("SHELL", "")).name != "zsh":
        return False
    return install_zsh_hook(writer)
