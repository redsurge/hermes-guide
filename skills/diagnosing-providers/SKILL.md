---
name: diagnosing-providers
description: Diagnose model provider issues — custom endpoints flooding the picker with hundreds of models, discover_models misbehaving, persisted catalogs bloating config, and provider/auth failures.
version: 1.1.9
metadata:
  hermes:
    tags: [hermes, configuration, troubleshooting]
    related_skills: [hermes-configuration-guide, diagnosing-auth]
---

# Diagnosing Model Providers

Goal: reduce any model-provider problem to one concrete fix — a `providers:` / `custom_providers:` entry in `$HERMES_HOME/config.yaml` (resolve with `hermes config path`) or a `hermes model` subcommand.

> **Disambiguation**: if an MCP server connects but exposes no tools, see `diagnosing-mcp`. If an external memory provider is configured but silently unavailable, see `diagnosing-memory`.

## Step 0 — Resolve the config first

Never edit a path you have not verified. Run `hermes config path` — it prints the active config file. `hermes config show` dumps the merged view; `hermes config set providers.<name>.<key> <value>` edits safely.

## Step 1 — The two discovery modes

Every provider entry accepts `discover_models`, which **defaults to `true`**:

```yaml
providers:
  my-gateway:
    api: https://llm.internal.example.com/v1
    discover_models: true        # default — probes /v1/models, full catalog in picker
    models:
      - my-finetune-v2
```

| `discover_models` | `models:` shape | Picker shows |
|---|---|---|
| `true` (default) | absent or dict | Full endpoint catalog, live probe |
| `false` | list | Only the listed IDs |
| `false` | absent | Only the saved `model:` |

There is no "top N", no "most-used", no auto-narrowing. The switch is binary.

> [!NOTE]
> `discover_models` accepts string values too: `"false"`, `"no"`, `"0"` all mean False.

## Step 2 — The catalog-bloat trap

Hermes persists a discovered catalog under `models:` as a **dict** with `models_discovered: true`. This is **metadata, not a pin** — `model_switch.py:_models_config_is_allowlist` treats a discovered catalog as never-a-pin. It does nothing but bloat `config.yaml`.

A persisted catalog is a copy of the last `/v1/models` response. It is not consulted at runtime; the endpoint is re-probed at every picker build. It drifts from the endpoint and must be hand-maintained if treated as authoritative.

**Fix:** remove the `models:` dict and `models_discovered:` flag. Keep `discover_models: true` for a live probe, or `false` to pin.

**Verify the fix:** `hermes config get providers` shows the entry with no `models:` block, and `wc -l "$(hermes config path)"` drops by roughly one line per persisted model.

## Step 2.5 — Distinguish config bloat from endpoint reality

Before editing anything, confirm the endpoint actually returns that many models. A persisted catalog is a snapshot; the live endpoint may differ. Probe the endpoint's `/models` route with your API key in the `Authorization: Bearer …` header (same request any OpenAI-compatible client sends) and count the entries in the `data` array — print only the count, never the key or the full response.

If the live count matches the persisted count, the catalog is current and the bloat is real. If it is much smaller, the persisted catalog is stale — removing it loses nothing.

> [!CAUTION]
> Never paste a real API key into a command line — neither as a `-H` argument (visible in `ps` output to other local users) nor inline in a script. Keep it in an environment variable and read it in-process inside whatever HTTP client you use.

## Step 3 — Allowlist vs metadata

`models:` shaped as a **list** is an allowlist that narrows a public endpoint. Shaped as a **dict**, it is per-model metadata and the probe still runs — so a dict never restricts the picker.

To pin a dict catalog, set `discover_models: false` **and** convert `models:` to a list:

```yaml
discover_models: false
models:
  - my-finetune-v2
  - my-finetune-v1
```

## Step 4 — API key resolution

A provider's key is resolved in this order, highest first:

1. **`key_cmd:`** — a command-run token provider. When present it is resolved first and **returns early** (`hermes_cli/model_switch_providers.py::_entry_credentials`: the `key_cmd` branch returns before `api_key` or `key_env` are read), so anything below it in the same entry is ignored. If a provider keeps using an old credential, check for `key_cmd:` before editing anything else.
2. **Inline `api_key:`** — a literal value or `${VAR}` reference in the entry. Outranks the env form.
3. **`key_env:`** — the name of an environment variable (the alias `api_key_env:` is accepted too — `_entry_credentials` reads whichever is set). Resolved at runtime from `$HERMES_HOME/.env` and the process environment.

```yaml
providers:
  my-gateway:
    api: https://llm.internal.example.com/v1
    key_env: MY_GATEWAY_API_KEY      # read from .env / environment
    api_key: ${MY_GATEWAY_API_KEY}    # equivalent inline form
```

If none of the three are set, the provider runs unauthenticated.

### The auto-generated key env var

