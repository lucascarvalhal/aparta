<p align="center">
  <img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/logo.svg" alt="aparta" width="480">
</p>

<p align="center">
  <a href="https://pypi.org/project/aparta/"><img src="https://img.shields.io/pypi/v/aparta" alt="PyPI"></a>
  <img src="https://img.shields.io/pypi/pyversions/aparta" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License: MIT">
  <a href="https://github.com/lucascarvalhal/aparta/actions/workflows/ci.yml"><img src="https://github.com/lucascarvalhal/aparta/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

<p align="center">
  <b>English</b> | <a href="README.pt-BR.md">Português (Brasil)</a>
</p>

**aparta** isolates your development accounts, git, GitHub CLI, gcloud, SSH keys, per project folder, and makes your terminal AI agents (Claude Code, Codex, Gemini CLI, Antigravity) use the right identity, always. *Aparta* is Portuguese for "set apart".

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/demo.gif" alt="aparta demo" width="900">

## Why aparta?

If you work with more than one identity, a day job, a side gig, freelance clients, open source, you know the drill:

- You commit to a client's repo and only later notice the commit went out **with your personal e-mail** (or worse: your personal work went out with your employer's e-mail). Rewriting published history is painful; sometimes it's impossible.
- `gh` and `gcloud` have **one globally active account**. Switching in one terminal switches *everywhere*, including that other terminal where a deploy script was about to run against the wrong project.
- Terminal AI agents inherit whatever identity your shell happens to have. An agent that clones, commits, pushes, or calls cloud APIs on your behalf multiplies the odds of an accident.

The fix is well known among people who've been burned: `[includeIf "gitdir:..."]` blocks in `~/.gitconfig`, parallel `gh` config directories selected via `GH_CONFIG_DIR`, named `gcloud` configurations selected via `CLOUDSDK_ACTIVE_CONFIG_NAME`, per-host SSH aliases. It works beautifully, but it's tedious to set up by hand, easy to get subtly wrong, and nobody documents how to make AI agents respect it.

**aparta automates the whole thing.** Folder decides identity. Enter a project under `~/work/acme`, and git, gh, gcloud, and your AI agents are the acme you. Enter `~/personal`, and they're you-you. No switching, no remembering, no accidents.

## How it works

One command, one interactive wizard:

