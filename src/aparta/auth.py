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
from .runner import clean_environment

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
    expires_at: float | None = None
    renewable: bool = False

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
    overlay = {
        k: v for k, v in profile.env().items() if k.startswith(("CLOUDSDK_", "GOOGLE_"))
    }
    overlay["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    env = clean_environment(os.environ, overlay)
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
        return AuthStatus("gcloud", OK, renewable=True)
    state, detail = _classify(r.stderr)
    return AuthStatus("gcloud", state, detail)


TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


def _refresh_adc_like_a_library(adc_path: Path) -> AuthStatus | None:
    """Refresh the ADC the way google-auth does, with no help from gcloud.

    gcloud can mint tokens from an ADC the raw libraries cannot: it knows
    the organization's reauth policy and holds a cached reauth proof
    (RAPT), so `print-access-token` says "valid" while Terraform and
    Dataform get invalid_rapt from a plain refresh. Only a plain refresh
    against the token endpoint tells the truth about what a library sees.
    Returns None when this probe does not apply (not a user credential).
    """
    import urllib.error
    import urllib.parse
    import urllib.request

    try:
        data = json.loads(adc_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("type") != "authorized_user":
        return None  # service accounts do not sit behind reauth policies
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": data.get("client_id", ""),
            "client_secret": data.get("client_secret", ""),
            "refresh_token": data.get("refresh_token", ""),
        }
    ).encode()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(TOKEN_ENDPOINT, data=body), timeout=PROBE_TIMEOUT
        ):
            return AuthStatus("ADC", OK, renewable=True)
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
        except Exception:
            err = {}
        text = " ".join(str(v) for v in err.values())
        # the RAPT verdict arrives as invalid_grant + invalid_rapt; the
        # policy message is the honest one, so check it before _classify
        # matches the generic invalid_grant
        if "invalid_rapt" in text.lower():
            return AuthStatus("ADC", REAUTH, _("session expired by your organization's policy"))
        state, detail = _classify(text)
        if state == UNKNOWN:
            return AuthStatus("ADC", UNKNOWN, detail or str(e))
        return AuthStatus("ADC", state, detail)
    except Exception:
        # a network failure must never cry wolf
        return AuthStatus("ADC", UNKNOWN, _("check timed out"))


