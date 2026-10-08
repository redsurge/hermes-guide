---
name: diagnosing-cli-tui
description: "Diagnose and fix Hermes Agent CLI/TUI issues on native Windows (PowerShell/conhost, Git Bash backend): rendering artifacts, themes/skins, busy indicators, mouse modes, encoding, and launch/resume."
version: 1.1.7
metadata:
  hermes:
    tags: [hermes, tui, cli, windows, themes, troubleshooting, diagnosing]
    related_skills: [hermes-configuration-guide, diagnosing-path, installing-hermes]
---

# Diagnose Hermes CLI/TUI (Windows)

Playbook for running and fixing the Hermes Agent CLI/TUI on this machine.
Use when the TUI misrenders, truncates, shows unreadable indicators, fails
to launch, or when asked how to theme/skin Hermes on Windows.

> **Disambiguation**: if the desktop app (Electron) fails to launch or shows a blank window, see `diagnosing-desktop` — that is a desktop-app problem, not a CLI/TUI problem. If a `/command` is missing or overridden, see `diagnosing-commands`.

## 0. Environment baseline (origin machine: one Windows box, re-verified 2026-09-14)

> [!CAUTION]
> This baseline records **one specific Windows machine** — the box this skill was written on. It is **not** a description of your machine. Before applying anything below, confirm the local environment with `hermes config path`, `hermes --version`, and `hermes doctor`; paths, `HERMES_HOME`, shell, and OS differ per machine (on macOS/Linux the **default** home is `~/.hermes` — overridable via `HERMES_HOME` or a named profile; `hermes config path` always prints the active one).

- Hermes Agent **v0.21.1** on the Windows desktop install (v0.20.4 when this skill was first written); git install: `%LOCALAPPDATA%\hermes\hermes-agent` (on the box this baseline was recorded the in-tree venv was a `.venv/`, not `venv/`; a PM-era install has no in-tree venv at all — see `diagnosing-path` for why that matters)
- `HERMES_HOME = %LOCALAPPDATA%\hermes` (native Windows; `~/.hermes` is NOT the active home)
- OS: Windows 10 Home 22H2 (build 19045.7663)
- Shell: Windows PowerShell 5.1; console host: conhost (classic window) or Windows Terminal 1.24.11911 (present on the reference box; a bare Windows 10 box has **only conhost**)
- Tool shell backend: PortableGit (MinGit, msys2) bash - resolved via `HERMES_GIT_BASH_PATH` or `%LOCALAPPDATA%\hermes\git\usr\bin\bash.exe` (non-busybox variant)
- TUI frontend: Node app `hermes-tui` (React 19 + custom Ink fork), launched as a subprocess of the Python CLI. Node resolution (2026-09): **through PM** — `hermes_cli/main_tui_launch.py::_tui_node_bin` prefers an explicit `HERMES_NODE` binary, else PM's locked Node (**26.7.0** in `pm/lock.json`); a system Node on PATH is deliberately **not** used to run Hermes's JS (`hermes_cli/main_tui_launch.py::_tui_node_bin`, asserted by the path-shape e2e tests). If no Node can be resolved, `hermes --tui` exits with a pointer to `hermes --cli`.
- Ground truth commands: `hermes config path`, `hermes config show`, `hermes --version`, `hermes doctor`

## 1. Launch and resume

```powershell
hermes              # classic CLI by default; launches TUI when display.interface: tui
hermes --tui        # force TUI
hermes --tui -c     # resume latest TUI session (or HERMES_TUI_RESUME=1 / display.tui_auto_resume_recent: true)
hermes --cli        # force classic REPL for one invocation
hermes -z "prompt"  # one-shot (--oneshot): run a single prompt with tools, print the answer, exit.
                    #   Non-interactive — ideal for scripts, cron, and CI smoke-tests (e.g. verifying a
                    #   skill is discoverable AND followed: hermes -z "Use the diagnosing-path skill: which
                    #   interpreter should a script in the checkout use?"). Exits non-zero on failure.
```

Applied on the origin machine (config.yaml, backup: `config.yaml.bak-20260824-0457`):

```yaml
display:
  interface: tui
  tui_status_indicator: ascii
  mouse_tracking: wheel
  details_mode: collapsed
```

