"""Credential health per profile: silent refresh, honest states, one login loop."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from .backends.aws import aws_sso_expiry, is_sso_profile
from .backends.gcloud import has_adc
from .i18n import _
from . import prompts
from .config import read_json, write_json
from .profiles import Profile, clean_environment
from .providers import canonical_provider, canonical_providers, provider_label

OK = "ok"
REAUTH = "reauth"
MISSING = "missing"
UNKNOWN = "unknown"

CACHE_TTL_SECONDS = 10 * 60
PROBE_TIMEOUT = 20
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

Rule = tuple[tuple[str, ...], str, Callable[[], str]]

_RULES: tuple[Rule, ...] = (
    (
        (
            "do not currently have an active account",
            "does not have any valid credentials",
            "not logged in",
            "no active account",
        ),
        MISSING,
        lambda: _("no credential stored for this profile"),
    ),
    (
        ("reauthentication", "invalid_rapt", "credentials are invalid"),
        REAUTH,
        lambda: _("session expired by your organization's policy"),
    ),
    (
        ("x-github-sso", "saml enforcement", "sso authorization", "sso session", "single sign-on"),
        REAUTH,
        lambda: _("the organization requires SSO authorization again"),
    ),
    (
        ("invalid_grant", "expired or revoked", "invalid credentials"),
        REAUTH,
        lambda: _("credential revoked or expired"),
    ),
)
_AWS_RULES: tuple[Rule, ...] = (
    (
        ("unable to locate credentials", "could not be found"),
        MISSING,
        lambda: _("no credential stored for this profile"),
    ),
    (
        ("token has expired", "expiredtoken", "sso session", "requires re-authentication"),
        REAUTH,
        lambda: _("session expired; log in again"),
    ),
)


@dataclass
class AuthStatus:
    provider: str
    state: str
    detail: str = ""
    expires_at: float | None = None
    renewable: bool = False

    @property
    def needs_human(self) -> bool:
        return self.state in (REAUTH, MISSING)

    @property
    def label(self) -> str:
        return provider_label(self.provider)


def checks_enabled() -> bool:
    return os.environ.get("APARTA_AUTH_CHECK", "").lower() != "off"


def _classify(stderr: str, rules: tuple[Rule, ...] = _RULES) -> tuple[str, str]:
    lowered = stderr.lower()
    for markers, state, detail in rules:
        if any(marker in lowered for marker in markers):
            return state, detail()
    return UNKNOWN, stderr.strip().splitlines()[-1] if stderr.strip() else ""


def _probe_env(profile: Profile) -> dict[str, str]:
    return clean_environment(
        os.environ, {**profile.gcloud_env(), "CLOUDSDK_CORE_DISABLE_PROMPTS": "1"}
    )


def _probe(
    label: str,
    args: list[str],
    env: dict[str, str],
    rules: tuple[Rule, ...] = _RULES,
    stdout_required: bool = True,
) -> AuthStatus:
    """Run a read-only credential probe and turn its outcome into a status."""
    try:
        r = subprocess.run(
            args,
            env=env,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return AuthStatus(label, UNKNOWN, _("{cmd} not found", cmd=args[0]))
    except subprocess.TimeoutExpired:
        return AuthStatus(label, UNKNOWN, _("check timed out"))
    if r.returncode == 0 and (r.stdout.strip() or not stdout_required):
        return AuthStatus(label, OK, detail=r.stdout.strip())
    state, detail = _classify(r.stderr, rules)
    return AuthStatus(label, state, detail)


def check_gcloud(profile: Profile) -> AuthStatus | None:
    """Probe the profile's gcloud credential, refreshing it silently."""
    if not profile.gcloud_account:
        return None
    status = _probe(
        "gcloud",
        ["gcloud", "auth", "print-access-token", "--account", profile.gcloud_account],
        _probe_env(profile),
    )
    if status.state == OK:
        return AuthStatus("gcloud", OK, renewable=True)
    return status


