<p align="right"><b>English</b> | <a href="CHANGELOG.pt-BR.md">Português (Brasil)</a></p>

# Changelog

All notable changes to aparta are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- `aparta apply` no longer writes `~/.gitconfig-<profile>` or a broad
  includeIf for the profile root. Every checkout has been bound through its
  own workspace gitconfig since 0.8.0, so the old file was written and then
  ignored; `aparta remove` still cleans it up on older installs.
- `aparta doctor` and `aparta remove` skip repositories that belong to a
  profile nested inside another, the same rule `aparta apply` already used.
  A parent profile no longer reports the nested profile's repositories as
  wrong.
- The GitHub credential probe confirms the token belongs to the expected
  user; a config dir logged into another account is reported as needing a
  login.
- `APARTA_AUTH_CHECK=off` now silences every credential read, including
  `aparta status` and `aparta check`.
- Adapters that end up with no aparta variables remove their file instead of
  leaving an empty one behind.

### Removed

- `gitlab` and `bitbucket` are no longer accepted by `aparta add`; they
  recorded a provider that changed nothing.

### Internal

- Agent adapters share one merge, validate, remove and hook algorithm on top
  of a file format strategy each; adding an agent is a few lines.
- Credential probes and interactive logins are table driven in `auth.py`;
  profile paths and persistence live in `config.py`; shared prompts in
  `prompts.py`; repository enumeration in `workspaces.py`.
- The wizard's subprocess helpers moved to the backends (`ssh.py` is new),
  and doctor's diagnosis is one function per area.
- `aparta help` is generated from the registered commands, so it cannot
  drift from `aparta <command> --help`; both are localized.
- Credential states are an enum, the gcloud isolated directory is written
  through SafeWriter, git is invoked through one helper, and the
  profile-to-provider mapping has a single source in `Profile.provider_env`.
- Tests fail when a string passed to `_()` has no catalog entry or when the
  catalog carries an entry nothing uses.

## [0.8.2] - 2026-09-17

### Changed

- The shell prompt segment now says `reauth needed` (or `reautenticar` in
  Portuguese) when a credential needs a human, instead of a bare `blocked`
  that named the consequence rather than the action.
- `aparta login` derives the application default credentials from the
  freshly renewed gcloud login when Google accepts it, so one expired
  session costs one trip to the browser instead of two. The copy is probed
  like a library first; if it does not pass, the interactive ADC login runs
  as before.
- `aparta login <profile> --provider adc` now renews the application
  credentials on request, like `--provider gcloud` already did for the CLI
  credential, instead of reporting them valid and doing nothing.

### Fixed

- The ADC login no longer stops at "Do you want to continue (Y/n)?". gcloud
  asked because the profile environment pins GOOGLE_APPLICATION_CREDENTIALS
  at the very file it was about to write; the login now runs without that
  variable, and CLOUDSDK_CONFIG alone keeps the file inside the profile.
- `aparta remove` now strips every aparta-managed key from the agent
  configurations, including the workspace Git include, and deletes the
  profile's isolated gcloud directory instead of leaving credentials.db
  behind.
- The GitHub CLI directory is resolved through XDG_CONFIG_HOME on apply and
  remove, the same path the injected environment points at.
- gcloud backend commands run with a scrubbed environment, so a CLOUDSDK
  selector inherited from the shell cannot redirect them to another profile.
- Credential error classification checks the organization policy expiry
  before the generic revoked marker and no longer matches the bare
  substring "sso" inside ordinary words.
- Parking and restoring the global ADC go through SafeWriter, with a backup.
- A credential cache written by another aparta version no longer breaks
  every command at startup.
- The test suite scrubs the variables the aparta zsh hook exports, so it
  passes from inside a registered workspace.

### Removed

- Planning notes and the agent policy file no longer ship in the repository,
  and every test fixture uses fictional companies and people.

## [0.8.1] - 2026-09-02

### Fixed

