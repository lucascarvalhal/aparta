"""Safe fallback: what a command outside any aparta profile is allowed to be."""

from __future__ import annotations

from collections.abc import Callable

from . import _toml

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table


from .fsutil import SafeWriter
from .i18n import _
from . import prompts
from .config import config_dir

console = Console()

NEUTRAL_CONFIG = "aparta-none"

_PROFILE_ENV = (
    "CLOUDSDK_ACTIVE_CONFIG_NAME",
    "CLOUDSDK_CONFIG",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GH_CONFIG_DIR",
)


def previous_path() -> Path:
    """Where the pre-secure global gcloud configuration is remembered."""
    return config_dir() / "fallback-previous"


ADC_PARKED_SUFFIX = ".aparta-fallback"


def global_adc_path() -> Path:
    """The fixed path every Google library falls back to for the ADC."""
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def parked_adc_path() -> Path:
    adc = global_adc_path()
    return adc.with_name(adc.name + ADC_PARKED_SUFFIX)


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
    adc_present: bool = False
    adc_state: str = ""
    adc_parked: bool = False

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


def _read_adc() -> tuple[bool, str, bool]:
    """Existence and library-style health of the global ADC."""
    from .auth import _refresh_adc_like_a_library

    path = global_adc_path()
    parked = parked_adc_path().exists()
    if not path.exists():
        return False, "", parked
    status = _refresh_adc_like_a_library(path)
    return True, status.state if status else "", parked


def read_state() -> State:
    """Probe gcloud and gh as if we were outside every configured folder."""
    gcloud_installed, configs = _read_gcloud()
    gh_installed, gh_user = _read_gh()
    adc_present, adc_state, adc_parked = _read_adc()
    return State(gcloud_installed, configs, gh_installed, gh_user, adc_present, adc_state, adc_parked)


def read_previous() -> str:
    """The gcloud configuration that was active before `--secure`, if any."""
    path = previous_path()
    if not path.exists():
        return ""
    try:
        return str(_toml.loads(path.read_text()).get("gcloud_config", ""))
    except (ValueError, OSError):
        return ""


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

    from .auth import OK as AUTH_OK, REAUTH as AUTH_REAUTH

    if state.adc_present:
        if state.adc_state == AUTH_OK:
            adc_identity = _("valid credential; any library without a profile env uses it")
        elif state.adc_state == AUTH_REAUTH:
            adc_identity = _("expired credential")
        else:
            adc_identity = _("credential of unknown health")
        table.add_row("ADC", adc_identity, str(global_adc_path()))
    elif state.adc_parked:
        table.add_row("ADC", _("parked by --secure; libraries fail loudly"), str(parked_adc_path()))
    else:
        table.add_row("ADC", _("none; libraries without a profile env fail loudly"), str(global_adc_path()))

    if not state.gh_installed:
        table.add_row("gh", _("not installed"), "—")
    else:
        table.add_row("gh", state.gh_user or _("no active account"), "~/.config/gh")

    console.print(table)
    if state.adc_present:
        console.print(
            _(
                "[yellow]Risk:[/yellow] libraries (Terraform, Dataform, every Google SDK) outside a "
                "configured folder use the global ADC without asking. "
                "[bold]aparta fallback --secure[/bold] parks it, reversibly."
            )
        )
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


