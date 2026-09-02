# Workspace Isolation and Automatic Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Isolate credentials by exact Git checkout, add contextual provider and login commands, and activate registered workspaces automatically in zsh.

**Architecture:** Keep profile credentials reusable while persisting exact workspace bindings separately. Build every runtime environment by clearing all Aparta-owned selectors before applying one workspace, then expose the same resolver to the CLI, shell hook, and agent adapters.

**Tech Stack:** Python 3.10+, Typer, Rich, TOML via tomli/tomli-w, pytest, zsh hook generation.

**Spec:** `docs/superpowers/specs/2026-09-02-workspace-isolation-design.md`

## Global Constraints

- The exact Git repository or linked worktree is the workspace boundary.
- Configured workspaces must never fall back to inherited global provider selectors.
- Entering a directory activates context but never starts an interactive login.
- Existing profiles and user configuration remain compatible and are merged, not overwritten.
- The prompt countdown appears only for known non-renewable expiry within 30 minutes.
- Token values must never be written to repository files or shell status output.

---

### Task 1: Workspace registry and exact resolver

**Files:**
- Create: `src/aparta/workspaces.py`
- Create: `tests/test_workspaces.py`
- Modify: `src/aparta/runner.py`

**Interfaces:**
- Consumes: `Profile`, `load_profiles()`, and the existing deepest-root ownership rule.
- Produces: `Workspace`, `load_workspaces()`, `save_workspaces()`, `git_workspace_root()`, `resolve_workspace()`, and `workspace_for_path()`.

- [x] **Step 1: Write failing persistence and exact-resolution tests**

```python
def test_workspace_roundtrip_and_exact_worktree_resolution(tmp_path):
    record = Workspace(name="eneva-api", path=str(tmp_path / "wt"), profile="eneva", providers=["git", "gcloud"])
    save_workspaces({record.name: record}, SafeWriter(), tmp_path / "workspaces.toml")
    assert load_workspaces(tmp_path / "workspaces.toml")[record.name] == record

def test_current_worktree_beats_broad_profile_root(tmp_path):
    profile = Profile(name="eneva", root=str(tmp_path), git_email="dev@eneva.com")
    workspace = Workspace(name="feature", path=str(tmp_path / "repo-feature"), profile="eneva", providers=["git"])
    assert workspace_for_path(tmp_path / "repo-feature" / "src", {"eneva": profile}, {"feature": workspace}) == workspace
```

- [x] **Step 2: Run the focused tests and verify missing workspace APIs cause failure**

Run: `uv run pytest tests/test_workspaces.py -q`

Expected: FAIL because `aparta.workspaces` does not exist.

- [x] **Step 3: Implement the typed registry and resolver**

```python
@dataclass
class Workspace:
    name: str
    path: str
    profile: str
    providers: list[str] = field(default_factory=list)

def workspace_for_path(path: Path, profiles: dict[str, Profile], workspaces: dict[str, Workspace]) -> Workspace | None:
    root = git_workspace_root(path)
    explicit = next((w for w in workspaces.values() if Path(w.path).expanduser().resolve() == root), None)
    if explicit:
        return explicit
    profile = profile_for_path(root, profiles)
    return implicit_workspace(root, profile) if profile else None
```

- [x] **Step 4: Run the focused tests until they pass**

Run: `uv run pytest tests/test_workspaces.py tests/test_run_env.py -q`

Expected: PASS.

- [x] **Step 5: Commit the workspace foundation**

```bash
git add src/aparta/workspaces.py src/aparta/runner.py tests/test_workspaces.py
git commit -m "feat(workspaces): resolve exact repository contexts"
```

### Task 2: Fail-closed environment construction

**Files:**
- Modify: `src/aparta/profiles.py`
- Modify: `src/aparta/runner.py`
- Modify: `tests/test_run_env.py`
- Modify: `tests/test_gcloud_backend.py`

**Interfaces:**
- Consumes: `Workspace`, `MANAGED_ENV_KEYS`, and profile provider settings.
- Produces: `workspace_env(workspace, profile) -> dict[str, str]` and `clean_environment(base, overlay) -> dict[str, str]`.

- [x] **Step 1: Write failing cross-client leakage and missing-ADC tests**

```python
def test_clean_environment_drops_selectors_from_previous_client():
    base = {"PATH": "/bin", "GH_CONFIG_DIR": "/effektra", "AWS_PROFILE": "effektra"}
    assert clean_environment(base, {"CLOUDSDK_CONFIG": "/eneva"}) == {"PATH": "/bin", "CLOUDSDK_CONFIG": "/eneva"}

def test_isolated_profile_blocks_global_adc_when_its_adc_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile = Profile(name="whirlpool", root="/repo", git_email="x@y", gcloud_account="x@y", gcloud_isolated=True)
    assert profile.env()["GOOGLE_APPLICATION_CREDENTIALS"] == str(tmp_path / "gcloud-whirlpool" / "application_default_credentials.json")
```

- [x] **Step 2: Run the focused tests and verify they fail on retained selectors and absent ADC**

