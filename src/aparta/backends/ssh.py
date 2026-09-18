"""SSH backend: keys and host aliases in ~/.ssh, plus key generation and upload."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

from ..i18n import _


class SshHost(NamedTuple):
    alias: str
    hostname: str
    identity: str


def list_ssh_keys(ssh_dir: Path | None = None) -> list[str]:
    """Private keys in ~/.ssh (files with a matching .pub)."""
    ssh_dir = ssh_dir or Path.home() / ".ssh"
    if not ssh_dir.exists():
        return []
    return [str(pub.with_suffix("")) for pub in sorted(ssh_dir.glob("*.pub")) if pub.with_suffix("").exists()]


def list_ssh_host_aliases(config: Path | None = None) -> list[SshHost]:
    """Concrete Host entries of ~/.ssh/config that point at another hostname."""
    config = config or Path.home() / ".ssh" / "config"
    if not config.exists():
        return []
    hosts: list[dict[str, str]] = []
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
                hosts.append(current)
            continue
        if current is None:
            continue
        m = re.match(r"(?i)^(HostName|IdentityFile)\s+(\S+)", line)
        if m:
            current[m.group(1).lower().replace("identityfile", "identity")] = m.group(2)
    return [SshHost(**h) for h in hosts if h["hostname"] and h["alias"] != h["hostname"]]


def key_path(profile_name: str) -> Path:
    return Path.home() / ".ssh" / f"id_ed25519_{profile_name}"


def create_key(key: Path, comment: str) -> str:
    """Generate an ed25519 key without passphrase; '' on success, else the error."""
    key.parent.mkdir(mode=0o700, exist_ok=True)
    try:
        r = subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", str(key), "-N", "", "-C", comment],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        return _("[red]ssh-keygen not found.[/red]")
    if r.returncode != 0:
        return _("[red]ssh-keygen failed:[/red] {error}", error=r.stderr.strip())
    return ""


def upload_key(key: str, title: str, gh_config_dir: Path | None = None) -> str:
    """Add the public key to the GitHub account gh is logged into; '' on success, else the error."""
    env = dict(os.environ)
    if gh_config_dir is not None and gh_config_dir.exists():
        env["GH_CONFIG_DIR"] = str(gh_config_dir)
    r = subprocess.run(
        ["gh", "ssh-key", "add", f"{key}.pub", "--title", title],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode == 0:
        return ""
    return r.stderr.strip().splitlines()[-1] if r.stderr.strip() else _("failed")