- The first `aparta add` in a legacy workspace now materializes an exact
  provider list containing Git and the requested provider. Repositories no
  longer inherit unrelated gcloud or ADC access from the whole profile and no
  longer show `blocked` when those cloud providers are not used there.

## [0.8.0] - 2026-09-02

### Added

- Exact workspace records bind each Git checkout or linked worktree to one
  profile and an explicit provider set. Sibling worktrees can now run at the
  same time with different gcloud, ADC, AWS, GitHub and SSH selectors.
- `aparta add <provider>` uses the current workspace, while `aparta add
  <workspace> <provider>` targets one explicitly. `aparta login` and `aparta
  status` follow the same contextual rule.
- `aparta shell-install` installs automatic zsh activation on directory
  changes. The right prompt shows the active workspace and cached credential
  lifetime without opening a login flow. Login remains an explicit action.

### Changed

- CI now runs for both `dev` and `main`, and provisions zsh before testing the
  automatic shell activation behavior on Linux runners.
- Workspace activation now clears every Aparta-managed selector before
  applying the exact workspace environment. An isolated ADC path is pinned
  even before its file exists, so Google libraries fail closed instead of
  falling back to the global ADC. `aparta run` reconfirms a cached expiration
  before blocking a protected command, and blocks a selected ADC locally when
  its isolated file is missing. Empty prompt caches show unknown, never a
  false green state.
- Adding or applying a workspace reconciles its agent configuration with only
  the providers enabled there. The Codex adapter now writes the supported
  `[shell_environment_policy.set]` table and migrates Aparta-owned keys from
  the old `[env]` table while preserving unrelated user configuration.
- Git and SSH now use a private config bound to each checkout's absolute Git
  dir. This distinguishes linked worktrees that share common repository
  storage, migrates old broad and shared local includes, and preserves
  unrelated global Git settings. Credential, account, project and repository
  override variables are cleared before the exact workspace values are set.
- Resolver failures clear the previous shell identity. Unknown network health
  is reported without opening a browser; an explicit provider still allows a
  user to force the intended login.

## [0.7.0] - 2026-08-28

### Added

- `aparta run -- <command>` runs any command with the profile environment
  of the current folder, exactly as the agents get it. A plain shell
  inherits nothing from the adapters, so people were writing wrapper
  scripts that re-export the paths by hand and forget the parts that
  matter (the pinned `CLOUDSDK_ACTIVE_CONFIG_NAME`, the existence check
  before exporting `GOOGLE_APPLICATION_CREDENTIALS`). The profile comes
  from the deepest root owning the folder, adopted repos included;
  `--profile` overrides.
- `aparta env [profile]` prints the same variables as shell-safe `export`
  lines, for `eval "$(aparta env)"` in scripts.
- `--with-gh-token`, on both, also exports `GITHUB_TOKEN` read from the
  profile's gh. Strictly opt-in: the token lives in the OS keyring, and
  materializing it into the environment exposes it to child processes.

## [0.6.8] - 2026-08-28

### Added

- `aparta fallback` now covers the global ADC, the other half of the
  fallback identity. The report shows the file with its library-style
  health verdict, `--secure` parks it next to the original (so libraries
  outside a profile fail loudly instead of silently borrowing a stale
  credential, which is how a nine-day-old ADC bit a Dataform run), and
  `--restore` puts it back. Run again after a new ADC appears, `--secure`
  parks that one too instead of saying there is nothing to do.

## [0.6.7] - 2026-08-28

### Changed

- The ADC probe now refreshes the credential the way the Google libraries
  do, straight against the token endpoint, instead of asking gcloud.
  gcloud holds a cached reauthentication proof (RAPT), so its own probe
  said "valid" while Terraform, Dataform and every other library got
  invalid_rapt from a plain refresh; only a plain refresh tells the truth
  about what a library will see. Service-account files keep the gcloud
  probe, since they do not sit behind reauth policies.