`display.tui_auto_resume_recent` is **false** (fresh session per launch). If `hermes` ever opens a previous chat instead of a fresh session, check that key or `HERMES_TUI_RESUME=1`; resume on demand with `hermes --tui -c` (`--resume <id>` for a specific session).

User env vars: `EDITOR=code --wait`, `HERMES_TUI_THEME=dark`.

## 2. In-TUI slash commands that fix rendering

| Command | Effect |
|---|---|
| `/indicator ascii` | Readable busy indicator (default is `kaomoji`, can be hard to read on conhost). Styles: kaomoji, emoji, unicode (braille), ascii. Persist: `display.tui_status_indicator` |
| `/skin <name>` | Live theme preview. Built-ins: default, ares, mono, slate, daylight, warm-lightmode, poseidon, sisyphus, charizard. Persist: `display.skin` |
| `/mouse wheel` | Mouse preset 1000+1006 (scroll + click, no hover). `all` includes 1003 hover - unsupported on conhost. Persist: `display.mouse_tracking` |
| `/details collapsed` | Quiet feed: fold thinking/tools under chevrons. Persist: `display.details_mode` or `display.sections.<section>: collapsed` |
| `/usage` | Token/cost panel. If silent in TUI, see upstream #37637 |
| `/exit` | Quit; conhost should restore a clean prompt (no residual frame) |

## 3. Skins & themes (style system)

- Skins live at `$HERMES_HOME/skins/<name>.yaml`; user skins inherit missing keys from `default`
- Keys: `colors` (banner_*, ui_*, prompt, input_rule, response_border, session_*, status_bar_bg, voice_status_bg, selection_bg, completion_menu_*), `spinner` (waiting_faces, thinking_faces, thinking_verbs, wings), `branding` (agent_name, response_label, prompt_symbol, help_header...), `tool_prefix`, `tool_emojis`, `banner_logo` / `banner_hero` (Rich markup ASCII art)
- Built-in skins load from `hermes_cli/skin_engine.py`; unknown skins fall back to `default`
- Consoles with poor glyph coverage: prefer ASCII-ish faces (e.g. `(>_<)`, `(^_^)`, `(o_o)`) and box-drawing `tool_prefix` like `|`
- Save skin YAML as UTF-8 WITHOUT BOM (a BOM inside a folded YAML scalar silently breaks parsing)
- Visual editor: `npx -y hermes-mod` (community tool; honors HERMES_HOME)
- Light/dark detection order (upstream `ui-tui/src/theme.ts`, verified 2026-09-14):
  1. `HERMES_TUI_LIGHT` — `1/true/yes/on` = light, `0/false/no/off` = dark. **Wins over everything.**
  2. `HERMES_TUI_THEME` — named only: `light` or `dark`.
  3. `HERMES_TUI_BACKGROUND` — 3- or 6-digit hex (with or without `#`); luminance decides.
  4. `COLORFGBG` last field (XFCE / rxvt / Terminal.app profiles).
  5. `TERM_PROGRAM` light-default allow-list (currently `Apple_Terminal`).
  Anything undecidable stays **dark**. There is **no OSC 11 probe** — the hex env var is named `HERMES_TUI_BACKGROUND` so a future OSC 11 client could feed it, nothing more. Note `hermes_cli/tips.py` advertises `HERMES_TUI_THEME=light|dark|<hex>`, which the TUI code does not implement; trust the code, and set hex via `HERMES_TUI_BACKGROUND`.)

## 4. Windows-specific troubleshooting

