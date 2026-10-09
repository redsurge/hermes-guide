---
name: diagnosing-desktop
description: "Diagnose Hermes desktop app failures — launch or build fails, 'npm was not found', 'Access is denied' on Hermes.exe, blank window or backend never ready, Electron download stuck. Build/launch pipeline, backend resolution order, and the desktop.* config block."
version: 1.1.8
metadata:
  hermes:
    tags: [hermes, desktop, electron, gui, troubleshooting, diagnosing]
    related_skills: [hermes-configuration-guide, diagnosing-path, diagnosing-cli-tui]
---

# Diagnosing Desktop

Goal: reduce any `hermes desktop` failure — build error, launch failure, wrong backend, or blank window — to one concrete fix: a missing dependency, a stale/locked build artifact, an env override, or a config field.

> **Disambiguation**: if the TUI misrenders or shows unreadable indicators on native Windows, see `diagnosing-cli-tui` — that is a CLI/TUI problem, not a desktop-app problem. If the wrong Python interpreter is active or the dual-venv layout is confusing, see `diagnosing-path`.

> [!NOTE]
> `hermes gui` is a **deprecated alias** of `hermes desktop` (same command). `hermes doctor` covers the desktop only on **macOS** (TCC signing identity) — on Windows/Linux this skill is the diagnostic layer. Desktop *plugins* (the SDK, `$HERMES_HOME/desktop-plugins/`) are a separate surface and out of scope here.

## 1. How desktop launches

`hermes desktop` runs a build-then-launch pipeline — the implementation lives in **`hermes_cli/main_desktop.py`** (`cmd_gui`, line ~1588); `hermes_cli/main.py` only imports it and wires the parser (`build_gui_parser`). Read `main_desktop.py` when you need the real order of operations:

1. Guard: `apps/desktop/package.json` must exist in the Hermes source tree (source installs only).
2. Resolve npm via the Hermes-managed Node tree first (a broken managed tree is an error, not a fallback).
3. Content-stamp check: `$HERMES_HOME/desktop-build-stamp.json` stores a SHA-256 over `apps/desktop/**` plus root `package.json`/`package-lock.json`. Stamp matches → launch as-is (`--force-build` overrides).
4. `npm ci`-style deterministic install at the **workspace root** (not `apps/desktop`), then `npm run pack` (packaged) or `npm run build` (`--source`).
5. Stage-and-swap: the new build lands in a staging dir and is atomically renamed over `apps/desktop/release` — a failed build leaves the previous app untouched.
6. Windows integrity gate on the packaged exe, then launch `apps/desktop/release/win-unpacked/Hermes.exe` (source installs) — packaged Windows installs live at `%LOCALAPPDATA%\Programs\Hermes` instead. Know which layout you have.

## 2. How the app finds the backend

The Electron main process resolves the hermes backend in order (`apps/desktop/electron/main.ts`, `resolveHermesBackend`) — resolution never throws, it degrades:

1. `HERMES_DESKTOP_HERMES_ROOT` (explicit override; must be a Hermes source root)
2. Dev source checkout (unpackaged runs)
3. The **active install root**: `%LOCALAPPDATA%\hermes\hermes-agent` (Windows) / `~/.hermes/hermes-agent` — the install's shims run a durable launcher bound to the PM-store Python (`python -m hermes_cli.main` is the legacy pre-PM shape)
4. A `hermes` binary on `PATH` (skipped when `HERMES_DESKTOP_IGNORE_EXISTING=1`; `HERMES_DESKTOP_HERMES` overrides the command — NixOS uses this)
5. pip-installed `hermes_cli` via system Python
6. `bootstrap-needed` sentinel → the app drives the first-run installer

Wrong-backend symptoms almost always trace to order 3 vs 4: a `hermes` shim on PATH shadowing the active install, or the opposite.

## 3. How to inspect

