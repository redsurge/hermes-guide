---
name: hermes-configuration-guide
description: Map of Hermes Agent configuration — where MCP servers, skills, commands, hooks, and plugins live, and which diagnostic skill to load when something does not work.
version: 1.3.5
metadata:
  hermes:
    tags: [hermes, configuration, troubleshooting]
    related_skills: [installing-hermes, diagnosing-mcp, diagnosing-skills, diagnosing-commands, diagnosing-hooks, diagnosing-plugins, diagnosing-path, diagnosing-cli-tui, diagnosing-memory, diagnosing-desktop, diagnosing-providers, diagnosing-bot-mode, diagnosing-browser, diagnosing-cron, diagnosing-gateway, diagnosing-voice]
---

# Hermes Configuration Guide

This skill is the **map**: where each Hermes extension surface is configured, how conflicts resolve, and which `diagnosing-*` skill to load when something breaks. Hermes is configured in **YAML** (`config.yaml`), not JSON — if you are migrating from Claude Code or Cursor, `mcpServers` becomes `mcp_servers:` and `hermes import-agent claude-code` migrates servers, skills, and instructions automatically.

## Step 0 — Resolve $HERMES_HOME first

Never guess where Hermes reads its files. The home directory differs by platform and profile:

- **POSIX / WSL**: `~/.hermes`
- **Native Windows**: `%LOCALAPPDATA%\hermes` (e.g. `C:\Users\<you>\AppData\Local\hermes`) — `~/.hermes` may also exist there and is NOT the active home
- **Named profiles**: each profile has its own home; `hermes -p <profile> ...` and `HERMES_HOME=<dir>` override it
- **Two different things are called "platform" in this guide set**: the **operating system** (POSIX vs Windows — as above, and the `platforms:` frontmatter field in skills) and the **chat/messaging platform** (Telegram, Discord, Slack — in slash-command permissions and plugin `platforms/` sub-categories). Check which one a sentence means before acting.
- **Ground truth**: run `hermes config path` — it prints the active config file's full path. `hermes config show` dumps the merged config; `hermes config set <section.key> <value>` edits it safely.

## The five surfaces at a glance

| Surface | Configured in | Inspect with |
|---|---|---|
| **MCP servers** | `$HERMES_HOME/config.yaml` → `mcp_servers:` (stdio: `command`/`args`/`env`; http: `url`/`headers`) | `hermes mcp`, `/reload-mcp` |
| **Skills** | `$HERMES_HOME/skills/<category>/<name>/SKILL.md` (source of truth); extra dirs via `skills_external_dirs`; hub installs via `hermes skills` | `hermes skills list`, `/skills list`, `/reload-skills` |
| **Slash commands** | No standalone command files. Built-in registry + every installed skill (`/<skill-name>`) + skill bundles (`$HERMES_HOME/skill-bundles/*.yaml`) + plugin commands | Type `/` for autocomplete, `hermes bundles list` |
| **Hooks** | Four systems: gateway hooks (`$HERMES_HOME/hooks/<name>/HOOK.yaml` + `handler.py`, gateway-only); plugin hooks (`ctx.register_hook()`); shell hooks (`hooks:` block in config.yaml); outbound webhooks (`hooks.outbound:`) | `hermes hooks list / test / doctor` |
| **Plugins** | `$HERMES_HOME/plugins/<name>/` with `plugin.yaml` + `register(ctx)`; **opt-in** via `plugins.enabled` | `hermes plugins`, `/plugins` |

## Instruction files (a separate system)

- `SOUL.md` (`$HERMES_HOME/SOUL.md`) — agent persona, always loaded as prompt slot #1. You edit it.
- `USER.md` / `MEMORY.md` (`$HERMES_HOME/memories/`) — agent-written memory, injected as a **frozen snapshot at session start**; mid-session saves appear only next session. This is the usual cause of "it forgot what I just told it."
- Project context — each source is looked up **differently**, and the difference decides where you must put the file (`agent/prompt_builder.py::discover_context_files`, verified):

| Source | Where it is read from |
|---|---|
| `.hermes.md` / `HERMES.md` | walked from cwd **up to the git root**; cwd only when there is no git root (`agent/prompt_builder.py::_find_hermes_md` — so a file planted in a parent like `/tmp` cannot be picked up) |
| `AGENTS.md` (`AGENTS.override.md` wins, `agents.md` accepted) | **merged directory chain, git root → cwd** — every directory's file is injected, deeper wins |
| `CLAUDE.md` | **cwd only** |
| `.cursorrules` (+ `.cursor/rules/*.mdc`) | **cwd only**, concatenated |

The practical consequence: `CLAUDE.md`/`.cursorrules` at a repository root are **ignored** when you launch from a subdirectory, while `AGENTS.md` is not. Exactly one source wins per session, first match in the order above.

