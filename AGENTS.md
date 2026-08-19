<!-- UMEM: START -->
# Universal Memory Active Policy
> [!IMPORTANT]
> UMEM bootstrap is a mandatory preflight at the start of a conversation, session, or new task (before planning, editing, investigation, review, skill workflow, slash command, or structured agent workflow).
> Run `umem status --format json`, `umem context --scope project --format json`, and `umem skills list --format json` only at the beginning of the conversation to load the context. During the conversation, do not repeat the full bootstrap on every interaction; instead, query, add, or remove facts and skills only when necessary.
> Use the equivalent MCP/FastMCP tools when they are available.
> Read and follow `.umem/skills/universal-memory/SKILL.md`. If a relevant active skill exists, inspect it with `umem skills detail <skill-id-or-name> --format json` before acting.
> For repeated durable workflows, consider latent skill tracking via the UMEM guide; do not track one-off work, raw evidence, secrets, or private data.
> If `umem` is unavailable or not initialized, report that explicitly before continuing without external memory.
> CRITICAL: proactively capture new memory or clean up outdated ones only when a durable preference is learned, an architectural decision is made, a bug is fixed, or facts become obsolete. Do NOT run remember/sync commands on every simple interaction. Use `umem remember "..."` to add, and `umem facts purge --id <id>` to remove outdated facts, followed by `umem host sync --apply`.
> MANDATORY OUTPUT FORMAT: Before completing your turn, you MUST append a line at the end of your final response stating either `[UMEM: Remembered "..."]` or `[UMEM: No new facts/skills to record]`. Do not forget this footer.

## Required Bootstrap
- Run `umem status --format json` to validate the integration.
- Run `umem context --scope project --format json` and treat the result as active context.
- Run `umem skills list --format json`; for each relevant skill, run `umem skills detail <skill-id-or-name> --format json`.
- If MCP/FastMCP is available, prefer the equivalent tools; otherwise, use the CLI commands above.
- Perform this bootstrap only at the start of a conversation/session. Do not repeat it on every interaction.
- Keep `AGENTS.md` and `CLAUDE.md` compact: they should point to `umem`, not store memory dumps.

## Proactive Memory Loop (Mandatory)
Before concluding your response to the user, assess if a durable preference, bug fix, or decision was made. If so:
1. Record: Proactively run `umem remember "Short fact." --scope project/global --tag <tag>` or `umem facts purge --id <id>` to remove outdated facts.
2. Track Skills: For newly observed repeated workflows, run `umem skills track` with sanitized evidence; use `umem skills propose` only for existing latent candidates after approval.
3. Sync: If you ran any mutation (remember or purge), run `umem host sync --apply` to bake it.
4. Report: Append the UMEM status line `[UMEM: Remembered "..."]` or `[UMEM: No new facts/skills to record]` to your final output.

## Consolidated Operational Rules
- Use `umem context` to retrieve active rules on demand.

## Canonical Pointers
- No additional canonical document registered.
<!-- UMEM: END -->