Run: `uv run pytest tests/test_run_env.py tests/test_gcloud_backend.py -q`

Expected: FAIL because inherited selectors remain and missing ADC is omitted.

- [x] **Step 3: Implement clearing and the fail-closed ADC selector**

```python
def clean_environment(base: Mapping[str, str], overlay: Mapping[str, str]) -> dict[str, str]:
    clean = {key: value for key, value in base.items() if key not in MANAGED_ENV_KEYS}
    clean.update(overlay)
    return clean
```

Always add the isolated profile ADC path to `Profile.env()`, whether or not the
file exists.

- [x] **Step 4: Run focused runtime tests**

Run: `uv run pytest tests/test_run_env.py tests/test_gcloud_backend.py tests/test_auth.py -q`

Expected: PASS.

- [x] **Step 5: Commit the security boundary**

```bash
git add src/aparta/profiles.py src/aparta/runner.py tests/test_run_env.py tests/test_gcloud_backend.py
git commit -m "fix(runtime): prevent inherited credential fallback"
```

### Task 3: Contextual add, login, and status commands

**Files:**
- Create: `src/aparta/providers.py`
- Modify: `src/aparta/cli.py`
- Modify: `src/aparta/auth.py`
- Create: `tests/test_contextual_cli.py`
- Modify: `tests/test_auth.py`
- Modify: `src/aparta/i18n.py`

**Interfaces:**
- Consumes: `resolve_workspace()`, `Workspace.providers`, `login_profile()`, and `cached_check()`.
- Produces: provider canonicalization, `aparta add [workspace] provider`, optional-context `aparta login`, and `aparta status`.

- [x] **Step 1: Write failing CLI tests**

```python
def test_add_one_argument_targets_current_worktree(runner, configured_workspace, monkeypatch):
    monkeypatch.chdir(configured_workspace.path)
    result = runner.invoke(app, ["add", "bitbucket"])
    assert result.exit_code == 0
    assert "bitbucket" in load_workspaces()[configured_workspace.name].providers

def test_login_without_argument_uses_current_workspace(runner, configured_workspace, monkeypatch):
    monkeypatch.chdir(configured_workspace.path)
    result = runner.invoke(app, ["login"])
    assert result.exit_code == 0
```

- [x] **Step 2: Run the focused tests and verify CLI contract failures**

Run: `uv run pytest tests/test_contextual_cli.py -q`

Expected: FAIL because `add`, optional login context, and status do not exist.

- [x] **Step 3: Implement canonical provider definitions and CLI parsing**

```python
PROVIDER_ALIASES = {"gh": "github", "google": "gcloud"}
KNOWN_PROVIDERS = {"git", "ssh", "github", "gitlab", "bitbucket", "gcloud", "adc", "aws"}

def parse_add_arguments(values: list[str]) -> tuple[str, str]:
    if len(values) == 1:
        return "", canonical_provider(values[0])
    if len(values) == 2:
        return values[0], canonical_provider(values[1])
    raise ValueError("usage: aparta add [workspace] <provider>")
```

Persist explicit workspace providers only after validation succeeds. Reject
`gcloud` and `adc` for light profiles with an actionable isolated-mode error.

- [x] **Step 4: Implement status output from cached provider health**

Extend `AuthStatus` with optional `expires_at` and `renewable` fields. Human
status reports every selected provider. Shell status returns only workspace,
profile, state, and earliest known non-renewable expiry.

- [x] **Step 5: Run focused CLI and auth tests**

Run: `uv run pytest tests/test_contextual_cli.py tests/test_auth.py tests/test_i18n.py -q`

Expected: PASS.

- [x] **Step 6: Commit contextual commands**

```bash
git add src/aparta/providers.py src/aparta/cli.py src/aparta/auth.py src/aparta/i18n.py tests/test_contextual_cli.py tests/test_auth.py
git commit -m "feat(cli): add contextual providers login and status"
```

### Task 4: Automatic zsh activation and prompt warning

**Files:**
- Create: `src/aparta/shell.py`
- Create: `tests/test_shell.py`
- Modify: `src/aparta/cli.py`
- Modify: `src/aparta/runner.py`
- Modify: `src/aparta/i18n.py`

**Interfaces:**
- Consumes: `resolve_workspace()`, `workspace_env()`, `clean_environment()`, and cached status metadata.
- Produces: `activation_lines()`, `render_zsh_hook()`, `install_zsh_hook()`, and `aparta env --activate`.

- [x] **Step 1: Write failing shell transition tests**

```python
def test_activation_unsets_every_managed_key_before_exporting_workspace(tmp_path):
    text = activation_lines(workspace_fixture, profile_fixture)
    assert "unset GH_CONFIG_DIR CLOUDSDK_CONFIG" in text
    assert "export APARTA_WORKSPACE=" in text

def test_unregistered_folder_deactivates_context(tmp_path):
    text = activation_lines(None, None)
    assert "unset APARTA_WORKSPACE APARTA_PROFILE" in text
```