1. **Mojibake / garbled output**: Hermes forces UTF-8 via `hermes_cli/stdio.py::configure_windows_stdio()` (sets CP_UTF8, PYTHONUTF8=1, PYTHONIOENCODING=utf-8). Do NOT set `HERMES_DISABLE_WINDOWS_UTF8`. If tool output from the Git Bash backend is garbled, set `LANG=C.UTF-8` / `LC_ALL=C.UTF-8` for that bash (msys2 reads Windows env). PS 5.1 pipes: `$OutputEncoding = [Text.UTF8Encoding]::new()`.
2. **Missing glyphs / tofu faces**: conhost has no font fallback. Fixes: Windows Terminal + Cascadia Mono, or `/indicator ascii`.
3. **Editor silent (`/edit`, Ctrl-X Ctrl-E)**: Hermes defaults `EDITOR=notepad`. Set `EDITOR=code --wait` (Cursor/VS Code shim works). Never point at an editor that returns immediately without `--wait`.
4. **WinError 193 (%1 is not a valid Win32 application)**: invoking an extensionless shebang script. Always use the `.cmd` shim (`npx.cmd`, not `npx`).
5. **Process liveness**: never `os.kill(pid, 0)` on Windows — upstream's own comment (`hermes_cli/gateway.py`): *"`os.kill(pid, 0)` hard-kills on Windows (TerminateProcess)"*, i.e. the probe kills the process instead of testing it. Use `psutil.pid_exists()` / `gateway.status._pid_exists()`.
6. **Gateway at login**: `hermes gateway install` uses schtasks (ONLOGON, no admin), spawns via pythonw.exe with DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW.
7. **Antivirus flags uv.exe**: false positive; whitelist the `%LOCALAPPDATA%\hermes\bin` folder (hash changes each upgrade). Verify authenticity via `gh attestation verify` (see README).
8. **Installer BOM**: `iex (irm ...)` strips BOM; `[scriptblock]::Create((irm ...))` does not.
9. **Config schema drift**: `hermes config set` flags `display.mouse_tracking` and `display.details_mode` as unrecognized - they ARE valid TUI keys (documented); values save and are read anyway. Do not delete them.
10. **ConPTY mouse/selection loss (Windows Terminal)**: Windows Terminal uses ConPTY, which never delivers DEC mouse sequences. The TUI's AlternateScreen + mouse tracking swallows the wheel and native text selection. PR #97663 defaults `hermes --tui` to inline mode (primary buffer) on native Windows ConPTY — the same fallback Termux uses. Git Bash/MSYS mintty outside WT is unaffected. Workaround until merge: `HERMES_TUI_INLINE=1`. Opt out with `HERMES_TUI_INLINE=0`. WSL2-in-WT is intentionally excluded (WSL reports `platform === 'linux'`, mouse sequences DO reach the Linux PTY).

## 5. Known upstream issues (check state before re-reporting)

States verified 2026-10-08. `closed` means fixed upstream — if you still see it, your install or config is behind, not the bug. PR-linked issues are one review/merge away from resolution.

| Issue | PR | State | Topic |
|---|---|---|---|
| #25418 | — | closed | Terminal resize corrupts TUI layout (Ghostty, iTerm2, ...) |
| #19216 | — | closed | TUI: resize causes infinite scroll/render loop (flicker, duplicated status bar) |
| #12130 | — | open | TUI v2 feature-parity gaps vs the classic CLI (overlays, slash commands, @ refs) |
| #53301 | — | open | TUI pet colors washed out on WSL/Windows Terminal — **cause is chalk falling back to 256-color when `COLORTERM` is unset** (not a Kitty-graphics issue; fix the env, e.g. `COLORTERM=truecolor`) |
| #37637 | — | closed | `/usage` silent in CLI/TUI (worked via Telegram) |
| #19214 | — | closed | `terminal.cwd` is a foot-gun: CLI/TUI should use the launch directory |
| #14638 | — | closed | Windows: exit 126 with empty output on every command (Git Bash backend) |
| #20782 | — | closed | Windows: `terminal` / `write_file` tools fail (exit 126 / empty file) |
| #83938 | — | open | `test_profiles.py` failures on Windows with a non-UTF-8 codepage |
| #86571 | #97663 | open (PR) | TUI mouse wheel + selection fail under Windows Terminal/ConPTY — fix: default inline mode on native Windows ConPTY |
| #96372 | #96410 | open (PR) | TUI chat history clears on terminal resize — fix: stable row keys independent of `cols` |
| #126970 | #126992 | open (PR) | CLI clarify panels stay ~67 columns wide — fix: derive panel width from live terminal width |
| #67151 | #128225 | open (PR) | Unicode glyphs render as tofu on conhost/Consolas — fix: degrade glyphs safely on legacy Windows console |
| #85278 | — | open | Windows same-surface guard weak + pid_alive blast radius + voice auto-restart bypasses throttle (partially stale; claim 3 still valid) |
| #86204 | — | open | Orphan CLI python.exe children not reaped on Windows — needs fresh repro |
| #93999 | — | open | KawaiiSpinner floods terminal when message exceeds terminal width |
| #129029 | #129052 | open (PR) | CLI input unresponsive after focus loss (macOS) |
| #129418 | #129422 | open (PR) | CLI importing resets TERMINAL_DOCKER_VOLUMES from .env |
| #134831 | — | open | CLI oneshot hangs in Honcho shutdown thread join |

