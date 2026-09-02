# Workspace Isolation and Automatic Activation Design

## Goal

Make the Git repository or linked worktree containing the current directory the
unit of identity isolation. Entering a registered workspace activates its
profile automatically, concurrent terminals remain independent, and no
configured workspace can fall back to credentials inherited from another
client.

## Product model

An Aparta profile owns reusable identity and credential configuration for a
client, such as Whirlpool or Eneva. A workspace is one exact Git checkout,
either the main checkout or a linked worktree. A workspace points to one
profile and records which providers are enabled there.

Workspace records live in the user's Aparta config directory, not inside the
repository. This prevents accidental commits and permits two worktrees of the
same repository to have different provider selections. Each record contains:

- A stable name.
- The canonical absolute worktree path.
- The owning profile name.
- The enabled provider names.

Git and SSH settings are rendered into a private config keyed by the canonical
workspace path. Aparta binds that file to the checkout's absolute Git dir, not
only to its visible folder. This matters for linked worktrees because their Git
dirs live under the main repository's common storage. Existing broad profile
includes and shared adopted-repository includes are migrated to exact bindings;
unrelated global Git settings remain intact.

Existing profiles remain valid. Until a workspace has an explicit provider
selection, it derives the configured providers from its profile. The first
`aparta add` materializes an explicit workspace record and preserves those
existing providers before adding the new one.

## Workspace resolution

Contextual commands resolve the exact Git top-level containing the current
directory. They then find the explicit workspace with that canonical path. If
there is no explicit record, the existing deepest-profile-root and adopted-repo
rules provide backward-compatible ownership.

An explicit selector may be:

- A registered workspace name.
- A canonical or user-provided path to a registered workspace.
- A unique repository basename discovered under the configured profile roots,
  including before its first explicit workspace record is materialized.
- A profile name for commands that operate on profile credentials, provided
  the operation does not need to choose among multiple workspace records.

Ambiguous selectors fail with a list of candidates. Aparta never guesses an
identity from whichever provider account happens to be globally active.

## Command contracts

### `aparta add`

```text
aparta add <provider>
aparta add <workspace> <provider>
```

With one argument, the current worktree is the target. With two arguments, the
first selects the target workspace and the second names the provider. The
operation is idempotent. It preserves existing provider configuration and
reports an already enabled provider without duplicating it.

The first implementation accepts the providers Aparta can already isolate:
`git`, `ssh`, `github` (`gh` alias), `gcloud`, `adc`, and `aws`. Forge names
`gitlab` and `bitbucket` are registered as Git/SSH workspace providers so the
provider model and CLI no longer assume GitHub. Interactive token provisioning
for forge APIs remains a separate provider adapter because tokens require a
defined secret-store contract and must never be written to repository files.

### `aparta login`

```text
aparta login
aparta login <workspace-or-profile>
aparta login <workspace-or-profile> --provider <provider>
```

Without an argument, login resolves the current worktree and its owning
profile. An explicit selector keeps the existing ability to authenticate from
another directory. Without `--provider`, Aparta probes every configured
credential and opens an interactive login only for missing or expired ones.
Unknown health, such as a network timeout, is reported without opening a
browser. An explicit provider continues to force that provider's login.

Entering a directory never opens a browser or authentication prompt.

### `aparta status`

```text
aparta status
aparta status <workspace-or-profile>
aparta status --shell
```

Human output shows the workspace, profile, effective provider selectors, and
credential health. Shell output is compact and contains no secrets. It reports
the earliest known non-renewable expiry. Providers whose short-lived access
tokens refresh automatically are reported as renewable instead of showing a
misleading countdown.

The default warning threshold is 30 minutes. It may be overridden with
`APARTA_EXPIRY_WARNING_MINUTES`.

## Fail-closed environment

Aparta owns a finite list of selector variables. Before applying a workspace,
it removes every owned key from the child or shell environment, then adds only
the selected workspace's values. This prevents a workspace without GitHub,
AWS, or Google configuration from retaining those selectors from the previous
client.

For isolated Google profiles, `CLOUDSDK_CONFIG` always points to the profile's
private gcloud directory. `GOOGLE_APPLICATION_CREDENTIALS` always points
inside that same directory, even before the ADC file exists. A missing file
there makes Google libraries fail instead of continuing through the global ADC
search chain.

Light gcloud profiles remain readable for compatibility but are marked unsafe
for automatic activation. Aparta does not claim fail-closed isolation for them.
Adding `gcloud` or `adc` to a workspace requires isolated mode.

`aparta run` uses the same clean environment construction and refuses to run
when a selected provider has a credential state that requires a person. An
unknown state caused by network failure is displayed but is not treated as an
expired credential. A selected ADC whose isolated file does not exist is a
local missing-credential state and is blocked even before a cached probe. The
same boundary applies to explicit `aparta run --profile` calls.

## Automatic shell activation

Aparta installs one marked, reversible line in the user's zsh startup file.
That line evaluates a generated hook. The hook registers `chpwd` and `precmd`
functions without replacing the user's existing hooks.

On directory change, the hook evaluates `aparta env --activate`. That command:

1. Clears all Aparta-managed selectors from the shell.
2. Resolves the exact current worktree.
3. Exports only that workspace's selectors and metadata.
4. Leaves the shell clean when the directory is unregistered.

If parsing or resolution fails, the generated hook still removes the previous
workspace's selectors. A broken registry cannot keep another client's identity
active.

The hook decorates `RPROMPT` without modifying the user's base prompt. It
always shows the active workspace. A countdown appears only when a known,
non-renewable credential expiry is within 30 minutes. Expired or invalid
credentials show a blocked state and direct the user to `aparta login`.

No login is started automatically. Processes already running keep their
original environment. New processes inherit the current terminal's workspace,
which allows Whirlpool and Eneva agents to run simultaneously.

## Agent integration

Project-level agent adapters remain a second activation path for launchers that
do not start from an interactive shell.

The Codex adapter writes environment overrides under
`shell_environment_policy.set`, the supported project configuration key. It
applies to every selected repository even if `.codex/` does not exist yet and
preserves unrelated TOML. Existing Aparta-owned keys in the obsolete `[env]`
table are removed during migration. SessionStart hooks remain installed.

Claude Code and other adapters keep their native project mechanisms. Every
adapter reconciles all managed keys so a provider removed from a workspace
cannot remain as stale configuration.

## Safety and compatibility

- No global provider configuration is selected or mutated during activation.
- Existing user configuration is merged and backed up when an installer must
  touch a shell startup file.
- Generated shell output is quoted and contains no arbitrary repository text.
- Workspace records and credential health caches are private user config, not
  repository content.
- Existing profile-only commands and configuration files continue to load.
- Dry-run covers workspace registration and shell hook installation.

## Verification

Focused tests cover exact worktree resolution, ambiguous selectors, provider
idempotency, contextual login, managed-variable clearing, Google ADC blocking,
concurrent environment construction, shell hook transitions, prompt warning
thresholds, and Codex TOML migration. The complete pytest suite remains the
final regression gate.