- [x] **Step 2: Run shell tests and verify the module is missing**

Run: `uv run pytest tests/test_shell.py -q`

Expected: FAIL because `aparta.shell` does not exist.

- [x] **Step 3: Implement quoted activation and the zsh hook**

```python
def activation_lines(workspace: Workspace | None, profile: Profile | None) -> str:
    lines = ["unset " + " ".join((*MANAGED_ENV_KEYS, *APARTA_METADATA_KEYS))]
    if workspace and profile:
        lines.extend(export_lines(workspace_env(workspace, profile)).splitlines())
    return "\n".join(lines)
```

The generated zsh code uses `add-zsh-hook chpwd` and `add-zsh-hook precmd`,
keeps the original `RPROMPT`, and calculates the 30-minute warning locally
from `APARTA_EXPIRES_AT`.

- [x] **Step 4: Test hook installation merge and idempotency**

Run: `uv run pytest tests/test_shell.py tests/test_dry_run.py -q`

Expected: PASS with one marked startup block after repeated installation.

- [x] **Step 5: Commit automatic activation**

```bash
git add src/aparta/shell.py src/aparta/cli.py src/aparta/runner.py src/aparta/i18n.py tests/test_shell.py
git commit -m "feat(shell): activate registered workspaces automatically"
```

### Task 5: Correct and reconcile agent adapters

**Files:**
- Modify: `src/aparta/agents/codex.py`
- Modify: `src/aparta/apply.py`
- Modify: `tests/test_agents_merge.py`
- Modify: `tests/test_apply.py`
- Modify: `README.md`
- Modify: `README.pt-BR.md`

**Interfaces:**
- Consumes: workspace-filtered environment and `MANAGED_ENV_KEYS`.
- Produces: Codex `shell_environment_policy.set` merge, old `[env]` migration, unconditional selected-adapter application, and current documentation.

- [ ] **Step 1: Write failing Codex schema and migration tests**

```python
def test_codex_uses_supported_shell_environment_policy_and_migrates_owned_old_keys():
    existing = '[env]\nFOO = "keep"\nGH_CONFIG_DIR = "/old"\n'
    data = tomllib.loads(merge_codex_env(existing, {"GH_CONFIG_DIR": "/new"}))
    assert data["shell_environment_policy"]["set"]["GH_CONFIG_DIR"] == "/new"
    assert data["env"] == {"FOO": "keep"}

def test_codex_adapter_applies_without_preexisting_directory(tmp_path):
    assert CodexAdapter().detect(tmp_path) is True
```

- [ ] **Step 2: Run the adapter tests and verify they fail on `[env]` and detection**

Run: `uv run pytest tests/test_agents_merge.py tests/test_apply.py -q`

Expected: FAIL because the current adapter writes `[env]` and skips new repos.

- [ ] **Step 3: Implement the supported Codex merge and reconciliation**

Write and validate values under `shell_environment_policy.set`. Remove only
Aparta-owned keys from the old `[env]` table, preserve unrelated values, and
remove an empty old table. Make `detect()` return true for configured Codex
workspaces.

- [ ] **Step 4: Update English and Portuguese documentation**

Document exact workspaces, `add`, contextual `login`, `status`, automatic zsh
activation, fail-closed ADC behavior, and the supported Codex configuration
key.

- [ ] **Step 5: Run adapter and documentation-adjacent tests**

Run: `uv run pytest tests/test_agents_merge.py tests/test_apply.py tests/test_registry.py -q`

Expected: PASS.

- [ ] **Step 6: Commit adapter corrections**

```bash
git add src/aparta/agents/codex.py src/aparta/apply.py tests/test_agents_merge.py tests/test_apply.py README.md README.pt-BR.md
git commit -m "fix(agents): reconcile workspace environment safely"
```

### Task 6: Regression verification and release-facing notes

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `CHANGELOG.pt-BR.md`
- Modify: `src/aparta/__init__.py` only if the project release convention requires a version change.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: user-visible release notes and complete verification evidence.

- [ ] **Step 1: Run formatting-neutral source checks**

Run: `python -m compileall -q src tests && git diff --check`

Expected: exit code 0.

- [ ] **Step 2: Run the complete suite**

Run: `uv run pytest -q`

Expected: all tests pass.

- [ ] **Step 3: Exercise CLI help and contextual error paths**

Run: `uv run aparta help && uv run aparta add --help && uv run aparta login --help && uv run aparta status --help`

Expected: every command renders, contextual forms are documented, and no update or credential probe pollutes machine-readable output.

- [ ] **Step 4: Add release-facing notes without publishing**

Describe the exact workspace boundary, automatic activation, contextual CLI,
credential countdown semantics, global-selector clearing, and Codex adapter
migration in both changelogs. Do not tag, push, publish, or merge `dev`.

- [ ] **Step 5: Commit verified release notes**

```bash
git add CHANGELOG.md CHANGELOG.pt-BR.md
git commit -m "docs(changelog): describe workspace isolation"
```
