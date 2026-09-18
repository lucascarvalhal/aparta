"""Interactive prompts shared by the wizard and the commands that ask before acting."""

from __future__ import annotations

import sys

from .i18n import _

SKIP = "(skip)"


def flush_stdin() -> None:
    """Drop stray bytes pending on stdin before handing the terminal to a prompt."""
    try:
        import termios

        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except Exception:
        pass


def confirm(question: str, default: bool = False) -> bool:
    """Yes/no with localized keys: y/N in English, s/N in Portuguese."""
    import questionary

    yes = _("y")
    answer = questionary.text(f"{question} ({yes}/n)", qmark="").ask()
    if answer is None:
        raise KeyboardInterrupt
    answer = answer.strip().lower()
    if not answer:
        return default
    return answer[0] in (yes, "y", "s")


def choose(
    question: str,
    options: list[str],
    sentinels: tuple[str, ...] = (SKIP,),
    default: str = "",
) -> str:
    """Select over options plus translated sentinel actions; '' when skipped."""
    import questionary

    choices = [questionary.Choice(o, value=o) for o in options]
    choices += [questionary.Choice(_(s), value=s) for s in sentinels]
    default_choice = next((c for c in choices if default and c.value == default), None)
    answer = questionary.select(question, choices=choices, default=default_choice, qmark="").ask()
    if answer is None:
        raise KeyboardInterrupt
    return "" if answer == SKIP else answer
