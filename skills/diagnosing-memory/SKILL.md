---
name: diagnosing-memory
description: "Diagnose Hermes memory problems — the agent forgot something, an external memory provider configured but silently unavailable, missing provider plugins or API keys, and built-in MEMORY.md/USER.md errors from config or char limits."
version: 1.2.6
metadata:
  hermes:
    tags: [hermes, memory, providers, troubleshooting, diagnosing]
    related_skills: [hermes-configuration-guide, diagnosing-plugins, diagnosing-path]
---

# Diagnosing Memory

Goal: reduce any "it forgot what I told it" / "my memories are gone" / memory-provider failure to one concrete fix — a config field, an env var, a plugin install, or a session restart.

> **Disambiguation**: if a model provider is configured but silently unavailable (not a memory issue), see `diagnosing-providers`.

> [!WARNING]
> **Hermes memory has two independent layers, and the external one fails silently.** Built-in memory (`MEMORY.md` / `USER.md`) is always active. At most one external provider can be active; if it is unavailable, **external memory is disabled for that session and built-in memory answers instead** — the agent does not announce this. "My mem0 memories are gone" usually means "mem0 was unavailable; built-in answered."

## 1. How memory resolves

| Layer | Files / source | Controlled by |
|---|---|---|
| **Built-in** (always available) | `$HERMES_HOME/memories/MEMORY.md` (agent notes) + `USER.md` (user profile) | `memory.memory_enabled`, `memory.user_profile_enabled` in `config.yaml` |
| **External provider** (opt-in, one at a time) | plugin at `$HERMES_HOME/plugins/memory/<name>/` + pip deps in the install's dependency environment (PM-era: `$HERMES_HOME/installs`; older checkouts: the in-tree venv) + secrets in `$HERMES_HOME/.env` | `memory.provider:` in `config.yaml` (empty string = built-in only) |

The `provider:` comment in `config.yaml` lists the one-at-a-time set — `openviking`, `mem0`, `holographic`, `retaindb`, `byterover`, plus catalog-installed ones such as `hindsight` (bundled → catalog move, 2026-09) — and that list is **not exhaustive**. Providers shipped as optional skills/plugins (e.g. `honcho`, from `optional-skills/autonomous-ai-agents/honcho`, pip `honcho-ai`) install the same way and show up in the installed-plugins list of `hermes memory status`. Trust that list over any comment.

A provider is *available* only when all four hold: plugin installed, its pip dependencies importable in the install's dependency environment (PM-era: `$HERMES_HOME/installs`; older checkouts: the in-tree venv), its env vars set, and its `is_available()` check passing. Any one missing → silent fallback to built-in (see the warning above).

> [!IMPORTANT]
> **Built-in memory is a frozen snapshot.** `MEMORY.md`/`USER.md` are injected into the system prompt once at session start. Mid-session saves hit disk immediately but do **not** update the current session's prompt — this is by design (it keeps the prompt cache stable). "It forgot what I just told it" is usually this, not a bug: the write landed and appears next session. Verify with a file read before diagnosing further.

## 2. How to inspect

Probe in this order — the first two are built-in helpers and answer most cases:

