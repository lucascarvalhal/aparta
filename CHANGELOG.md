<p align="right"><b>English</b> | <a href="CHANGELOG.pt-BR.md">Português (Brasil)</a></p>

# Changelog

All notable changes to aparta are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/lucascarvalhal/aparta/compare/v0.6.1...HEAD
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
