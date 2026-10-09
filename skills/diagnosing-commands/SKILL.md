---
name: diagnosing-commands
description: Diagnose missing or overridden Hermes slash commands — skills as commands, skill bundles, plugin-registered commands, and per-platform admin/user permissions.
version: 1.1.5
metadata:
  hermes:
    tags: [hermes, commands, troubleshooting]
    related_skills: [hermes-configuration-guide]
---

# Diagnosing Slash Commands

Hermes has **no standalone custom command files** (no `commands/*.md` directory like Claude Code). Every `/command` comes from exactly four sources, dispatched through one central registry (`hermes_cli/commands.py`) on two surfaces: the interactive CLI/TUI and the messaging gateway. Diagnose by identifying which source the command should come from.

> **Disambiguation**: if the skill itself is missing from the index (not just its `/command`), see `diagnosing-skills` — that is a skill-discovery problem, not a command-surface problem.

## 1. The four sources

| Source | How it's created | Notes |
|---|---|---|
| **Built-in registry** | Ships with Hermes (`/model`, `/skills`, `/reload-mcp`, …) | Case-insensitive; see `/help` |
| **Skills** | Every installed skill is automatically `/<skill-name>` | The name comes from SKILL.md frontmatter, not the directory |
| **Skill bundles** | `hermes bundles create <name> --skill a --skill b` → `$HERMES_HOME/skill-bundles/<slug>.yaml` | Loads several skills at once; **a bundle wins a slug collision with a skill** |
| **Plugin commands** | `ctx.register_command(name, handler, description="", args_hint="")` in a plugin | Only while that plugin is enabled. A name that collides with a **built-in** command is warned and skipped (`resolve_command` check); a collision between two plugins is a **late-registration replace** — the last registrant wins (`hermes_cli/plugins.py::register_command`, `@_serialized_replacement`), which is why a command can silently change behaviour when another plugin loads |

Multiple leading `/skill` tokens stack in one message — the cap is **`_MAX_STACKED_SKILLS = 5`** (`agent/skill_commands.py`, verified 2026-09-14); parsing stops at the first token that isn't an installed skill, so argument paths like `/tmp/scan.pdf` are safe.

## 2. Pitfalls (symptom → cause → fix)

1. **`/my-skill` not found** — skill not discovered at all (wrong directory, missing/misnamed `SKILL.md`, shadowed by a local copy). → Follow **`diagnosing-skills`**; the command appears when discovery does (`/reload-skills`).
2. **Command name differs from the folder name** — the slash command uses the frontmatter `name`. → Reference the frontmatter name or rename it.
3. **`/name` loads the wrong thing** — a bundle with the same slug shadows the skill (intentional), or a local skill shadows an external one. → `hermes bundles list`; rename one of them.
4. **A plugin's command is missing** — the plugin is installed but not in `plugins.enabled`. → `hermes plugins enable <name>`; restart. Follow **`diagnosing-plugins`**.
5. **Command works in the CLI but not on Telegram/Discord/Slack** — each messaging platform can gate slash commands by role, **scoped separately for DMs and groups**: when `allow_admin_from` (DMs) or `group_allow_admin_from` (groups) lists user IDs, admins get every command and non-admins get only the scope's allowlist — `user_allowed_commands` for DMs, `group_user_allowed_commands` for groups (plus `/help`, `/whoami`); if **no** admin list is set for a scope, gating is **off** for that scope and every allowed user can run everything. → **Permanent:** set the keys in the platform's `extra:` block in the active config file — resolve it first with `hermes config path` (`$HERMES_HOME` or a named profile redirects the default), then restart the gateway. **Temporary:** run the command from the CLI (no gating there) while you fix the platform config. (All four keys verified in `gateway/config_loader.py`.)
6. **Command exists but arguments vanish** — stacking parsing consumed what looked like a flag, or the command takes no args (e.g. `/plan` treats trailing text as its request). → Check the command's entry in `/help`; avoid leading `/` in arguments you want passed through.
7. **Aliases behave oddly** — many commands have aliases (`/reset`→`/new`, `/ctx`→`/context` — both verified in `hermes_cli/commands.py`); both dispatch identically. → Not a bug; check the canonical name in the reference.

## 3. Localization workflow

1. Type `/` and search the autocomplete — found? It's a dispatch/args issue (6/7). Not found? → step 2.
2. Which source should provide it? skill → **`diagnosing-skills`** (pitfall 1/2); bundle → `hermes bundles show <name>` (3); plugin → **`diagnosing-plugins`** (4); expected built-in → check `/help` and your Hermes version (`hermes --version`; built-ins gain commands over releases).
3. Surface-specific failure (CLI works, gateway doesn't) → pitfall 5.
4. Apply the fix, `/reload-skills` or restart as appropriate, confirm via autocomplete or invocation.

## Report

This skill diagnoses missing or overridden slash commands — skills as commands, skill bundles, plugin-registered commands, and per-platform admin/user permissions. When you run the diagnostic workflow, present findings in the standard format below.

### Summary
Your `/my-skill` command works in the CLI but not on Telegram because the platform's command gating is configured to restrict non-admin users. The command exists but is not in the Telegram allowlist for your user ID.

### Findings
| Severity | What | Evidence |
|---|---|---|
| HIGH | Command not in Telegram allowlist for non-admin users | Command works in CLI; Telegram returns "command not found"; `gateway.platforms.telegram.extra.user_allowed_commands` does not include `/my-skill` |
| MEDIUM | `allow_admin_from` is set, enabling gating | Config has `allow_admin_from: [12345]` but your user ID is not listed |

### Recommended Fix
Add `/my-skill` to `user_allowed_commands` in the Telegram platform's `extra:` block in `config.yaml`, then run `hermes gateway restart`. Alternatively, add your user ID to `allow_admin_from` to get all commands.

### References
- `$HERMES_HOME/config.yaml` — `gateway.platforms.telegram.extra:` block
- `gateway/config_loader.py` — the four gating keys (`allow_admin_from`, `group_allow_admin_from`, `user_allowed_commands`, `group_user_allowed_commands`)
- `hermes_cli/commands.py` — command registry and dispatch

---

*Facts re-verified 2026-10-09 against upstream source at commit `50035ef63c5536757e63bc1c1ffe4e5c19ac7fad`: no standalone command files (no `commands/` tree); bundle path `<HERMES_HOME>/skill-bundles/` and bundle-over-skill precedence (`agent/skill_bundles.py`); the stacking cap `_MAX_STACKED_SKILLS = 5` (`agent/skill_commands.py`); `ctx.register_command(name, handler, description=..., args_hint=...)` (`plugins/context_engine/__init__.py`); all four platform gating keys (`gateway/config_loader.py`); alias pairs `new`←`reset` and `context`←`ctx` (`hermes_cli/commands.py`). No claim required correction in this pass — comments were added so each load-bearing fact is traceable. Re-verify before reuse.*