def _refresh_adc_like_a_library(adc_path: Path) -> AuthStatus | None:
    """Refresh the ADC the way google-auth does, with no help from gcloud."""
    try:
        data = json.loads(adc_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("type") != "authorized_user":
        return None
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
            return AuthStatus("adc", OK, renewable=True)
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
        except Exception:
            err = {}
        state, detail = _classify(" ".join(str(v) for v in err.values()))
        return AuthStatus("adc", state, detail or (str(e) if state == UNKNOWN else ""))
    except Exception:
        return AuthStatus("adc", UNKNOWN, _("check timed out"))


def check_adc(profile: Profile) -> AuthStatus | None:
    """Probe the profile's application default credentials, when it has any."""
    if not profile.gcloud_isolated or not has_adc(profile.gcloud_config_dir):
        return None
    status = _refresh_adc_like_a_library(profile.adc_path)
    if status is not None:
        return status
    status = _probe(
        "adc", ["gcloud", "auth", "application-default", "print-access-token"], _probe_env(profile)
    )
    if status.state == OK:
        return AuthStatus("adc", OK, renewable=True)
    return status


def check_aws(profile: Profile) -> AuthStatus | None:
    """Probe the AWS profile the way every SDK does: an STS call."""
    if not profile.aws_profile:
        return None
    env = clean_environment(os.environ, {"AWS_PROFILE": profile.aws_profile})
    status = _probe(
        "aws",
        ["aws", "sts", "get-caller-identity", "--output", "json"],
        env,
        rules=_AWS_RULES,
        stdout_required=False,
    )
    if status.state == OK:
        return AuthStatus("aws", OK, expires_at=aws_sso_expiry(profile.aws_profile))
    return status


def check_gh(profile: Profile) -> AuthStatus | None:
    """Probe the profile's GitHub token and confirm it belongs to the expected user."""
    if not profile.gh_user:
        return None
    env = clean_environment(os.environ, {"GH_CONFIG_DIR": str(profile.gh_config_dir)})
    status = _probe("github", ["gh", "api", "user", "--jq", ".login"], env, stdout_required=False)
    if status.state != OK:
        return status
    login = status.detail
    if login and login.lower() != profile.gh_user.lower():
        return AuthStatus(
            "gh", REAUTH, _("logged in as {user}, expected {expected}", user=login, expected=profile.gh_user)
        )
    return AuthStatus("github", OK)


def check_profile(profile: Profile) -> list[AuthStatus]:
    return [
        s
        for s in (check_gcloud(profile), check_adc(profile), check_gh(profile), check_aws(profile))
        if s is not None
    ]


CACHE_FILE = "auth-check.json"


def _read_cache() -> dict:
    return read_json(CACHE_FILE)


def _write_cache(data: dict) -> None:
    write_json(CACHE_FILE, data)


_LEGACY_PROVIDER_NAMES = {"ADC": "adc", "gh": "github"}


def _statuses_from(entry: dict) -> list[AuthStatus] | None:
    try:
        statuses = [AuthStatus(**status) for status in entry.get("statuses", [])]
    except (TypeError, ValueError):
        return None
    for status in statuses:
        status.provider = _LEGACY_PROVIDER_NAMES.get(status.provider, status.provider)
    return statuses


def read_cached_status(profile: Profile) -> list[AuthStatus] | None:
    """Read cached health without probing, for latency-sensitive shell prompts."""
    entry = _read_cache().get(profile.name)
    if not isinstance(entry, dict) or "statuses" not in entry:
        return None
    return _statuses_from(entry)


def cached_check(profile: Profile, force: bool = False) -> list[AuthStatus]:
    """Probe at most once per TTL per profile; the cache keeps it cheap, APARTA_AUTH_CHECK=off turns it off."""
    if not checks_enabled():
        return []
    cache = _read_cache()
    entry = cache.get(profile.name, {})
    fresh = time.time() - entry.get("checked_at", 0) < CACHE_TTL_SECONDS
    cached = _statuses_from(entry) if not force and fresh else None
    if cached is not None:
        return cached
    statuses = check_profile(profile)
    cache[profile.name] = {
        "checked_at": time.time(),
        "statuses": [s.__dict__ for s in statuses],
    }
    _write_cache(cache)
    return statuses


def missing_adc(profile: Profile, providers: set[str]) -> AuthStatus | None:
    """A workspace that enables the ADC is blocked until the isolated file exists."""
    if "adc" in providers and not profile.adc_path.is_file():
        return AuthStatus("adc", MISSING, _("no credential stored for this profile"))
    return None


def workspace_statuses(
    profile: Profile, providers: set[str], source: list[AuthStatus] | None
) -> list[AuthStatus]:
    """The statuses that matter to a workspace, with a selected but absent ADC counted as missing."""
    statuses = [status for status in (source or []) if status.provider in providers]
    adc = missing_adc(profile, providers)
    if adc is not None and not any(status.provider == "adc" for status in statuses):
        statuses.append(adc)
    return statuses


def problems(profiles: list[Profile]) -> list[tuple[str, AuthStatus]]:
    """(profile name, status) for everything that needs a human."""
    return [
        (profile.name, status)
        for profile in profiles
        for status in cached_check(profile)
        if status.needs_human
    ]


def _interactive(args: list[str], env: dict[str, str], console: Console) -> bool:
    """Run a login command that owns the terminal; False when it fails or is missing."""
    prompts.flush_stdin()
    try:
        return subprocess.run(args, env=env).returncode == 0
    except FileNotFoundError:
        console.print(_("[red]{cmd} not found in PATH.[/red]", cmd=args[0]))
        return False


def _gcloud_env(profile: Profile) -> dict[str, str]:
    return clean_environment(os.environ, profile.gcloud_env())


def _gcloud_login(profile: Profile, console: Console, forced: bool) -> bool:
    env = _gcloud_env(profile)
    console.print(
        _("Opening the Google login for '{account}' (profile {name})...", account=profile.gcloud_account, name=profile.name)
    )
    if not _interactive(["gcloud", "auth", "login", profile.gcloud_account], env, console):
        return False
    subprocess.run(
        ["gcloud", "config", "set", "account", profile.gcloud_account],
        env=env,
        capture_output=True,
        text=True,
        timeout=PROBE_TIMEOUT,
    )
    console.print(_("[green]gcloud:[/green] '{account}' reauthenticated", account=profile.gcloud_account))
    return True


def _gh_login(profile: Profile, console: Console, forced: bool) -> bool:
    env = clean_environment(os.environ, {"GH_CONFIG_DIR": str(profile.gh_config_dir)})
    console.print(_("Opening the GitHub login for '{user}' (profile {name})...", user=profile.gh_user, name=profile.name))
    if not _interactive(["gh", "auth", "login"], env, console):
        return False
    console.print(_("[green]gh:[/green] '{user}' reauthenticated", user=profile.gh_user))
    return True


def _aws_login(profile: Profile, console: Console, forced: bool = False) -> bool:
    """Renew what a browser can renew: the SSO session."""
    if not is_sso_profile(profile.aws_profile):
        console.print(
            _(
                "[yellow]aws:[/yellow] profile '{name}' uses static keys; refresh them with `aws configure --profile {name}`",
                name=profile.aws_profile,
            )
        )
        return True
    env = clean_environment(os.environ, {"AWS_PROFILE": profile.aws_profile})
    console.print(_("Opening the AWS SSO login for profile '{name}'...", name=profile.aws_profile))
    if not _interactive(["aws", "sso", "login", "--profile", profile.aws_profile], env, console):
        return False
    console.print(_("[green]aws:[/green] profile '{name}' reauthenticated", name=profile.aws_profile))
    return True


def _adc_step(profile: Profile, console: Console, forced: bool) -> bool:
    return _ensure_adc(profile, _gcloud_env(profile), console, announce_ok=True, force=forced)


@dataclass(frozen=True)
class Credential:
    """One credential a profile may hold, with its probe and its interactive renewal."""

    provider: str
    applies: Callable[[Profile], bool]
    check: Callable[[Profile], AuthStatus | None]
    login: Callable[[Profile, Console, bool], bool]
    still_valid: Callable[[Profile], str]


CREDENTIALS: tuple[Credential, ...] = (
    Credential(
        "gcloud",
        lambda p: bool(p.gcloud_account),
        lambda p: check_gcloud(p),
        lambda p, console, forced: _gcloud_login(p, console, forced),
        lambda p: _("[green]gcloud:[/green] '{account}' is still valid; skipping the browser login", account=p.gcloud_account),
    ),
    Credential(
        "adc",
        lambda p: bool(p.gcloud_account and p.gcloud_isolated),
        lambda p: None,
        lambda p, console, forced: _adc_step(p, console, forced),
        lambda p: "",
    ),
    Credential(
        "github",
        lambda p: bool(p.gh_user),
        lambda p: check_gh(p),
        lambda p, console, forced: _gh_login(p, console, forced),
        lambda p: _(
            "[green]gh:[/green] '{user}' is still valid; use `aparta login {name} --provider gh` to force a new login",
            user=p.gh_user,
            name=p.name,
        ),
    ),
    Credential(
        "aws",
        lambda p: bool(p.aws_profile),
        lambda p: check_aws(p),
        lambda p, console, forced: _aws_login(p, console, forced),
        lambda p: _("[green]aws:[/green] profile '{name}' is still valid", name=p.aws_profile),
    ),
)


def login_profile(
    profile: Profile,
    provider: str = "",
    enabled_providers: list[str] | None = None,
) -> bool:
    """Renew every wanted credential of a profile, in the profile's own scope."""
    console = Console()
    forced = canonical_provider(provider) if provider else ""
    if forced:
        wanted = {forced}
    elif enabled_providers is not None:
        wanted = set(canonical_providers(enabled_providers))
    else:
        wanted = {credential.provider for credential in CREDENTIALS}
    ok = True
    for credential in CREDENTIALS:
        if credential.provider not in wanted or not credential.applies(profile):
            continue
        status = None if forced else credential.check(profile)
        if status is not None and status.state == OK:
            console.print(credential.still_valid(profile))
            continue
        if status is not None and not status.needs_human:
            console.print(
                _("{provider} in '{name}': {detail}", provider=provider_label(credential.provider), name=profile.name, detail=status.detail)
            )
            ok = False
            continue
        ok &= credential.login(profile, console, bool(forced))
    cached_check(profile, force=True)
    return ok


def _ensure_adc(
    profile: Profile, env: dict, console: Console, announce_ok: bool = False, force: bool = False
) -> bool:
    """Create or renew the profile's application default credentials."""
    if not profile.gcloud_isolated:
        return True
    exists = has_adc(profile.gcloud_config_dir)
    if force:
        return _run_adc_login(profile, env, console, created=not exists)
    if not exists:
        return _offer_adc(profile, env, console)
    status = check_adc(profile)
    if status is None or status.state == OK:
        if announce_ok:
            console.print(_("[green]ADC:[/green] the application credentials are still valid"))
        return True
    if status.state == UNKNOWN:
        console.print(_("{provider} in '{name}': {detail}", provider=status.label, name=profile.name, detail=status.detail))
        return False
    console.print(_("[yellow]ADC:[/yellow] {detail}; renewing the application credentials...", detail=status.detail))
    return _run_adc_login(profile, env, console, created=False)


def _offer_adc(profile: Profile, env: dict, console: Console) -> bool:
    """A profile with no ADC yet gets the offer to create one, inside its own scope."""
    console.print(
        _("[dim]This profile has no application credentials of its own yet; SDKs and Terraform need them.[/dim]")
    )
    if not sys.stdin.isatty():
        console.print(_("Create them with: aparta login {name}", name=profile.name))
        return True
    if not prompts.confirm(_("Create them now? (opens the browser)"), default=True):
        return True
    return _run_adc_login(profile, env, console, created=True)


def _adc_login_env(env: dict) -> dict:
    """The login env without GOOGLE_APPLICATION_CREDENTIALS, or gcloud stops to ask about it."""
    return {k: v for k, v in env.items() if k != "GOOGLE_APPLICATION_CREDENTIALS"}


def _adc_from_cli_credential(profile: Profile, env: dict) -> bool:
    """Derive the ADC from the cached gcloud credential, with no browser."""
    if not profile.gcloud_account:
        return False
    try:
        r = subprocess.run(
            [
                "gcloud",
                "auth",
                "login",
                profile.gcloud_account,
                "--update-adc",
                "--brief",
                "--no-launch-browser",
                "--quiet",
            ],
            env=_adc_login_env(env),
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT * 4,
            stdin=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    if r.returncode != 0:
        return False
    status = check_adc(profile)
    return status is not None and status.state == OK


def _run_adc_login(profile: Profile, env: dict, console: Console, created: bool) -> bool:
    if _adc_from_cli_credential(profile, env):
        console.print(_("[green]ADC:[/green] application credentials derived from the gcloud login, no browser needed"))
        succeeded = True
    else:
        if profile.gcloud_account:
            console.print(_("[dim]In the browser, pick the account {account}.[/dim]", account=profile.gcloud_account))
        succeeded = _interactive(
            ["gcloud", "auth", "application-default", "login", "--quiet"], _adc_login_env(env), console
        )
    if not succeeded or not has_adc(profile.gcloud_config_dir):
        console.print(
            _("[yellow]The ADC login did not complete; run `aparta login {name}` to try again.[/yellow]", name=profile.name)
        )
        return False
    if not created:
        console.print(_("[green]gcloud:[/green] application credentials renewed"))
        return True
    console.print(_("[green]gcloud:[/green] application credentials created for this profile"))
    from .apply import apply_profile
    from .fsutil import SafeWriter
    from .profiles import load_profiles

    apply_profile(profile, SafeWriter(), siblings=load_profiles())
    return True
