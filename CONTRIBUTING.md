<p align="right"><b>English</b> | <a href="CONTRIBUTING.pt-BR.md">Português (Brasil)</a></p>

# Contributing to aparta

Thanks for your interest! The workflow is simple:

```bash
git clone <your-fork>
cd aparta
uv sync
uv run pytest      # all green before opening a PR
uv run aparta --help
```

CI runs the test suite on Python 3.10 to 3.13; a PR needs it green.

## Adding support for a new agent

1. Create `src/aparta/agents/<agent>.py` with an `AgentAdapter` subclass
   defining `name`, `display_name` and the methods `detect`, `inject` and
   `validate`. Implement `read_env` too when the agent's config can be read
   back, so discovery detects previous setups.
2. Done, the registry imports the package modules automatically and the
   wizard lists the agent. Add tests in `tests/`.

## Golden rules

- Every write to an existing file goes through `SafeWriter` (backup plus
  merge); never overwrite a user's file.
- Tests use `tmp_path` and `APARTA_CONFIG_DIR`, never the real home.
- User-facing strings are written in English through the `_()` helper from
  `aparta/i18n.py`, with a Brazilian Portuguese entry added to the catalog
  in the same module.
- Code comments and docstrings are English, short, and only where needed.
- Commits follow conventional commits (`feat:`, `fix:`, `docs:`, `test:` ...),
  in English.