### Added

- AWS joined the credential check and `aparta login`: the probe is the
  same STS call every SDK makes, an expired SSO session is renewed with
  `aws sso login` in the profile's scope (`--provider aws` targets it
  directly), and profiles on static keys are pointed at `aws configure`,
  the only thing that can refresh those.
- The ADC browser flow cannot preselect an account, so the login now says
  which account to pick before opening the browser.

## [0.6.6] - 2026-08-21

### Fixed

- The credential check now covers the profile's application default
  credentials too. The CLI credential and the ADC are two independent
  credentials the same reauth policy expires on separate schedules, so
  `gcloud` commands could work all day while Terraform tripped on an
  expired ADC, and `aparta login` looked at the first, said "still valid"
  and skipped the browser. The check, the doctor and the agent startup
  hooks now probe the ADC as its own credential, `aparta login` renews an
  expired one inside the profile's scope, and `--provider adc` targets it
  directly. A profile that chose to live without an ADC is not probed and
  not nagged.

## [0.6.5] - 2026-08-20

### Fixed

- `aparta login` now creates the profile's application default credentials
  itself, inside the isolated scope. The old message told the user to run
  `gcloud auth application-default login` by hand, but in a plain shell that
  command writes the global ADC every profile would share, the exact leak
  the isolation exists to prevent. The login now offers the browser flow
  with the profile's environment and re-applies the profile afterwards, so
  the SDKs that only honor `GOOGLE_APPLICATION_CREDENTIALS` see the new
  file.
- `aparta login` no longer drags the user through a browser login for a
  credential that is still valid; only what needs a human runs, and
  `--provider` still forces a specific one.
- The GitHub login no longer dies with "unexpected escape sequence from
  terminal". Terminals answer status queries on stdin, and gh's prompt
  aborts on the leftover bytes; aparta now drains them before handing over
  the terminal.

## [0.6.4] - 2026-08-20

### Fixed

- `aparta update` no longer says an install is current when a release was
  announced but is not installable yet. PyPI's JSON API lists a version
  before the index installers read, and in that window the upgrade finds
  nothing to do; aparta now names the wait instead of contradicting the
  line it just printed.

## [0.6.3] - 2026-08-20

### Fixed

- `aparta update` says what the upgrade actually did. The upgrade command
  exits successfully even when it changes nothing, which is what happens
  while a fresh release has not propagated to PyPI's index yet, and aparta
  reported an update either way. It now names the version it moved to, or
  says the install was already current.

## [0.6.2] - 2026-08-20

### Fixed

- Isolated gcloud directories no longer carry the other profiles'
  configurations. Seeding copied all of them, so a directory could name an
  account it had no business naming, and a `CLOUDSDK_ACTIVE_CONFIG_NAME`
  left in the shell picked it. Each directory now holds exactly one
  configuration, named after the profile and pinned through the injected
  environment, which an agent cannot unset the way a shell can. Running
  `aparta apply` cleans up directories created by earlier versions.
- `aparta apply` clears variables the profile no longer sets. Injection only
  merged, so anything that dropped out stayed behind, which after the 0.6.1
  fix left `GOOGLE_APPLICATION_CREDENTIALS` pointing at a file that no longer
  exists.
- `aparta doctor` checks gcloud with the same environment the agents receive,
  so it can no longer pass while the real thing resolves a different account.

## [0.6.1] - 2026-08-20

### Fixed

- Isolated profiles no longer inherit the global application default
  credentials. There is only one such file per machine, from whoever ran
  `gcloud auth application-default login` last, so copying it would give
  every profile the same identity. A profile now starts without it, doctor
  says so, and `aparta login` points at the command that creates its own.

## [0.6.0] - 2026-08-20

### Added

