# Hermes Guide

> **Package / slug:** `hermes-guide`

Hermes usage and self-diagnosis guide for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

It **complements — never replaces —** Hermes's own diagnostics (`hermes doctor`, `hermes verify`, and the per-surface helpers): it covers the gaps they leave. It ships two independent things:

1. **A plugin.** `/hermes-doctor` in a session, `hermes guide` in a terminal. Read-only health checks across <!-- BEGIN GENERATED: intro-scopes -->
`config`, `mcp`, `skills`, `commands`, `hooks`, `plugins`, `memories`
<!-- END GENERATED: intro-scopes --> — every one of those names is a valid scope.
2. **A skills tap.** <!-- BEGIN GENERATED: intro-inventory -->
**Twenty troubleshooting skills** — one install guide, one configuration map, and eighteen per-surface `diagnosing-*` playbooks.
<!-- END GENERATED: intro-inventory -->

## Install the plugin

```bash
hermes plugins install redsurge/hermes-guide --enable
```

This clones the repo from GitHub and enables it. To pin an immutable commit:

```bash
hermes plugins install redsurge/hermes-guide --ref <40-char-SHA> --enable
```

### Manual install

Alternatively, clone this repo into your Hermes plugins directory:

```bash
# POSIX / WSL: $HERMES_HOME is ~/.hermes
git clone --depth 1 https://github.com/redsurge/hermes-guide ~/.hermes/plugins/hermes-guide
hermes plugins enable hermes-guide
```

A clone (rather than `cp -r .`) keeps VCS metadata and local caches out of the plugin directory.

> [!NOTE]
> On native Windows `$HERMES_HOME` is `%LOCALAPPDATA%\hermes`, not `~/.hermes`. Run `hermes config path` to confirm where yours is.

## Use the plugin

- **In a session:** `/hermes-doctor` for every surface, or `/hermes-doctor mcp` for one.
- **In a terminal:** `hermes guide`. Exits `1` if any surface is broken or unknown, `2` for an unrecognized scope name, `0` when healthy.

### Proactive mode (opt-in)

Add to `config.yaml`:

```yaml
plugins:
  entries:
    hermes-guide:
      settings:
        proactive: true
```

Drift findings are then logged at session start/end — watch `hermes logs --follow`.

## Install the skills

Installing the plugin does **not** install the skills; they ship as separate, opt-in reference material. Add the repo as a skills tap, then install what you want:

```bash
hermes skills tap add redsurge/hermes-guide
hermes skills install redsurge/hermes-guide/skills/diagnosing-mcp
```

> [!IMPORTANT]
> The identifier must include the `skills/` prefix — it is the repo-relative path to the skill's `SKILL.md`. The shorter `redsurge/hermes-guide/<name>` form does not resolve.

### Install all skills at once

<!-- BEGIN GENERATED: install-all-loop -->
```bash
for s in diagnosing-auth diagnosing-bot-mode diagnosing-browser diagnosing-cli-tui diagnosing-commands diagnosing-cron diagnosing-desktop diagnosing-gateway diagnosing-hooks diagnosing-host-pressure diagnosing-mcp diagnosing-memory diagnosing-path diagnosing-plugins diagnosing-providers diagnosing-skills diagnosing-triage diagnosing-voice hermes-configuration-guide installing-hermes; do hermes skills install "redsurge/hermes-guide/skills/$s"; done
```
<!-- END GENERATED: install-all-loop -->

Each skill still passes its own scan and consent individually, so it stays individually updatable. Every installed skill is also available as a slash command (e.g. `/diagnosing-mcp`).

## What's included

| Skill | Purpose |
|---|---|
| `installing-hermes` | Install routes — install.sh/Desktop/Nix, what each creates on disk, config bootstrap, update/uninstall, and the gotchas (PM-era runtime layout, NixOS specifics) |
| `hermes-configuration-guide` | The map: resolving `$HERMES_HOME`, where each surface is configured, instruction files, orphaned/legacy settings, and routing to the diagnostic skills |
| `diagnosing-mcp` | MCP servers that won't connect, expose no tools, fail OAuth, or ignore `mcp_servers:` config |
| `diagnosing-skills` | Skills not discovered, shadowed, hidden by platform/toolset conditions, or stuck "user-modified" |
| `diagnosing-commands` | Missing or overridden slash commands — skills-as-commands, bundles, plugin commands, per-platform permissions |
| `diagnosing-hooks` | Hooks that don't fire — the four hook systems, shell-hook consent, `hermes hooks doctor` |
| `diagnosing-plugins` | Plugins that don't load — the `plugins.enabled` gate, capability consent, discovery locations |
| `diagnosing-path` | Path issues — the dual-venv layout on older checkouts, the PM-era no-in-tree-venv case, detection, canonical resolution order, cross-platform best practices |
| `diagnosing-triage` | Route vague user descriptions to the correct diagnostic skill — a triage layer that maps symptoms to the right `diagnosing-*` playbook |
| `diagnosing-cli-tui` | CLI/TUI issues on native Windows — rendering artifacts, themes, busy indicators, mouse modes, encoding, launch/resume |
| `diagnosing-auth` | Hub-install auth failures — dead/shadowing `GITHUB_TOKEN` in the profile `.env`, `gh-cli` fallback, 401 vs anonymous probes, rate-limit verdicts |
| `diagnosing-memory` | Memory problems — built-in `MEMORY.md`/`USER.md` stores, external providers configured but silently unavailable, missing plugins/keys, char-limit and approval gates |
| `diagnosing-desktop` | Desktop app build/launch failures — npm/Node issues, locked or torn builds, Electron download fallbacks, backend resolution, `desktop.*` config |
| `diagnosing-providers` | Model provider issues — custom endpoints flooding the picker with hundreds of models, `discover_models` misbehaving, persisted catalogs bloating `config.yaml`, provider/auth failures |
| `diagnosing-bot-mode` | Bot Mode issues — bots not appearing, profile conflicts, bot-to-bot messaging, model/memory/skill routing per bot |
| `diagnosing-voice` | Voice mode issues — STT/TTS provider failures, audio device problems, latency, ffmpeg missing, voice transcription |
| `diagnosing-browser` | Browser automation issues — CDP connection failures, Chrome 144+ compatibility, Playwright setup, agent-browser gating |
| `diagnosing-cron` | Cron job issues — jobs not firing, scheduler dead, wedged fire-claim, timezone issues, delivery failures |
| `diagnosing-gateway` | Gateway & messaging issues — bot not responding, platform allowlist, token validation, gateway connectivity |
| `diagnosing-host-pressure` | Host resource exhaustion presenting as multiple Hermes faults — load-vs-CPU, plugin load-budget discards, resolution order |

## Design principle

**Complement, don't duplicate.** When a built-in already answers the question, use it — hermes-guide exists for the gaps: deep per-surface playbooks, deterministic read-only health checks, and the routing map between surfaces. If a check here ever starts duplicating a built-in, the built-in wins and the check gets trimmed.

Every diagnosis resolves to a concrete action: a `hermes <subcommand>` command or a specific file + field edit, then a `/reload-*` or restart to apply.

## Contributing

Skills track the Hermes Agent source and its shipped documentation (`website/docs/` in `hermes-agent`). When Hermes changes behavior, update the affected skill and bump its `version`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
