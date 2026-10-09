---
name: diagnosing-skills
description: Diagnose Hermes skills that are not discovered, not loading, shadowed, hidden by platform or toolset conditions, or stuck as user-modified after edits.
version: 1.1.6
metadata:
  hermes:
    tags: [hermes, skills, troubleshooting]
    related_skills: [hermes-configuration-guide]
---

# Diagnosing Skill Configuration

Goal: reduce any skill problem to one concrete fix. Distinguish **discovered** (appears in the index / as a `/command`) from **loading** (frontmatter parses) from **triggering** (the model chooses to use it) — they fail differently.

> **Disambiguation**: if the skill is present but its `/command` is missing or shadowed, see `diagnosing-commands` — that is a command-surface problem, not a skill-discovery problem.

## 1. Where skills come from

- **Local (source of truth)**: `$HERMES_HOME/skills/<category>/<name>/SKILL.md`. Bundled skills are seeded here on install and on every `hermes update` (a `.no-bundled-skills` marker opts a profile out). Agent-created and hub-installed skills land here too.
- **External dirs**: `skills.external_dirs` in `config.yaml` (supports `~` and `${VAR}`). Non-existent paths are **silently skipped**. On a name collision, **local wins**. Upstream documents these as **read-only / externally owned** (`agent/prompt_builder.py`: *"External dirs (`skills.external_dirs`) are read-only and lose name collisions to local skills"*), so treat an edit here as unreliable — with `skills.write_approval: true`, an agent-side write to an external skill is also staged rather than applied.
- **Hub/taps**: `hermes skills install` (official / skills-sh / well-known / github / url / clawhub / lobehub / browse-sh), each recorded in `skills/.hub/lock.json` with provenance for `hermes skills check`/`update`.
- **Plugin-bundled**: `ctx.register_skill(name, path)` — namespaced `plugin:skill`; only available while that plugin is enabled.

### Creation flows

| Flow | Where it lands | Who creates it | Authoritative? |
|---|---|---|---|
| **User-local** | `~/.hermes/skills/<category>/<name>/SKILL.md` (POSIX) or `%LOCALAPPDATA%\hermes\skills\...` (native Windows) | Agent via `skill_manage` tool with `action='create'` | Yes — local wins on collision |
| **In-repo authoring** | `skills/<category>/<name>/SKILL.md` or `optional-skills/<category>/<name>/SKILL.md` inside the hermes-agent repo | Contributor via `write_file` + `git add` | Ships with the package; not user-editable. `skill_manage(action='create')` does **not** target this tree |
| **Hub install** | `$HERMES_HOME/skills/<category>/<name>/SKILL.md` | `hermes skills install` (official / skills-sh / well-known / github / url / clawhub / lobehub / browse-sh) | Recorded in `skills/.hub/lock.json`; local copy wins on collision |
| **Plugin-bundled** | `ctx.register_skill(name, path)` — namespaced `plugin:skill` | Plugin developer | Only while that plugin is enabled |
| **External dirs** | `skills.external_dirs` in `config.yaml` | External tool/user | Read-only; loses to local on collision |

For in-repo authoring conventions (frontmatter standards, tier selection, description rules), see the upstream bundled skill `skills/software-development/hermes-agent-skill-authoring/SKILL.md` (v2.0.0) and `website/docs/developer-guide/creating-skills.md`.

## 2. SKILL.md format

`---` frontmatter requires `name` and `description` (house style: front-load the trigger wording — the index shows name + description and that is what the model matches on; keep the first ~60 characters to the point, and it is fine for the full description to run longer — verify triggering with a one-shot `hermes -z` ask if unsure). Optional: `version`, `platforms: [macos, linux, windows]`, `required_environment_variables`, and `metadata.hermes` — `tags`, `category`, and the conditional activation keys `fallback_for_toolsets` / `requires_toolsets` / `fallback_for_tools` / `requires_tools` / `session_platforms` (`agent/skill_utils.py::_CONDITION_KEYS` is the authoritative list — check it rather than trusting any doc, which can lag). **Two different surfaces — do not mix them:** the activation keys are evaluated from the **frontmatter** itself, so they only have effect there; a separate `metadata.hermes.config` declaration is the one that becomes runtime configuration under `skills.config`, surfaced by `hermes config migrate`. A `session_platforms` key placed in config does nothing.

## 3. How to inspect

- `hermes skills list` / in chat `/skills list` — everything discovered, including source.
- `skills_list` / `skill_view(name)` agent tools — exactly what the model sees.
- `/reload-skills` — re-scan after adding/removing files on disk.

## 4. Pitfalls (symptom → cause → fix)

