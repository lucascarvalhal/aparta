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

**aparta** isolates your development accounts, git, GitHub CLI, gcloud, AWS, SSH keys, per project folder, and makes your terminal AI agents (Claude Code, Codex, Gemini CLI, Antigravity) use the right identity, always. *Aparta* is Portuguese for "set apart".

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

Upgrading later: just run `aparta update`, it detects how aparta was installed and runs the right upgrade. aparta also tells you when a new version is out (checked at most once a day), and the wizard's first run asks whether you prefer automatic or manual updates; `APARTA_UPDATES=off` disables the check entirely. Shell autocompletion: `aparta --install-completion`.

## Languages

The CLI speaks English and Brazilian Portuguese. The first run of the wizard asks which one you prefer and remembers it; `APARTA_LANG=en` or `APARTA_LANG=pt` overrides the saved choice, and without any of that the locale (`LANG`) decides.

## Quick start

```bash
aparta            # first run opens the wizard; later runs open a menu
```

1. On the very first run, pick your language and whether updates should be automatic or manual.
2. Pick which AI agents should receive per-project environment (Claude Code, Codex, Gemini CLI, Antigravity, opencode, or a generic `.envrc` via direnv).
3. Pick which providers to configure (GitHub CLI, Google Cloud, AWS), or keep them all for a full sweep. git and SSH are always included.
4. Choose **"Detect what I already use"** (recommended) or **"Start from zero"**.
5. Confirm each suggested profile, name, folder, git e-mail, SSH key, remote alias and accounts all come pre-filled from the scan.
6. Optionally adopt stray repos that live outside your profile folders (they keep their location; identity is applied locally via a git `include.path`).
7. Review the summary, confirm once. Done.

```bash
aparta doctor     # verify everything actually resolves to the right identity
aparta scan       # read-only: show detected project groups
aparta apply X    # re-apply a profile (e.g. after cloning new repos)
aparta remove X   # remove a profile and undo what it applied (backups kept)
aparta list       # list configured profiles
aparta add bitbucket       # add a provider to the current worktree
aparta add repo bitbucket  # or target a unique repo/workspace explicitly
aparta login      # reauthenticate the current worktree when needed
aparta login X    # or target a workspace/profile from another folder
aparta status     # active workspace, providers, health and known expiry
aparta check      # check every credential, quiet when all is well
aparta run -- cmd # run any command with the folder's profile environment
aparta env        # print the profile's exports for scripts: eval "$(aparta env)"
aparta shell-install # install automatic zsh activation
aparta fallback   # what runs outside any profile; --secure makes it neutral, --restore undoes it
aparta update     # update aparta to the latest release
aparta help       # every command and what it does
aparta --dry-run  # any command: show diffs, change nothing
aparta --verbose  # any command: show every file, backup and diff
```

On installations created before exact workspaces existed, the first `aparta add`
inside a repo materializes its provider list instead of inheriting every provider
from the profile. Run `aparta add git` for a Git-only repo, then add only the extra
providers that checkout actually uses.

## When credentials expire

Cloud sessions do not last forever: Google Workspace defaults to 16 hours for new customers, and organizations can set anything from 1 to 24. aparta deals with that in three steps:

- **Silent renewal while it is possible.** As long as the refresh token lives, aparta renews the access token for you and you never notice anything.
- **A warning before it hurts, not after.** The prompt always identifies the active workspace. When a provider exposes a non-renewable expiry, a countdown appears during the last 30 minutes. Automatically refreshed credentials are labeled renewable instead of showing a misleading timer. `APARTA_EXPIRY_WARNING_MINUTES` changes the threshold.
- **One command that cannot land in the wrong place.** `aparta login` resolves the current worktree; `aparta login <workspace-or-profile>` works from anywhere. Login runs inside the selected profile's own scope, skips valid credentials, and `--provider gcloud|gh|adc|aws` targets one credential.
- **The ADC is checked the way the libraries see it.** gcloud holds a cached reauthentication proof, so its own probe can say "valid" while Terraform, Dataform and every SDK get `invalid_rapt` from a plain refresh. aparta probes the profile's application default credentials with that plain refresh, and `aparta login` creates or renews them inside the profile's scope. A workspace that does not enable ADC is not nagged; one that enables it is blocked until its isolated file exists.
- **AWS is covered by the same principle.** The probe is the STS call every SDK makes; an expired SSO session is renewed with `aws sso login` in the profile's scope, and profiles on static keys are pointed at `aws configure`, the only thing that can refresh those.
- **The warning shows up where the accident happens.** aparta installs a startup check through each agent's own mechanism, so the message appears inside Claude Code, Codex, Gemini CLI, Antigravity or opencode, not only when you run aparta yourself. The check reads a cache, so nothing waits on the network.

Reauthentication itself cannot be automated: the browser step and the security key exist precisely to require a person. What aparta removes is the guessing, the wrong terminal and the surprise.

## Outside any profile

Whatever runs outside a configured folder falls back to the global default, and that default is whatever you happened to select last. On a machine with client work, that usually means a stray terminal, script or agent acts as a client without anyone noticing.

`aparta fallback` shows what would happen right now, including the global ADC, the file every Google library falls back to, with its health verdict. `aparta fallback --secure` points the global gcloud default at an empty configuration and parks the global ADC next to its original path, so both commands and libraries outside a profile fail loudly instead of borrowing an identity. `aparta fallback --restore` puts both back. Your named configurations, per-profile credentials and projects are never touched.

GitHub is reported but not changed: gh keeps the active token in the system keyring and falls back to it even without an active user, so the only way to disable it would be a logout that destroys the token. Per-profile config dirs, which aparta already sets in every configured folder, remain the answer there.

