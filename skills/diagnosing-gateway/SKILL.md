---
name: diagnosing-gateway
description: Diagnose Hermes gateway and messaging platform issues — bot not responding, platform allowlist confusion, token validation, gateway connectivity, and multi-platform setup.
version: 1.1.3
metadata:
  hermes:
    tags: [hermes, gateway, messaging, troubleshooting]
    related_skills: [hermes-configuration-guide, diagnosing-auth, diagnosing-bot-mode]
---

# Diagnosing Gateway & Messaging

Goal: reduce any messaging problem to one concrete fix — a gateway restart, a token refresh, or an allowlist entry. The gateway connects Hermes to 20+ messaging platforms.

## 1. Configuration shape

Platform config lives under `gateway.platforms.<name>` in `config.yaml`, but **each platform has its own schema** — there is no universal `token`/`allowlist`/`enabled` shape. Telegram uses polling/webhook with `token`; Discord uses `bot_token` and intents; Matrix uses `homeserver` + `access_token`; WhatsApp uses QR pairing. Always run `hermes gateway setup` for the target platform to see the actual fields.

> [!WARNING]
> Do not copy-paste a `gateway.platforms.<name>` block from one platform to another. Applying a Telegram-shaped block to Discord (or vice versa) silently ignores credentials and the platform will not connect.

## 2. How to inspect

- `hermes gateway status` — gateway process status, platform connections
- `hermes gateway status --deep --full` — detailed diagnostics (macOS: use full PATH)
- `hermes gateway start` / `hermes gateway restart` — manage gateway lifecycle
- `hermes gateway setup` — interactive platform setup wizard (shows actual fields per platform)
- `hermes logs --follow` — watch gateway logs in real-time
- `~/.hermes/logs/gateway.log` — gateway log file

## 3. Pitfalls (symptom → cause → fix)

1. **Bot not responding to messages** — (a) gateway not running; (b) bot not authorized; (c) user not in allowlist; (d) token expired. → Run `hermes gateway status`; start gateway (`hermes gateway start`); check allowlist in config.yaml; verify token with `hermes gateway setup`.
2. **Messages not delivering** — (a) invalid bot token; (b) platform API down; (c) network issue. → Verify token with `hermes gateway setup`; check platform status page; test network connectivity.
3. **Allowlist confusion — who can talk to the bot?** — (a) user not on platform-specific allowlist; (b) wrong access mode (pairing vs allowlist); (c) first DM already claimed by another user. → Run `hermes gateway setup <platform>` to see the actual access-mode options for that platform; check `gateway.platforms.<name>` in config.yaml for the platform-specific allowlist field.
4. **Gateway crashes on start** — (a) invalid config.yaml; (b) port already in use; (c) missing dependencies. → Check `~/.hermes/logs/gateway.log`; verify config.yaml syntax; check for port conflicts (`lsof -i :<port>`).
5. **Platform shows as disconnected** — (a) token expired or revoked; (b) platform API changed; (c) network/firewall blocking. → Re-authenticate via `hermes gateway setup`; check platform API status; verify network/firewall rules.
6. **Bot responds twice** — (a) duplicate gateway processes; (b) platform retry on timeout. → Check `launchctl list | grep -i hermes` (macOS); kill duplicate processes; check platform retry settings.
7. **Voice messages not transcribing on Telegram** — ffmpeg unavailable. → ffmpeg is a PM-managed required runtime tool on a PM-era install, so check it with `hermes pm status` / `hermes doctor` and restore it with `hermes pm install ffmpeg` (or `hermes update`); on an older checkout install it with your system package manager (`apt install ffmpeg`, `brew install ffmpeg`). Restart the gateway afterward.
8. **Gateway not persisting across reboots** — (a) no launchd/systemd service; (b) gateway not set to auto-start. → Create launchd plist (macOS) or systemd service (Linux); enable auto-start.

## 4. Localization workflow

1. `hermes gateway status` — verify gateway is running and platforms connected.
2. `hermes gateway status --deep --full` — detailed diagnostics.
3. Check `~/.hermes/logs/gateway.log | tail -50` — recent errors.
4. Check config.yaml `gateway.platforms.<name>` — verify token, allowlist, enabled.
5. Match the failure: not responding → pitfall 1; not delivering → pitfall 2; allowlist → pitfall 3.
6. Apply the fix, `hermes gateway restart`, and verify with `hermes gateway status`.

## 5. Cross-references

- `hermes-configuration-guide` — for $HERMES_HOME resolution and config.yaml structure
- `diagnosing-auth` — for token validation and OAuth flows
- `diagnosing-bot-mode` — for bot-specific gateway issues
- `diagnosing-voice` — for voice message transcription issues
- `diagnosing-host-pressure` — when several platforms fail at once or adapters are discarded after a load timeout; rule out host pressure before editing tokens or allowlists

## Report

This skill diagnoses gateway and messaging platform issues — bot not responding, platform allowlist confusion, token validation, gateway connectivity, and multi-platform setup. When you run the diagnostic workflow, present findings in the standard format below.

### Summary
Your Telegram bot is not responding to messages because the gateway is not running. The bot token is valid, but the gateway process that polls Telegram for updates is stopped.

### Findings
| Severity | What | Evidence |
|---|---|---|
| HIGH | Gateway process is not running | `hermes gateway status` shows `gateway: not running`; no platform connections listed |
| MEDIUM | Bot token may be expired | `hermes gateway status --deep` shows `telegram: token validation failed` |

### Recommended Fix
Run `hermes gateway start` to start the gateway, then verify with `hermes gateway status`. If the token is expired, run `hermes gateway setup telegram` to re-authenticate, then `hermes gateway restart`.

### References
- `~/.hermes/logs/gateway.log` — gateway log file
- `hermes_cli/gateway.py` — gateway CLI commands
- `hermes_cli/platforms/` — platform-specific adapters

*Facts re-verified 2026-10-09 against upstream source at commit `50035ef63c5536757e63bc1c1ffe4e5c19ac7fad`: `hermes_cli/gateway.py`, `hermes_cli/platforms/`; plus the official docs (hermes-agent.nousresearch.com/docs/user-guide/messaging/). Re-verify before reuse.*
