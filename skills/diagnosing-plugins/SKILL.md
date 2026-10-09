---
name: diagnosing-plugins
description: Diagnose Hermes plugins that do not load or run — the plugins.enabled opt-in gate, capability consent, discovery locations, and provider sub-categories.
version: 1.2.4
metadata:
  hermes:
    tags: [hermes, plugins, troubleshooting]
    related_skills: [hermes-configuration-guide, diagnosing-host-pressure]
---

# Diagnosing Plugins

A Hermes plugin is a **Python package**: a directory with a `plugin.yaml` manifest and a `register(ctx)` function. The single most common failure: **the plugin is discovered but not enabled** — Hermes deliberately loads nothing from third-party code until you add it to `plugins.enabled`.

> **Disambiguation**: if a provider sub-category (e.g. `context.engine`, `image_gen.provider`) is misconfigured, see `diagnosing-providers` — that is a provider configuration problem, not a plugin-loading problem.

## 1. Discovery locations (later sources override same-name earlier ones)

| Source | Path | Gate |
|---|---|---|
| Bundled | `<install>/plugins/` | Platform/backend sub-plugins auto-load; bundled standalone plugins still need opt-in |
| User | `$HERMES_HOME/plugins/<name>/` | `plugins.enabled` allow-list |
| Project | `<repo>/.hermes/plugins/` | Requires `HERMES_ENABLE_PROJECT_PLUGINS=true` at startup |
| pip | `hermes_agent.plugins` entry points | `plugins.enabled` |
| Nix | `services.hermes-agent.extraPlugins` | Nix config |

`hermes plugins install owner/repo [--ref <40-char SHA>] [--enable|--no-enable]` installs from Git (pinned commits only); `hermes plugins update` refuses to move a pinned plugin. Sub-category directories have their **own loaders and selection keys** — they do not obey `plugins.enabled`. Verified present at current main: `platforms/<name>/` (messaging channels, gated per messaging platform in config), `memory/<name>/` (one active, `memory.provider`), `context_engine/<name>/` (`context.engine`), `model-providers/<name>/` (picked via `--provider`/config), `image_gen/<name>/` (`image_gen.provider`), plus `browser/`, `video_gen/`, `cron_providers/`, `observability/`, `dashboard_auth/`, `google_meet/`, `spotify/`, `teams_pipeline/`, `web/`. **Not every bundled entry auto-loads:** upstream's discovery reports disabled bundled plugins as *"not enabled in config (run `hermes plugins enable <key>` to activate)"* (`hermes_cli/plugins_discovery.py`), and bundled Kanban is one of them — check `hermes plugins list` for the real state instead of assuming a bundled directory is live. **The set grows — list `plugins/` in the installed source instead of trusting this list.**

## 2. The enable gate and capabilities

```yaml
plugins:
  enabled: [my-plugin]
  disabled: [noisy-plugin]   # deny-list always wins over enabled
```

Three ways to flip: `hermes plugins` (interactive), `hermes plugins enable <name>`, `hermes plugins disable <name>`. Declared capabilities require a separate one-time consent recorded under `plugins.entries.<id>.granted_capabilities` (legacy `allow_*` keys are still read). Verified capability ids at current main: **`tools.override`** and **`gateway.platform_actions`** — this list is code-defined and grows, so check `plugin_capability_granted()` / `ctx.has_capability()` rather than trusting any doc (an earlier revision of this skill named a `llm.model_override` id that **does not exist**). Two behaviours worth knowing: **bundled plugins are trusted for `tools.override`** (no consent needed), and unknown ids or unreadable consent **fail closed** (False). **Non-interactive installs/enables grant nothing** — the plugin runs with capabilities off and must degrade gracefully (`ctx.has_capability()`).

## 3. How to inspect

- `hermes plugins` — interactive UI (SPACE toggles enabled).
- `hermes plugins list` — enabled / disabled / not-enabled per plugin.
- `hermes plugins capabilities [name]` — declared vs granted.
- `/plugins` in chat — status listing.
- `hermes logs --follow` — a plugin whose `register()` raises is skipped with a logged error (never crashes Hermes), so read the log for load failures.

## 4. Pitfalls (symptom → cause → fix)

