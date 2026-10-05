#!/usr/bin/env python3
"""Behavioral test: a malformed frontmatter ``name`` must not crash ``check_skills``.

``check_skills`` labels a skill ``[bundled]`` by testing its declared
frontmatter ``name`` against the bundled-name set. ``name`` is parsed with
``yaml.safe_load`` and only the frontmatter *root* is type-checked, so the
*value* may be any YAML node. A mapping (``name: {a: b}``) or a sequence
(``name: [1, 2]``) is unhashable, and ``name in bundled`` then raises
``TypeError``.

That crash is swallowed by ``run_all``'s per-check isolation and surfaced as
``status: "broken"`` with reason ``"check crashed (...)"`` -- so a single
malformed third-party SKILL.md made every ``hermes guide`` / ``/hermes-doctor``
run exit 1 while reporting the wrong cause. A diagnostic must survive the
broken inputs it exists to diagnose, so the check has to degrade to a normal
finding instead.

Asserts, for each unhashable ``name`` shape:
  - ``check_skills`` returns an envelope instead of raising
  - the envelope is ``broken`` and names the offending skill
  - the finding is the ordinary missing/invalid-``name`` one, not a crash
  - ``run_all`` reports the ``skills`` label ``broken`` but never ``crashed``,
    and no other check is collaterally affected

Uses a synthetic ``$HERMES_HOME`` (monkeypatched) so it does not touch the
real install and does not require the ``hermes`` CLI.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Unhashable YAML shapes a real (or malformed) SKILL.md could carry.
BAD_NAMES = {
    "mapping": "name: {a: b}\n",
    "sequence": "name: [1, 2]\n",
}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_checks(td: str):
    """Import checks.py as a package member (it uses ``from . import constants``)."""
    pkg = Path(td) / "hermes_guide"
    pkg.mkdir(exist_ok=True)
    for name in ("__init__.py", "checks.py", "constants.py"):
        shutil.copy(REPO / name, pkg / name)
    sys.path.insert(0, td)
    import hermes_guide.checks as checks  # noqa: E402

    return checks


def _plugin_skill_names_cases() -> list[str]:
    """``_plugin_skill_names`` walks the plugin's OWN ``skills/`` directory.

    It has the same unvalidated-YAML hazard as ``check_skills``: the declared
    ``name`` is fed straight into ``set.add``, so a mapping or sequence value
    raises TypeError instead of degrading. It cannot be reached through
    ``$HERMES_HOME`` (that is ``check_skills``' job), so it needs a plugin-side
    fixture: a copy of the repo whose ``skills/`` holds one malformed file.

    A non-string name must fall back to the directory basename so the inventory
    stays usable, and the malformed file is reported by the count/provenance
    guards rather than crashing the plugin.
    """
    failures: list[str] = []
    for shape, name_line in BAD_NAMES.items():
        with tempfile.TemporaryDirectory() as td:
            checks = _load_checks(td)
            plugin_root = Path(td) / "plugin"
            (plugin_root / "skills").mkdir(parents=True)

            # one healthy skill so the inventory is not empty
            _write(
                plugin_root / "skills/healthy/SKILL.md",
                "---\nname: healthy\ndescription: fine\nversion: 1.0.0\n---\nbody\n",
            )
            _write(
                plugin_root / "skills/malformed/SKILL.md",
                f"---\n{name_line}description: unhashable name\nversion: 1.0.0\n---\nbody\n",
            )

            checks._cache.clear()
            # point the walker at the fixture instead of the real repo skills/
            checks.__file__ = str(plugin_root / "checks.py")
            try:
                names = checks._plugin_skill_names()
            except Exception as exc:  # noqa: BLE001 - that is the regression
                failures.append(
                    f"[plugin/{shape}] _plugin_skill_names raised "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            if not any(isinstance(n, str) for n in names):
                failures.append(f"[plugin/{shape}] inventory unusable: {names!r}")
            if "healthy" not in names:
                failures.append(f"[plugin/{shape}] healthy skill lost from inventory: {names!r}")
            # the malformed one must be tracked by basename, not crash or vanish
            if "malformed" not in names:
                failures.append(
                    f"[plugin/{shape}] malformed skill not tracked by basename: {names!r}"
                )
    return failures

def main(argv: list[str]) -> int:
    failures: list[str] = []

    for shape, name_line in BAD_NAMES.items():
        with tempfile.TemporaryDirectory() as td:
            checks = _load_checks(td)
            home = Path(td) / "home"
            skill_dir = home / "skills" / "malformed"

            # A healthy control skill alongside it, so the tree is not empty.
            _write(
                home / "skills/healthy/SKILL.md",
                "---\nname: healthy\ndescription: fine\nversion: 1.0.0\n---\nbody\n",
            )
            _write(
                skill_dir / "SKILL.md",
                f"---\n{name_line}description: unhashable name\nversion: 1.0.0\n---\nbody\n",
            )

            checks._cache.clear()
            checks._hermes_home_from_library = lambda: str(home)
            checks._hermes_config_path = lambda: str(home / "config.yaml")
            _write(home / "config.yaml", "model: test\n")

            # Baseline: the same tree WITHOUT the malformed skill. Checks that
            # depend on state this fixture does not populate (plugins, memory)
            # are compared against it rather than asserted absolutely, so the
            # test stays honest instead of hard-coding unrelated verdicts.
            baseline = {}
            checks._cache.clear()
            for label, env in checks.run_all().items():
                baseline[label] = env.get("status")
            _healthy_only = dict(baseline)
            _healthy_only["skills"] = "informational"

            # (a) the check itself must not raise
            try:
                res = checks.check_skills()
            except Exception as exc:  # noqa: BLE001 - that is the regression
                failures.append(f"[{shape}] check_skills raised {type(exc).__name__}: {exc}")
                continue

            # (b) it must still report the skill as an issue
            if res.get("status") != "broken":
                failures.append(
                    f"[{shape}] expected broken, got {res.get('status')!r} ({res.get('reason')!r})"
                )
                continue

            detail = res.get("detail") or []
            if not any("malformed" in str(d) for d in detail):
                failures.append(f"[{shape}] offending skill not named in findings: {detail}")

            # (c) the reason must be the real cause, not "check crashed"
            if "crash" in str(res.get("reason", "")).lower():
                failures.append(
                    f"[{shape}] reported a crash instead of the real defect: {res.get('reason')!r}"
                )

            # (d) via the shipped entry point: broken, but never a crash envelope
            checks._cache.clear()
            results = checks.run_all()
            skills_env = results.get("skills", {})
            if skills_env.get("status") != "broken":
                failures.append(
                    f"[{shape}] run_all skills status {skills_env.get('status')!r}, expected broken"
                )
            if "crash" in str(skills_env.get("reason", "")).lower():
                failures.append(
                    f"[{shape}] run_all surfaced a crash: {skills_env.get('reason')!r}"
                )
            # every other check must land exactly where the baseline put it
            for label, env in results.items():
                if label == "skills":
                    continue
                if env.get("status") != _healthy_only.get(label):
                    failures.append(
                        f"[{shape}] collateral damage: {label} moved "
                        f"{_healthy_only.get(label)!r} -> {env.get('status')!r} "
                        f"({env.get('reason')!r})"
                    )

    failures.extend(_plugin_skill_names_cases())

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("OK: malformed frontmatter name degrades to a finding, never a crash")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
