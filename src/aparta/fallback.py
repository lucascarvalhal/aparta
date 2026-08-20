"""Safe fallback: what a command outside any aparta profile is allowed to be.

Outside a configured folder no profile env is injected, so gcloud falls back to
its globally active configuration and gh to its globally active account. When
that global default belongs to a client, every stray terminal, script or AI
agent silently acts as that client. The safe default is the opposite: outside a
profile the command should fail loudly ("no active account") instead of
borrowing someone's identity.

`--secure` makes the global gcloud default a neutral, empty configuration
(reversibly, remembering the previous one); `--restore` puts the old one back.
gh is reported but never changed, see note_gh() below.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import tomli_w
from rich.console import Console
from rich.table import Table

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from .fsutil import SafeWriter
from .i18n import _
from .profiles import config_dir

console = Console()

# neutral gcloud configuration: exists, has no account and no project, so any
# gcloud command that needs credentials fails instead of picking an identity
NEUTRAL_CONFIG = "aparta-none"

# env vars aparta injects per profile; cleared before probing so we always see
# the global default, not the profile of the folder the user happens to be in
_PROFILE_ENV = (
    "CLOUDSDK_ACTIVE_CONFIG_NAME",
    "CLOUDSDK_CONFIG",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GH_CONFIG_DIR",
)


def previous_path() -> Path:
    """Where the pre-secure global gcloud configuration is remembered."""
    return config_dir() / "fallback-previous"


def _global_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in _PROFILE_ENV:
        env.pop(name, None)
    return env


def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess | None:
    """Run a CLI with the profile env stripped; None when it is not installed."""
    if not shutil.which(args[0]):
        return None
    try:
        return subprocess.run(
            args, env=_global_env(), capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError):
        return None


@dataclass
class GcloudConfig:
    name: str
    active: bool
    account: str
    project: str


@dataclass
class State:
    """What a command run outside any profile would use right now."""

    gcloud_installed: bool = True
    gcloud_configs: list[GcloudConfig] | None = None
    gh_installed: bool = True
    gh_user: str = ""

    @property
    def gcloud_active(self) -> GcloudConfig | None:
        for cfg in self.gcloud_configs or []:
            if cfg.active:
                return cfg
        return None

    @property
    def secure(self) -> bool:
        active = self.gcloud_active
        return bool(active and active.name == NEUTRAL_CONFIG and not active.account)


def _read_gcloud() -> tuple[bool, list[GcloudConfig]]:
    result = _run(
        [
            "gcloud",
            "config",
            "configurations",
            "list",
            "--format=value(name,is_active,properties.core.account,properties.core.project)",
        ]
    )
    if result is None:
        return False, []
    configs: list[GcloudConfig] = []
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            fields = (line.split("\t") + ["", "", "", ""])[:4]
            if not fields[0]:
                continue
            configs.append(
                GcloudConfig(fields[0], fields[1].strip().lower() == "true", fields[2], fields[3])
            )
    return True, configs


def _read_gh() -> tuple[bool, str]:
    result = _run(["gh", "auth", "status", "--active", "--json", "hosts"])
    if result is None:
        return False, ""
    if result.returncode == 0 and result.stdout.strip():
        import json

        try:
            hosts = json.loads(result.stdout).get("hosts", {})
        except ValueError:
            return True, ""
        for accounts in hosts.values():
            for account in accounts:
                if account.get("active"):
                    return True, account.get("login") or _("(unnamed account)")
    return True, ""


def read_state() -> State:
    """Probe gcloud and gh as if we were outside every configured folder."""
    gcloud_installed, configs = _read_gcloud()
    gh_installed, gh_user = _read_gh()
    return State(gcloud_installed, configs, gh_installed, gh_user)


def read_previous() -> str:
    """The gcloud configuration that was active before `--secure`, if any."""
    path = previous_path()
    if not path.exists():
        return ""
    try:
        return str(tomllib.loads(path.read_text()).get("gcloud_config", ""))
    except (ValueError, OSError):
        return ""


# gh keeps the active token in the OS keyring under an unnamed "active" slot
# and falls back to it whenever hosts.yml has no active user, so clearing that
# key does not deactivate anything: measured with gh 2.97, `gh auth status`
# still reports a logged in account. The only lever that works is deleting the
# keyring entry, which no gh command does non destructively (`gh auth logout`
# throws the token away). Reversibility comes first, so gh is left alone.
def note_gh() -> str:
    """Why gh is reported but never touched (see the comment above)."""
    return _(
        "[yellow]gh:[/yellow] the global GitHub account is only reported, never changed. "
        "gh keeps the active token in the OS keyring and falls back to it even with no "
        "active user in hosts.yml, so the only way to deactivate it is `gh auth logout`, "
        "which deletes the token. Keep using a config dir per profile (aparta already "
        "sets GH_CONFIG_DIR in every configured folder)."
    )


def show_state(state: State | None = None) -> State:
    """Print what runs outside a profile today. Changes nothing."""
    state = state or read_state()
    table = Table(title=_("Outside any aparta profile"))
    table.add_column(_("Tool"), style="bold")
    table.add_column(_("Identity in use"))
    table.add_column(_("Where it comes from"))

    if not state.gcloud_installed:
        table.add_row("gcloud", _("not installed"), "—")
    else:
        active = state.gcloud_active
        if active is None:
            table.add_row("gcloud", _("no active configuration"), "—")
        else:
            identity = active.account or _("no account")
            if active.project:
                identity += _(" (project {project})", project=active.project)
            table.add_row("gcloud", identity, _("configuration '{name}'", name=active.name))

    if not state.gh_installed:
        table.add_row("gh", _("not installed"), "—")
    else:
        table.add_row("gh", state.gh_user or _("no active account"), "~/.config/gh")

    console.print(table)
    if state.secure:
        console.print(
            _("[green]Safe fallback is on:[/green] outside a profile gcloud has no account.")
        )
    elif state.gcloud_active and state.gcloud_active.account:
        console.print(
            _(
                "[yellow]Risk:[/yellow] any terminal, script or AI agent outside a configured "
                "folder acts as [bold]{account}[/bold] without asking. "
                "Run [bold]aparta fallback --secure[/bold] to make the global default neutral, "
                "so those commands fail loudly instead.",
                account=state.gcloud_active.account,
            )
        )
    console.print(note_gh())
    return state


def _ask(question: str) -> bool:
    """Localized yes/no; isolated so tests can replace it."""
    from .wizard import _confirm

    return _confirm(question)


def make_secure(writer: SafeWriter, assume_yes: bool = False) -> bool:
    """Point the global gcloud default at a neutral configuration, reversibly."""
    state = read_state()
    if not state.gcloud_installed:
        console.print(_("[yellow]gcloud is not installed, nothing to secure.[/yellow]"))
        console.print(note_gh())
        return False
    active = state.gcloud_active
    if state.secure:
        console.print(
            _("[green]Nothing to do:[/green] '{name}' is already the global default.", name=NEUTRAL_CONFIG)
        )
        return True

    current = active.name if active else ""
    exists = any(cfg.name == NEUTRAL_CONFIG for cfg in state.gcloud_configs or [])
    console.print(_("[bold]This is what will happen:[/bold]"))
    if not exists:
        console.print(
            _("  - create the gcloud configuration '{name}' (no account, no project)", name=NEUTRAL_CONFIG)
        )
    console.print(
        _("  - remember '{name}' in {path}", name=current or _("(none)"), path=previous_path())
    )
    console.print(
        _("  - make '{name}' the globally active configuration", name=NEUTRAL_CONFIG)
    )
    console.print(
        _("  - your other configurations, credentials and projects stay untouched")
    )
    console.print(note_gh())

    if writer.dry_run:
        if not exists:
            console.print(
                f"[yellow]--dry-run[/yellow] gcloud config configurations create {NEUTRAL_CONFIG} --no-activate"
            )
        console.print(
            f"[yellow]--dry-run[/yellow] gcloud config configurations activate {NEUTRAL_CONFIG}"
        )
        writer.write_text(previous_path(), tomli_w.dumps({"gcloud_config": current}))
        return True

    if not assume_yes and not _ask(_("Make the global fallback neutral?")):
        console.print(_("[yellow]Cancelled.[/yellow]"))
        return False

    # remembered before switching, so an interrupted run is still reversible
    writer.write_text(previous_path(), tomli_w.dumps({"gcloud_config": current}))

    if not exists:
        created = _run(["gcloud", "config", "configurations", "create", NEUTRAL_CONFIG, "--no-activate"])
        if created is None or created.returncode != 0:
            console.print(
                _("[red]gcloud configurations create failed:[/red] {error}", error=_stderr(created))
            )
            return False
    switched = _run(["gcloud", "config", "configurations", "activate", NEUTRAL_CONFIG])
    if switched is None or switched.returncode != 0:
        console.print(
            _("[red]gcloud configurations activate failed:[/red] {error}", error=_stderr(switched))
        )
        return False
    console.print(
        _(
            "[green]Done:[/green] outside a profile gcloud now has no account. "
            "Undo with [bold]aparta fallback --restore[/bold]."
        )
    )
    return True


def restore(writer: SafeWriter) -> bool:
    """Reactivate the gcloud configuration that was global before `--secure`."""
    previous = read_previous()
    if not previous:
        console.print(
            _("[yellow]Nothing to restore:[/yellow] no previous configuration saved in {path}.", path=previous_path())
        )
        return False
    if writer.dry_run:
        console.print(
            f"[yellow]--dry-run[/yellow] gcloud config configurations activate {previous}"
        )
        return True
    result = _run(["gcloud", "config", "configurations", "activate", previous])
    if result is None:
        console.print(_("[yellow]gcloud is not installed, nothing to restore.[/yellow]"))
        return False
    if result.returncode != 0:
        console.print(
            _("[red]gcloud configurations activate failed:[/red] {error}", error=_stderr(result))
        )
        return False
    writer.remove_file(previous_path())
    console.print(_("[green]Restored:[/green] '{name}' is the global default again.", name=previous))
    return True


def _stderr(result: subprocess.CompletedProcess | None) -> str:
    return result.stderr.strip() if result is not None else _("gcloud not found")
