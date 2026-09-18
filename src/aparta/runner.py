"""Run a command, or print exports, with a profile's environment."""

from __future__ import annotations

from pathlib import Path

import os
import shlex
import subprocess

from .i18n import _
from .profiles import Profile, clean_environment
from .workspaces import Workspace

TOKEN_TIMEOUT = 20


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
    """The variables this profile stands for, optionally with GITHUB_TOKEN."""
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
    """Execute with every provider configured by an explicitly chosen profile."""
    from .workspaces import implicit_workspace

    workspace = implicit_workspace(Path.cwd(), profile)
    return run_in_workspace(profile, workspace, command, with_gh_token)


def run_in_workspace(
    profile: Profile,
    workspace: Workspace,
    command: list[str],
    with_gh_token: bool = False,
) -> int:
    """Execute with only the providers enabled for the exact workspace."""
    from . import auth
    from .providers import canonical_providers, status_provider_name, workspace_env

    selected = set(canonical_providers(workspace.providers))

    def relevant_problem(statuses: list[auth.AuthStatus]) -> auth.AuthStatus | None:
        return next(
            (
                status
                for status in statuses
                if status.needs_human and status_provider_name(status.provider) in selected
            ),
            None,
        )

    adc_path = profile.gcloud_config_dir / "application_default_credentials.json"
    problem = (
        auth.AuthStatus("ADC", auth.MISSING, _("no credential stored for this profile"))
        if "adc" in selected and not adc_path.is_file()
        else None
    )
    if problem is None and auth.checks_enabled():
        cached = auth.read_cached_status(profile) or []
        problem = relevant_problem(cached)
        if problem is not None:
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
