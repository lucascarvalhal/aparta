"""Context discovery: scan the disk and infer profile suggestions.

Signals, strongest first: existing ~/.gitconfig includeIf blocks, the
effective user.email of repos under common roots grouped by parent folder,
and traces left by agent adapters. Everything here is read-only.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .fsutil import tilde
from .profiles import config_home, gh_config_dir as gh_config_path

# Build artifacts and dependency caches, never project roots.
IGNORED_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "target",
    "vendor",
    "Pods",
    "DerivedData",
    "site-packages",
}

# OS-managed home directories that cannot contain the user's own projects.
SYSTEM_DIRS = {
    "Library",
    "Applications",
    "Movies",
    "Music",
    "Pictures",
    "Public",
    "AppData",
}

DEFAULT_SCAN_DEPTH = 4


@dataclass
class ContextSuggestion:
    name: str
    root: str  # shown with ~ when possible
    git_email: str = ""
    git_name: str = ""  # user.name from the included gitconfig
    repo_count: int = 0
    gh_config: str = ""  # e.g. "gh-personal" (dir found in agent env)
    gcloud_config: str = ""  # e.g. "personal" (CLOUDSDK_ACTIVE_CONFIG_NAME)
    ssh_key: str = ""  # from core.sshCommand in the included gitconfig
    ssh_alias: str = ""  # from the [url "git@<alias>:"] insteadOf block
    gh_user: str = ""  # from the gh_config hosts.yml
    gcloud_account: str = ""  # from the named gcloud configuration
    gcloud_project: str = ""  # same source (project = ... line)
    aws_profile: str = ""  # from agent env (AWS_PROFILE) or a matching ~/.aws profile
    source: str = "repos"  # "gitconfig" | "repos"


# ---------------------------------------------------- signal 1: ~/.gitconfig

def parse_includeifs(gitconfig_text: str) -> list[tuple[str, str]]:
    """Extract (gitdir, path) pairs from [includeIf "gitdir:..."] blocks."""
    pairs: list[tuple[str, str]] = []
    current_gitdir: str | None = None
    for line in gitconfig_text.splitlines():
        line = line.strip()
        m = re.match(r'\[includeIf\s+"gitdir:(.+?)"\]', line)
        if m:
            current_gitdir = m.group(1)
            continue
        if line.startswith("["):
            current_gitdir = None
            continue
        if current_gitdir:
            m = re.match(r"path\s*=\s*(.+)", line)
            if m:
                pairs.append((current_gitdir, m.group(1).strip()))
                current_gitdir = None
    return pairs


def suggestions_from_gitconfig(gitconfig: Path | None = None) -> list[ContextSuggestion]:
    """Turn pre-existing manual includeIf setup into ready suggestions."""
    gitconfig = gitconfig or Path.home() / ".gitconfig"
    if not gitconfig.exists():
        return []
    suggestions = []
    for gitdir, include_path in parse_includeifs(gitconfig.read_text()):
        root = Path(gitdir.rstrip("/")).expanduser()
        email = ""
        git_name = ""
        ssh_key = ""
        ssh_alias = ""
        included = Path(include_path).expanduser()
        if not included.is_absolute():
            included = gitconfig.parent / included
        if included.exists():
            text = included.read_text()
            m = re.search(r"email\s*=\s*(\S+)", text)
            email = m.group(1) if m else ""
            m = re.search(r"^\s*name\s*=\s*(.+)$", text, re.M)
            git_name = m.group(1).strip() if m else ""
            m = re.search(r"sshCommand\s*=\s*ssh\s+-i\s+(\S+)", text)
            ssh_key = m.group(1) if m else ""
            m = re.search(r'\[url "git@([^:"]+):"\]', text)
            ssh_alias = m.group(1) if m else ""
        suggestions.append(
            ContextSuggestion(
                name=root.name,
                root=tilde(root),
                git_email=email,
                git_name=git_name,
                ssh_key=ssh_key,
                ssh_alias=ssh_alias,
                source="gitconfig",
            )
        )
    return suggestions


# --------------------------------------------------- signal 2: repos on disk

def find_repos(root: Path, max_depth: int = 3) -> list[Path]:
    """git repos under root, depth-limited, skipping non-project directories."""
    repos: list[Path] = []
    if not root.exists():
        return repos
    if (root / ".git").exists():
        return [root]

    def walk(d: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            children = sorted(
                p
                for p in d.iterdir()
                if p.is_dir()
                and not p.is_symlink()
                and not p.name.startswith(".")
                and p.name not in IGNORED_DIRS
                and p.name not in SYSTEM_DIRS
            )
        except PermissionError:
            return
        for child in children:
            if (child / ".git").exists():
                repos.append(child)
            else:
                walk(child, depth + 1)

    walk(root, 1)
    return repos


def find_all_repos(
    scan_roots: list[str] | None = None, max_depth: int = DEFAULT_SCAN_DEPTH
) -> list[Path]:
    """Every git repo under the given roots (the user's home by default).

    No assumptions about folder naming: the whole tree is walked, pruning
    only hidden directories, build artifacts and OS-managed directories.
    """
    roots = [Path(r).expanduser() for r in scan_roots] if scan_roots else [Path.home()]
    repos: dict[Path, None] = {}
    for root in roots:
        for repo in find_repos(root, max_depth=max_depth):
            repos[repo] = None
    return list(repos)


def repo_git_email(repo: Path) -> str:
    """Effective repo e-mail (local > includeIf > global)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip()


# --------------------------------------------- signal 3: adapter traces

def read_agent_env(repo: Path) -> dict[str, str]:
    """Env already injected by previous setups, read via the agent registry."""
    from .agents import ADAPTERS

    env: dict[str, str] = {}
    for cls in ADAPTERS.values():
        for key, value in cls().read_env(repo).items():
            env.setdefault(key, value)
    return env


# ------------------------------------------------------------------ discover

def _scan_groups(repos: list[Path]) -> list[ContextSuggestion]:
    """Group repos by parent folder; summarize majority e-mail/gh/gcloud."""
    groups: dict[Path, list[Path]] = {}
    for repo in repos:
        groups.setdefault(repo.parent, []).append(repo)

    suggestions = []
    for parent, repos in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        emails = Counter(e for e in (repo_git_email(r) for r in repos) if e)
        gh_dirs: Counter[str] = Counter()
        gcloud_names: Counter[str] = Counter()
        aws_names: Counter[str] = Counter()
        for r in repos:
            env = read_agent_env(r)
            if env.get("GH_CONFIG_DIR"):
                gh_dirs[Path(env["GH_CONFIG_DIR"]).name] += 1
            if env.get("CLOUDSDK_ACTIVE_CONFIG_NAME"):
                gcloud_names[env["CLOUDSDK_ACTIVE_CONFIG_NAME"]] += 1
            if env.get("AWS_PROFILE"):
                aws_names[env["AWS_PROFILE"]] += 1
        suggestions.append(
            ContextSuggestion(
                name=parent.name,
                root=tilde(parent),
                git_email=emails.most_common(1)[0][0] if emails else "",
                repo_count=len(repos),
                gh_config=gh_dirs.most_common(1)[0][0] if gh_dirs else "",
                gcloud_config=gcloud_names.most_common(1)[0][0] if gcloud_names else "",
                aws_profile=aws_names.most_common(1)[0][0] if aws_names else "",
            )
        )
    return suggestions


def gh_user_from_config_dir(dirname: str, config_root: Path | None = None) -> str:
    """Active user of a gh config dir, read from its hosts.yml."""
    config_root = config_root or config_home()
    hosts = config_root / dirname / "hosts.yml"
    if not hosts.exists():
        return ""
    m = re.search(r"^\s*user:\s*(\S+)", hosts.read_text(), re.M)
    return m.group(1) if m else ""


def gcloud_config_values(name: str, gcloud_dir: Path | None = None) -> tuple[str, str]:
    """(account, project) of a named gcloud configuration (config_<name>)."""
    if gcloud_dir is None:
        gcloud_dir = Path(
            os.environ.get("CLOUDSDK_CONFIG", str(config_home() / "gcloud"))
        ).expanduser()
    cfg = gcloud_dir / "configurations" / f"config_{name}"
    if not cfg.exists():
        return "", ""
    text = cfg.read_text()
    account = re.search(r"^account\s*=\s*(\S+)", text, re.M)
    project = re.search(r"^project\s*=\s*(\S+)", text, re.M)
    return (account.group(1) if account else ""), (project.group(1) if project else "")


def gcloud_account_from_config(name: str, gcloud_dir: Path | None = None) -> str:
    """Account of a named gcloud configuration."""
    return gcloud_config_values(name, gcloud_dir)[0]


def _enrich_accounts(
    s: ContextSuggestion, config_root: Path | None = None, aws_dir: Path | None = None
) -> None:
    """Resolve gh user and gcloud account from configs on disk, falling
    back to aparta's own naming convention (gh-<name>, config_<name>)."""
    config_root = config_root or config_home()
    gh_dir = s.gh_config or gh_config_path(s.name, config_root).name
    if (config_root / gh_dir).exists():
        s.gh_config = gh_dir
        s.gh_user = s.gh_user or gh_user_from_config_dir(gh_dir, config_root)
    gcloud_name = s.gcloud_config or s.name
    account, project = gcloud_config_values(gcloud_name, config_root / "gcloud")
    if account:
        s.gcloud_config = gcloud_name
        s.gcloud_account = s.gcloud_account or account
        s.gcloud_project = s.gcloud_project or project
    if not s.aws_profile:
        from .backends.aws import aws_profile_exists

        if aws_profile_exists(s.name, aws_dir):
            s.aws_profile = s.name


def loose_repos(
    profile_roots: list[Path | str],
    scan_roots: list[str] | None = None,
) -> list[Path]:
    """Repos found by the scan that no profile root covers."""
    covered = [Path(p).expanduser() for p in profile_roots]
    return sorted(
        repo
        for repo in find_all_repos(scan_roots)
        if not any(repo == c or c in repo.parents for c in covered)
    )


def discover(
    scan_roots: list[str] | None = None,
    gitconfig: Path | None = None,
    config_root: Path | None = None,
    aws_dir: Path | None = None,
) -> list[ContextSuggestion]:
    """Context suggestions: gitconfig includeIfs first, then the disk scan.

    The scan walks the user's home (or the given roots) with no naming
    assumptions. Scan groups whose root an includeIf already covers only
    enrich the existing suggestion (repo count, detected accounts).
    """
    by_root: dict[str, ContextSuggestion] = {}

    for s in suggestions_from_gitconfig(gitconfig):
        by_root[s.root] = s

    for s in _scan_groups(find_all_repos(scan_roots)):
        existing = None
        for known_root, known in by_root.items():
            if s.root == known_root or s.root.startswith(known_root.rstrip("/") + "/"):
                existing = known
                break
        if existing:
            existing.repo_count += s.repo_count
            existing.git_email = existing.git_email or s.git_email
            existing.gh_config = existing.gh_config or s.gh_config
            existing.gcloud_config = existing.gcloud_config or s.gcloud_config
        else:
            by_root[s.root] = s

    ordered = sorted(
        by_root.values(), key=lambda s: (s.source != "gitconfig", -s.repo_count)
    )
    for s in ordered:
        _enrich_accounts(s, config_root, aws_dir)
    return ordered
