---
name: diagnosing-triage
description: "Route vague user descriptions to the correct diagnostic skill â€” a triage layer that maps symptoms to the right diagnosing-* playbook."
version: 1.0.1
metadata:
  hermes:
    tags: [hermes, triage, routing, diagnostics]
    related_skills: [hermes-configuration-guide, diagnosing-cli-tui, diagnosing-path, diagnosing-host-pressure, diagnosing-commands, diagnosing-mcp, diagnosing-skills, diagnosing-plugins, diagnosing-hooks, diagnosing-auth, diagnosing-memory, diagnosing-desktop, diagnosing-providers, diagnosing-bot-mode, diagnosing-browser, diagnosing-cron, diagnosing-gateway, diagnosing-voice, installing-hermes]
---

# Diagnosing Triage

Route vague user descriptions to the correct diagnostic skill. This is the **triage layer** â€” when the user says "something is wrong" without naming a subsystem, use the flowchart and mapping table below to pick the right `diagnosing-*` playbook.

> **Disambiguation**: this skill does **not** diagnose anything itself. It only routes. Once you have identified the target skill, load that skill and follow its playbook. If the description is too vague to route, ask the clarifying questions in Â§3 before guessing.

## 0. When to use this skill

Load this skill when the user's description is **non-specific** â€” they know something is broken but haven't (or can't) name the subsystem. Typical triggers:

- "Something is wrong with Hermes."
- "It's slow." / "It keeps timing out."
- "It crashed." / "It stopped working."
- "The bot isn't responding." (without saying which platform or layer)
- "Skills aren't working." (without saying whether it's discovery, triggering, or a `/command`)
- "I can't install anything." (without saying whether it's skills, plugins, or the whole app)

Do **not** load this skill when the user has already named a specific subsystem ("MCP won't connect", "a hook isn't firing", "the TUI looks garbled") â€” go directly to the relevant `diagnosing-*` skill.

## 1. Triage flowchart

Start at the top. Follow the first branch that matches the user's description.

```
Is the problem about INSTALLING or UPGRADING Hermes itself?
  â””â”€ YES â†’ installing-hermes
  â””â”€ NO â†“

Is the problem about HOST RESOURCES â€” high load, OOM, plugin discards,
  resource exhaustion, multiple surfaces failing at once?
  â””â”€ YES â†’ diagnosing-host-pressure
  â””â”€ NO â†“

Is the problem about the DESKTOP APP (Electron) not launching,
  showing a blank window, or npm/build errors?
  â””â”€ YES â†’ diagnosing-desktop
  â””â”€ NO â†“

Is the problem about the CLI/TUI â€” rendering, themes, busy indicators,
  mouse modes, encoding, garbled output, launch/resume?
  â””â”€ YES (native Windows; POSIX/WSL: `hermes doctor`) â†’ diagnosing-cli-tui
  â””â”€ NO â†“

Is the problem about PATHS, VENVS, or the wrong Python interpreter?
  â””â”€ YES â†’ diagnosing-path
  â””â”€ NO â†“

Is the problem about a MESSAGING PLATFORM â€” bot not responding,
  platform allowlist, token validation, gateway connectivity?
  â””â”€ YES â†’ diagnosing-gateway
  â””â”€ NO â†“

Is the problem about a BOT PROFILE â€” bots not appearing, profile conflicts,
  bot-to-bot messaging?
  â””â”€ YES â†’ diagnosing-bot-mode
  â””â”€ NO â†“

Is the problem about BROWSER AUTOMATION â€” CDP connection failures,
  Chrome version, Playwright, agent-browser?
  â””â”€ YES â†’ diagnosing-browser
  â””â”€ NO â†“

Is the problem about SCHEDULED JOBS â€” cron not firing, scheduler dead,
  wedged fire-claim, timezone issues?
  â””â”€ YES â†’ diagnosing-cron
  â””â”€ NO â†“

Is the problem about VOICE â€” STT/TTS failures, audio device, latency, ffmpeg?
  â””â”€ YES â†’ diagnosing-voice
  â””â”€ NO â†“

Is the problem about AUTH â€” "Could not fetch from any source", GitHub 401,
  rate-limit 403, hub install fails?
  â””â”€ YES â†’ diagnosing-auth
  â””â”€ NO â†“

Is the problem about MEMORY â€” agent forgot, memory provider down,
  MEMORY.md/USER.md errors?
  â””â”€ YES â†’ diagnosing-memory
  â””â”€ NO â†“

Is the problem about PROVIDERS â€” provider picker flooded, discover_models,
  auth failures, model catalog bloat?
  â””â”€ YES â†’ diagnosing-providers
  â””â”€ NO â†“

Is the problem about MCP â€” server won't connect, no tools, OAuth, config?
  â””â”€ YES â†’ diagnosing-mcp
  â””â”€ NO â†“

Is the problem about SKILLS â€” not discovered, shadowed, hidden, user-modified?
  â””â”€ YES â†’ diagnosing-skills
  â””â”€ NO â†“

Is the problem about SLASH COMMANDS â€” missing, overridden, skills-as-commands,
  bundles?
  â””â”€ YES â†’ diagnosing-commands
  â””â”€ NO â†“

Is the problem about HOOKS â€” not firing, gateway HOOK.yaml, plugin hooks,
  shell hooks?
  â””â”€ YES â†’ diagnosing-hooks
  â””â”€ NO â†“

Is the problem about PLUGINS â€” not loading, not enabled, plugins.enabled gate?
  â””â”€ YES â†’ diagnosing-plugins
  â””â”€ NO â†“

Still unsure?
  â””â”€ Ask the clarifying questions in Â§3.
  â””â”€ If the user is asking "where is X configured?" â†’ hermes-configuration-guide
```

## 2. Symptom â†’ Skill mapping table

Comprehensive mapping from specific symptoms to the target diagnostic skill. When the user's description matches a row, load that skill directly.

| Symptom | Target skill |
|---|---|
| "Could not fetch from any source" / "Could not find â€¦ in any source" | diagnosing-auth |
| GitHub 401 on hub installs | diagnosing-auth |
| Rate-limit 403 during installs | diagnosing-auth |
| `hermes skills install` / `hermes plugins install` fails | diagnosing-auth |
| Bots not appearing in chat | diagnosing-bot-mode |
| Profile conflicts between bots | diagnosing-bot-mode |
| Bot-to-bot messaging broken | diagnosing-bot-mode |
| CDP connection failures | diagnosing-browser |
| Chrome 144+ compatibility | diagnosing-browser |
| Playwright errors | diagnosing-browser |
| agent-browser not working | diagnosing-browser |
| CLI glitches / rendering artifacts | diagnosing-cli-tui |
| Themes / skins not applying | diagnosing-cli-tui |
| Busy indicators unreadable | diagnosing-cli-tui |
| Mouse modes not working | diagnosing-cli-tui |
| Encoding / mojibake issues | diagnosing-cli-tui |
| CLI/TUI issues on POSIX/WSL | `hermes doctor` + the `display:` block of `config.yaml` (no dedicated skill yet) |
| Missing slash commands | diagnosing-commands |
| Overridden slash commands | diagnosing-commands |
| Skills-as-commands not appearing | diagnosing-commands |
| Skill bundles not loading | diagnosing-commands |
| Cron not firing | diagnosing-cron |
| Scheduler dead / wedged | diagnosing-cron |
| Fire-claim stuck | diagnosing-cron |
| Timezone wrong | diagnosing-cron |
| Desktop app won't launch | diagnosing-desktop |
| npm errors on desktop | diagnosing-desktop |
| Blank window on launch | diagnosing-desktop |
| Electron crash | diagnosing-desktop |
| Bot not responding on platform | diagnosing-gateway |
| Platform allowlist issues | diagnosing-gateway |
| Token validation failures | diagnosing-gateway |
| Hooks not firing | diagnosing-hooks |
| Gateway HOOK.yaml errors | diagnosing-hooks |
| Plugin hooks broken | diagnosing-hooks |
| Shell hooks not executing | diagnosing-hooks |
| High system load during agent operation | diagnosing-host-pressure |
| OOM kills | diagnosing-host-pressure |
| Plugin discards after load timeout | diagnosing-host-pressure |
| Resource exhaustion | diagnosing-host-pressure |
| MCP won't connect | diagnosing-mcp |
| MCP tools not appearing | diagnosing-mcp |
| MCP OAuth failures | diagnosing-mcp |
| MCP config errors | diagnosing-mcp |
| Agent forgot something | diagnosing-memory |
| Memory provider down | diagnosing-memory |
| MEMORY.md errors | diagnosing-memory |
| USER.md errors | diagnosing-memory |
| Path / venv confusion | diagnosing-path |
| Dual-venv layout issues | diagnosing-path |
| Wrong Python interpreter | diagnosing-path |
| Plugin not loading | diagnosing-plugins |
| Plugin not enabled | diagnosing-plugins |
| plugins.enabled gate blocking | diagnosing-plugins |
| Provider picker flooded | diagnosing-providers |
| discover_models misbehaving | diagnosing-providers |
| Provider auth failures | diagnosing-providers |
| Model catalog bloat | diagnosing-providers |
| Skills not discovered | diagnosing-skills |
| Skills shadowed | diagnosing-skills |
| Skills hidden | diagnosing-skills |
| Skills stuck "user-modified" | diagnosing-skills |
| STT/TTS failures | diagnosing-voice |
| Audio device not found | diagnosing-voice |
| Voice latency | diagnosing-voice |
| ffmpeg errors | diagnosing-voice |
| "Where is X configured?" | hermes-configuration-guide |
| Install / reinstall / upgrade / uninstall | installing-hermes |

## 3. Clarifying questions

When the description is too vague to route with confidence, ask these questions before guessing. Pick the question(s) that match the ambiguity.

### Scope questions

- **"Is this about the CLI/TUI, the desktop app, or a messaging platform?"**
  - CLI/TUI (native Windows) â†’ diagnosing-cli-tui; POSIX/WSL â†’ `hermes doctor`
  - Desktop app â†’ diagnosing-desktop
  - Messaging platform â†’ diagnosing-gateway (or diagnosing-bot-mode if it's about bot profiles)

- **"Is this about a specific feature (MCP, skills, hooks, plugins) or general performance?"**
  - Specific feature â†’ route to that feature's skill
  - General performance â†’ diagnosing-host-pressure

### History questions

- **"Did this work before and stop, or never work?"**
  - Worked before, stopped â†’ likely config drift, token expiry, or resource pressure; check diagnosing-auth, diagnosing-host-pressure, or the relevant feature skill
  - Never worked â†’ likely install, path, or config issue; check installing-hermes, diagnosing-path, or hermes-configuration-guide

### Consistency questions

- **"Is the problem consistent or intermittent?"**
  - Consistent â†’ likely a config or code issue; route to the relevant feature skill
  - Intermittent â†’ likely resource pressure, rate-limiting, or a race condition; check diagnosing-host-pressure or diagnosing-auth

### Surface questions

- **"Is this about installing something, or about something that's already installed?"**
  - Installing â†’ diagnosing-auth (hub installs) or installing-hermes (Hermes itself)
  - Already installed â†’ route to the relevant feature skill

## 4. Escalation

When multiple skills might apply, use these priority rules to decide which to load first.

### Priority order

1. **Host pressure before per-surface config.** If multiple surfaces are failing at once, or if adapters are being discarded after a load timeout, load `diagnosing-host-pressure` first. Resource exhaustion mimics dozens of unrelated config bugs.

2. **Auth before hub operations.** If a hub install or inspect fails with "not found" messages, load `diagnosing-auth` before `diagnosing-skills`. A dead token degrades every source adapter to "not found" at once.

3. **Path before feature config.** If the wrong Python interpreter is active or the venv layout is confusing, load `diagnosing-path` before any feature-specific skill. Path issues cause cascading failures that look like feature bugs.

4. **Install before diagnosis.** If Hermes itself is broken (won't start, crashes on load), load `installing-hermes` before any `diagnosing-*` skill. You can't diagnose a broken install.

5. **Platform before bot-mode.** If the bot isn't responding, load `diagnosing-gateway` before `diagnosing-bot-mode`. Gateway connectivity is a prerequisite for bot profiles.

### When to load multiple skills

Some problems span multiple layers. In these case, load the higher-priority skill first, then the second:

- **Skill not discovered AND `/command` missing** â†’ load `diagnosing-skills` first (if the skill itself is missing from the index, the `/command` won't exist either). If the skill is present but the `/command` is shadowed, load `diagnosing-commands` instead.

- **MCP server up but no tools AND provider configured but unavailable** â†’ load `diagnosing-mcp` first (the MCP server is the more specific failure). If the MCP server connects fine but the model provider is the problem, load `diagnosing-providers`.

- **Memory not persisting AND external memory provider configured** â†’ load `diagnosing-memory` (it owns both built-in and external memory diagnosis).

- **Several faults at once, intermittently** â†’ load `diagnosing-host-pressure` first. Intermittent multi-surface failures are the signature of resource pressure.

### When to use hermes-configuration-guide

If the user is asking "where is X configured?" rather than "X is broken", load `hermes-configuration-guide` instead of a diagnostic skill. The configuration guide maps each extension surface to its config location and points to the right diagnostic skill if something is wrong.

---

## 5. Report format

When the triage skill routes to a diagnostic skill, the model reports findings using the standard format defined in `hermes-configuration-guide`. The triage skill itself reports only the routing decision:

**Triage report example**:

- **Summary**: "Your description matches a host resource pressure problem. Load average is high with idle CPU, indicating I/O bottleneck."
- **Routed to**: `diagnosing-host-pressure`
- **Reason**: "High load + idle CPU + plugin load timeouts = host pressure, not Hermes config"
- **Next step**: "Run `bash skills/diagnosing-host-pressure/scripts/host_pressure_probe.sh` and follow the resolution order in that skill."

*Triage mappings derived from the skill descriptions in this repo's `skills/` directory (2026-10-09). No upstream source verification is claimed â€” this skill routes between hermes-guide's own skills. Re-verify before reuse.*
