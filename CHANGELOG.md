<p align="right"><b>English</b> | <a href="CHANGELOG.pt-BR.md">Português (Brasil)</a></p>

# Changelog

All notable changes to aparta are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/lucascarvalhal/aparta/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/lucascarvalhal/aparta/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/lucascarvalhal/aparta/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/lucascarvalhal/aparta/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/lucascarvalhal/aparta/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/lucascarvalhal/aparta/releases/tag/v0.1.0
