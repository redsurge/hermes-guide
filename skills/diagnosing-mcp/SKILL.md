---
name: diagnosing-mcp
description: Diagnose Hermes MCP servers that will not connect, expose no tools, fail OAuth, or ignore config — with the exact config.yaml fields and hermes mcp commands to fix each.
version: 1.1.5
metadata:
  hermes:
    tags: [hermes, mcp, troubleshooting]
    related_skills: [hermes-configuration-guide]
---

# Diagnosing MCP Configuration

Goal: reduce any MCP problem to one concrete fix — a `mcp_servers:` entry in `$HERMES_HOME/config.yaml` (resolve with `hermes config path`) or a `hermes mcp` subcommand. Hermes registers server tools as `mcp__<server>__<tool>` and one runtime toolset per contributing server (`mcp-<server>`).

> **Disambiguation**: if a model provider is configured but silently unavailable (not an MCP server issue), see `diagnosing-providers`.

## 1. Configuration shape

```yaml
mcp_servers:
  filesystem:                      # stdio server
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
  linear:                          # OAuth 2.1 HTTP server
    url: "https://mcp.linear.app/mcp"
    auth: oauth
```

Key fields: stdio → `command`, `args`, `env` (only these plus a safe baseline reach the subprocess); http → `url`, `headers`; mTLS → `client_cert` (PEM path or `[cert, key(, password)]`), `client_key`; timing → `timeout` (tool call; `_DEFAULT_TOOL_TIMEOUT = 300` in `tools/mcp_tool_common.py`), `connect_timeout` (resolved from `_DEFAULT_CONNECT_TIMEOUT` in the same module — read the constant rather than trusting a remembered number), `keepalive_interval`; recycling → `idle_timeout_seconds`, `max_lifetime_seconds` (`tools/mcp_tool.py`, `tools/mcp_tool_health.py`); `enabled` (default true — `hermes_cli/mcp_config.py`); `supports_parallel_tool_calls`; `sampling`. **Verify any default against the installed source:** the defaults live in constants, and a doc that quotes a stale number sends you chasing a non-bug. (`elicitation` is referenced in discovery code; treat its default as version-dependent unless you have checked it.) `${VAR}` in command/args/url/headers is expanded at connect time from the environment including `$HERMES_HOME/.env`.

Per-server tool filtering: `tools.include` (whitelist) / `tools.exclude` (blacklist, fnmatch globs allowed) — **`include` wins when both are set** (`tools/mcp_tool_registration.py`, verified); an empty `tools.include: []` registers **nothing**; `tools.prompts: false` / `tools.resources: false` disable utility wrappers. If everything callable and all utilities are filtered out, Hermes creates no toolset for that server — by design.

## 2. How to inspect

- `hermes mcp` — interactive picker showing each server's status (available / enabled / installed (disabled)).
- `hermes mcp configure <name>` — re-probe the server and re-pick its tools.
- `hermes mcp login <name>` — run the OAuth flow with a full 5-minute wait.
- In chat: `/reload-mcp` reloads from config; `/context` shows the MCP token share.
- Edit config from a **fresh terminal** while a session is running — the in-session config auto-reload window is short (previously documented as 30s; the window is version-dependent, and a reload that lands mid-OAuth kills the browser flow). Prefer a fresh terminal regardless.

## 3. Pitfalls (symptom → cause → fix)