- **Boot/build log**: `$HERMES_HOME/logs/desktop.log` (written when the subcommand is `desktop`/`gui`/`dashboard`/`serve`); follow with `hermes logs gui -f`. The Electron-side log distinguishes backend-resolution kinds.
- **Stamp file**: read `$HERMES_HOME/desktop-build-stamp.json` — `contentHash`, `sourceMode`, `builtAt` (all three verified in source; the stamp is read/written by `hermes_cli/main_desktop.py` and `hermes_cli/main_web_build.py`). A missing/stale stamp with a source change means the next plain `hermes desktop` rebuilds.
- **Toolchain**: Node engines are pinned in `apps/desktop/package.json` — verified at current main: `"node": "^22.22.0 || ^24.11.0 || >=26.0.0"`. It drifts; read the file, don't trust docs. npm resolves through the PM-composed build environment (`hermes_cli/npm_engine.py` → `pm.ensure("npm")`); PM's locked Node/npm run the build.
- **Port readiness**: the backend must announce a port within the announce timeout — `HERMES_DESKTOP_PORT_ANNOUNCE_TIMEOUT_MS` overrides it; the default is **90 s** with a **45 s floor** (`DEFAULT_PORT_ANNOUNCE_TIMEOUT_MS = 90_000`, `MIN_PORT_ANNOUNCE_TIMEOUT_MS = 45_000` in `apps/desktop/electron/backend-ready.ts`; an override is clamped with `Math.max`, so a malformed value cannot drop below the floor). Windows cold starts legitimately approach the limit because Defender scans fresh `.pyc` files.
- `hermes status` and `hermes doctor` have no desktop build/launch checks (macOS TCC only).

## 4. Pitfalls (symptom → cause → fix)

| Symptom | Cause | Fix |
|---|---|---|
| Desktop build fails on Node/npm resolution | PM's Node/npm tree missing or broken (the old "npm was not found on PATH" error string no longer exists at head) | Repair the install (`hermes update` / installer); `hermes doctor` shows the PM Node check |
| `Access is denied` / `ERR_ELECTRON_BUILDER_CANNOT_EXECUTE` during build | A running `Hermes.exe` locks `release/win-unpacked/` | **Permanent:** close the running desktop app, then rebuild — the builder terminates only the processes it owns, so a hand-started instance must be closed manually. **Temporary:** none — `--build-only` still writes the packaged artifact into `release/`, so it hits the same lock (`hermes_cli/main_desktop.py`: "--build-only: produce the artifact but do NOT launch"). Close the app first; there is no safe build-while-running path |
| "A previous update left the desktop bundle incomplete" | Interrupted update (file locks) left a torn renderer bundle | Close the running desktop app, then `hermes desktop --force-build`. Automatic detection is a heuristic — it catches index.html naming chunks that aren't there, but other damage (chunks present yet corrupt, exe damage) passes both the tear check and the source stamp, so plain relaunch reproduces the crash; when an interrupted update is suspected, force the rebuild |
| Build stuck on Electron download (~114 MB from github.com/electron releases) | Blocked/rate-limited network | Built-in auto-heal: cache purge + npmmirror.com retry; pin a mirror with `ELECTRON_MIRROR=<url> hermes desktop --force-build` |
| `--skip-build` errors "no packaged desktop app was found" | No prior successful build | Run a full `hermes desktop` (or `--build-only`) once; `--skip-build` only launches existing artifacts |
| Backend never announces its port | Defender scanning fresh `.pyc` files; slow disk; the announce timeout (default 90 s, floor 45 s) may be too short for a cold start | Raise `HERMES_DESKTOP_PORT_ANNOUNCE_TIMEOUT_MS` above the 45 s floor (values below it are clamped up), then re-run once warmed; add AV perf exclusions |
| Desktop runs the wrong hermes backend | Resolution order (§2): PATH shim vs active install | **Temporary:** `HERMES_DESKTOP_IGNORE_EXISTING=1` for one launch. **Permanent:** fix the PATH shim, or pin `HERMES_DESKTOP_HERMES_ROOT` to the intended source root |
| "HERMES_DESKTOP_REMOTE_URL is set but HERMES_DESKTOP_REMOTE_TOKEN is not" | Remote mode needs both | Set both, or unset both |
| "desktop self-update only runs against a source install" | Packaged installs don't self-update | Update via the installer; source installs update via `hermes update` |
| Linux build fails on native modules | Missing toolchain | `g++` / `build-essential`; Wayland issues → `desktop.ozone_platform_hint: x11` |
| GPU artifacts / blank panes | GPU driver incompatibility | `desktop.disable_gpu: true` (or `HERMES_DESKTOP_DISABLE_GPU=1`) |
| Keyring errors on Linux | Credential store mismatch | `desktop.password_store: gnome-libsecret` / `kwallet6` / `basic` |
| NixOS build environment breaks | Nix needs explicit env vars | `HERMES_DESKTOP_HERMES` (backend command override) is the supported hook; the build wraps a NixOS env internally |
| Dashboard won't start | Stale process holding port 9119 | Stale PID detection is automatic; kill the orphan `hermes` dashboard process if it persists |

## 5. The `desktop.*` config block

