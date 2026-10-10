# AGENTS.md

Operating instructions for AI agents working **in this repository**. It answers
two questions: *what do I run and what must not break*, and *how to write about
it here*.

It is not a Hermes tutorial. The per-surface knowledge lives in `skills/`; the
authoring standard lives in [CONTRIBUTING.md](CONTRIBUTING.md). Where those two
disagree, CONTRIBUTING.md wins on **what to write** and this file wins on **how
to work in the repo**.

## What ships

<!-- BEGIN GENERATED: inventory -->
- **Plugin** — `plugin.yaml` + `__init__.py` / `checks.py` / `constants.py`. Registers `/hermes-doctor` and `hermes guide` (seven read-only health checks: config, mcp, skills, commands, hooks, plugins, memories).
- **Skills** — `twenty` `skills/<name>/SKILL.md` files: one install guide (`installing-hermes`), one configuration map (`hermes-configuration-guide`), eighteen `diagnosing-*` playbooks. They install separately, through the skills tap.
<!-- END GENERATED: inventory -->

Two install paths, both out of tree: the plugin (`hermes plugins install iap/hermes-guide --enable`) and the tap (`hermes skills tap add iap/hermes-guide`). `$HERMES_HOME` is `~/.hermes` on POSIX and `%LOCALAPPDATA%\hermes` on native Windows; `hermes config path` is the ground-truth command.

## Layout

| Path | Purpose |
|---|---|
| `plugin.yaml` | Plugin manifest — name, version, config schema. Declares no `capabilities:` on purpose |
| `__init__.py` | Plugin entrypoint; registers `/hermes-doctor` and `hermes guide` |
| `checks.py` | The read-only health checks and the `_CHECKS` registry every doc derives its scope list from |
| `constants.py` | Single source of truth for names/values that drift across Hermes versions |
| `pyproject.toml` | Project metadata and the mypy configuration |
| `skills/<name>/SKILL.md` | The skills tap surface (one directory per skill) |
| `tools/check_*.py` | Guard linters — every one is a machine gate with an exit code |
| `tools/check_doc_style.py` | Tone guard: emoji outside Python string literals, filler phrases in Markdown prose |
| `tools/check_issue_templates.py` | Reporter-surface guard: issue-template schema, and docs that promise a route the chooser does not offer |
| `tools/check_skill_dogfood.py` | Read-only live-install smoke test: version, config path, skills, plugins, doctor |
| `tools/test_*.py` | Regression suites for the plugin and for `tools/` itself |
| `tools/render_docs.py` | Renders the generated blocks in README.md and AGENTS.md from the repo |
| `tools/pr_metadata_labels.py` | PR label/priority parser shared by the labelling workflows |
| `.github/workflows/reusable-ci.yml` | The CI body: ubuntu+windows × Python 3.11/3.12 matrix, all gates |
| `.github/workflows/ci.yml` | Thin caller that triggers `reusable-ci.yml` and passes it `base-ref` / `run-full-gate` |
| `.github/workflows/upstream-drift.yml` | Weekly watch; opens an issue when Hermes changes a watched file or drift-prone fact |
| `.github/workflows/validate-claim.yml` | Re-runs the hermetic gates and machine-checks the PR's validation table |
| `.github/workflows/label-prs.yml`, `label-pr-metadata.yml` | Auto-labelling (paths, then PR body) |
| `.github/workflows/release.yml` | Release on tag; compares the tag against `plugin.yaml` |
| `.github/upstream-drift.baseline` | The pinned upstream revision that file/symbol citations resolve against |
| `.github/ISSUE_TEMPLATE/` | Bug report, config, and per-skill drift templates |
| `.github/PULL_REQUEST_TEMPLATE.md` | The validation table `validate-claim.yml` checks |
| `.github/labeler.yml` | Path-based labels (the body-based ones live in a workflow, since labeler v5 cannot read the body) |
| `.github/dependabot.yml` | Weekly version-update PRs for the SHA-pinned actions |
| `.pre-commit-config.yaml` | Local hook running the hermetic gate tier at commit time |
| `AGENTS.md` | This file |
| `CLAUDE.md` | `@AGENTS.md` import — the Claude Code entry point |
| `CONTRIBUTING.md` | The authoring standard: naming, content rules, voice |
| `README.md` | User-facing overview, install instructions, skill table |
| `SECURITY.md` | Security policy |
| `CHANGELOG.md` | Release history generated from conventional commits |
| `LICENSE` | MIT |
| `.gitignore` | The durable control for what never enters the index |

Keep the layout stable: plugin Python at the repo root, skills under
`skills/<name>/`, harness scripts only under `tools/`. Do not add ad-hoc scripts
at the root or under `skills/` that CI or agents are expected to run.

## Run this before you claim done