## Scripts and plain shells

`aparta shell-install` adds automatic zsh activation once. From then on, entering a registered repository or worktree selects its exact workspace, clears selectors inherited from another client and shows the credential countdown in the right prompt. Leaving registered workspaces clears the managed environment again.

Agents also receive the workspace environment through their adapters. Scripts can request that same environment explicitly:

```bash
aparta run -- terraform apply          # any command, with the folder's profile env
aparta run --profile work -- gcloud storage ls   # or name the profile explicitly
eval "$(aparta env)"                   # the same variables as export lines, for scripts
```

The workspace is resolved from the exact Git top-level, so sibling worktrees can safely use different profiles and providers. `--with-gh-token`, on both commands, additionally exports `GITHUB_TOKEN` read from the profile's gh, useful for Terraform's GitHub provider; it is opt-in because it materializes a keyring secret into the environment of every child process.

## Two ways to separate gcloud

When a profile uses Google Cloud, the wizard asks how far the separation should go:

- **Isolated (recommended).** The profile gets its own gcloud config directory, seeded from your global one and pruned to that profile's account. Credentials, named configurations and the application default credentials live inside it, so the gcloud CLI, the SDKs, Terraform and anything your agents run all follow the profile. A seeded directory is a few dozen kilobytes, because logs and the bundled virtualenv are never copied.
- **Light.** Only the active configuration changes, which is enough for the `gcloud` command itself. Credentials stay global, so SDKs and Terraform keep using whichever account logged in last. Pick this if you do not want a second copy of anything.

## What each profile configures

| Tool | Mechanism |
|---|---|
| git | private config per exact checkout under Aparta's config directory, selected by its absolute Git dir; linked worktrees can resolve different `user.email` values even when they share `.git` storage |
| GitHub CLI | copy of `~/.config/gh` to `~/.config/gh-<profile>` + `gh auth switch` inside the copy; selected via `GH_CONFIG_DIR` (tokens stay in your keyring, no re-login) |
| gcloud | isolated mode (recommended): the profile's own config dir with its own credentials and ADC, selected via `CLOUDSDK_CONFIG`; light mode: a named configuration selected via `CLOUDSDK_ACTIVE_CONFIG_NAME` |
| AWS | your existing named profiles in `~/.aws`; selected via `AWS_PROFILE`, honored by the CLI, every SDK, Terraform and the CDK |
| SSH | workspace Git config with a dedicated key and optional host-alias rewrite; the shell and agents also receive an exact `GIT_SSH_COMMAND` |
| Stray repos | the same exact Git-dir binding as any other workspace, without moving the folder or writing a shared local identity |

## Supported AI agents

| Agent | Injection mechanism | Expiry warning |
|---|---|---|
| Claude Code | `env` field in `.claude/settings.local.json` (merged) | `SessionStart` hook |
| Codex CLI | [`[shell_environment_policy.set]`](https://developers.openai.com/codex/config-reference) in the repo's `.codex/config.toml` | `SessionStart` hook (Codex asks you to trust it once) |
| Gemini CLI | project `.gemini/.env` (loaded natively by the CLI) | `SessionStart` hook in `.gemini/settings.json` |
| Antigravity | `terminal.integrated.env.{osx,linux}` in `.vscode/settings.json` | task that runs on folder open |
| opencode | generated `shell.env` plugin in `.opencode/plugins/aparta-env.js` | same plugin, at startup and on each new session |
| Cursor CLI | no native per-project env, inherits the shell, covered by the direnv adapter | through direnv |
| direnv (generic) | `export` lines in `.envrc`, works for any tool (needs [direnv](https://direnv.net) installed and a one-time `direnv allow` per repo) |

Adding a new agent = dropping one file in `src/aparta/agents/` (auto-registered).

## Safety model

- Every write to an existing file creates a timestamped backup and **merges**: aparta never overwrites your dotfiles.
- `--dry-run` previews every change as a diff.
- The scan is 100% read-only.
- Workspace activation clears inherited credential, account, project and Git selectors before applying the exact workspace. Missing isolated ADC files fail closed instead of falling back to a global account, and a resolver failure clears the previous workspace instead of retaining it.
- Nothing is sent anywhere. No telemetry, no network calls beyond the ones *you* trigger (`gh auth login`, `gcloud auth login`).

## Roadmap

Planned providers, in rough order:

- Azure CLI: parallel config directories via `AZURE_CONFIG_DIR`
- Kubernetes: per-profile kubeconfig via `KUBECONFIG`
- Docker: per-profile context via `DOCKER_CONTEXT`
- GitLab CLI (glab): parallel config directories via `GLAB_CONFIG_DIR`
- Terraform Cloud: per-profile credentials via `TF_CLI_CONFIG_FILE`
- More AI agents as they gain per-project config support

## We strongly recommend using

- [Orca](https://www.onorca.dev/): an Agent Development Environment that runs several AI agents at once in isolated worktrees, with terminals, editor and browser in one app. Every agent Orca launches inherits the per-folder identity that aparta configured, so parallel agents across different clients stay on the right accounts.
- [Universal Memory (U-Mem)](https://universal-memory.com/): a local-first, vendor-agnostic memory layer for AI agents. aparta makes every agent use the right account per folder; U-Mem makes them remember your context and preferences across sessions and tools. Together they cover identity and memory. Keep its `.umem/` directory out of version control (this repo's .gitignore already does).

## Contributing

Issues and PRs are welcome, see [CONTRIBUTING.md](CONTRIBUTING.md). Release history lives in the [CHANGELOG](CHANGELOG.md).

## License

[MIT](LICENSE)
