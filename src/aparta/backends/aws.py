"""AWS backend: named profiles from ~/.aws, selected via AWS_PROFILE.

AWS already stores named profiles natively (~/.aws/config and
~/.aws/credentials), so this backend never creates anything; it verifies
the chosen profile exists and the agents get AWS_PROFILE injected. The
variable is honored by the AWS CLI, every SDK, Terraform and the CDK.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..fsutil import SafeWriter
from ..i18n import _
from ..profiles import Profile
from . import Note


def list_aws_profiles(aws_dir: Path | None = None) -> list[str]:
    """Named profiles from ~/.aws/config and ~/.aws/credentials."""
    aws_dir = aws_dir or Path.home() / ".aws"
    names: dict[str, None] = {}
    config = aws_dir / "config"
    if config.exists():
        for m in re.finditer(r"^\[(?:profile\s+)?([^\]]+)\]", config.read_text(), re.M):
            names[m.group(1).strip()] = None
    credentials = aws_dir / "credentials"
    if credentials.exists():
        for m in re.finditer(r"^\[([^\]]+)\]", credentials.read_text(), re.M):
            names[m.group(1).strip()] = None
    return list(names)


def aws_profile_exists(name: str, aws_dir: Path | None = None) -> bool:
    return name in list_aws_profiles(aws_dir)


def is_sso_profile(name: str, aws_dir: Path | None = None) -> bool:
    """Whether the named profile authenticates through AWS SSO.

    SSO sessions expire and a browser login renews them; static keys do
    not, so knowing which kind a profile is decides what a login can do.
    """
    aws_dir = aws_dir or Path.home() / ".aws"
    config = aws_dir / "config"
    if not config.exists():
        return False
    section = None
    for line in config.read_text().splitlines():
        m = re.match(r"^\[(?:profile\s+)?([^\]]+)\]", line)
        if m:
            section = m.group(1).strip()
            continue
        if section == name and re.match(r"\s*sso_\w+\s*=", line):
            return True
    return False


def apply_aws(profile: Profile, writer: SafeWriter) -> list[Note]:
    notes: list[Note] = []
    if not profile.aws_profile:
        return notes
    if aws_profile_exists(profile.aws_profile):
        notes.append(Note("info", _("[green]aws:[/green] profile '{name}' found in ~/.aws", name=profile.aws_profile)))
    else:
        notes.append(Note(
            "warn",
            _("[yellow]warning:[/yellow] AWS profile '{name}' not found, run `aws configure --profile {name}`.", name=profile.aws_profile),
        ))
    return notes