```bash
python tools/check_gates.py          # the hermetic tier — 5 gates, no network/git/Hermes
python -m py_compile __init__.py checks.py constants.py
hermes plugins doctor . --ci         # needs a local Hermes
```

`python tools/check_gates.py --list` prints the tier and, just as importantly,
what it deliberately leaves to CI. Adding a skill or editing a `SKILL.md` also
means:

```bash
python tools/render_docs.py --write  # refresh generated blocks (never hand-edit inside them)
python tools/check_skill_version_bump.py origin/master
python tools/check_skill_provenance.py
```

CI is the authority and runs more than the above: the `tools/test_*.py`
regression suites, `check_citation_integrity.py` against the pinned upstream
revision, mypy, and bandit. Several of those need a Hermes checkout or a
network — if you skip one, say so explicitly in the PR's validation table rather
than leaving it blank.

> [!NOTE]
> Every guard in `tools/` reads *text*, so a script that parses host output
> wrongly still passes all of them. Executable scripts shipped in a skill
> (`skills/*/scripts/`) need behavioral coverage in `tools/test_*.py` that runs
> them against stubbed inputs — a green guard suite is not evidence the script
> is correct.

## Rules the gates enforce

Learn these from the guard, not from memory — each one names its own script.

### Three output layers, never mixed

| Layer | Lives in | Contract |
|---|---|---|
| Hermes CLI | upstream `hermes …` | Whatever Hermes prints. Parse it inside a check; never rebrand or rewrite a Hermes message as ours |
| Plugin UX | `__init__.py` + `checks.py` | Check **envelopes** (`status` / `reason` / `detail`); `+/x/~/?` marks; `hermes guide` exits `0` healthy, `1` broken/unknown, `2` bad scope |
| Repo harness | `tools/` | Machine output — `OK:` / `FAIL` / `error:`, success on stdout, failures on stderr, non-zero exit. `--selftest` / `--warn` stay harness-only |

- **Checks return data; the plugin formats UX.** A check must not print a report
  or invent a second exit-code scheme. Return an envelope; `_format_result` and
  `_run_cli` own presentation.
- **A new tool** is `tools/check_<concern>.py` or `tools/test_<concern>.py`.
  Mirror its neighbours: argparse or argv flags, `--selftest` where the detector
  needs its own fixture, stderr for errors, a one-line summary, non-zero on
  failure.
- When a check shells out to Hermes, keep Hermes stdout/stderr as evidence inside
  `detail` / `reason`.

### Read-only, always

`checks.py` resolves paths, reads files, parses, and shells out to read-only
`hermes …` commands. It never mutates config and never auto-fixes
(`tools/check_no_mutation.py`). A new check returns an envelope and tolerates
malformed input without crashing.

`plugin.yaml` keeps `capabilities:` empty. Do not add one without a concrete need.

### Values that drift go in `constants.py`

When an upstream name or value changes, edit `constants.py` — not a string
literal in `checks.py`. `tools/check_upstream_drift.py` watches these upstream.

### Versions and provenance

- A changed `SKILL.md` needs a higher `version` (`check_skill_version_bump.py`,
  ordered — a downgrade fails too).
- `plugin.yaml`, `__init__.py`, `SECURITY.md`, and `pyproject.toml` must agree on
  the plugin version (`check_version_consistency.py`).
- Every skill ends with a dated, upstream-anchored provenance footer on its final
  non-empty line (`check_skill_provenance.py`). Refresh the date when you
  re-check the facts — do not touch it when you only reworded prose, or the
  footer starts claiming verification that did not happen.
- File/symbol citations (`path.py::symbol`, `path.py:123`) must resolve against
  the revision in `.github/upstream-drift.baseline`
  (`check_citation_integrity.py --src <checkout>`).

## Working conventions

### What belongs in git

Publish the plugin + tap surface and the harness CI runs. Everything else is
local until the user explicitly asks for it.

| Commit | Do not commit |
|---|---|
| `plugin.yaml`, `__init__.py`, `checks.py`, `constants.py`, `pyproject.toml` | Secrets and env files — already gitignored, never force-add |
| `skills/*/SKILL.md` | Agent/verification scratch (`.cluster/`, `.verify/`, root `tmp*.json`, `q*.json`, `.openclaw/`) |
| `tools/*.py`, `.github/workflows/` | IDE/OS junk, venvs, caches, logs, archives |
| Docs (`README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`) | Unsolicited new top-level files or directories — ask first |
| A deliberate `.gitignore` entry when a private path keeps recurring | Personal notes, one-off probes, "just in case" dumps |

- **`.gitignore` is the durable control; this table is the reminder.** Extend the
  ignore rules rather than relying on remembering what not to `git add`.
- **Never `git add -A` / `git add .`** here. Stage named paths.
- **User intent wins.** If they want a previously private path published, stage it
  on purpose and say so in the commit message — do not silently broaden the ignore
  rules afterwards.

