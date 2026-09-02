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
from collections.abc import Mapping

from .i18n import _
from .profiles import MANAGED_ENV_KEYS, MANAGED_ENV_PREFIXES, Profile
from .workspaces import Workspace, profile_for_path

TOKEN_TIMEOUT = 20


def is_managed_env_key(key: str) -> bool:
    return key in MANAGED_ENV_KEYS or key.startswith(MANAGED_ENV_PREFIXES)


def clean_environment(
    base: Mapping[str, str], overlay: Mapping[str, str]
) -> dict[str, str]:
    """Replace Aparta-owned selectors instead of layering across clients."""
    clean = {key: value for key, value in base.items() if not is_managed_env_key(key)}
    clean.update(overlay)
    return clean


def gh_token(profile: Profile) -> str:
    """The profile's GitHub token, read from gh's keyring scope."""
    env = clean_environment(os.environ, {"GH_CONFIG_DIR": str(profile.gh_config_dir)})
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
    env = clean_environment(os.environ, profile_env(profile, with_gh_token))
    try:
        return subprocess.run(command, env=env).returncode
    except FileNotFoundError:
        from rich.console import Console

        Console(stderr=True).print(_("[red]{cmd} not found in PATH.[/red]", cmd=command[0]))
        return 127


def run_in_workspace(
    profile: Profile,
    workspace: Workspace,
    command: list[str],
    with_gh_token: bool = False,
) -> int:
    """Execute with only the providers enabled for the exact workspace."""
    from . import auth
    from .providers import canonical_providers, status_provider_name, workspace_env

    def relevant_problem(statuses: list[auth.AuthStatus]) -> auth.AuthStatus | None:
        selected = set(canonical_providers(workspace.providers))
        return next(
            (
                status
                for status in statuses
                if status.needs_human and status_provider_name(status.provider) in selected
            ),
            None,
        )

    if auth.checks_enabled():
        cached = auth.read_cached_status(profile) or []
        problem = relevant_problem(cached)
        if problem is not None:
            # Confirm a cached failure synchronously. A manual login outside
            # aparta must not leave a stale verdict blocking the workspace.
            problem = relevant_problem(auth.cached_check(profile, force=True))
        if problem is not None:
            from rich.console import Console

            Console(stderr=True).print(
                _(
                    "[red]{provider} credential for workspace '{workspace}' requires login: {detail}.[/red] Run [bold]aparta login[/bold] in that workspace.",
                    provider=problem.provider,
                    workspace=workspace.name,
                    detail=problem.detail,
                )
            )
            return 1

    overlay = workspace_env(workspace, profile)
    if with_gh_token and "github" in workspace.providers and profile.gh_user:
        token = gh_token(profile)
        if token:
            overlay["GITHUB_TOKEN"] = token
    env = clean_environment(os.environ, overlay)
    try:
        return subprocess.run(command, env=env).returncode
    except FileNotFoundError:
        from rich.console import Console

        Console(stderr=True).print(_("[red]{cmd} not found in PATH.[/red]", cmd=command[0]))
        return 127