- Isolated gcloud mode: a profile can own its whole gcloud config directory
  through `CLOUDSDK_CONFIG`, so credentials and the application default
  credentials are separated too, not just the active configuration. The
  directory is seeded from the global one and pruned to that profile's
  account, and `GOOGLE_APPLICATION_CREDENTIALS` is exported alongside it
  because the Node and Go libraries, and therefore Terraform, ignore
  `CLOUDSDK_CONFIG`.
- `aparta login <profile>`: reauthenticates inside the profile's own scope
  and reasserts the expected account, so a login can no longer land in the
  wrong configuration.
- `aparta check`: credential health for every profile, with silent renewal
  while the refresh token lives and four honest states, where a network
  failure is unknown rather than a false alarm.
- Expiry warnings inside the agents themselves, through each agent's own
  mechanism: SessionStart hooks for Claude Code, Codex and Gemini CLI, a
  folder-open task for Antigravity, the generated plugin for opencode, and
  direnv for everything else.
- `aparta doctor --fix`: repairs what is deterministic (gcloud account and
  project, agent env, includeIf, gh config dir) and only reports what needs
  a person.
- `aparta fallback`: shows what runs outside any profile, and `--secure`
  makes the global gcloud default empty so stray commands fail instead of
  borrowing a client identity. `--restore` puts it back.
- The wizard asks for the name shown on commits, pre-filled from the
  profile's gitconfig or the global one.

### Fixed

- The per-profile gitconfig is merged instead of regenerated, so `user.name`,
  comments and any other key you had there survive an apply.

## [0.5.0] - 2026-08-19

### Added

- `aparta update`: self-update that detects the install method (uv tool,
  pipx, pip or ephemeral uvx/npx) and runs the matching upgrade. aparta
  announces new releases (checked at most once a day, `APARTA_UPDATES=off`
  disables it) and the wizard asks whether updates should be automatic or
  manual.
- AWS support: profiles get an `aws_profile` selected from your existing
  `~/.aws` named profiles (or created via `aws configure`), injected into
  agents as `AWS_PROFILE` and checked by `aparta doctor`.
- Provider selection step in the wizard: pick which providers to configure
  (GitHub CLI, Google Cloud, AWS) or keep the full sweep.

## [0.4.4] - 2026-08-19

### Security

- The sdists of 0.4.1 through 0.4.3 accidentally included local development
  files and were removed from PyPI (the wheels were never affected). Sdists
  now build from an explicit allowlist, so stray files cannot ship again.

### Changed

- Supported platforms are stated explicitly: macOS, Linux and Windows
  through WSL. Native Windows support leaves the roadmap.
- The README recommends Orca and Universal Memory as companion tools.

## [0.4.3] - 2026-08-19

### Changed

- Supported platforms are stated explicitly: macOS, Linux and Windows
  through WSL. Native Windows support leaves the roadmap.

## [0.4.2] - 2026-08-19

### Changed

- The Brazilian Portuguese documentation is rewritten as native text with a
  friendlier voice instead of a literal translation (README, CONTRIBUTING,
  SECURITY).
- Conversational CLI messages in Portuguese got the same natural-voice pass.

## [0.4.1] - 2026-08-19

### Added

- `aparta remove <profile>`: deletes a profile and undoes everything it
  applied (agent env vars, adopted-repo includes, gitconfig and includeIf,
  gh config dir, gcloud configuration), with backups and `--dry-run`.
- `aparta help`: localized overview of every command.
- First-run language question in the wizard (English or Portuguese),
  persisted; `APARTA_LANG` still overrides.
- Localized yes/no confirmations (`y/N` in English, `s/N` in Portuguese).
- Shell autocompletion documented (`aparta --install-completion`).
- Screenshots and the demo recording now exist in both languages, generated
  from the real message catalog.

### Changed

- Documentation is English-first across the repo, with Brazilian Portuguese
  twins (README, CONTRIBUTING, SECURITY, this changelog).
- The install guide now recommends `uv tool install aparta`.

## [0.4.0] - 2026-08-19

### Added

