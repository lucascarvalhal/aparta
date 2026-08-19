"""Regenerate the README screenshots in both languages with demo data.

Run from the repo root: uv run python docs/screenshots.py
Strings come from the real i18n catalog, so the images track the product.
"""

from __future__ import annotations

import os
from pathlib import Path

DOCS = Path(__file__).parent


def render(lang: str, suffix: str) -> None:
    os.environ["APARTA_LANG"] = lang
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    from aparta.i18n import _

    def record() -> Console:
        return Console(record=True, width=100, force_terminal=True)

    # ---- scan ----
    c = record()
    c.print(_("[dim]Scanning {where} and ~/.gitconfig (read-only)...[/dim]", where=_("your home")))
    t = Table(title=_("Detected project groups"))
    t.add_column(_("Suggested name"), style="bold")
    t.add_column(_("Folder"))
    t.add_column(_("Repos"), justify="right")
    t.add_column(_("Git e-mail"))
    t.add_column("gh / gcloud")
    t.add_column(_("Source"))
    t.add_row("acme", "~/work/acme", "14", "ana@acme.com", "gh-acme / acme", "~/.gitconfig")
    t.add_row("client-x", "~/work/client-x", "6", "ana@client-x.io", "gcloud:client-x", "~/.gitconfig")
    t.add_row("personal", "~/personal", "5", "ana.dev@gmail.com", "gh-personal / personal", "~/.gitconfig")
    t.add_row("projects", "~/projects", "3", "ana.dev@gmail.com", "—", _("scan"))
    c.print(t)
    c.print(_("Use [bold]aparta init[/bold] to turn them into profiles."))
    c.save_svg(str(DOCS / f"scan{suffix}.svg"), title="aparta scan")

    # ---- wizard ----
    c = record()
    c.print(Panel(_("Welcome to [bold]aparta[/bold]! Let's isolate your development accounts per project folder."), border_style="cyan"))
    c.print(f"[bold]?[/bold] {_('Which AI agents should receive the environment variables?')}  [cyan]Claude Code, Gemini CLI[/cyan]")
    c.print(f"[bold]?[/bold] {_('How do you want to start?')}  [cyan]{_('Detect what I already use: scans logged-in accounts, keys and existing projects').split(':')[0]}[/cyan]")
    c.print(_("[dim]Scanning your home for git repositories (read-only)...[/dim]"))
    c.print(_("Found [bold]{n}[/bold] project group(s) already in use:", n=2))
    c.print("  [green]●[/green] ~/work/acme (14 repos, ana@acme.com, gh:ana-acme)")
    c.print("  [green]●[/green] ~/personal (5 repos, ana.dev@gmail.com, gh:anadev)")
    c.print(
        Panel(
            "~/work/acme (14 repos, ana@acme.com, gh:ana-acme)\n"
            + _("[dim]Enter accepts the suggested values; edit whatever you want.[/dim]"),
            title=_("Group {i}/{n}: {root}", i=1, n=2, root="~/work/acme"),
            border_style="cyan",
        )
    )
    c.print(f"[bold]?[/bold] {_('Profile name for {root}:', root='~/work/acme')}  [cyan]acme[/cyan]")
    root_prompt = _("Root folder of this profile's projects:")
    c.print(f"[bold]?[/bold] {root_prompt}  [cyan]~/work/acme[/cyan]")
    c.print(f"[bold]?[/bold] {_('git e-mail for these repositories:')}  [cyan]ana@acme.com[/cyan]")
    c.print(f"[bold]?[/bold] {_('Dedicated SSH key for this profile:')}  [cyan]~/.ssh/id_ed25519_acme[/cyan]")
    c.print(f"[bold]?[/bold] {_('GitHub CLI account for this profile:')}  [cyan]ana-acme[/cyan]")
    c.print(f"[bold]?[/bold] {_('gcloud account for this profile:')}  [cyan]ana@acme.com[/cyan]")
    c.save_svg(str(DOCS / f"wizard{suffix}.svg"), title="aparta wizard")

    # ---- summary ----
    c = record()
    t = Table(title=_("Summary: what aparta is going to do"), show_lines=True)
    t.add_column(_("Profile"), style="bold")
    t.add_column(_("Actions"), overflow="fold")
    t.add_row(
        "acme",
        _("git: create ~/.gitconfig-{name} (email {email}", name="acme", email="ana@acme.com")
        + _(", key {key}", key="~/.ssh/id_ed25519_acme")
        + _(") and add an includeIf for ")
        + "~/work/acme\n"
        + _("gh: copy ~/.config/gh to ~/.config/gh-{name} and activate '{user}'", name="acme", user="ana-acme")
        + "\n"
        + _("gcloud: configuration '{name}' with {account}{proj}", name="acme", account="ana@acme.com", proj=_(" (project {project})", project="acme-data-prod"))
        + "\n"
        + _("agents ({names}): inject {vars} into the repos of {root}", names="Claude Code, Gemini CLI", vars="GH_CONFIG_DIR, CLOUDSDK_ACTIVE_CONFIG_NAME", root="~/work/acme"),
    )
    t.add_row(
        "personal",
        _("git: create ~/.gitconfig-{name} (email {email}", name="personal", email="ana.dev@gmail.com")
        + _(") and add an includeIf for ")
        + "~/personal\n"
        + _("gh: copy ~/.config/gh to ~/.config/gh-{name} and activate '{user}'", name="personal", user="anadev")
        + "\n"
        + _("agents ({names}): inject {vars} into the repos of {root}", names="Claude Code, Gemini CLI", vars="GH_CONFIG_DIR", root="~/personal"),
    )
    c.print(t)
    c.print(Panel(_("Every write to an existing file creates a backup (.bak-aparta-<timestamp>) and merges, nothing is overwritten. Use --dry-run to only see the diff."), title=_("Safety"), border_style="dim"))
    c.save_svg(str(DOCS / f"summary{suffix}.svg"), title="aparta summary")

    # ---- doctor ----
    c = record()
    t = Table(title=_("doctor: profile '{name}'", name="acme"), show_lines=False)
    t.add_column(_("Area"), style="bold")
    t.add_column(_("Item"))
    t.add_column("OK", justify="center")
    t.add_column(_("Detail"), overflow="fold")
    ok = "[green]✔[/green]"
    t.add_row("git", "api-gateway", ok, "ana@acme.com")
    t.add_row("git", "billing-service", ok, "ana@acme.com")
    t.add_row("git", "infra-terraform", ok, "ana@acme.com")
    t.add_row("gh", "gh-acme", ok, _("logged in as {user}", user="ana-acme"))
    t.add_row("gcloud", "account", ok, "ana@acme.com")
    t.add_row("gcloud", "project", ok, "acme-data-prod")
    t.add_row("claude-code", "api-gateway", ok, _("env ok"))
    t.add_row("gemini", "api-gateway", ok, _("env ok"))
    c.print(t)
    c.save_svg(str(DOCS / f"doctor{suffix}.svg"), title="aparta doctor")


if __name__ == "__main__":
    render("en", "")
    render("pt", ".pt-BR")
    print("screenshots written to", DOCS)