Precedence throughout: **explicit env var > `config.yaml` > auto-detection**.

| Key | Meaning |
|---|---|
| `electron_flags` | Extra Electron CLI flags appended at launch |
| `ozone_platform_hint` | `auto` / `x11` / `wayland` (Linux display) |
| `disable_gpu` | `auto` or bool — GPU workaround |
| `password_store` | Linux credential backend (`gnome-libsecret`, `kwallet*`, `basic`) |
| `repo_scan_enabled` / `repo_scan_roots` / `repo_scan_exclude_paths` | Projects sidebar Git discovery |
| `auto_continue.enabled` / `.freshness_minutes` / `.max_attempts` | Interrupted-turn auto-resume |
| `macos_signing_identity` | macOS TCC-persistent signing (see `hermes desktop --setup-tcc-identity`) |

Hermes configuration is **YAML** — edit `config.yaml`, never JSON syntax.

## 6. Apply and verify

After fixing: close any running desktop app, then `hermes desktop` (a source change triggers the stamp rebuild automatically; use `--force-build` after upstream updates or when in doubt, `--build-only` to validate a build without launching). Confirm via `hermes logs gui -f` that the backend announces its port and the window renders. There is no `/reload-desktop` — a running app must be closed and relaunched.

> [!CAUTION]
> `hermes uninstall --gui` removes build artifacts, desktop `node_modules`, the build stamp, and the electron user-data dir (`%APPDATA%\Hermes` — connection settings, `connection.json`, Chromium cache). It never touches agent config or memory — but connection setup is not recoverable from the uninstall, so re-pairing is required afterwards.

## Report

This skill diagnoses desktop app failures — launch or build fails, "Access is denied" on Hermes.exe, blank window or backend never ready, Electron download stuck. When you run the diagnostic workflow, present findings in the standard format below.

### Summary
The desktop build fails with "Access is denied" because a running Hermes.exe process has locked the `release/win-unpacked/` directory. The build cannot swap in the new artifact while the old one is in use.

### Findings
| Severity | What | Evidence |
|---|---|---|
| HIGH | Running Hermes.exe locks `release/win-unpacked/` | Build error: `ERR_ELECTRON_BUILDER_CANNOT_EXECUTE` — `Access is denied` |
| MEDIUM | Stale build stamp may cause unnecessary rebuilds | `$HERMES_HOME/desktop-build-stamp.json` contentHash does not match current source |

### Recommended Fix
Close the running desktop app, then run `hermes desktop --force-build`. If the build still fails, check `$HERMES_HOME/logs/desktop.log` for the full error output.

### References
- `$HERMES_HOME/logs/desktop.log` — build/launch log
- `$HERMES_HOME/desktop-build-stamp.json` — content stamp file
- `hermes_cli/main_desktop.py` — `cmd_gui` build pipeline
- `apps/desktop/electron/main.ts` — backend resolution logic

---

*Facts re-verified 2026-10-09 against upstream source at commit `50035ef63c5536757e63bc1c1ffe4e5c19ac7fad`: `cmd_gui` lives in `hermes_cli/main_desktop.py` (main.py imports/wires it); the desktop env-var set (`HERMES_DESKTOP_HERMES_ROOT`, `_IGNORE_EXISTING`, `_HERMES`, `_PORT_ANNOUNCE_TIMEOUT_MS`, `_REMOTE_URL`, `_REMOTE_TOKEN`, `_DISABLE_GPU`); the stamp file and its three fields; the engines range in `apps/desktop/package.json`; the `desktop.*` keys `ozone_platform_hint`, `disable_gpu`, `password_store`; `ELECTRON_MIRROR`/npmmirror auto-heal; `win-unpacked`; dashboard port 9119; the `gui` alias deprecation; and the two error strings quoted in the pitfalls. **Corrected:** the pipeline's module pointer (`main.py` → `main_desktop.py`). **Re-corrected 2026-09-15:** the port-announce values (`90_000` default, `45_000` floor, `apps/desktop/electron/backend-ready.ts`) *are* present at this baseline — the previous pass wrongly recorded them as absent and removed them. **Re-pointed 2026-09-29 (drift #123):** `cmd_gui` moved to line ~1588 at `5000e2993`. **Re-checked 2026-09-29 at `5000e2993` (pm rework):** npm resolves through the PM build env (`source_build_env` → `pm.ensure("npm")`); the "npm was not found on PATH" pitfall string is gone; the `apps/desktop/package.json` engines range is unchanged. Re-verify at the baseline before reuse.*
