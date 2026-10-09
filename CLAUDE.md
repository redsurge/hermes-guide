@AGENTS.md

# Claude Code Quick Reference

This repo is a Hermes Agent plugin + skills tap. The full contributing guide is
in AGENTS.md (imported above). Here is what a Claude Code session needs beyond
that.

## What ships

- **Plugin** — `plugin.yaml` + `__init__.py` / `checks.py` / `constants.py`.
  Registers `/hermes-doctor` in sessions and `hermes guide` in terminals. Seven
  read-only health checks: config, mcp, skills, commands, hooks, plugins, memories.
- **Skills tap** — 20 `skills/<name>/SKILL.md` files. Install separately via
  `hermes skills tap add redsurge/hermes-guide`.

## Before you claim done

Run the gates. They are the authority, not a green CI run:

```bash
python tools/check_gates.py          # hermetic tier — no network, no Hermes
```

If you added or changed a skill, also run:

```bash
python tools/render_docs.py --write  # refresh generated blocks
python tools/check_skill_version_bump.py origin/master
python tools/check_skill_provenance.py
```

CI runs more than the above (mypy, bandit, citation integrity against the
pinned upstream revision). Report anything you could not run as `not run` in
the PR template's validation table — an honest gap is accepted, an unsupported
claim is not.

## Key rules

- **Read-only plugin.** `checks.py` never mutates config. `tools/check_no_mutation.py`
  enforces this. Do not add write-mode `open()`, `yaml.dump()`, `json.dump()`,
  `Path.write_text()`, `os.remove()`, or `shutil.*`.
- **Provenance footers.** Every skill ends with a dated, upstream-anchored footer.
  When you update facts, refresh the date and the commit SHA. When you only
  reword prose, leave the footer alone — otherwise it claims verification that did
  not happen.
- **Skill versions.** Any content change to a SKILL.md bumps `version` up. A
  downgrade fails the guard the same way a missing bump does.
- **Account rename.** All references use `redsurge/hermes-guide`, not `iap/hermes-guide`.
  The repo was renamed; GitHub redirects still work but the docs should be correct.

## Layout

| Path | Purpose |
|---|---|
| `plugin.yaml` | Plugin manifest — name, version, config schema |
| `__init__.py` | Plugin entrypoint; registers `/hermes-doctor` and `hermes guide` |
| `checks.py` | The read-only health checks and the `_CHECKS` registry |
| `constants.py` | Single source of truth for names/values that drift across Hermes versions |
| `skills/<name>/SKILL.md` | The skills tap surface (one directory per skill) |
| `tools/check_*.py` | Guard linters — every one is a machine gate with an exit code |
| `tools/test_*.py` | Regression suites for the plugin and for `tools/` itself |
| `tools/render_docs.py` | Renders the generated blocks in README.md and AGENTS.md |
| `.github/upstream-drift.baseline` | The pinned upstream Hermes commit that citations resolve against |

## When skills are wrong

Open a `skill-drift.yml` issue (not a blank issue — blank issues are disabled).
The template requires the Hermes version, the skill name, and the evidence for the
drift. Do not open an issue for a question — use Discussions instead.