def _secure_steps(writer: SafeWriter, state: State) -> list[tuple[str, str, Callable[[], bool]]]:
    """(what will happen, the dry-run line, how to do it) for every change --secure makes."""
    active = state.gcloud_active
    current = active.name if active else ""
    exists = any(cfg.name == NEUTRAL_CONFIG for cfg in state.gcloud_configs or [])

    def remember() -> bool:
        writer.write_text(previous_path(), _toml.dumps({"gcloud_config": current}))
        return True

    def gcloud(*args: str) -> Callable[[], bool]:
        def run() -> bool:
            result = _run(["gcloud", "config", "configurations", *args])
            if result is None or result.returncode != 0:
                console.print(_("[red]gcloud configurations {verb} failed:[/red] {error}", verb=args[0], error=_stderr(result)))
                return False
            return True

        return run

    def park() -> bool:
        _park_adc(writer)
        return True

    steps: list[tuple[str, str, Callable[[], bool]]] = []
    if not state.secure:
        if not exists:
            steps.append((
                _("  - create the gcloud configuration '{name}' (no account, no project)", name=NEUTRAL_CONFIG),
                f"gcloud config configurations create {NEUTRAL_CONFIG} --no-activate",
                gcloud("create", NEUTRAL_CONFIG, "--no-activate"),
            ))
        steps.append((
            _("  - remember '{name}' in {path}", name=current or _("(none)"), path=previous_path()),
            "",
            remember,
        ))
        steps.append((
            _("  - make '{name}' the globally active configuration", name=NEUTRAL_CONFIG),
            f"gcloud config configurations activate {NEUTRAL_CONFIG}",
            gcloud("activate", NEUTRAL_CONFIG),
        ))
    if state.adc_present:
        steps.append((
            _("  - park the global ADC at {path} (--restore puts it back)", path=parked_adc_path()),
            f"mv {global_adc_path()} {parked_adc_path()}",
            park,
        ))
    return steps


def make_secure(writer: SafeWriter, assume_yes: bool = False) -> bool:
    """Point the global gcloud default at a neutral configuration, reversibly."""
    state = read_state()
    if not state.gcloud_installed:
        console.print(_("[yellow]gcloud is not installed, nothing to secure.[/yellow]"))
        console.print(note_gh())
        return False
    if state.secure and not state.adc_present:
        console.print(
            _("[green]Nothing to do:[/green] '{name}' is already the global default.", name=NEUTRAL_CONFIG)
        )
        return True

    steps = _secure_steps(writer, state)
    console.print(_("[bold]This is what will happen:[/bold]"))
    for description, _line, _do in steps:
        console.print(description)
    console.print(_("  - your other configurations, credentials and projects stay untouched"))
    console.print(note_gh())

    if writer.dry_run:
        for _description, line, do in steps:
            if line:
                console.print(f"[yellow]--dry-run[/yellow] {line}")
            else:
                do()
        return True

    if not assume_yes and not prompts.confirm(_("Make the global fallback neutral?")):
        console.print(_("[yellow]Cancelled.[/yellow]"))
        return False
    for _description, _line, do in steps:
        if not do():
            return False
    console.print(
        _(
            "[green]Done:[/green] outside a profile gcloud now has no account. "
            "Undo with [bold]aparta fallback --restore[/bold]."
        )
    )
    return True


def _park_adc(writer: SafeWriter) -> None:
    """Move the global ADC aside, keeping its bytes for --restore."""
    adc = global_adc_path()
    if not adc.exists():
        return
    writer.move_file(adc, parked_adc_path())
    console.print(
        _("[green]ADC parked:[/green] libraries outside a profile now fail loudly instead of borrowing it.")
    )


def restore(writer: SafeWriter) -> bool:
    """Put back what `--secure` changed: the configuration and the parked ADC."""
    previous = read_previous()
    parked = parked_adc_path()
    if not previous and not parked.exists():
        console.print(
            _("[yellow]Nothing to restore:[/yellow] no previous configuration saved in {path}.", path=previous_path())
        )
        return False
    if writer.dry_run:
        if previous:
            console.print(
                f"[yellow]--dry-run[/yellow] gcloud config configurations activate {previous}"
            )
        if parked.exists():
            console.print(f"[yellow]--dry-run[/yellow] mv {parked} {global_adc_path()}")
        return True
    if previous:
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
    if parked.exists():
        writer.move_file(parked, global_adc_path())
        console.print(_("[green]ADC restored:[/green] the global application credentials are back."))
    return True


def _stderr(result: subprocess.CompletedProcess | None) -> str:
    return result.stderr.strip() if result is not None else _("gcloud not found")