1. **`hermes memory status`** — the authoritative check. Real example (a machine with `honcho` selected but no API key):

   ```
   Memory status
   ────────────────────────────────────────
     Built-in (MEMORY.md / USER.md):
       Memory injection:   enabled ✓
       User profile:       enabled ✓
       Memory tool:        enabled ✓
     Provider:  honcho
     Plugin:    installed ✓
     Status:    not available ✗
     Missing:
       ✗ HONCHO_API_KEY  → https://app.honcho.dev
   ```

   A trailing `Note:` line (quoted verbatim in the tool's output) explains that systemd/gateway services do not inherit the profile `.env` secrets file — set any listed variables in the service environment itself (see the gateway/systemd row in §3).

   Read it line by line: the three built-in lines confirm the stores and the `memory` tool are on; `Provider:` shows what `memory.provider` is set to; `Plugin:` / `Status:` / `Missing:` are the three failure points in order (plugin file → pip deps → env vars). The installed-plugins list at the bottom is the ground truth for provider names — the `hermes memory --help` string is not kept in sync with it.

2. **`hermes doctor`** — its "Memory Provider" section probes the active provider deeper (config file, API key, live connect, `ImportError` on the provider package). Run it after `memory status` points at a layer.

3. **Config + files** — read the `memory:` block of `$HERMES_HOME/config.yaml` (or `hermes config show`), and `ls "$HERMES_HOME/memories/"`. On native Windows `$HERMES_HOME` is `%LOCALAPPDATA%\hermes` — confirm with `hermes config path`, never assume.

4. **Session log** — a provider selected but unavailable logs a one-shot warning at agent start (wording varies by version; look for a line naming the provider and saying external memory is disabled for the session): `hermes logs --follow` while starting a session. The gate that produces it is the external-provider block in `agent/system_prompt.py`.

5. **`hermes guide memories`** (or `/hermes-doctor memories` in-session) — this plugin's read-only hygiene audit of the built-in stores: over-limit files, exact/near-duplicate entries, user-profile facts mis-targeted into `MEMORY.md`, and undated dynamic entries. It reports content-level findings that `hermes memory status` does not look at.

## 3. Pitfalls (symptom → cause → fix)

| Symptom | Cause | Fix |
|---|---|---|
| Agent forgot something said mid-session | Frozen snapshot by design (see §1) | **Temporary:** start a new session (it picks the write up). **Permanent:** none — this is intended. Verify the write landed in `$HERMES_HOME/memories/MEMORY.md` first |
| External provider "not available ✗", missing env var listed | Secret absent from `$HERMES_HOME/.env` | **Temporary:** none needed — built-in memory is already carrying the running session (the fallback happened at session start). **Permanent:** add the var to `.env` (and to the service environment for gateway/systemd) via `hermes memory setup <provider>`; alternatively `hermes memory off` to stop future external-provider attempts — it takes effect for **subsequently started** sessions, not the current one. Keep secrets out of `config.yaml` |
| Provider works in terminal, not in gateway/systemd | Services do not inherit `$HERMES_HOME/.env` | Set the provider's env vars in the service environment itself |
| `hermes memory status`: "Plugin: NOT installed ✗" | `memory.provider` names a provider with no plugin under `$HERMES_HOME/plugins/memory/` | Install the provider plugin (hub: `hermes plugins install …`), or `hermes memory off` to go built-in-only |
| `hermes doctor`: "honcho-ai not installed" / "mem0ai not installed" | dependency-environment resync stripped provider pip deps (PM-era: `$HERMES_HOME/installs`; older checkouts: the in-tree venv) | Re-run `hermes memory setup <provider>` (force-reinstalls its deps) or `hermes update` |
| Hindsight local mode fails to import | local mode needs `hindsight-all`, not `hindsight-client` | `hermes memory setup hindsight` after setting `mode: local` in `hindsight/config.json` |
| Memory tool missing from the tool schema | Both stores disabled: `memory.memory_enabled: false` **and** `user_profile_enabled: false` | Re-enable one in `config.yaml`; both off removes the tool entirely |
| Writes rejected: "…would exceed the limit. Consolidate now…" | Char limits are hard caps (defaults 2200 / 1375 chars) — there is no auto-compaction | **Temporary:** consolidate/dedupe in the same turn. **Permanent:** raise `memory.memory_char_limit` deliberately, or keep entries dated (`[YYYY-MM-DD] …`) so consolidation stays cheap |
| Writes silently staged, never saved | `memory.write_approval: true` stages writes for review | Approve via `/memory approve` in-session, or set `write_approval: false` |
| Hygiene check flags "no entry has a [YYYY-MM-DD] date prefix" | Entries carry no dates, so staleness is uncheckable — the `memories` scope of `hermes guide` reports undated entries as notes | Date new entries `[YYYY-MM-DD] …` where staleness matters; undated entries are a note, not an error |
| Provider config edits ignored | Active-provider name mismatch, or edits made to the wrong profile's home | `hermes config path` to confirm the active home/profile; one provider at a time — `memory.provider` is a single string |
| Memory "disappeared" after profile work | `HERMES_HOME` unset while a non-default profile is active → files written to the wrong home | Set `HERMES_HOME` explicitly for profile work; watch for the `[HERMES_HOME fallback]` stderr warning |

Two name traps that are **not** this surface:

- `context.memory_trim` is **process-heap release** for long-lived gateway processes (Linux/glibc only) — nothing to do with `MEMORY.md`.
- `hermes memory-graph` is an alias of `hermes journey` (learned-skills/memory timeline viewer), not a memory provider.

## 4. The `memory:` config block

| Key | Default | Meaning |
|---|---|---|
| `provider` | `""` | Active external provider; empty = built-in only; `hermes memory off` sets this |
| `memory_enabled` | `true` | Agent-notes store (`MEMORY.md`) |
| `user_profile_enabled` | `true` | User-profile store (`USER.md`) |
| `memory_char_limit` | `2200` | Hard cap in characters of the decoded file (`len(text)`) — not bytes, not tokens |
| `user_char_limit` | `1375` | Hard cap in characters of the decoded file (`len(text)`) — not bytes, not tokens |
| `nudge_interval` | `10` | Memory-save nudge every N user turns; `0` = off |
| `write_approval` | `false` | Stage writes for `/memory approve` instead of saving |

Hermes configuration is **YAML** — edit `config.yaml`, never JSON syntax.

## 5. Apply and verify

There is no `/reload-memory`: built-in memory is snapshotted at session start, so **restart the session** after any config/`.env`/plugin fix. Then confirm with `hermes memory status` (all lines ✓, or provider lines as intended) and, for built-in, ask the agent to remember something and check the file changed on disk.

> [!CAUTION]
> `hermes memory reset` **erases** `$HERMES_HOME/memories/MEMORY.md` and/or `USER.md` irreversibly (`--target all|memory|user`, confirmation prompt, `--yes` skips it). It resets built-in memory only — it does not touch external providers.

## 6. The session database (`state.db`) — size and compaction

Built-in memory and the external provider are the *content* stores. The session
*log* lives separately in `$HERMES_HOME/state.db` (SQLite), and its growth has
nothing to do with either store. A 900+ MB `state.db` is not a memory problem
and trimming `MEMORY.md` will not shrink it.

### What is in it

| Table | Meaning |
|---|---|
| `sessions` | one row per conversation (953 in a typical install) |
| `messages` | every user/assistant/tool row (~250K) |
| `messages_fts` | full-text index over `messages` (kept in sync) |
| `session_model_usage` | token accounting per session |
| `system_prompts` | cached system prompt variants |
| `compaction_events` | **records of every compaction run** |

### The compaction signal

`compaction_events` is the canary. If it is **0**, compaction has never fired —
the database has been growing with no trim ever applied. This is the most common
cause of a bloated `state.db`.

**Diagnose it directly:**

```bash
sqlite3 "$HERMES_HOME/state.db" "SELECT COUNT(*) FROM compaction_events;"
```

Correlate with the other tables:

```bash
sqlite3 "$HERMES_HOME/state.db" \
  "SELECT 'sessions', COUNT(*) FROM sessions
   UNION ALL SELECT 'messages', COUNT(*) FROM messages
   UNION ALL SELECT 'open_sessions', COUNT(*) FROM sessions WHERE ended_at IS NULL
   UNION ALL SELECT 'sessions_older_than_90d',
     COUNT(*) FROM sessions WHERE started_at < $(date +%s) - 7776000;"
```

A healthy profile: `compaction_events > 0`, few open sessions, old sessions
summarized. A sick one: `compaction_events = 0`, 100+ open sessions, 18+ sessions
older than 90 days, and a top session carrying 10K+ raw message rows.

### Integrity checks (run before anything else)

Corruption and FTS drift are separate from growth. Verify both:

```bash
# FTS in sync with messages — 0 means clean
sqlite3 "$HERMES_HOME/state.db" \
  "SELECT COUNT(*) FROM messages m LEFT JOIN messages_fts f ON m.rowid = f.rowid
   WHERE f.rowid IS NULL;"
# Stale FTS rows whose source messages were deleted — 0 means clean
sqlite3 "$HERMES_HOME/state.db" \
  "SELECT COUNT(*) FROM messages_fts f LEFT JOIN messages m ON f.rowid = m.rowid
   WHERE m.rowid IS NULL;"
# Orphan messages pointing at deleted sessions — 0 means clean
sqlite3 "$HERMES_HOME/state.db" \
  "SELECT COUNT(*) FROM messages m LEFT JOIN sessions s ON m.session_id = s.id
   WHERE s.id IS NULL;"
```

If any returns non-zero, the database is damaged: back it up first (see below),
then consider `hermes sessions repair` before anything destructive — pruning and
optimizing assume a consistent store.

### The fix

There is no `hermes compact` command. Reclaim space with the real
session-store commands, in this order:

```bash
hermes backup -q -l pre-prune          # explicit snapshot; verify the zip exists
hermes sessions prune --help           # delete old sessions (filterable) — read flags first
hermes sessions archive --help         # soft-hide instead of deleting, if preferred
hermes sessions optimize               # VACUUM + merge FTS5 segments (no data change)
```

`optimize-storage` migrates the search index to the compact v23 layout and
reclaims disk on large DBs; `repair` fixes a malformed schema so hidden
sessions reappear. Run these on a session you are not currently in, since they
operate on the live database.

> [!CAUTION]
> Pruning is lossy by design — it deletes raw message rows. Compaction creates
> no backup itself, and nothing guarantees a recent archive already exists
> (`backups/` holds conditional full archives, `state-snapshots/` holds quick
> snapshots). Create one explicitly with `hermes backup -q -l pre-prune` and
> confirm the zip before pruning a database you have not trimmed before.

## Report

This skill diagnoses memory problems — the agent forgot something, an external memory provider configured but silently unavailable, missing provider plugins or API keys, and built-in MEMORY.md/USER.md errors. When you run the diagnostic workflow, present findings in the standard format below.

### Summary
Your external memory provider (honcho) is not available because the API key is missing from `.env`. The provider is selected in config but silently falls back to built-in memory, so your honcho memories appear "gone."

### Findings
| Severity | What | Evidence |
|---|---|---|
| HIGH | HONCHO_API_KEY missing from `.env` | `hermes memory status` shows `Status: not available ✗` with `Missing: ✗ HONCHO_API_KEY → https://app.honcho.dev` |
| MEDIUM | External memory disabled for session | Log at session start: `honcho unavailable; external memory disabled for this session` |

### Recommended Fix
Add `HONCHO_API_KEY=*** to `$HERMES_HOME/.env`, then restart the session. Verify with `hermes memory status` — the provider should show `Status: available ✓`. If the provider plugin is also missing, run `hermes memory setup honcho` first.

### References
- `$HERMES_HOME/.env` — the missing API key
- `$HERMES_HOME/config.yaml` — `memory.provider: honcho`
- `agent/system_prompt.py` — external-provider gate
- `tools/memory_tool_store.py` — memory store limits

---

*Facts re-verified 2026-10-09 against upstream source at commit `50035ef63c5536757e63bc1c1ffe4e5c19ac7fad`: `tools/memory_tool_store.py` (limits + rejection text), `hermes_cli/config_defaults.py` (the `memory:` block and its provider comment), `agent/memory_provider.py` (plugin path), `agent/system_prompt.py` (the external-provider gate), `hermes_cli/mem_trim.py` (`context.memory_trim`), `hermes_cli/subcommands/journey.py` (`memory-graph` alias), plus `optional-skills/autonomous-ai-agents/honcho/` for the provider-list note; provider comment re-verified 2026-09-29 at `5000e2993` (`hindsight` is now catalog-installed). Re-verify before reuse.*