1. **Not discovered** — directory not under a real skills root, or the file is not named exactly `SKILL.md`. → **Permanent:** move it to `$HERMES_HOME/skills/<category>/<name>/SKILL.md`. **Temporary:** `/reload-skills` to re-scan without restarting.
2. **Discovered as `/name` but name surprises you** — the slash command comes from the frontmatter `name`, not the directory name. → Align them or reference the frontmatter name.
3. **Edits to a shared/external copy never apply** — a same-named **local** skill shadows every external dir. → Edit the local copy, rename one, or delete the local shadow.
4. **Bundled skill stuck as "user-modified"** — you hand-restored a bundled skill by copy-paste; the `.bundled_manifest` origin hash no longer matches, so updates skip it forever. → `hermes skills reset <name>` (keep current) or `--restore` (pristine bundled copy). Per-profile.
5. **Skill hidden on this machine** — `platforms:` excludes the current OS, or conditional activation applies (`fallback_for_*` hides it when a toolset/tool IS available; `requires_*` hides it when one is NOT). → Check frontmatter; this hiding is intentional.
6. **Skill present but prompts for setup / fails at runtime** — `required_environment_variables` unset (local CLI prompts once; messaging surfaces never prompt). → Set the value in `$HERMES_HOME/.env` or run `hermes setup`.
7. **Agent's skill writes never land** — `skills.write_approval: true` stages every write under `$HERMES_HOME/pending/skills/`. → Review with `/skills pending`, `/skills diff <id>`, `/skills approve|reject <id>`; toggle the gate with `/skills approval off`.
8. **Hub skill drifted from upstream** — upstream changed after install. → **Temporary:** keep working; note the drift. **Permanent:** `hermes skills check` then `hermes skills update [name]`.
9. **New bundled skills never appear** — profile has a `.no-bundled-skills` marker. → `hermes skills opt-in --sync`.
10. **Plugin skill gone** — the providing plugin was disabled. → `hermes plugins enable <name>`.
11. **`hermes-agent` cannot be disabled** — it is in `ESSENTIAL_SKILLS` (`agent/skill_utils.py`): disable requests for it are ignored everywhere the disabled list is consulted, by design (it is the agent's operating manual and the system prompt points at it unconditionally). → Not a bug.

## 5. Duplicates & consolidation

When the same skill exists in several roots (local copy vs external dir vs plugin copy vs hub install), **local wins** and edits anywhere else silently no-op. To consolidate:

1. **Enumerate every copy**: `hermes skills list --source all` — note which sources have the skill.
2. **Pick the source of truth**: usually the local copy (`$HERMES_HOME/skills/<category>/<name>/SKILL.md`). If the skill should be hub-managed, the hub install is the source of truth.
3. **Consolidate**:
   - If the local copy is the source of truth: edit it directly, then remove shadows (`hermes skills reset <name>` for bundled, or delete the external-dir copy).
   - If a hub install is the source of truth: `hermes skills update <name>` to pull the latest, then remove any local shadow.
   - If a plugin copy is the source of truth: ensure the plugin is enabled (`hermes plugins enable <name>`).
4. **Re-verify**: `hermes skills list --source all` to confirm only the intended source remains, then `skill_view(name)` to confirm content.

## 6. Localization workflow

1. `/reload-skills`, then `hermes skills list` — absent? → pitfalls 1, 5, 10, 9.
2. Present but wrong content? → check shadowing (3) and provenance (`hermes skills list --source hub`).
3. Present, correct, but the model ignores it? → description quality (2 §2): make the first ~60 characters state when to use it.
4. Agent-side write issues? → gate (7).
5. Apply the fix and verify with `skill_view(name)` or by invoking `/<name>`.

## Report

This skill diagnoses skills that are not discovered, not loading, shadowed, hidden by platform or toolset conditions, or stuck as user-modified after edits. When you run the diagnostic workflow, present findings in the standard format below.

### Summary
Your skill edits have no effect because a same-named local skill in `$HERMES_HOME/skills/` is shadowing the external dir copy you are editing. The local copy wins on name collision, so your changes to the external copy are silently ignored.

### Findings
| Severity | What | Evidence |
|---|---|---|
| HIGH | Local skill shadows external dir copy | `hermes skills list --source all` shows the skill exists in both `local` and `external` sources; `skill_view(name)` returns the local copy's content, not your edits |
| MEDIUM | Edits to external copy are unreliable | External dirs are documented as read-only (`agent/prompt_builder.py`: "External dirs are read-only and lose name collisions to local skills") |

### Recommended Fix
Edit the local copy at `$HERMES_HOME/skills/<category>/<name>/SKILL.md` directly, or remove the local shadow with `hermes skills reset <name>` if the external copy should be the source of truth. Then run `/reload-skills` and verify with `skill_view(name)`.

### References
- `$HERMES_HOME/skills/<category>/<name>/SKILL.md` — the local shadow
- `agent/prompt_builder.py` — external-dir ownership and collision rules
- `agent/skill_utils.py` — `_CONDITION_KEYS`, `ESSENTIAL_SKILLS`

---

*Facts re-verified 2026-10-09 against upstream source at commit `50035ef63c5536757e63bc1c1ffe4e5c19ac7fad`: all eight hub source names (`tools/skills_hub_*.py`), `_CONDITION_KEYS` and `ESSENTIAL_SKILLS` (`agent/skill_utils.py`), external-dir ownership (`agent/prompt_builder.py`), `skills/.hub/lock.json` (`tools/skills_hub.py`), the bundled marker and `skills opt-in --sync` / `skills reset --restore` paths (`hermes_cli/`), `required_environment_variables` (`tools/skills_tool.py`), the skills-scoped `write_approval` and `$HERMES_HOME/pending/skills/`, and `plugin:skill` qualified dispatch (`tools/skills_tool.py`). Creation flows table and duplicates & consolidation section added 2026-10-06, verified against upstream `skills/software-development/hermes-agent-skill-authoring/SKILL.md` (v2.0.0) at pinned baseline `5000e29936df69d5209f7cf2eea8e5776cb4cbb1`. Re-verify before reuse.*
