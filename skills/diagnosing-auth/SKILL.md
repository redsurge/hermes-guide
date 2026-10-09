---
name: diagnosing-auth
description: "Diagnose hub-install failures that end in '… found in any source' / 'Could not find … in any source' on public repos with gh logged in (historic phrasing: 'Could not fetch from any source', see #98725) — a dead or shadowing GITHUB_TOKEN in the profile .env, the gh-cli fallback, 401-vs-anonymous probes, and rate-limit verdicts."
version: 1.2.7
metadata:
  hermes:
    tags: [hermes, auth, github, token, rate-limit, troubleshooting, diagnosing]
    related_skills: [hermes-configuration-guide, diagnosing-skills]
---

# Diagnosing Hub Authentication

Goal: reduce any "… found in any source" / GitHub 401 / rate-limit failure on `hermes skills install` or `hermes plugins install` to one concrete fix — remove or refresh a token, or add one.

**Which string you will actually see (verified 2026-09-14).** Upstream now emits two messages, and neither is the historic `Could not fetch from any source` (that phrasing survives only in the issue title #98725, which is still open):

| Where | Current message | Source |
|---|---|---|
| Skill *name* lookup fails | `No skill named '<name>' found in any source.` | `hermes_cli/skills_hub.py:219` |
| Identifier / inspect / tap resolution fails | `Could not find '<identifier>' in any source.` | `hermes_cli/skills_hub.py:463` |

These strings are **what the adapter prints when a lookup finds nothing** — auth is the most common cause, but not the only one. Keep this skill's triage order (§4): **probe auth first** — resolve the method, then probe that token (a dead high-priority token degrades every source adapter to "not found" at once, so it is the cheapest thing to rule out; the signature is *all* sources failing, not one). Only when the probe answers 200 and installs still fail does the cause move to non-auth territory: the identifier's source scope, repository access restrictions, or a scanner verdict. Do not replace credentials blindly — and do not skip the probe to chase the identifier either.

## 1. How auth resolves (priority order)

`GitHubAuth` (**`tools/skills_hub_github.py`** — it moved out of `tools/skills_hub.py`; the CLI surface lives in `hermes_cli/skills_hub.py`) tries methods **in priority order** and stops at the first that yields a token:

| Priority | Source | Method label | Notes |
|---|---|---|---|
| 1 | `get_secret("GITHUB_TOKEN") or get_secret("GH_TOKEN")` | `pat` | fed by the profile secret scope (the `$HERMES_HOME/.env` file, loaded at import); **if set, later priorities are never consulted** |
| 2 | `gh auth token` | `gh-cli` | keyring-stored, no expiry; GitHub's authenticated limit (5,000 req/hr per GitHub docs) |
| 3 | GitHub App JWT + installation token | `github-app` | only when app credentials are configured |
| 4 | unauthenticated | `anonymous` | GitHub's anonymous limit (60 req/hr per GitHub docs), public repos only |

The load-bearing fact: **a stale token at priority 1 shadows everything below it.** Its 401 is swallowed, and every GitHub-backed source surfaces the same generic *not-found* message — `No skill named '<name>' found in any source.` or `Could not find '<identifier>' in any source.` (historic phrasing, still in issue #98725's title: `Could not fetch from any source`) — on public repos too. (On versions without the exit-code fix, the failed install also exits **0** — do not trust the exit code alone; read the output.)

Second load-bearing fact: **`GitHubAuth().is_authenticated()` checks presence, not validity.** A dead fine-grained PAT (`github_pat_…`) reports `auth_method='pat'` / `authenticated=True` while every API call returns 401 (verified live: the auth probe passed and `_github_get` returned 401 in the same process). Trust only the §2 API probe, never the `is_authenticated()` flag.

## 2. How to inspect

- **Auth-method probe** — what Hermes actually resolves right now:

  ```python
  import sys; sys.path.insert(0, "/path/to/hermes-agent")
  from tools.skills_hub_github import GitHubAuth   # NOT tools.skills_hub (moved)
  a = GitHubAuth()
  print(a.auth_method(), a.is_authenticated())   # e.g. "gh-cli True"
  ```

- **Is the env token itself alive?** `GET https://api.github.com/rate_limit` with `Authorization: Bearer <token>` — print only the status code, never the token. **401 = dead** (remove or refresh it); **200 = alive**; compare against the same request without the header (public repos answer 200 anonymous).
- **Alive is not authorized.** A `200` from `/rate_limit` proves the token is valid, **not** that it can see the repo being installed — fine-grained PATs scoped to other repos answer `404` on that repository's endpoint. Probe the repo itself (`GET /repos/<owner>/<repo>`) with the same header: `404` on a live token means no access for that token (scope or wrong identifier), not a dead token.
- `gh auth status` — account, scopes, and whether the gh token is still valid.
- Scan the profile `.env` for *active* (uncommented) `GITHUB_TOKEN` / `GH_TOKEN` lines — a commented line is inert, an active one wins priority 1.

## 3. Pitfalls (symptom → cause → fix)

1. **`… found in any source` / `Could not find … in any source` on a public repo with `gh` logged in** (historic phrasing: `Could not fetch from any source`) — a dead `GITHUB_TOKEN` in the profile `.env` shadows the working gh token (priority 1 wins, 401 swallowed; `_resolve_token` never validates). **Temporary:** comment out or delete the `.env` line — installs resume via `gh-cli` immediately. **Permanent:** replace the token with a live one and record its expiry beside it, or drop `.env` tokens entirely and rely on `gh auth login`. Upstream still swallows the 401, so this workaround stays necessary until **#98725** (open) is fixed. (Verified end-to-end; see NousResearch/hermes-agent#98725.)
2. **`hermes skills inspect` / tap resolution fails with `Could not find '<owner/repo/path>' in any source` on a correctly-formed identifier, while the tap is listed and `gh` works** — the same dead `.env` token, on a different surface: inspect/tap resolution hits the GitHub API too, and the 401 degrades every source adapter to "not found" (verified: `_github_get` → 401 inside the CLI; the same identifier resolved fine with the token removed). → Same fix as pitfall 1: remove or refresh the `.env` token.
3. **Anonymous rate-limit 403s during installs** — no token anywhere (method `anonymous`): 60 req/hr exhausts quickly with multi-file skills. → `gh auth login` once (method `gh-cli`, 5,000 req/hr).
4. **Fine-grained PAT stopped working** — they always carry an expiry (max 1 year) and can be revoked; a 401 gives no reason. `github_pat_…` tokens are in the dead-token class of pitfalls 1–2. → Refresh it, or drop it in favor of `gh auth login`. If you keep one, write its expiry date next to the line.
5. **`gh` token suddenly invalid** — rotated or revoked server-side. → `gh auth status` shows it; `gh auth login` re-authenticates.
6. **Auth is fine but the install still fails** — the failure is not auth: wrong identifier form (`owner/repo/skills/<name>`), or the scanner blocked it. → Route to **`diagnosing-skills`** (discovery/identifier) and re-read the install output for a scan verdict.

## 4. Localization workflow

1. `GitHubAuth().auth_method()` → `pat`? A token exists — probe it (§2): 401 → pitfalls 1–2 (remember: `authenticated=True` proves nothing); 200 → the token is fine, look elsewhere.
2. `gh-cli` and still failing? Not auth — check the identifier (pitfall 6) and the scanner verdict in the output.
3. `anonymous`? → pitfall 3 (add auth for anything beyond a couple of installs).
4. Apply the fix, re-run `GitHubAuth().auth_method()` to confirm the method, then re-run the install.

When probing the `.env` token, use Hermes's own loader — `agent.secret_scope.get_secret("GITHUB_TOKEN")` under the Hermes venv — and send the result to the §2 API probe. Ad-hoc text scans of `.env` can false-clear a token (a wrong grep pattern reads "token present" as "token absent" and sends you chasing the wrong layer).

**Automate it:** the §1–§2 probes are cron-able — a monthly health check that reports the method and the env-token probe status catches a dying token before installs break.

## Report

This skill diagnoses hub-install authentication failures — dead or shadowing GITHUB_TOKEN, gh-cli fallback issues, 401-vs-anonymous probes, and rate-limit verdicts. When you run the diagnostic workflow, present findings in the standard format below.

### Summary
Your `hermes skills install` fails with "No skill named 'foo' found in any source" because a dead GITHUB_TOKEN in your `.env` file is shadowing your working `gh` CLI token. The dead token's 401 error is silently swallowed, causing every GitHub-backed source to report "not found."

### Findings
| Severity | What | Evidence |
|---|---|---|
| HIGH | Dead GITHUB_TOKEN in `.env` shadows working gh-cli token | `GitHubAuth().auth_method()` returns `pat`; API probe with the `.env` token returns 401 |
| MEDIUM | All GitHub-backed sources degraded to "not found" | Install output: `No skill named 'foo' found in any source.` |

### Recommended Fix
Comment out or delete the `GITHUB_TOKEN` line in `$HERMES_HOME/.env`, then re-run `hermes skills install <name>`. The gh-cli fallback (priority 2) will take over immediately.

### References
- `$HERMES_HOME/.env` — the dead `GITHUB_TOKEN` line
- `tools/skills_hub_github.py` — `_resolve_token` priority order (pat → gh-cli → github-app → anonymous)
- `hermes_cli/skills_hub.py:219` — the "found in any source" error string

---

*Facts re-verified 2026-10-09 against upstream source at commit `50035ef63c5536757e63bc1c1ffe4e5c19ac7fad`: `tools/skills_hub_github.py` (`_resolve_token`, `_try_pat`, `_try_gh_cli`, `is_authenticated`), `hermes_cli/skills_hub.py` (error strings), `agent/secret_scope.py`; plus the issue tracker (#98725 open). Module paths and error strings changed since the previous revision — the mechanism did not. Re-verify before reuse.*
