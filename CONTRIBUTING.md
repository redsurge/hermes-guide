# Contributing

This repository documents Hermes behavior, so every skill is a claim about what a
specific Hermes version actually does. Verify each claim against the version in
use, then run `python tools/check_gates.py` — the gate list is under
[Pull requests](#pull-requests).

**This file is the authoring standard.** It owns *what gets written* — skill
naming, frontmatter, content rules, voice, and the PR workflow. It does not
duplicate how the repo's gates work or how to run them; that is
[AGENTS.md](AGENTS.md), and the two files split on that line deliberately. If you
find the same rule in both, one of them is wrong — fix the copy that drifted.

## What this project is

hermes-guide is a [Hermes Agent](https://github.com/NousResearch/hermes-agent)
plugin **plus** a skills tap, and they are installed separately.

- The **plugin** (`plugin.yaml` + `__init__.py` / `checks.py` / `constants.py`)
  ships read-only diagnostics: `/hermes-doctor` in a session and `hermes guide` in
  a terminal.
- The **skills tap** (`skills/`) ships per-surface troubleshooting playbooks.

The counts live in a generated block in [README.md](README.md) and
[AGENTS.md](AGENTS.md) — `python tools/render_docs.py` renders them from the
tree, so there is no number in this file to keep in sync.

## Reporting issues

If a skill gives inaccurate guidance for a specific Hermes version, or misses a
known pitfall, [open an issue](https://github.com/redsurge/hermes-guide/issues). There
are two templates — `bug-report.yml` for anything broken in the plugin, checks or
docs, and `skill-drift.yml` for a fact that no longer matches Hermes — and blank
issues are disabled. The `skill-drift.yml` dropdown carries one option per shipped
skill, so pick the right one to keep drift reports attributable. Both templates
require the Hermes version; `skill-drift.yml` also requires the skill and the
evidence for the drift.

A configuration problem is not a separate form. `config.yml` in
`.github/ISSUE_TEMPLATE/` is GitHub's chooser configuration, not a report you can
select, so it is not offered in the new-issue list. Report a wrong configuration
answer through `skill-drift.yml` when a skill documents it, or `bug-report.yml`
when the checks produce it.

For a question rather than a defect, do not open an issue — see
[Questions](#questions).

What happens after you submit is in [Contribution gate](#contribution-gate).

## Contribution gate

What happens after you submit, stated up front so nothing is a surprise later.

**The bar.** An issue or PR is reviewable when it clears all of these:

- It uses a template. Blank issues are disabled
  (`.github/ISSUE_TEMPLATE/config.yml`), and the templates carry the required
  fields: `bug-report.yml` requires the Hermes version, `skill-drift.yml`
  requires the skill.
- It is about this repo. A Hermes-core defect or feature request belongs
  upstream; both contact links are in `config.yml`.
- A vulnerability goes to the private advisory route in
  [SECURITY.md](SECURITY.md), not the public tracker.
- It states what was expected and what happened, with the command and its output.
  Redact tokens.
- It is not a question a shipped skill already answers — start with
  `hermes-configuration-guide` and the [skill table](README.md#whats-included).

**What a maintainer may do.** Close an issue or PR that misses the bar, with a
reason recorded on it. That reason is the response: no further discussion is
promised. Reopening is not automatic and is not granted on request — but a
maintainer may reopen at any time, including when a later Hermes release changes
the answer.

Clearing the bar does not oblige anyone to review or merge. The same discretion
applies to pull requests; the parts of the PR bar that machines already enforce
are listed under [Pull requests](#pull-requests).

This section is policy rather than a machine gate, with two exceptions that
already are: `blank_issues_enabled: false` is structural, and
`tools/test_skill_counts.py` fails when the `skill-drift.yml` dropdown and the
shipped skills disagree.

## Branch naming

Short-lived branches, prefixed by type. Branch → merge to `master` → delete.
Never keep long-lived category buckets.

| Prefix | Use for |
|---|---|
| `fix/` | Defects (wrong behavior), e.g. `fix/mcp-key-constants` |
| `feat/` | Enhancements and refactors, e.g. `feat/plugin-hardening` |
| `docs/` | Documentation-only changes |
| `style/` | Formatting, no behavior change |
| `refactor/` | Same behavior, different structure |
| `perf/` | Performance improvements |
| `test/` | Tests |
| `chore/` | Deps, build tooling |
| `ci/` | CI workflow changes (prefer `ci/` over `chore/` for workflow-only changes) |

Add a new prefix only when you actually need it.

## Commit messages

Conventional Commits: `type(scope): summary`.

| Type | Use for |
|---|---|
| `fix` | Defects |
| `feat` | Enhancements |
| `docs` | Documentation |
| `style` | Formatting |
| `refactor` | Same behavior, different structure |
| `perf` | Performance |
| `test` | Tests |
| `ci` | CI workflow changes |
| `chore` | Deps, build |

Scope is the affected surface: `mcp`, `checks`, `config`, `skills`, `hooks`,
`plugins`, `ci`, `deps`.

Examples:

- `fix(mcp): correct key constants for OAuth flow`
- `docs(skills): document the PM-era no-in-tree-venv case`
- `feat(guide): add the diagnosing-cron skill`

## Tone

Rules for everything a contribution carries: commit messages, PR bodies, issue
comments, source, and documentation.

- **Short and direct.** Lead with the result.
- **No cheerful filler.** "Thanks @user", not `Thanks so much @user!`. No
  `great question`, `hope this helps`, or apologies for things that were not your
  fault.
- **Technical prose only.** No enthusiasm, no reassurance, no restatement of
  the request before answering it.
- **No emoji** in prose, commit messages, PR or issue bodies, or source.

Three carve-outs, because each of these quotes rather than decorates:

- **Transcribed output.** Inside a fenced code block or an inline code span, a
  glyph is part of the data. A skill reproducing what a terminal prints has to
  match it byte for byte, or it is lying to the reader.
- **Protocol characters in code.** `checks.py` parses the hook markers
  `hermes hooks doctor` emits, so those glyphs belong in the string literal that
  matches them — never in a comment, where the codepoint name (`U+2717 BALLOT X`)
  is both ASCII-safe and more precise.
- **Bot-generated GitHub output.** `validate-claim.yml` posts a verdict icon in
  its PR comment on purpose; an at-a-glance pass/fail marker is the point.

`tools/check_doc_style.py` enforces the half that is mechanically decidable:
emoji outside string literals in Python, and a deny-list of filler phrases in
Markdown prose. Emoji in Markdown prose, commit messages, and PR bodies are left
to review — every legitimate exception above would need an allowlist, and an
allowlist rots.

Quoting a banned phrase is fine as long as it sits in a code span, which is why
the examples above are in backticks: the guard must not flag the standard for
stating itself.

## Adding or changing a skill

A skill is one directory, `skills/<name>/SKILL.md`, with YAML frontmatter
carrying exactly three keys:

```yaml
---
name: diagnosing-mcp
description: "One or two sentences an agent can route on."
version: 1.0.0
metadata:
  hermes:
    tags: [hermes, mcp, troubleshooting, guide]
    related_skills: [hermes-configuration-guide]
---
```

- **Naming.** `diagnosing-<surface>` for playbooks, lowercase kebab-case, ≤20
  characters. `installing-hermes` is the install guide and `hermes-configuration-guide`
  is the routing map — both predate the length limit and are exempt. Do not rename
  either to fit it.
- **Description.** This is the only thing a router sees. Name the surface and the
  symptom; do not spend it on adjectives.
- **Version.** Any change to a `SKILL.md` bumps `version`, and the bump must go
  *up* — a downgrade fails the same way a missing bump does.
- **Provenance footer.** The final non-empty line must be dated and upstream-anchored:
  `*Facts (re-)verified YYYY-MM-DD against upstream source at \`<rev>\` (<files/symbols>).*`
  Refresh the date when you re-check the facts. Leave it alone when you only
  reworded prose — otherwise the footer starts claiming work that did not happen.
- **Routing.** Every new `diagnosing-*` skill needs a bullet in the configuration
  map's `## Routing` section, and an entry in the README table and the
  `.github/ISSUE_TEMPLATE/skill-drift.yml` dropdown. `render_docs.py` refreshes
  the generated blocks; the rest is yours to edit.

### Content rules

- **Ground every fact in the installed Hermes.** `website/docs/` for
  documentation, `hermes_cli/` / `agent/` / `hermes_constants.py` for source
  truth. Web search alone is not evidence.
- **End on an action.** Every diagnosis resolves to a `hermes <subcommand>` or a
  specific file + field edit, followed by a `/reload-*` or a restart. Advice the
  reader cannot execute is not a diagnosis.
- **Name the exact command.** `hermes config path`, not "run the config command".
- **Configuration is YAML.** `config.yaml`, never JSON syntax.
- **Paths are platform-dependent.** `$HERMES_HOME` is `~/.hermes` on POSIX and
  `%LOCALAPPDATA%\hermes` on native Windows; teach `hermes config path` as the
  ground truth rather than picking one.
- **One surface per skill.** If a section would need a second `## Routing` entry
  to be found, it belongs in another skill.
- **Citations must resolve.** `path.py::symbol` and `path.py:123` are checked
  against the revision pinned in `.github/upstream-drift.baseline`.
- **Cite the behavior, not the plan.** Do not describe a feature that upstream has
  not shipped; if the upstream change is behind a release, say which.

### Content voice

How the *content* reads — distinct from the conversational tone above. Describe
behavior; never assert quality.

- ✅ "Skills track the Hermes source"
- ✅ "Checks report malformed bundles, missing plugins, and slug collisions"
- ❌ "The most reliable, fully accurate guide to Hermes"

The ✅/❌ markers above are the one place Markdown prose uses emoji, and they are
exempt on purpose: they mark a good example against a bad one, which is a
judgment no reader should have to infer.

`tools/check_self_claim.py` enforces the substance over every Markdown file in the
repo and holds the deny-list. If it trips, reword the line into a factual
statement of what the code does.

Structure prose for scanning: tables for structured data (pitfall catalogs,
system comparisons), lists for steps, and GitHub alert callouts where they earn
their place:

> [!NOTE] — context not to miss
> [!TIP] — optional shortcut
> [!IMPORTANT] — required for success
> [!WARNING] — breakage or data-loss risk
> [!CAUTION] — irreversible action

## Questions

A question is not a defect report. `bug-report.yml` and `skill-drift.yml` both
want a reproduction, and "how do I..." has none — so the new-issue list offers a
Questions entry that opens Discussions instead.

Before asking, check whether a shipped skill already answers it:
`hermes-configuration-guide` is the map, and the
[skill table](README.md#whats-included) lists the rest.

When you do ask, three facts turn most questions into answers: the Hermes
version, your platform (native Windows or POSIX), and the output of
`hermes config path`.

## Pull requests

1. Fork and branch: `git checkout -b fix/diagnosing-mcp-oauth`.
2. Make the change.
3. Run the gates. `python tools/check_gates.py` is the fast tier;
   `python tools/render_docs.py --write` refreshes generated blocks; see
   [AGENTS.md](AGENTS.md) for the full list and what CI adds on top.
4. Fill in the PR template — **Environment** and **Validation Results** are read
   by workflows, not just by reviewers. The validation table is machine-checked:
   `validate-claim.yml` re-runs the hermetic gates against your head and fails
   the check if your table does not match reality.
5. Report anything you could not run as `not run` rather than omitting the row.
   An honest gap is accepted; an unsupported claim is not.

Because this repo is maintained from several platforms in parallel, a claim
verified on one host is not verified on the others. Name the platform in the PR.
