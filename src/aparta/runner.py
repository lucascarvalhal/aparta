"""Run a command, or print exports, with a profile's environment.

Agents get the profile env through their adapters, but a plain shell or a
hand-run script inside a profile folder inherits nothing, so people write
wrapper scripts that re-export the paths by hand and forget the parts that
matter (the pinned CLOUDSDK_ACTIVE_CONFIG_NAME, the existence check on the
ADC). `aparta run` and `aparta env` expose the same battle-tested
Profile.env() instead.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from .i18n import _
from .profiles import Profile

TOKEN_TIMEOUT = 20


def profile_for_path(path: Path, profiles: dict[str, Profile]) -> Profile | None:
    """The profile owning a path: deepest root wins, adopted repos count."""
    path = path.resolve()
    best: Profile | None = None
    best_depth = -1
    for profile in profiles.values():
        candidates = [profile.root_path] + [Path(r).expanduser() for r in profile.adopted_repos]
        for root in candidates:
            root = root.resolve()
            if path == root or root in path.parents:
                depth = len(root.parts)
                if depth > best_depth:
                    best, best_depth = profile, depth
    return best


def gh_token(profile: Profile) -> str:
    """The profile's GitHub token, read from gh's keyring scope."""
    env = dict(os.environ, GH_CONFIG_DIR=str(profile.gh_config_dir))
    try:
        r = subprocess.run(
            ["gh", "auth", "token"],
            env=env,
            capture_output=True,
            text=True,
            timeout=TOKEN_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def profile_env(profile: Profile, with_gh_token: bool = False) -> dict[str, str]:
    """The variables this profile stands for, optionally with GITHUB_TOKEN.

    The token lives in the OS keyring; materializing it into an environment
    variable exposes it to every child process, so it is strictly opt-in.
    """
    env = profile.env()
    if with_gh_token and profile.gh_user:
        token = gh_token(profile)
        if token:
            env["GITHUB_TOKEN"] = token
    return env


def export_lines(env: dict[str, str]) -> str:
    """Shell-safe `export` lines for `eval "$(aparta env)"`."""
    return "\n".join(f"export {key}={shlex.quote(value)}" for key, value in env.items())


def run_in_profile(profile: Profile, command: list[str], with_gh_token: bool = False) -> int:
    """Execute a command with the profile env layered over the current one."""
    env = dict(os.environ)
    env.update(profile_env(profile, with_gh_token))
    try:
        return subprocess.run(command, env=env).returncode
    except FileNotFoundError:
        from rich.console import Console

        Console(stderr=True).print(_("[red]{cmd} not found in PATH.[/red]", cmd=command[0]))
        return 127