- Full internationalization: canonical English strings with a complete
  Brazilian Portuguese catalog, selected by `APARTA_LANG` or the locale.
- opencode adapter through a generated `shell.env` plugin.
- Home-wide repository scan with no folder-name assumptions; the wizard can
  scan extra folders and `aparta scan` accepts explicit paths.
- `Profile.git_host` parameterizes remote URL rewriting (GitLab, Bitbucket
  and self-hosted hosts work).
- npm launcher package `aparta-cli`, so `npx aparta-cli` runs the CLI.
- Release automation: tag-driven workflow publishing to PyPI and npm via
  trusted publishing, gated by protected environments and a version check.

### Changed

- New application layer (`apply.py`) with a backend registry; adapters
  expose `read_env` and discovery reads previous setups through the
  registry.
- Paths honor `XDG_CONFIG_HOME` and `CLOUDSDK_CONFIG`.

### Fixed

- A repo with a broken JSON/TOML config no longer aborts apply or doctor.
- `gh auth switch` ran with a stripped environment that could break keyring
  access.
- Locale-safe detection of existing gcloud configurations.

## [0.3.0] - 2026-08-18

### Added

- Start modes in the wizard: detect existing setup or start from scratch.
- Connect flows: new GitHub/Google accounts logged in straight into the
  profile's isolated config, SSH key generation with upload via
  `gh ssh-key add`.
- Stray-repo adoption: repos outside profile roots get the profile identity
  through a local git include, without moving folders.
- Discovery pre-fills SSH keys, host aliases, gh users, gcloud accounts and
  GCP projects from existing configuration.
- SSH host aliases from `~/.ssh/config` offered as a select for remote
  rewriting.

## [0.2.0] - 2026-08-18

### Added

- Disk discovery: existing `includeIf` blocks and repositories grouped by
  folder and commit e-mail become pre-filled wizard suggestions.
- `aparta scan` read-only command.
- Per-group header and unified wording in the wizard.

## [0.1.0] - 2026-08-18

### Added

- First release: `init` wizard, `apply`, `doctor`, `list`, global
  `--dry-run`.
- Backends: git (`includeIf` plus per-profile gitconfig), GitHub CLI
  (parallel config dir via `GH_CONFIG_DIR`), gcloud (named configurations).
- Agent adapters: Claude Code, Codex CLI, Gemini CLI, Antigravity, direnv.
- SafeWriter: timestamped backups, merges, dry-run diffs.

[Unreleased]: https://github.com/lucascarvalhal/aparta/compare/v0.8.2...HEAD
[0.8.2]: https://github.com/lucascarvalhal/aparta/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/lucascarvalhal/aparta/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/lucascarvalhal/aparta/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/lucascarvalhal/aparta/compare/v0.6.8...v0.7.0
[0.6.8]: https://github.com/lucascarvalhal/aparta/compare/v0.6.7...v0.6.8
[0.6.7]: https://github.com/lucascarvalhal/aparta/compare/v0.6.6...v0.6.7
[0.6.6]: https://github.com/lucascarvalhal/aparta/compare/v0.6.5...v0.6.6
[0.6.5]: https://github.com/lucascarvalhal/aparta/compare/v0.6.4...v0.6.5
[0.6.4]: https://github.com/lucascarvalhal/aparta/compare/v0.6.3...v0.6.4
[0.6.3]: https://github.com/lucascarvalhal/aparta/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/lucascarvalhal/aparta/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/lucascarvalhal/aparta/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/lucascarvalhal/aparta/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/lucascarvalhal/aparta/compare/v0.4.4...v0.5.0
[0.4.4]: https://github.com/lucascarvalhal/aparta/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/lucascarvalhal/aparta/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/lucascarvalhal/aparta/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/lucascarvalhal/aparta/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/lucascarvalhal/aparta/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/lucascarvalhal/aparta/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/lucascarvalhal/aparta/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/lucascarvalhal/aparta/releases/tag/v0.1.0