### Where a change goes

| Change | Touch |
|---|---|
| Upstream name/value drift | `constants.py` |
| New or changed health surface | `checks.py` + `_CHECKS`, then skill text if users need a fix path |
| How-to / troubleshooting | `skills/<name>/SKILL.md` + version bump + provenance footer |
| Repo CI / guard / regression | `tools/check_*.py` or `tools/test_*.py`, wired into `reusable-ci.yml` when it must gate PRs |
| Which gates run locally | `tools/check_gates.py` + `.pre-commit-config.yaml`. CI stays the authority |
| Generated doc blocks | `tools/render_docs.py`, never by hand |

## Multi-environment maintenance

This repo is maintained in parallel from **different host environments** (native
Windows, macOS/POSIX), each with its own checkout and its own installed Hermes.

- **Verify platform-dependent facts only on your own machine.** `$HERMES_HOME`
  resolution, CLI/TUI behavior, installers, paths, shells. Never assert a platform
  fact you could not confirm here — the session on that platform owns its
  verification. The Windows-native agent owns `diagnosing-cli-tui` and the Windows
  sides of `diagnosing-path` / `diagnosing-desktop`; the POSIX agent owns
  `~/.hermes` behavior.
- **Say which platform verified a cross-platform change** (CI, `constants.py`,
  shared skill text) and leave platform-specific wording the other environment
  can adjust.
- **Expect parallel sessions.** Rebase before pushing, check open PRs before
  starting overlapping work — duplicate fixes have collided before (#54/#55).
- The PR template's **Environment** block exists for this. Fill it in.

## Tone

Applies to everything you write here — replies in this session, commit messages,
PR bodies, comments, and doc or skill prose.

- **Short and direct.** Lead with the result. Reasoning goes after it, or in the
  file you edited.
- **Technical prose only.** No enthusiasm, no reassurance, no restating the
  request back before answering it.
- **No cheerful filler.** "Thanks @user", not `Thanks so much @user!`. Drop
  `great question`, `hope this helps`, and apologies for things that were not
  your fault.
- **State the gap instead of smoothing it over.** If a check did not run, say so.
  If you are unsure, name the part you are unsure about and what would resolve it.

The artifact-level rules — no emoji in commits, PR bodies, or source — and their
carve-outs are in [CONTRIBUTING.md](CONTRIBUTING.md#tone). The mechanically
decidable half is enforced by `tools/check_doc_style.py`.

### Explaining

Applies when the answer is not a one-liner. Brevity is governed in **Tone**
above; this covers what a longer answer owes the reader.

- Structure a non-trivial design or problem as problem → concrete example or
  short trace → solution, then say why the solution is necessary rather than
  optional complexity.
- Prefer concrete behavior and a small illustration over an abstract summary,
  dense terminology, or an unexplained list of changes. Name the exact command,
  file, and field rather than the category it belongs to.
- Removing filler does not license replacing it with hedging. A short answer
  plus the command that produced the fact beats an adjective about the fact.

## Traps

Details live in the skills. These are the one-liners worth keeping in your head.

> [!IMPORTANT]
> **Don't guess Hermes hook event names.** The valid set is
> `hermes_cli/plugins.py::VALID_HOOKS` and it grows across releases — read the
> installed source, never a hardcoded count.

> [!WARNING]
> **Don't confuse Hermes with Claude Code or ZCode.** Hermes has no standalone
> command files (commands come from built-ins, skills-as-slash, bundles, and
> plugins), hooks span four separate systems, and plugins are `plugin.yaml` +
> `register(ctx)` — not `plugin.json`. See `diagnosing-commands` and
> `diagnosing-hooks`.

> [!WARNING]
> **Don't hardcode a venv path.** Older checkouts carry `venv/` and `.venv/` side
> by side and `project_venv_dir()` resolves `venv` first; PM-era installs have no
> in-tree venv at all and `project_venv_dir()` returns `None` even when a
> dependency environment exists — ask PM (`committed_venv()` for the directory,
> `project_python()` for the interpreter, and they are not interchangeable).
> `diagnosing-path` has the resolution order and the cross-platform patterns.

> [!NOTE]
> **An untracked `skills/<name>/` fails the pre-commit hook.** The gates read the
> working tree, so a new skill directory that is not yet staged breaks the count
> and routing gates on every commit. `git add` or `git stash` it first.

> [!TIP]
> **Hermes configuration is YAML**, never JSON. And every diagnosis should end in a
> concrete action: a `hermes <subcommand>`, or a specific file + field edit,
> followed by a `/reload-*` or a restart.

## Before you finish

State plainly what you checked, what passed, and what you skipped. A validation
table with honest `not run` entries is accepted; a claim that outruns the evidence
is not — `validate-claim.yml` re-runs the hermetic gates against your PR head and
fails the check if your table does not match reality.