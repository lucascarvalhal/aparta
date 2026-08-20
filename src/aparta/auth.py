"""Credential health per profile: silent refresh, honest states, one command.

gcloud refreshes access tokens on its own while the refresh token lives, so
probing is also the renewal. What cannot be automated is reauthentication
after the organization's session policy expires (Google Workspace defaults to
16 hours for new customers): that needs a human at a browser or a security
key, by design. The best a tool can do is notice early, say so clearly and
offer a single command that runs the login in the right place.

A network failure is never reported as an expired credential: it becomes
UNKNOWN, so a flaky connection cannot cry wolf.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .i18n import _
from .profiles import Profile, config_dir

OK = "ok"
REAUTH = "reauth"
MISSING = "missing"
UNKNOWN = "unknown"

CACHE_TTL_SECONDS = 10 * 60
PROBE_TIMEOUT = 20

# stderr fingerprints, from the gcloud and gh error surfaces
_REVOKED = ("invalid_grant", "expired or revoked", "invalid credentials")
_REAUTH_NEEDED = ("reauthentication", "invalid_rapt", "credentials are invalid")
_NO_ACCOUNT = (
    "do not currently have an active account",
    "does not have any valid credentials",
    "not logged in",
    "no active account",
)
_SSO = ("x-github-sso", "saml enforcement", "sso")


@dataclass
class AuthStatus:
    provider: str  # "gcloud" or "gh"
    state: str  # OK, REAUTH, MISSING or UNKNOWN
    detail: str = ""

    @property
    def needs_human(self) -> bool:
        return self.state in (REAUTH, MISSING)


def checks_enabled() -> bool:
    return os.environ.get("APARTA_AUTH_CHECK", "").lower() != "off"


def _classify(stderr: str) -> tuple[str, str]:
    lowered = stderr.lower()
    if any(marker in lowered for marker in _NO_ACCOUNT):
        return MISSING, _("no credential stored for this profile")
    if any(marker in lowered for marker in _SSO):
        return REAUTH, _("the organization requires SSO authorization again")
    if any(marker in lowered for marker in _REVOKED):
        return REAUTH, _("credential revoked or expired")
    if any(marker in lowered for marker in _REAUTH_NEEDED):
        return REAUTH, _("session expired by your organization's policy")
    return UNKNOWN, stderr.strip().splitlines()[-1] if stderr.strip() else ""


def check_gcloud(profile: Profile) -> AuthStatus | None:
    """Probe the profile's gcloud credential, refreshing it silently."""
    if not profile.gcloud_account:
        return None
    env = dict(os.environ, CLOUDSDK_CORE_DISABLE_PROMPTS="1")
    env.update(
        {k: v for k, v in profile.env().items() if k.startswith(("CLOUDSDK_", "GOOGLE_"))}
    )
    try:
        r = subprocess.run(
            ["gcloud", "auth", "print-access-token", "--account", profile.gcloud_account],
            env=env,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return AuthStatus("gcloud", UNKNOWN, _("{cmd} not found", cmd="gcloud"))
    except subprocess.TimeoutExpired:
        return AuthStatus("gcloud", UNKNOWN, _("check timed out"))
    if r.returncode == 0 and r.stdout.strip():
        return AuthStatus("gcloud", OK)
    state, detail = _classify(r.stderr)
    return AuthStatus("gcloud", state, detail)


def check_gh(profile: Profile) -> AuthStatus | None:
    """Probe the profile's GitHub token with a cheap authenticated call."""
    if not profile.gh_user:
        return None
    env = dict(os.environ, GH_CONFIG_DIR=str(profile.gh_config_dir))
    try:
        r = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            env=env,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return AuthStatus("gh", UNKNOWN, _("{cmd} not found", cmd="gh"))
    except subprocess.TimeoutExpired:
        return AuthStatus("gh", UNKNOWN, _("check timed out"))
    if r.returncode == 0:
        return AuthStatus("gh", OK)
    state, detail = _classify(r.stderr)
    return AuthStatus("gh", state, detail)


def check_profile(profile: Profile) -> list[AuthStatus]:
    return [s for s in (check_gcloud(profile), check_gh(profile)) if s is not None]


# ----------------------------------------------------------------- cache

def _cache_path() -> Path:
    return config_dir() / "auth-check.json"


def _read_cache() -> dict:
    try:
        return json.loads(_cache_path().read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _write_cache(data: dict) -> None:
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    except OSError:
        pass


def cached_check(profile: Profile, force: bool = False) -> list[AuthStatus]:
    """Probe at most once per TTL per profile; the cache keeps it cheap."""
    cache = _read_cache()
    entry = cache.get(profile.name, {})
    fresh = time.time() - entry.get("checked_at", 0) < CACHE_TTL_SECONDS
    if not force and fresh:
        return [AuthStatus(**s) for s in entry.get("statuses", [])]
    statuses = check_profile(profile)
    cache[profile.name] = {
        "checked_at": time.time(),
        "statuses": [s.__dict__ for s in statuses],
    }
    _write_cache(cache)
    return statuses


def problems(profiles: list[Profile]) -> list[tuple[str, AuthStatus]]:
    """(profile name, status) for everything that needs a human."""
    if not checks_enabled():
        return []
    found = []
    for profile in profiles:
        for status in cached_check(profile):
            if status.needs_human:
                found.append((profile.name, status))
    return found


# ------------------------------------------------------------------ login

def _flush_stdin() -> None:
    """Drop stray bytes pending on stdin before an interactive prompt.

    Terminals answer status queries with escape sequences on stdin; gh's
    prompt library aborts on them ("unexpected escape sequence from
    terminal") instead of ignoring them.
    """
    try:
        import sys
        import termios

        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except Exception:
        pass


def login_profile(profile: Profile, provider: str = "") -> bool:
    """Run the interactive login for a profile, in the profile's own scope.

    The whole point is that the user never has to remember an environment
    variable: the credential always lands in the right place, and the
    expected account is reasserted afterwards.
    """
    from rich.console import Console

    console = Console()
    ok = True

    if profile.gcloud_account and provider in ("", "gcloud"):
        env = dict(os.environ)
        env.update(
            {k: v for k, v in profile.env().items() if k.startswith(("CLOUDSDK_", "GOOGLE_"))}
        )
        # asked for the whole profile, not gcloud specifically: skip the
        # browser dance when the credential is still good
        status = check_gcloud(profile) if provider == "" else None
        if status is not None and status.state == OK:
            console.print(
                _("[green]gcloud:[/green] '{account}' is still valid; skipping the browser login", account=profile.gcloud_account)
            )
            _offer_adc(profile, env, console)
        else:
            console.print(
                _("Opening the Google login for '{account}' (profile {name})...", account=profile.gcloud_account, name=profile.name)
            )
            try:
                r = subprocess.run(["gcloud", "auth", "login", profile.gcloud_account], env=env)
            except FileNotFoundError:
                console.print(_("[red]{cmd} not found in PATH.[/red]", cmd="gcloud"))
                return False
            if r.returncode == 0:
                # a login can leave another account selected; put ours back
                subprocess.run(
                    ["gcloud", "config", "set", "account", profile.gcloud_account],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=PROBE_TIMEOUT,
                )
                console.print(_("[green]gcloud:[/green] '{account}' reauthenticated", account=profile.gcloud_account))
                _offer_adc(profile, env, console)
            else:
                ok = False

    if profile.gh_user and provider in ("", "gh"):
        env = dict(os.environ, GH_CONFIG_DIR=str(profile.gh_config_dir))
        status = check_gh(profile) if provider == "" else None
        if status is not None and status.state == OK:
            console.print(
                _(
                    "[green]gh:[/green] '{user}' is still valid; use `aparta login {name} --provider gh` to force a new login",
                    user=profile.gh_user,
                    name=profile.name,
                )
            )
        else:
            console.print(
                _("Opening the GitHub login for '{user}' (profile {name})...", user=profile.gh_user, name=profile.name)
            )
            try:
                _flush_stdin()
                r = subprocess.run(["gh", "auth", "login"], env=env)
            except FileNotFoundError:
                console.print(_("[red]{cmd} not found in PATH.[/red]", cmd="gh"))
                return False
            if r.returncode == 0:
                console.print(_("[green]gh:[/green] '{user}' reauthenticated", user=profile.gh_user))
            else:
                ok = False

    # the cached verdict is stale now
    cached_check(profile, force=True)
    return ok


def _offer_adc(profile: Profile, env: dict, console) -> None:
    """An isolated profile needs its own application default credentials.

    Telling the user the command is not enough: run in their own shell,
    without the profile's CLOUDSDK_CONFIG, it would create the GLOBAL ADC
    shared by every profile, the exact leak the isolation exists to prevent.
    So the login runs right here with the profile's environment, and the
    profile is re-applied afterwards so the SDKs that only honor
    GOOGLE_APPLICATION_CREDENTIALS see the new file.
    """
    import sys

    from .backends.gcloud import has_adc

    if not profile.gcloud_isolated or has_adc(profile.gcloud_config_dir):
        return
    console.print(
        _("[dim]This profile has no application credentials of its own yet; SDKs and Terraform need them.[/dim]")
    )
    if not sys.stdin.isatty():
        console.print(_("Create them with: aparta login {name}", name=profile.name))
        return
    from .wizard import _confirm

    if not _confirm(_("Create them now? (opens the browser)"), default=True):
        return
    _flush_stdin()
    r = subprocess.run(["gcloud", "auth", "application-default", "login"], env=env)
    if r.returncode != 0 or not has_adc(profile.gcloud_config_dir):
        console.print(
            _("[yellow]The ADC login did not complete; run `aparta login {name}` to try again.[/yellow]", name=profile.name)
        )
        return
    console.print(_("[green]gcloud:[/green] application credentials created for this profile"))
    # the env of every repo must now point GOOGLE_APPLICATION_CREDENTIALS
    # at the new file; a fresh apply reconciles that
    from .apply import apply_profile
    from .fsutil import SafeWriter
    from .profiles import load_profiles

    apply_profile(profile, SafeWriter(), siblings=load_profiles())