1. **Server not listed at all** — YAML syntax error in `config.yaml` drops servers (or the whole file), `enabled: false` skips the server entirely, or the entry was **simply never added**. → **Permanent:** validate YAML, check the entry exists under `mcp_servers:`, set `enabled: true` or remove the field. **Temporary:** `/reload-mcp` picks up a corrected config without restarting the session.
2. **`command not found` / spawn ENOENT** — `command` is not on PATH. On Windows point at the `.cmd`/`.exe` or use an absolute path; check the PATH the server will actually be spawned with. Note that Hermes's own JS runs on the PM-managed Node, not a system Node, so `node --version` in your shell does not describe the interpreter Hermes uses — it only tells you what a server you launch with a bare `node` would get.
3. **Tools missing** — a `tools.include`/`exclude` filter removed them (include wins), or the server session lacks the capability (resource/prompt wrappers only register when the server supports them), or the server failed to connect so nothing registered. → Run `hermes mcp configure <name>`; check status in `hermes mcp`.
4. **OAuth never completes** — (a) config edited inside a running session: the version-dependent auto-reload window can interrupt the browser flow → run `hermes mcp login <name>` from a fresh terminal; (b) headless/remote host → use paste-back of the redirect URL, SSH port-forward, or `oauth.redirect_uri` (`tools/mcp_oauth.py`, verified); (c) WAF 403s loopback redirects → check the redirect-host knob **in your version** (`oauth.redirect_host` is not present in `tools/mcp_oauth*.py` at current main — verify before relying on it).
5. **OAuth login "works" but tool calls time out** — the provider rejects dynamic client registration (Google Drive, Atlassian): `tools/list` succeeds unauthenticated, so login looks fine but no token lands. → Create an OAuth client in the provider console and set `oauth.client_id` / `oauth.client_secret`, then `hermes mcp login <name>`.
6. **Tool call times out** — slow server startup. → Raise `timeout` / `connect_timeout` on that entry.
7. **Catalog entry stale after Hermes update** — catalog MCPs never auto-update. → Re-run `hermes mcp install <name>`.
8. **Claude-Code-style config pasted in** — `mcpServers` JSON or nested `mcp.servers` is not read. → Use top-level `mcp_servers:` in YAML (or `hermes import-agent claude-code`).

## 4. Localization workflow

1. `hermes config path` → open the file, confirm the entry exists under `mcp_servers:` and YAML parses.
2. `hermes mcp` → read the entry's status: absent → pitfall 1; disabled → enable it; present-but-failing → step 3.
3. Match the failure: ENOENT → 2; timeout → 6; OAuth → 4/5.
4. Check filters (pitfall 3) before blaming the connection.
5. Apply the fix, then `/reload-mcp` (or restart), and confirm the `mcp__<server>__*` tools appear (`/context`).

## Report

This skill diagnoses MCP servers that will not connect, expose no tools, fail OAuth, or ignore config. When you run the diagnostic workflow, present findings in the standard format below.

### Summary
Your MCP server is not listed because the `command` field is not on PATH. The server entry exists in config.yaml but the spawn fails with ENOENT, so the server is silently dropped.

### Findings
| Severity | What | Evidence |
|---|---|---|
| HIGH | MCP server `command` not found on PATH | `hermes mcp` shows server as `failed`; error: `spawn npx ENOENT` |
| MEDIUM | Server uses bare `npx` instead of absolute path | Config has `command: "npx"` but `npx` is not on the PATH the server is spawned with |

### Recommended Fix
Edit `$HERMES_HOME/config.yaml` and change the server's `command` to an absolute path (e.g., `/usr/local/bin/npx` on POSIX or `C:\path\to\npx.cmd` on Windows), then run `/reload-mcp` and verify with `hermes mcp`.

### References
- `$HERMES_HOME/config.yaml` — `mcp_servers:` entry
- `hermes_cli/mcp_config.py` — MCP config loading
- `tools/mcp_tool_common.py` — `_DEFAULT_TOOL_TIMEOUT`, `_DEFAULT_CONNECT_TIMEOUT`

---

*Facts re-verified 2026-10-09 against upstream source at the declared baseline `b56a10246e81e23d10bf6f49ae176c082db53ed9`: `mcp__<server>__<tool>` naming and the per-server `mcp-<server>` toolset alias (`tools/mcp_tool_schema.py`, `tools/mcp_tool_registration.py`); the server field set and defaults (`tools/mcp_tool_common.py`, `tools/mcp_tool_discovery.py`, `hermes_cli/mcp_config.py`); `include`-wins filtering with fnmatch and the empty-list semantics (`tools/mcp_tool_registration.py`); recycling fields (`tools/mcp_tool.py`); `redirect_uri` (`tools/mcp_oauth.py`); the `install`/`configure`/`login` subcommands. Four previously asserted specifics could **not** be confirmed at current main and are now marked version-dependent instead of quoted as fact: the 30s reload window, `oauth.redirect_host`, the `elicitation` default, and the exact `connect_timeout` value. Re-verify before reuse.*