When you add a provider through the CLI setup wizard (`hermes model`), Hermes derives the env var name from the endpoint's host:port so two servers on one host keep separate credentials. `hermes_cli/config.py:2739`:

```python
def custom_endpoint_key_env(identity: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "_", str(identity or "").upper()).strip("_")
    return f"HERMES_CUSTOM_{slug}_API_KEY" if slug else "HERMES_CUSTOM_API_KEY"
```

| Endpoint identity | Generated var |
|---|---|
| `api.example.com` | `HERMES_CUSTOM_API_EXAMPLE_COM_API_KEY` |
| `localhost:8088` | `HERMES_CUSTOM_LOCALHOST_8088_API_KEY` |

The fixed `HERMES_CUSTOM_` prefix is required — it keeps the name POSIX-valid when the slug starts with a digit, since `save_env_value` rejects those.

**You do not need to adopt this convention.** `key_env` accepts any valid env var name; hand-named vars like `MY_GATEWAY_API_KEY` work identically. The generated form is only used by wizard-provisioned endpoints. Mixing the two is fine — what matters is that the var exists in `.env` and matches the `key_env` string.

> [!NOTE]
> Entries relying on `key_env` must not get a synthesized `api_key` written into config — the runtime resolves `key_env` directly, and persisting the value would downgrade credential hygiene.

## Step 5 — Provider/auth failures

- `Could not fetch models from endpoint` at picker time → the endpoint rejected the request. Check `key_env` / inline `api_key`, and whether the endpoint serves `/v1/models` at all (some gateways route only `/chat/completions`).
- `gh` / hub 401 on install → see `diagnosing-auth`.
- A model listed in `models:` but absent from the endpoint stays listed and **fails at request time** — there is no validation against the endpoint.

## Step 6 — Legacy format

Older configs use a top-level `custom_providers:` list with `base_url` instead of `api`. Still supported and auto-migrated to the `providers:` dict on `hermes update` (config v12).

> [!CAUTION]
> **Keep this skill host-agnostic.** Do not reintroduce a real third-party provider
> hostname, base URL, or `key_env` name as a worked example — `api.example.com` and
> `MY_GATEWAY_API_KEY` are the placeholders. A skill whose subject is *model
> providers in general* must not carry the flavor of whatever provider the last
> debugging session happened to touch.

Every diagnosis ends in a concrete action: a `providers:` field edit or a `hermes model` command, then `hermes gateway restart` to apply.

## Report

This skill diagnoses model provider issues — custom endpoints flooding the picker with hundreds of models, discover_models misbehaving, persisted catalogs bloating config, and provider/auth failures. When you run the diagnostic workflow, present findings in the standard format below.

### Summary
Your model picker is flooded with hundreds of models because a persisted catalog from a previous `/v1/models` response is bloating `config.yaml`. The catalog is metadata (not a pin) and is not consulted at runtime — the endpoint is re-probed every time.

### Findings
| Severity | What | Evidence |
|---|---|---|
| MEDIUM | Persisted catalog bloating config.yaml | `wc -l "$(hermes config path)"` shows 500+ lines; `hermes config get providers` shows a `models:` dict with `models_discovered: true` |
| LOW | Catalog is stale — live endpoint returns fewer models | Live probe of `/v1/models` returns 12 models; persisted catalog has 340 |

### Recommended Fix
Remove the `models:` dict and `models_discovered:` flag from the provider entry in `config.yaml`. Keep `discover_models: true` for a live probe. Verify with `hermes config get providers` — the entry should have no `models:` block.

### References
- `$HERMES_HOME/config.yaml` — `providers:` entry with persisted catalog
- `hermes_cli/model_switch.py` — `_models_config_is_allowlist` (discovered catalog is never a pin)
- `hermes_cli/model_switch_providers.py` — `_discover_flag`, `_entry_credentials`

---

*Facts re-verified 2026-10-09 against upstream source at commit `50035ef63c5536757e63bc1c1ffe4e5c19ac7fad`: `hermes_cli/model_switch_providers.py::_entry_credentials` (key_cmd resolved first and returned early; `key_env` read for the identity tuple but not used as the credential when key_cmd wins; inline `api_key` next) and `::_discover_flag` (`discover_models` defaults True; `"false"`/`"no"`/`"0"` strings coerce to False); `hermes_cli/model_switch.py::_models_config_is_allowlist` (a `discovered` catalog is never a pin; dict shape is per-model metadata, list shape is an allowlist); `hermes_cli/config.py:2739` (`custom_endpoint_key_env` — `HERMES_CUSTOM_<SLUG>_API_KEY` derivation). The Step 2.5 probe was rewritten 2026-09-21 (prose form) after the skills scanner rated the scripted curl|python and urllib forms as supply-chain/exfiltration shapes. **Re-pointed 2026-09-29 (drift #123):** `config.py` citations updated to `2739` at `5000e2993`. Re-verify before reuse.*