## Key $HERMES_HOME inventory

`config.yaml` (main config + `platforms:`/`gateway:` messaging settings) · `.env` (secrets; documented vars override config) · `gateway.json` (legacy gateway fallback) · `skills/` · `skill-bundles/` · `hooks/` (gateway hooks) · `agent-hooks/` (shell-hook script convention) · `plugins/` · `shell-hooks-allowlist.json` (shell-hook consent) · `mcp-tokens/` (OAuth caches) · `logs/` · `state.db` (sessions).

## Orphaned & legacy settings

Config keys that Hermes **silently stopped reading** are inert: they look meaningful in `config.yaml`, but no code consumes them — and their presence proves nothing. **Temporary:** the suspected key may stay while you confirm it is inert — but do not treat its presence as evidence that Hermes reads it, and do not leave it in place during an active diagnosis (an inert `disabled: true` on an MCP server reads as "server off" while the loader keeps it **on**). **Permanent:** move to the live replacement below and delete the dead key so it misleads neither the current investigation nor the next reader. Before trusting a key, verify it against the installed source: search for actual readers (e.g. `grep -rn 'get("profile")' <hermes-agent-source>`), and check whether it appears in the shipped `cli-config.yaml.example` (the documented schema). Known cases, last checked against the installed source at commit `8d3745a99b` (present in history; 2026-09-04). **Re-check before quoting a key as orphaned** — the honest test is a reader grep plus the shipped `cli-config.yaml.example`; a key absent from that example and with no reader is inert, but a key that has gained a reader since this list was written is live again:

| Setting | Status | Live replacement |
|---|---|---|
| `profile:` block in `config.yaml` (e.g. `profile.description`) | **Orphaned** — written by an older scheme, zero readers today | Per-profile `profile.yaml` metadata: `hermes profile describe <name> --text "…"` |
| `mcpServers` (top-level, Claude-Code-style paste) | Silently not read | `mcp_servers:` |
| `disabled:` inside an MCP server entry | Silently ignored (server stays enabled) — the loader reads `enabled` only (`hermes_cli/mcp_config.py`) | `enabled: false` |

Notes:

