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
        else:
            ok = False

    if profile.gh_user and provider in ("", "gh"):
        env = dict(os.environ, GH_CONFIG_DIR=str(profile.gh_config_dir))
        console.print(
            _("Opening the GitHub login for '{user}' (profile {name})...", user=profile.gh_user, name=profile.name)
        )
        try:
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