1. **Installed but tools/hooks/commands absent** — not in `plugins.enabled` (install defaults to disabled; `--enable` or the post-install prompt is opt-in). → **Permanent:** add it to `plugins.enabled` (`hermes plugins enable <name>`) and restart. **Temporary:** there is no read-only way to load a disabled plugin — enabling is the fix, so do it deliberately rather than working around it. Bundled standalone plugins are opt-in too — only platform/backend sub-plugins auto-load.
2. **Plugin works but a privileged feature is off** — capability declared but never granted (non-TTY install, or declined). → `hermes plugins capabilities <name>`; re-consent via interactive `hermes plugins enable <name>`.
3. **Project plugin ignored** — `.hermes/plugins/` is disabled by default. → Set `HERMES_ENABLE_PROJECT_PLUGINS=true` before starting Hermes, and only for trusted repos.
4. **Plugin in `list` but nothing loads at all** — `register()` raised (bad code, missing dependency). → Check `hermes logs` for the load error; fix the plugin or its requirements. If the log instead says `load timed out after Ns` (optionally followed by `called register_*() after its load timed out; ignored`), the loader's own budget expired before `import()` + `register()` returned. That budget covers the **plugin's** work as much as the host's, so the message alone does not tell you which one was too slow — a slow import or a blocking `register()` reaches the same deadline on a healthy host. Check the load-timeout figure in that plugin's `__init__.py` against what its own import and `register()` actually do, and run `diagnosing-host-pressure` to rule the host in or out. Only treat it as host pressure once the probe says so.
5. **Edits to a bundled plugin don't apply** — a same-name user plugin at `$HERMES_HOME/plugins/<name>/` overrides the bundled copy. → Edit the user copy (the one that actually wins) or remove it.
6. **`hermes plugins update` refuses** — the install is pinned to an exact commit SHA. → Choose a new commit explicitly: `hermes plugins install <source> --force --ref <new-sha>`.
7. **Plugin edits after install lost on update** — updates autostash and re-apply local edits, but conflicts can drop them. → Keep plugin customizations in your own fork/repo and install from that.
8. **It's not really a plugin** — TTS/STT command providers are config-driven (`tts.providers.<name>` / `stt.providers.<name>` with `type: command`); MCP integrations are `mcp_servers:` entries; gateway hooks are directories. → Route to the right surface: **`diagnosing-mcp`**, **`diagnosing-hooks`**, or the config docs.

## 5. Localization workflow

1. `hermes plugins list` — is it discovered? No → wrong location / not installed (§1 table; project plugins → pitfall 3).
2. Discovered but "not enabled" → pitfall 1 (`hermes plugins enable`).
3. Enabled but broken → `hermes logs` for a `register()` failure (pitfall 4) or a capability gap (pitfall 2). A **load-timeout** message points at host pressure, not the plugin → `diagnosing-host-pressure`.
4. Sub-category plugin (memory/context/model-provider/platform) → check its selection key in config, not `plugins.enabled`.
5. Restart the session/gateway and verify: tools appear in `/tools list`, commands in `/` autocomplete, hooks via `hermes hooks list`.

## Report

This skill diagnoses plugins that do not load or run — the plugins.enabled opt-in gate, capability consent, discovery locations, and provider sub-categories. When you run the diagnostic workflow, present findings in the standard format below.

### Summary
Your plugin is installed but its tools and commands are absent because it is not in the `plugins.enabled` allowlist. Hermes deliberately loads nothing from third-party code until you explicitly enable it.

### Findings
| Severity | What | Evidence |
|---|---|---|
| HIGH | Plugin not in `plugins.enabled` | `hermes plugins list` shows `my-plugin: not enabled`; no tools or commands from the plugin appear in the session |
| MEDIUM | Plugin discovered but not enabled after install | `hermes plugins list` shows the plugin under "Installed" but not under "Enabled" |

### Recommended Fix
Run `hermes plugins enable my-plugin`, then restart the session. Verify with `hermes plugins list` (should show "Enabled") and check that the plugin's tools appear in `/tools list`.

### References
- `$HERMES_HOME/config.yaml` — `plugins.enabled` list
- `hermes_cli/plugins.py` — `plugins.enabled` handling
- `hermes_cli/plugins_discovery.py` — plugin discovery and "not enabled" message

---

*Facts re-verified 2026-10-09 against upstream source at commit `50035ef63c5536757e63bc1c1ffe4e5c19ac7fad` (corrective pass): entry-point group `hermes_agent.plugins` and the project-plugins gate `HERMES_ENABLE_PROJECT_PLUGINS` (`plugins/memory/__init__.py`, `hermes_cli/plugin_dev.py`); the capability set and fail-closed behaviour (`hermes_cli/plugins.py::has_capability`, `plugin_capability_granted`); `plugins.enabled` handling (`hermes_cli/plugins.py`); the sub-category directory list (`plugins/`, narrowed in the corrective pass — bundled Kanban is gated by `plugins.enabled`, per `hermes_cli/plugins_discovery.py`); selection keys `context.engine` (`hermes_cli/web_server_config.py`) and `image_gen.provider` (`agent/image_gen_*.py`). One claim was corrected (the nonexistent `llm.model_override` id). Re-verify before reuse.*