## 5b. Temporary workaround vs permanent fix

Label every remedy. A temporary workaround unblocks **now** and is worth undoing once the
real fix lands; a permanent fix changes the host or the config and is worth keeping. Some
permanent fixes are **outside Hermes entirely** — do not report those as Hermes bugs.

| Symptom | Temporary (until a proper fix) | Permanent |
|---|---|---|
| Tofu / unreadable busy face on conhost | `/indicator ascii` (or persist `display.tui_status_indicator: ascii`) | Install **Windows Terminal** (winget: `Microsoft.WindowsTerminal`) + Cascadia Mono, set it as the default terminal — a **non-Hermes** fix for a conhost/PowerShell-5.1 limitation; Hermes itself is fine |
| Garbled tool output from the Git Bash backend | `LANG=C.UTF-8 LC_ALL=C.UTF-8` for that shell | Leave `configure_windows_stdio()` enabled — never set `HERMES_DISABLE_WINDOWS_UTF8`; PS 5.1 pipes: `$OutputEncoding = [Text.UTF8Encoding]::new()` |
| Editor silent on `/edit` | one-off `EDITOR=code --wait` in that session | Persist `EDITOR` in config/env with the same `--wait` |
| Washed-out colors (#53301) | none needed | Export a truthful `COLORTERM` (e.g. `truecolor`) so chalk stops downgrading to 256-color |
| `hermes config set` warns on a TUI key | ignore the notice (the value still saves and is read) | Report upstream if a key the TUI honors stays unrecognized long-term |

When a workaround is temporary, say what "done" looks like: the upstream issue to watch, or
the version that carries the fix.

## 6. Cross-platform guardrails

- Prefer config/env fixes (work identically on POSIX); keep path logic runtime-resolved via `HERMES_HOME`
- Never hardcode `C:\...` paths in skills/plugins - use `%LOCALAPPDATA%\hermes` on Windows, `~/.hermes` elsewhere
- Shell commands issued by the agent keep POSIX syntax (the Windows backend is Git Bash); mind MSYS2 path translation and `core.autocrlf`
- Skins degrade to `default`; unknown indicator styles fall back; when Node can't be resolved the TUI exits with a `hermes --cli` pointer (no silent fallback) - preserve these behaviors

## 7. Verification checklist

```powershell
hermes --version; hermes doctor      # PM-managed Node, bash, deps
hermes config get display            # confirm keys above
hermes skills list                   # this skill should appear (hub or local, enabled)
# in TUI: /indicator ascii; /skin slate; /mouse wheel; /usage; /exit
```

Deep-dive reference: the original investigation with screenshot forensics,
redundancy analysis, and full source evidence lives at
`references/hermes-cli-tui-windows-investigation.md` in this skill's directory.

---

*Facts re-verified 2026-10-08 against upstream source at commit `f97608f178d1ffeca59860195ab7da295f7c8e5f` (skin_engine.py, config_defaults.py, stdio.py, gateway.py, tui_gateway/server.py, ui-tui/src/theme.ts, ui-tui/src/app/useMainApp.ts, hermes_cli/cli_tui_mixin.py, hermes_cli/update_cmd.py, hermes_cli/doctor_platform.py, hermes_cli/active_sessions.py, hermes_cli/cli_voice_mixin.py), upstream docs (installation.md), the issue tracker (18 citations, states noted), and the live Windows 10 desktop install (v0.21.1, `.venv`, Windows Terminal 1.24.12741); Node resolution re-checked 2026-09-29 at `5000e2993` (TUI node resolves through PM; `pm/lock.json` pins Node 26.7.0). Re-verify before reuse.*
