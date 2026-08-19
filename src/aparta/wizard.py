"""Interactive wizard: agents, then start mode, then guided profiles.

Flow: pick AI agents; choose "detect" (disk scan pre-fills every answer) or
"from scratch" (connect accounts and generate keys along the way); configure
each profile; optionally adopt stray repos; confirm a single summary.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .agents import ADAPTERS
from .discovery import ContextSuggestion, discover
from .fsutil import SafeWriter
from .i18n import _
from .profiles import Profile, gh_config_dir, load_profiles, profiles_path, save_profiles

console = Console()

SKIP = "(skip)"
NEW_GH_LOGIN = "(connect a new GitHub account...)"
NEW_GCLOUD_LOGIN = "(connect a new Google account...)"
NEW_SSH_KEY = "(generate a new SSH key for this profile...)"


# ----------------------------------------------------------------- discovery

def list_ssh_keys(ssh_dir: Path | None = None) -> list[str]:
    """Private keys in ~/.ssh (files with a matching .pub)."""
    ssh_dir = ssh_dir or Path.home() / ".ssh"
    if not ssh_dir.exists():
        return []
    keys = []
    for pub in sorted(ssh_dir.glob("*.pub")):
        private = pub.with_suffix("")
        if private.exists():
            keys.append(str(private))
    return keys


def list_ssh_host_aliases(config: Path | None = None) -> list[dict[str, str]]:
    """Host aliases from ~/.ssh/config: [{alias, hostname, identity}].

    Only blocks with a HostName and an alias that differs from it count as
    real aliases; wildcard entries are skipped.
    """
    config = config or Path.home() / ".ssh" / "config"
    if not config.exists():
        return []
    aliases: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in config.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"(?i)^Host\s+(.+)", line)
        if m:
            name = m.group(1).split()[0]
            current = None
            if "*" not in name and "?" not in name:
                current = {"alias": name, "hostname": "", "identity": ""}
                aliases.append(current)
            continue
        if current is None:
            continue
        m = re.match(r"(?i)^HostName\s+(\S+)", line)
        if m:
            current["hostname"] = m.group(1)
            continue
        m = re.match(r"(?i)^IdentityFile\s+(\S+)", line)
        if m:
            current["identity"] = m.group(1)
    return [a for a in aliases if a["hostname"] and a["alias"] != a["hostname"]]


def parse_gh_accounts(status_output: str) -> list[str]:
    """Logged-in users from `gh auth status` output (every account)."""
    return list(dict.fromkeys(re.findall(r"Logged in to \S+ account (\S+)", status_output)))


def list_gh_accounts() -> list[str]:
    try:
        r = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True, timeout=30
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return parse_gh_accounts(r.stdout + r.stderr)


def list_gcloud_accounts() -> list[str]:
    try:
        r = subprocess.run(
            ["gcloud", "auth", "list", "--format=value(account)"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if r.returncode != 0:
        return []
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


# ------------------------------------------------------------ new accounts

def login_new_gh_account(profile_name: str, dry_run: bool = False) -> str:
    """Interactive `gh auth login` inside ~/.config/gh-<profile>.

    The new account is born isolated in the profile's config dir; the global
    gh config is untouched. Returns the logged-in user ('' on failure).
    """
    dst = gh_config_dir(profile_name)
    if dry_run:
        console.print(f"[yellow]--dry-run[/yellow] GH_CONFIG_DIR={dst} gh auth login")
        return ""
    dst.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GH_CONFIG_DIR=str(dst))
    try:
        r = subprocess.run(["gh", "auth", "login"], env=env)  # interactive, inherits TTY
    except FileNotFoundError:
        console.print(_("[red]gh not found in PATH.[/red]"))
        return ""
    if r.returncode != 0:
        console.print(_("[yellow]Login cancelled or failed; skipping gh.[/yellow]"))
        return ""
    status = subprocess.run(
        ["gh", "auth", "status"], env=env, capture_output=True, text=True, timeout=30
    )
    accounts = parse_gh_accounts(status.stdout + status.stderr)
    if accounts:
        console.print(_("[green]gh:[/green] '{user}' logged in at {dst}", user=accounts[0], dst=dst))
        return accounts[0]
    return ""


def login_new_gcloud_account(profile_name: str, dry_run: bool = False) -> str:
    """Interactive `gcloud auth login` inside the profile's named config.

    The configuration is created with --no-activate first and the login runs
    with CLOUDSDK_ACTIVE_CONFIG_NAME pointing at it, so the globally active
    account never changes. Returns the logged-in account ('' on failure).
    """
    if dry_run:
        console.print(
            f"[yellow]--dry-run[/yellow] CLOUDSDK_ACTIVE_CONFIG_NAME={profile_name} gcloud auth login"
        )
        return ""
    from .backends.gcloud import configuration_exists

    try:
        if not configuration_exists(profile_name):
            create = subprocess.run(
                ["gcloud", "config", "configurations", "create", profile_name, "--no-activate"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if create.returncode != 0:
                console.print(_("[red]gcloud configurations create failed:[/red] {error}", error=create.stderr.strip()))
                return ""
        env = dict(os.environ, CLOUDSDK_ACTIVE_CONFIG_NAME=profile_name)
        r = subprocess.run(["gcloud", "auth", "login"], env=env)  # interactive
        if r.returncode != 0:
            console.print(_("[yellow]Login cancelled or failed; skipping gcloud.[/yellow]"))
            return ""
        active = subprocess.run(
            ["gcloud", "config", "get", "account"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        console.print(_("[red]gcloud not found in PATH.[/red]"))
        return ""
    account = active.stdout.strip()
    if account:
        console.print(_("[green]gcloud:[/green] '{account}' in configuration '{name}'", account=account, name=profile_name))
    return account


def generate_ssh_key(profile_name: str, dry_run: bool = False) -> str:
    """Generate ~/.ssh/id_ed25519_<profile> (no passphrase) and show the
    public key. Returns the private key path ('' on failure/dry-run)."""
    key = Path.home() / ".ssh" / f"id_ed25519_{profile_name}"
    if dry_run:
        console.print(f"[yellow]--dry-run[/yellow] ssh-keygen -t ed25519 -f {key}")
        return ""
    if key.exists():
        console.print(_("[dim]{key} already exists; using it.[/dim]", key=key))
        return str(key)
    key.parent.mkdir(mode=0o700, exist_ok=True)
    try:
        r = subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", str(key), "-N", "",
             "-C", f"{profile_name} (generated by aparta)"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        console.print(_("[red]ssh-keygen not found.[/red]"))
        return ""
    if r.returncode != 0:
        console.print(_("[red]ssh-keygen failed:[/red] {error}", error=r.stderr.strip()))
        return ""
    console.print(_("[green]key created:[/green] {key}", key=key))
    console.print(Panel(key.with_suffix(".pub").read_text().strip(), title=_("Public key")))
    return str(key)


def offer_upload_ssh_key(ssh_key: str, gh_user: str, profile_name: str) -> None:
    """Offer to upload the freshly created public key via `gh ssh-key add`."""
    import questionary

    if not _confirm(
        _("Upload this key to the GitHub account '{user}' now? (gh ssh-key add)", user=gh_user),
        default=True,
    ):
        console.print(
            _("[dim]Later: gh ssh-key add {key}.pub --title {name}[/dim]", key=ssh_key, name=profile_name)
        )
        return
    env = dict(os.environ)
    profile_gh_dir = gh_config_dir(profile_name)
    if profile_gh_dir.exists():
        env["GH_CONFIG_DIR"] = str(profile_gh_dir)
    r = subprocess.run(
        ["gh", "ssh-key", "add", f"{ssh_key}.pub", "--title", f"{profile_name}-aparta"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode != 0:
        console.print(
            _(
                "[yellow]Could not upload ({error}).[/yellow]\n"
                "[dim]Manual: gh ssh-key add {key}.pub --title {name} "
                "(the token needs the admin:public_key scope, gh auth refresh -s admin:public_key)[/dim]",
                error=r.stderr.strip().splitlines()[-1] if r.stderr.strip() else _("failed"),
                key=ssh_key,
                name=profile_name,
            )
        )
    else:
        console.print(_("[green]gh:[/green] key added to account '{user}'.", user=gh_user))


# ------------------------------------------------------------------- wizard

def _confirm(question: str, default: bool = False) -> bool:
    """Yes/no with localized keys: y/N in English, s/N in Portuguese.

    Typed answer plus Enter; empty keeps the default. Both the localized
    letter and y/s are accepted regardless of language.
    """
    import questionary

    yes = _("y")
    suffix = f" ({yes.upper()}/n)" if default else f" ({yes}/N)"
    answer = questionary.text(question + suffix).ask()
    if answer is None:
        raise KeyboardInterrupt
    answer = answer.strip().lower()
    if not answer:
        return default
    return answer[0] in (yes, "y", "s")


def _choose_from(
    question: str,
    options: list[str],
    sentinels: tuple[str, ...] = (SKIP,),
    default: str = "",
) -> str:
    """Select over options plus translated sentinel actions; '' when skipped.

    `default` starts selected when among the choices, so Enter confirms it.
    Sentinels display translated but return their canonical value.
    """
    import questionary

    choices = [questionary.Choice(o, value=o) for o in options]
    choices += [questionary.Choice(_(s), value=s) for s in sentinels]
    default_choice = next((c for c in choices if default and c.value == default), None)
    answer = questionary.select(question, choices=choices, default=default_choice).ask()
    if answer is None:
        raise KeyboardInterrupt
    return "" if answer == SKIP else answer


def _ask_ssh_alias(ssh_key: str, suggested: str = "") -> str:
    """Ask for the remotes SSH alias, listing ~/.ssh/config hosts.

    With an alias, the profile gitconfig rewrites GitHub URLs (https and
    git@) to git@<alias>:, guaranteeing the right key on any clone.
    """
    import questionary

    no_alias = _("(do not use, connect directly with the chosen key)")
    aliases = list_ssh_host_aliases()
    if not aliases:
        return (
            questionary.text(
                _("Remotes SSH shortcut (a Host from ~/.ssh/config; empty = use the key directly):"),
                default=suggested,
            ).ask()
            or ""
        ).strip()

    key_resolved = str(Path(ssh_key).expanduser())
    default = suggested or next(
        (
            a["alias"]
            for a in aliases
            if a["identity"] and str(Path(a["identity"]).expanduser()) == key_resolved
        ),
        "",
    )
    choices = [
        questionary.Choice(
            f"{a['alias']}  (→ {a['hostname']}"
            + (_(", key {key}", key=Path(a["identity"]).name) if a["identity"] else "")
            + ")",
            value=a["alias"],
        )
        for a in aliases
    ] + [questionary.Choice(no_alias, value="")]
    default_choice = next((c for c in choices if c.value == default and default), None)
    answer = questionary.select(
        _("SSH shortcut for this profile's remotes (rewrites GitHub URLs to use the right key):"),
        choices=choices,
        default=default_choice,
    ).ask()
    if answer is None:
        raise KeyboardInterrupt
    return answer


def _ask_context(
    agents: list[str],
    existing_names: list[str],
    suggestion: ContextSuggestion | None = None,
    dry_run: bool = False,
) -> Profile | None:
    import questionary

    name = questionary.text(
        _("Profile name for {root}:", root=suggestion.root)
        if suggestion
        else _("New profile name (e.g. personal, work, client-x):"),
        default=suggestion.name if suggestion else "",
        validate=lambda v: bool(v.strip()) or _("required"),
    ).ask()
    if name is None:
        return None
    name = name.strip()
    if name in existing_names:
        if not _confirm(_("'{name}' already exists. Overwrite?", name=name)):
            return None

    root = questionary.path(
        _("Root folder of this profile's projects:"),
        default=suggestion.root if suggestion else f"~/{name}",
    ).ask()
    if root is None:
        return None

    git_email = questionary.text(
        _("git e-mail for these repositories:"),
        default=suggestion.git_email if suggestion else "",
        validate=lambda v: "@" in v or _("enter a valid e-mail"),
    ).ask()
    if git_email is None:
        return None

    ssh_keys = list_ssh_keys()
    ssh_alias = ""
    suggested_key = str(Path(suggestion.ssh_key).expanduser()) if suggestion and suggestion.ssh_key else ""
    ssh_key = _choose_from(
        _("Dedicated SSH key for this profile:"),
        ssh_keys,
        sentinels=(NEW_SSH_KEY, SKIP),
        default=suggested_key,
    )
    generated_key = False
    if ssh_key == NEW_SSH_KEY:
        ssh_key = generate_ssh_key(name, dry_run=dry_run)
        generated_key = bool(ssh_key)
    if ssh_key:
        ssh_alias = _ask_ssh_alias(ssh_key, suggestion.ssh_alias if suggestion else "")

    gh_accounts = list_gh_accounts()
    if not gh_accounts:
        console.print(_("[dim]No gh account logged in yet (gh auth status).[/dim]"))
    gh_user = _choose_from(
        _("GitHub CLI account for this profile:"),
        gh_accounts,
        sentinels=(NEW_GH_LOGIN, SKIP),
        default=suggestion.gh_user if suggestion else "",
    )
    if gh_user == NEW_GH_LOGIN:
        gh_user = login_new_gh_account(name, dry_run=dry_run)
    if gh_user and generated_key:
        offer_upload_ssh_key(ssh_key, gh_user, name)

    gcloud_accounts = list_gcloud_accounts()
    if not gcloud_accounts:
        console.print(_("[dim]No gcloud account logged in yet (gcloud auth list).[/dim]"))
    gcloud_account = _choose_from(
        _("gcloud account for this profile:"),
        gcloud_accounts,
        sentinels=(NEW_GCLOUD_LOGIN, SKIP),
        default=suggestion.gcloud_account if suggestion else "",
    )
    if gcloud_account == NEW_GCLOUD_LOGIN:
        gcloud_account = login_new_gcloud_account(name, dry_run=dry_run)
    gcloud_project = ""
    if gcloud_account:
        gcloud_project = (
            questionary.text(
                _("GCP project id for this profile (e.g. my-project-123; empty = set later):"),
                default=suggestion.gcloud_project if suggestion else "",
            ).ask()
            or ""
        ).strip()

    return Profile(
        name=name,
        root=root.strip(),
        git_email=git_email.strip(),
        ssh_key=ssh_key,
        ssh_alias=ssh_alias,
        gh_user=gh_user,
        gcloud_account=gcloud_account,
        gcloud_project=gcloud_project,
        agents=agents,
    )


def _suggestion_label(s: ContextSuggestion) -> str:
    parts = [f"{s.root} ({s.repo_count} {_('repo') if s.repo_count == 1 else _('repos')}"]
    if s.git_email:
        parts.append(f", {s.git_email}")
    if s.gh_user or s.gh_config:
        parts.append(f", gh:{s.gh_user or s.gh_config}")
    if s.gcloud_account or s.gcloud_config:
        parts.append(f", gcloud:{s.gcloud_account or s.gcloud_config}")
    if s.source == "gitconfig":
        parts.append(_(", already in ~/.gitconfig"))
    return "".join(parts) + ")"


def _adopt_loose_repos(all_profiles: list[Profile]) -> None:
    """Offer repos outside every profile root for adoption (local identity,
    no folder moves). Mutates all_profiles in place via adopted_repos."""
    import questionary

    from .discovery import loose_repos

    already = {r for p in all_profiles for r in p.adopted_repos}
    loose = [r for r in loose_repos([p.root for p in all_profiles]) if str(r) not in already]
    if not loose:
        return
    console.print(
        "\n"
        + _(
            "Found [bold]{n}[/bold] repository(ies) outside the profile folders. "
            "You can adopt them: they stay where they are and get the profile "
            "identity in the repo itself.",
            n=len(loose),
        )
    )
    remaining = [str(r) for r in loose]
    for p in all_profiles:
        if not remaining:
            break
        chosen = questionary.checkbox(
            _("Which of these belong to '{name}'? (Enter = none)", name=p.name),
            choices=remaining,
        ).ask()
        if chosen is None:
            return
        p.adopted_repos.extend(chosen)
        remaining = [r for r in remaining if r not in chosen]


def _summary(new_profiles: list[Profile]) -> None:
    table = Table(title=_("Summary: what aparta is going to do"), show_lines=True)
    table.add_column(_("Profile"), style="bold")
    table.add_column(_("Actions"), overflow="fold")
    for p in new_profiles:
        actions = [
            _("git: create ~/.gitconfig-{name} (email {email}", name=p.name, email=p.git_email)
            + (_(", key {key}", key=p.ssh_key) if p.ssh_key else "")
            + _(") and add an includeIf for ")
            + p.root,
        ]
        if p.ssh_alias:
            actions.append(_("git: rewrite https remotes through the git@{alias}: shortcut", alias=p.ssh_alias))
        if p.adopted_repos:
            actions.append(
                _("git: adopt {n} repo(s) outside the root (local include.path, no moves): ", n=len(p.adopted_repos))
                + ", ".join(Path(r).name for r in p.adopted_repos)
            )
        if p.gh_user:
            actions.append(
                _("gh: copy ~/.config/gh to ~/.config/gh-{name} and activate '{user}'", name=p.name, user=p.gh_user)
            )
        if p.gcloud_account:
            proj = _(" (project {project})", project=p.gcloud_project) if p.gcloud_project else ""
            actions.append(_("gcloud: configuration '{name}' with {account}{proj}", name=p.name, account=p.gcloud_account, proj=proj))
        env = p.env()
        if env and p.agents:
            names = ", ".join(ADAPTERS[a].display_name for a in p.agents if a in ADAPTERS)
            actions.append(_("agents ({names}): inject {vars} into the repos of {root}", names=names, vars=", ".join(env), root=p.root))
        table.add_row(p.name, "\n".join(actions))
    console.print(table)
    console.print(
        Panel(
            _(
                "Every write to an existing file creates a backup (.bak-aparta-<timestamp>) "
                "and merges, nothing is overwritten. Use --dry-run to only see the diff."
            ),
            title=_("Safety"),
            border_style="dim",
        )
    )


def _ask_language() -> bool:
    """First-run language question; False when the user cancelled.

    Skipped when APARTA_LANG is set or a choice was already saved. The
    question itself is bilingual on purpose, it runs before any language
    is known.
    """
    import questionary

    from .i18n import saved_language, set_language

    if os.environ.get("APARTA_LANG") or saved_language():
        return True
    choice = questionary.select(
        "Language / Idioma:",
        choices=[
            questionary.Choice("English", value="en"),
            questionary.Choice("Português (Brasil)", value="pt"),
        ],
    ).ask()
    if choice is None:
        return False
    set_language(choice)
    return True


def run_wizard(dry_run: bool = False) -> None:
    """Full wizard. Raises KeyboardInterrupt/returns early when cancelled."""
    import questionary

    if not _ask_language():
        return

    console.print(
        Panel(
            _(
                "Welcome to [bold]aparta[/bold]! Let's isolate your development "
                "accounts per project folder."
            ),
            border_style="cyan",
        )
    )

    # step 1: AI agents (from the registry; new adapters show up on their own)
    agents = questionary.checkbox(
        _("Which AI agents should receive the environment variables?"),
        choices=[
            questionary.Choice(cls.display_name, value=name, checked=(name == "claude-code"))
            for name, cls in sorted(ADAPTERS.items())
        ],
    ).ask()
    if agents is None:
        return

    # step 2: start mode, detect existing setup or build from scratch
    mode = questionary.select(
        _("How do you want to start?"),
        choices=[
            questionary.Choice(
                _("Detect what I already use: scans logged-in accounts, keys and existing projects"),
                value="scan",
            ),
            questionary.Choice(
                _("Start from scratch: connect accounts and create keys step by step"),
                value="zero",
            ),
        ],
    ).ask()
    if mode is None:
        return

    # step 3: discovery, scan the disk and suggest ready-made groups
    profiles = load_profiles()
    new_profiles: list[Profile] = []

    suggestions: list[ContextSuggestion] = []
    if mode == "scan":
        console.print(
            _("[dim]Scanning your home for git repositories (read-only)...[/dim]")
        )
        suggestions = [s for s in discover() if s.name not in profiles]
        extra = ""
        if _confirm(_("Scan an extra folder outside your home?")):
            extra = (questionary.path(_("Which folder?"), default="").ask() or "").strip()
        if extra:
            known_roots = {s.root for s in suggestions}
            suggestions += [
                s
                for s in discover(scan_roots=[extra])
                if s.name not in profiles and s.root not in known_roots
            ]
        if not suggestions:
            console.print(
                _("[yellow]Nothing detected, let's create your first profile from scratch.[/yellow]")
            )
    if suggestions:
        console.print(
            _("Found [bold]{n}[/bold] project group(s) already in use:", n=len(suggestions))
        )
        chosen = questionary.checkbox(
            _("Which should become profiles? (answers come pre-filled)"),
            choices=[
                questionary.Choice(_suggestion_label(s), value=s, checked=True)
                for s in suggestions
            ],
        ).ask()
        for i, s in enumerate(chosen or [], start=1):
            console.print(
                Panel(
                    _suggestion_label(s)
                    + "\n" + _("[dim]Enter accepts the suggested values; edit whatever you want.[/dim]"),
                    title=_("Group {i}/{n}: {root}", i=i, n=len(chosen), root=s.root),
                    border_style="cyan",
                )
            )
            profile = _ask_context(
                agents,
                list(profiles) + [p.name for p in new_profiles],
                suggestion=s,
                dry_run=dry_run,
            )
            if profile is not None:
                new_profiles.append(profile)

    # manual profiles (the first is mandatory when nothing was detected/selected)
    while True:
        if new_profiles and not _confirm(_("Configure another profile?")):
            break
        profile = _ask_context(
            agents, list(profiles) + [p.name for p in new_profiles], dry_run=dry_run
        )
        if profile is not None:
            new_profiles.append(profile)
        elif new_profiles:
            break
        elif not _confirm(_("Try again?"), default=True):
            break

    if not new_profiles:
        console.print(_("[yellow]No profile configured.[/yellow]"))
        return

    # stray repos outside profile roots can be adopted (detect mode only)
    if mode == "scan":
        _adopt_loose_repos(list(profiles.values()) + new_profiles)

    # summary + single confirmation
    _summary(new_profiles)
    action = questionary.select(
        _("How to proceed?"),
        choices=[
            questionary.Choice(_("Save and apply now"), value="apply"),
            questionary.Choice(_("Just save the profiles (apply later with `aparta apply`)"), value="save"),
            questionary.Choice(_("Cancel"), value="cancel"),
        ],
    ).ask()
    if action in (None, "cancel"):
        console.print(_("[yellow]Cancelled; nothing was saved.[/yellow]"))
        return

    writer = SafeWriter(dry_run=dry_run)
    for p in new_profiles:
        profiles[p.name] = p
    save_profiles(profiles, writer)
    if not dry_run:
        console.print(_("[green]Profiles saved to {path}.[/green]", path=profiles_path()))

    if action == "apply":
        from .apply import apply_profile

        for p in new_profiles:
            apply_profile(p, writer)
    else:
        console.print(_("Whenever you want to apply: [bold]aparta apply {name}[/bold]", name=new_profiles[0].name))