- **Scans what you already have**, logged-in gh/gcloud accounts, SSH keys and host aliases, existing `includeIf` blocks, and every git repo on disk grouped by folder and commit e-mail. Existing setups become pre-filled suggestions: confirming a profile is just pressing Enter.
- **Or starts from zero**, connect a new GitHub account (`gh auth login` scoped to the profile's own config dir), a new Google account, generate a fresh SSH key (and upload it to GitHub for you).
- **Applies safely**, every file it touches is backed up first (`.bak-aparta-<timestamp>`) and merged, never overwritten. `--dry-run` shows the full diff without changing anything. Nothing ever leaves your machine.
- **Verifies**, `aparta doctor` checks the real state: the resolved git e-mail in each repo, gh auth, gcloud config, injected agent env.

### Screenshots

*The wizard detects your existing setup and pre-fills everything:*

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/wizard.svg" alt="aparta wizard" width="820">

*One summary, one confirmation, with a safety net:*

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/summary.svg" alt="aparta summary" width="820">

*`aparta scan` shows what it found without touching anything:*

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/scan.svg" alt="aparta scan" width="820">

*`aparta doctor` proves each profile is actually working:*

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/doctor.svg" alt="aparta doctor" width="680">

## Installation

Works on macOS, Linux and Windows through WSL. Requires Python ≥ 3.10. `gh` and `gcloud` are optional, aparta selects credentials for the tools you use; it never logs in for you (unless you ask it to, in the wizard).

**Recommended:** install it as a permanent tool with [uv](https://docs.astral.sh/uv/), it is fast, isolated from your projects, and trivial to upgrade:

```bash
uv tool install aparta     # recommended
aparta                     # from now on it is just this
```

Other ways, whatever fits your setup:

```bash
uvx aparta            # try it without installing anything
pipx install aparta   # same idea as uv tool, using pipx
pip install aparta    # plain pip, goes into the active environment
npx aparta-cli        # Node ecosystem launcher (needs uv or pipx installed)
```

Upgrading later: `uv tool upgrade aparta` (or the equivalent in your chosen tool). Shell autocompletion: `aparta --install-completion`.

## Languages

The CLI speaks English and Brazilian Portuguese. The first run of the wizard asks which one you prefer and remembers it; `APARTA_LANG=en` or `APARTA_LANG=pt` overrides the saved choice, and without any of that the locale (`LANG`) decides.

## Quick start

```bash
aparta            # first run opens the wizard; later runs open a menu
```

1. Pick which AI agents should receive per-project environment (Claude Code, Codex, Gemini CLI, Antigravity, or a generic `.envrc` via direnv).
2. Choose **"Detect what I already use"** (recommended) or **"Start from zero"**.
3. Confirm each suggested profile, name, folder, git e-mail, SSH key, remote alias, gh account, gcloud account/project all come pre-filled from the scan.
4. Optionally adopt stray repos that live outside your profile folders (they keep their location; identity is applied locally via a git `include.path`).
5. Review the summary, confirm once. Done.

```bash
aparta doctor     # verify everything actually resolves to the right identity
aparta scan       # read-only: show detected project groups
aparta apply X    # re-apply a profile (e.g. after cloning new repos)
aparta list       # list configured profiles
aparta --dry-run  # any command: show diffs, change nothing
```

## What each profile configures

| Tool | Mechanism |
|---|---|
| git | `~/.gitconfig-<profile>` with `user.email`, `core.sshCommand` (dedicated key), optional `url insteadOf` rewrite; included via `[includeIf "gitdir:~/folder/"]` |
| GitHub CLI | copy of `~/.config/gh` to `~/.config/gh-<profile>` + `gh auth switch` inside the copy; selected via `GH_CONFIG_DIR` (tokens stay in your keyring, no re-login) |
| gcloud | named configuration (`--no-activate`) with account/project; selected via `CLOUDSDK_ACTIVE_CONFIG_NAME` |
| SSH | per-profile key; optional `~/.ssh/config` host-alias rewrite so any clone URL uses the right key |
| Stray repos | local `include.path` in the repo's `.git/config` pointing at the profile's gitconfig, full identity without moving the folder |

## Supported AI agents

| Agent | Injection mechanism |
|---|---|
| Claude Code | `env` field in `.claude/settings.local.json` (merged) |
| Codex CLI | `[env]` section in the repo's `.codex/config.toml` |
| Gemini CLI | project `.gemini/.env` (loaded natively by the CLI) |
| Antigravity | `terminal.integrated.env.{osx,linux}` in `.vscode/settings.json` |
| opencode | generated `shell.env` plugin in `.opencode/plugins/aparta-env.js` |
| Cursor CLI | no native per-project env, inherits the shell, covered by the direnv adapter |
| direnv (generic) | `export` lines in `.envrc`, works for any tool (needs [direnv](https://direnv.net) installed and a one-time `direnv allow` per repo) |

Adding a new agent = dropping one file in `src/aparta/agents/` (auto-registered).

## Safety model

- Every write to an existing file creates a timestamped backup and **merges**: aparta never overwrites your dotfiles.
- `--dry-run` previews every change as a diff.
- The scan is 100% read-only.
- Nothing is sent anywhere. No telemetry, no network calls beyond the ones *you* trigger (`gh auth login`, `gcloud auth login`).

## Roadmap

- More agents as they gain per-project config support

## We strongly recommend using

- [Orca](https://www.onorca.dev/): an Agent Development Environment that runs several AI agents at once in isolated worktrees, with terminals, editor and browser in one app. Every agent Orca launches inherits the per-folder identity that aparta configured, so parallel agents across different clients stay on the right accounts.
- [Universal Memory (U-Mem)](https://universal-memory.com/): a local-first, vendor-agnostic memory layer for AI agents. aparta makes every agent use the right account per folder; U-Mem makes them remember your context and preferences across sessions and tools. Together they cover identity and memory. Keep its `.umem/` directory out of version control (this repo's .gitignore already does).

## Contributing

Issues and PRs are welcome, see [CONTRIBUTING.md](CONTRIBUTING.md). Release history lives in the [CHANGELOG](CHANGELOG.md).

## License

[MIT](LICENSE)