def check_adc(profile: Profile) -> AuthStatus | None:
    """Probe the profile's application default credentials.

    The CLI credential and the ADC are two independent credentials that
    expire on their own schedules: `gcloud` commands can work all day while
    Terraform trips on an ADC the same reauth policy already expired. A
    profile without an ADC is a choice, not an error, so only an existing
    file is probed, and probed like a library, not like gcloud.
    """
    if not profile.gcloud_isolated:
        return None
    from .backends.gcloud import has_adc

    if not has_adc(profile.gcloud_config_dir):
        return None
    adc_path = profile.gcloud_config_dir / "application_default_credentials.json"
    status = _refresh_adc_like_a_library(adc_path)
    if status is not None:
        return status
    # not a user credential (or unreadable): fall back to gcloud's own probe
    overlay = {
        k: v for k, v in profile.env().items() if k.startswith(("CLOUDSDK_", "GOOGLE_"))
    }
    overlay["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    env = clean_environment(os.environ, overlay)
    try:
        r = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            env=env,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return AuthStatus("ADC", UNKNOWN, _("{cmd} not found", cmd="gcloud"))
    except subprocess.TimeoutExpired:
        return AuthStatus("ADC", UNKNOWN, _("check timed out"))
    if r.returncode == 0 and r.stdout.strip():
        return AuthStatus("ADC", OK, renewable=True)
    state, detail = _classify(r.stderr)
    return AuthStatus("ADC", state, detail)


# aws stderr fingerprints, from the CLI and botocore error surfaces
_AWS_EXPIRED = ("token has expired", "expiredtoken", "sso session", "requires re-authentication")
_AWS_MISSING = ("unable to locate credentials", "could not be found")


def _classify_aws(stderr: str) -> tuple[str, str]:
    lowered = stderr.lower()
    if any(marker in lowered for marker in _AWS_MISSING):
        return MISSING, _("no credential stored for this profile")
    if any(marker in lowered for marker in _AWS_EXPIRED):
        return REAUTH, _("session expired; log in again")
    return UNKNOWN, stderr.strip().splitlines()[-1] if stderr.strip() else ""


def check_aws(profile: Profile) -> AuthStatus | None:
    """Probe the AWS profile the way every SDK does: an STS call.

    Static keys do not expire, but SSO sessions and role session tokens
    do; only asking STS who we are tells the truth for all of them.
    """
    if not profile.aws_profile:
        return None
    env = clean_environment(os.environ, {"AWS_PROFILE": profile.aws_profile})
    try:
        r = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--output", "json"],
            env=env,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return AuthStatus("aws", UNKNOWN, _("{cmd} not found", cmd="aws"))
    except subprocess.TimeoutExpired:
        return AuthStatus("aws", UNKNOWN, _("check timed out"))
    if r.returncode == 0:
        from .backends.aws import aws_sso_expiry

        return AuthStatus("aws", OK, expires_at=aws_sso_expiry(profile.aws_profile))
    state, detail = _classify_aws(r.stderr)
    return AuthStatus("aws", state, detail)


def check_gh(profile: Profile) -> AuthStatus | None:
    """Probe the profile's GitHub token with a cheap authenticated call."""
    if not profile.gh_user:
        return None
    env = clean_environment(os.environ, {"GH_CONFIG_DIR": str(profile.gh_config_dir)})
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
    return [
        s
        for s in (check_gcloud(profile), check_adc(profile), check_gh(profile), check_aws(profile))
        if s is not None
    ]


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


def read_cached_status(profile: Profile) -> list[AuthStatus] | None:
    """Read cached health without probing, for latency-sensitive shell prompts."""
    entry = _read_cache().get(profile.name)
    if not isinstance(entry, dict) or "statuses" not in entry:
        return None
    try:
        return [AuthStatus(**status) for status in entry.get("statuses", [])]
    except (TypeError, ValueError):
        return None


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


def login_profile(
    profile: Profile,
    provider: str = "",
    enabled_providers: list[str] | None = None,
) -> bool:
    """Run the interactive login for a profile, in the profile's own scope.

    The whole point is that the user never has to remember an environment
    variable: the credential always lands in the right place, and the
    expected account is reasserted afterwards.
    """
    from rich.console import Console

    console = Console()
    ok = True

    from .providers import auth_provider_name, canonical_providers

    forced = auth_provider_name(provider) if provider else ""
    enabled = (
        set(canonical_providers(enabled_providers))
        if enabled_providers is not None
        else {"gcloud", "adc", "github", "aws"}
    )
    wants_gcloud = forced == "gcloud" if forced else "gcloud" in enabled
    wants_adc = forced == "adc" if forced else "adc" in enabled
    wants_github = forced == "gh" if forced else "github" in enabled
    wants_aws = forced == "aws" if forced else "aws" in enabled

    if profile.gcloud_account and wants_gcloud:
        env = _gcloud_env(profile)
        # asked for the whole profile, not gcloud specifically: skip the
        # browser dance when the credential is still good
        status = check_gcloud(profile) if not forced else None
        if status is not None and status.state == OK:
            console.print(
                _("[green]gcloud:[/green] '{account}' is still valid; skipping the browser login", account=profile.gcloud_account)
            )
            if wants_adc:
                ok &= _ensure_adc(profile, env, console)
        elif status is not None and not status.needs_human:
            console.print(
                _(
                    "{provider} in '{name}': {detail}",
                    provider="gcloud",
                    name=profile.name,
                    detail=status.detail,
                )
            )
            ok = False
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
                if wants_adc:
                    ok &= _ensure_adc(profile, env, console)
            else:
                ok = False

    if profile.gcloud_account and wants_adc and not wants_gcloud:
        ok &= _ensure_adc(profile, _gcloud_env(profile), console, announce_ok=True)

    if profile.gh_user and wants_github:
        env = clean_environment(os.environ, {"GH_CONFIG_DIR": str(profile.gh_config_dir)})
        status = check_gh(profile) if not forced else None
        if status is not None and status.state == OK:
            console.print(
                _(
                    "[green]gh:[/green] '{user}' is still valid; use `aparta login {name} --provider gh` to force a new login",
                    user=profile.gh_user,
                    name=profile.name,
                )
            )
        elif status is not None and not status.needs_human:
            console.print(
                _(
                    "{provider} in '{name}': {detail}",
                    provider="gh",
                    name=profile.name,
                    detail=status.detail,
                )
            )
            ok = False
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

    if profile.aws_profile and wants_aws:
        status = check_aws(profile) if not forced else None
        if status is not None and not status.needs_human:
            if status.state == OK:
                console.print(
                    _("[green]aws:[/green] profile '{name}' is still valid", name=profile.aws_profile)
                )
            else:
                console.print(_("{provider} in '{name}': {detail}", provider="aws", name=profile.aws_profile, detail=status.detail))
                ok = False
        else:
            ok &= _aws_login(profile, console)

    # the cached verdict is stale now
    cached_check(profile, force=True)
    return ok


def _aws_login(profile: Profile, console) -> bool:
    """Renew what a browser can renew: the SSO session.

    Static keys never expire on their own; when they are the problem, the
    only honest move is pointing at `aws configure`.
    """
    from .backends.aws import is_sso_profile

    env = clean_environment(os.environ, {"AWS_PROFILE": profile.aws_profile})
    if not is_sso_profile(profile.aws_profile):
        console.print(
            _(
                "[yellow]aws:[/yellow] profile '{name}' uses static keys; refresh them with `aws configure --profile {name}`",
                name=profile.aws_profile,
            )
        )
        return True
    console.print(_("Opening the AWS SSO login for profile '{name}'...", name=profile.aws_profile))
    _flush_stdin()
    try:
        r = subprocess.run(["aws", "sso", "login", "--profile", profile.aws_profile], env=env)
    except FileNotFoundError:
        console.print(_("[red]{cmd} not found in PATH.[/red]", cmd="aws"))
        return False
    if r.returncode != 0:
        return False
    console.print(_("[green]aws:[/green] profile '{name}' reauthenticated", name=profile.aws_profile))
    return True


def _gcloud_env(profile: Profile) -> dict:
    overlay = {
        k: v for k, v in profile.env().items() if k.startswith(("CLOUDSDK_", "GOOGLE_"))
    }
    return clean_environment(os.environ, overlay)


def _ensure_adc(profile: Profile, env: dict, console, announce_ok: bool = False) -> bool:
    """Create or renew the profile's application default credentials.

    A fresh CLI credential says nothing about the ADC: they are two
    independent credentials the same reauth policy expires on its own
    schedule, and Terraform only ever uses the ADC. Saying "still valid"
    while the ADC sits expired would be lying by omission.
    """
    from .backends.gcloud import has_adc

    if not profile.gcloud_isolated:
        return True
    if not has_adc(profile.gcloud_config_dir):
        return _offer_adc(profile, env, console)
    status = check_adc(profile)
    if status is None or status.state == OK:
        if announce_ok:
            console.print(_("[green]ADC:[/green] the application credentials are still valid"))
        return True
    if status.state == UNKNOWN:
        console.print(
            _(
                "{provider} in '{name}': {detail}",
                provider="ADC",
                name=profile.name,
                detail=status.detail,
            )
        )
        return False
    console.print(
        _("[yellow]ADC:[/yellow] {detail}; opening the browser to renew the application credentials...", detail=status.detail)
    )
    return _run_adc_login(profile, env, console, created=False)


def _offer_adc(profile: Profile, env: dict, console) -> bool:
    """A profile with no ADC yet gets the offer to create one.

    Telling the user the command is not enough: run in their own shell,
    without the profile's CLOUDSDK_CONFIG, it would create the GLOBAL ADC
    shared by every profile, the exact leak the isolation exists to prevent.
    So the login runs right here with the profile's environment. Declining
    is fine: no ADC is safer than the wrong ADC.
    """
    import sys

    console.print(
        _("[dim]This profile has no application credentials of its own yet; SDKs and Terraform need them.[/dim]")
    )
    if not sys.stdin.isatty():
        console.print(_("Create them with: aparta login {name}", name=profile.name))
        return True
    from .wizard import _confirm

    if not _confirm(_("Create them now? (opens the browser)"), default=True):
        return True
    return _run_adc_login(profile, env, console, created=True)


def _run_adc_login(profile: Profile, env: dict, console, created: bool) -> bool:
    from .backends.gcloud import has_adc

    if profile.gcloud_account:
        # the ADC flow cannot preselect an account; the human picking the
        # wrong one would put another identity in this profile's file
        console.print(
            _("[dim]In the browser, pick the account {account}.[/dim]", account=profile.gcloud_account)
        )
    _flush_stdin()
    try:
        r = subprocess.run(["gcloud", "auth", "application-default", "login"], env=env)
    except FileNotFoundError:
        console.print(_("[red]{cmd} not found in PATH.[/red]", cmd="gcloud"))
        return False
    if r.returncode != 0 or not has_adc(profile.gcloud_config_dir):
        console.print(
            _("[yellow]The ADC login did not complete; run `aparta login {name}` to try again.[/yellow]", name=profile.name)
        )
        return False
    if not created:
        console.print(_("[green]gcloud:[/green] application credentials renewed"))
        return True
    console.print(_("[green]gcloud:[/green] application credentials created for this profile"))
    # the env of every repo must now point GOOGLE_APPLICATION_CREDENTIALS
    # at the new file; a fresh apply reconciles that
    from .apply import apply_profile
    from .fsutil import SafeWriter
    from .profiles import load_profiles

    apply_profile(profile, SafeWriter(), siblings=load_profiles())
    return True