- `hermes migrate` covers **retired models and deprecated settings** (currently the xAI migration); the sibling `hermes config migrate` applies new config options. Neither detects arbitrary orphaned keys — audit for those by hand.
- Profile descriptions reach a model in only two contexts: kanban task routing (the decomposer's profile roster) and dispatch guidance. Normal sessions and `hermes guide`/`hermes doctor` never see them.
- When a diagnosis behaves as if part of `config.yaml` is invisible, audit for orphans before suspecting the model: inert keys produce exactly that symptom.

## Routing — when something is wrong
- Vague description ("something is wrong", "it's slow", "it crashed") without naming a subsystem → **`diagnosing-triage`** (meta-skill that routes to the correct diagnostic skill)

- MCP server not connecting, tools missing, OAuth failing → **`diagnosing-mcp`**
- A skill not discovered, not triggering, shadowed, or stuck "user-modified" → **`diagnosing-skills`**
- A `/command` missing, wrong, or overridden → **`diagnosing-commands`**
- A hook not firing, blocked consent, or behaving unexpectedly → **`diagnosing-hooks`**
- A plugin not loading, not enabled, or missing capabilities → **`diagnosing-plugins`**
- Auth/API failures on hub installs (`Could not fetch from any source`, GitHub 401, rate-limit 403) → **`diagnosing-auth`**
- Memory not persisting ("it forgot"), an external memory provider silently unavailable, or `MEMORY.md`/`USER.md` errors → **`diagnosing-memory`**
- Desktop app build/launch failures, wrong backend, or blank window → **`diagnosing-desktop`**; terminal/TUI rendering issues are `diagnosing-cli-tui`, not desktop
- Model provider issues — custom endpoints flooding the picker with hundreds of models, `discover_models` misbehaving, persisted catalogs bloating `config.yaml`, or provider/auth failures → **`diagnosing-providers`**
- Script/path/venv problems (wrong interpreter — on PM-era installs the launcher runs the PM-store Python, not the shell's; on older checkouts `venv/bin/python` missing or the dual `.venv`/`venv` layout) → **`diagnosing-path`**
- Terminal/TUI issues on **native Windows** (misrendering, themes, indicators, launch failures) → **`diagnosing-cli-tui`**; on POSIX/WSL there is no dedicated skill yet — start with `hermes doctor` and the `display:` block of `config.yaml`
- A bot/agent profile not answering, a per-bot `config.yaml` problem, or a routine not firing for a bot → **`diagnosing-bot-mode`**
- Browser automation not connecting, Chrome/CDP version problems, or a missing Playwright → **`diagnosing-browser`**
- A scheduled job not firing, running at the wrong time, or failing to deliver → **`diagnosing-cron`**
- Messaging-platform connectivity, allowlists, or a platform not receiving replies → **`diagnosing-gateway`**
- Several surfaces failing at once, or adapters discarded after a load timeout — suspect host resource pressure before per-surface config → **`diagnosing-host-pressure`**
- Voice mode not transcribing or replying, or voice-message handling problems → **`diagnosing-voice`**

### Disambiguation — when two skills can claim the same symptom

- **Skill not discovered vs `/command` missing**: if the skill itself is missing from the index, see `diagnosing-skills`; if the skill is present but its `/command` is missing or shadowed, see `diagnosing-commands`.
- **MCP server up but no tools vs provider configured but unavailable**: if the MCP server connects but exposes no tools, see `diagnosing-mcp`; if a model provider is configured but silently unavailable, see `diagnosing-providers`.
- **Plugin not loading vs provider sub-category**: if a plugin is discovered but not enabled, see `diagnosing-plugins`; if a provider sub-category (e.g. `context.engine`, `image_gen.provider`) is misconfigured, see `diagnosing-providers`.
- **Memory not persisting vs provider store unavailable**: if built-in `MEMORY.md`/`USER.md` has errors, see `diagnosing-memory`; if an external memory provider is configured but silently unavailable, see `diagnosing-memory` (it owns external-memory diagnosis).
- **Several faults at once, intermittently**: suspect host resource pressure before per-surface config — see `diagnosing-host-pressure`.
- **Launch/UI failure vs command surface vs app build**: if the desktop app fails to launch or shows a blank window, see `diagnosing-desktop`; if the TUI misrenders or shows unreadable indicators on native Windows, see `diagnosing-cli-tui`; if a `/command` is missing or overridden, see `diagnosing-commands`.
- **Which venv/home applies where**: if the wrong Python interpreter is active or the dual-venv layout is confusing, see `diagnosing-path`; if the desktop app's backend resolution is wrong, see `diagnosing-desktop`; if the install itself is broken, see `installing-hermes`.

## Standard report format

Every diagnostic skill reports findings in this format. The model uses this structure when presenting results to the user.

### Summary

One or two sentences in plain language. What is wrong, in terms the user understands. No jargon, no file paths, no command output.

**Example**: "Your Hermes gateway is not responding because the Telegram plugin failed to load. The plugin timed out during startup, likely due to high disk latency."

### Findings

Severity-ordered list. Each finding has:
- **Severity**: HIGH (blocks core functionality), MEDIUM (degraded but usable), LOW (cosmetic or informational)
- **What**: The specific problem
- **Evidence**: The command output, file content, or log line that proves it

**Example**:
| Severity | What | Evidence |
|---|---|---|
| HIGH | Telegram plugin discarded after load timeout | `Plugin 'telegram-platform' called register_platform() after its load timed out; ignored` |
| MEDIUM | Disk latency causing plugin load failures | `probe wall time: 47s` (threshold: 20s) |

### Recommended Fix

One concrete action the user can take. Include the exact command or file edit. If the fix is not obvious, explain why this action and not another.

**Example**:
1. Check disk health: `smartctl -a /dev/sda` (Linux) or `wmic diskdrive get status` (Windows)
2. If disk is failing, replace it — no Hermes config change will fix this
3. If disk is healthy, run `hermes gateway restart` and check if plugins load within budget

### References

File paths, line numbers, and command output that support the findings. This is for the user to verify, not for the model to re-run.

**Example**:
- `$HERMES_HOME/logs/errors.log` — plugin load timeout lines
- `skills/diagnosing-host-pressure/scripts/host_pressure_probe.sh` — probe output

Every diagnosis should end in a concrete action: a `hermes <subcommand>` command or a specific file + field edit, then a restart or `/reload-*` to apply.

---

*Facts re-verified 2026-10-09 against upstream source at the declared baseline `f97608f178d1ffeca59860195ab7da295f7c8e5f`: the earlier-cited commit `8d3745a99b` exists in history (2026-09-04); the `profile:` block has no config reader (the `profile` hits in the tree are session records, not this block); an MCP entry's `disabled:` key is unread — `enabled` is the control (`hermes_cli/mcp_config.py`); **project context is looked up per source, not by one rule** — `.hermes.md`/`HERMES.md` walk cwd→git root (`agent/prompt_builder.py::_find_hermes_md`), `AGENTS.md` is a merged chain git root→cwd, and `CLAUDE.md`/`.cursorrules` are cwd-only (`agent/prompt_builder.py::discover_context_files`, `_hermes_md_candidates`/`_find_hermes_md`); the former bare line citation for project-context discovery was re-pointed to those symbols at `2f6170bf` (2026-09-22, drift #103); `mcp-tokens/`, `profile describe`, and `import-agent` all exist. Re-verify before reuse.*
