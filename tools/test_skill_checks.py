#!/usr/bin/env python3
"""Behavioral test for the skill-library checks.

Verifies three behaviors introduced for mixed bundled/user skill libraries:

1. Hidden/archive directories (``.archive``, ``.curator_backups``, ``.hub``)
   are skipped by ``_iter_skills``, so archived/backup skill copies never
   produce false positives.
2. ``check_skills`` labels a skill ``[bundled]`` only from its declared
   frontmatter ``name`` (what Hermes keys ``.bundled_manifest`` on). The
   directory basename is never used as ownership evidence, so a nested or
   unreadable user skill that merely shares a basename with a bundled skill
   is not mislabeled.
3. ``check_commands`` includes each skill's ``version`` in slug-collision
   messages, so a stale unversioned copy is distinguishable from a newer
   versioned one at a glance.

Uses a synthetic ``$HERMES_HOME`` (monkeypatched) so it does not touch the
real install and does not require the ``hermes`` CLI.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_home(root: Path) -> None:
    _write(root / "skills/.bundled_manifest", "dogfood:abc123\nstub:def456\nweather:098fed\n")
    # valid bundled skill (healthy control)
    _write(root / "skills/dogfood/SKILL.md", "---\nname: dogfood\ndescription: bundled skill\n---\nbody\n")
    # no-fence skill whose basename matches a bundled name -> must NOT be [bundled]
    # and must NOT be reported as broken (Hermes loads it under its directory name)
    _write(root / "skills/stub/SKILL.md", "just text no frontmatter")
    # no-fence skill whose basename is not bundled -> no tag, not broken
    _write(root / "skills/user-broken/SKILL.md", "also no frontmatter")
    # nested user skill with no `name` but basename collides with bundled -> no tag, not broken
    _write(root / "skills/user-collection/dogfood/SKILL.md", "---\ndescription: user skill, no name\n---\nbody\n")
    # declared name matches manifest but missing description -> [bundled], not broken
    _write(root / "skills/weather/SKILL.md", "---\nname: weather\n---\nbody\n")
    # non-string name -> broken (the loader cannot use it)
    _write(root / "skills/bad-name/SKILL.md", "---\nname: [a, b]\ndescription: bad\n---\nbody\n")
    # non-string description -> broken (the loader cannot use it)
    _write(root / "skills/bad-desc/SKILL.md", "---\nname: bad-desc\ndescription: [a, b]\n---\nbody\n")
    # non-mapping frontmatter block -> broken
    _write(root / "skills/bad-block/SKILL.md", "---\n- just\n- a\n- list\n---\nbody\n")
    # malformed YAML with recoverable name -> NOT broken (loader recovers it)
    _write(root / "skills/malformed-yaml/SKILL.md", "---\nname: malformed-yaml\ndescription: fine\nkey: [unclosed\n---\nbody\n")
    _write(root / "skills/foo/SKILL.md", "---\nname: foo\ndescription: old\n---\nold\n")
    _write(root / "skills/category/foo/SKILL.md", "---\nname: foo\ndescription: new\nversion: 1.2.0\n---\nnew\n")
    _write(root / "skills/.archive/foo-old/SKILL.md", "---\nname: foo\ndescription: archived\nversion: 0.1.0\n---\narchived\n")
    _write(root / "skills/plain/SKILL.md", "---\nname: plain\ndescription: p\nversion: 2.0.0\n---\nbody\n")


def main(argv: list[str]) -> int:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as td:
        pkg = Path(td) / "hermes_guide"
        pkg.mkdir()
        for name in ("__init__.py", "checks.py", "constants.py"):
            shutil.copy(REPO / name, pkg / name)
        sys.path.insert(0, td)

        import hermes_guide.checks as checks  # noqa: E402

        home = Path(td) / "home"
        _build_home(home)

        checks._cache.clear()
        checks._hermes_home_from_library = lambda: str(home)

        # (1) hidden/archive dirs are skipped
        walked = list(checks._iter_skills())
        if len(walked) != 12:
            failures.append(f"expected 12 skills (hidden .archive skipped), got {len(walked)}")
        if any(".archive" in d for d, _ in walked):
            failures.append("hidden .archive dir was not skipped")

        # (2) bundled label comes only from declared name, never basename
        sr = checks.check_skills()
        sdetail = sr.get("detail") or []
        if sr["status"] != "broken" or sr["reason"] != "3 skill issue(s)":
            failures.append(f"check_skills unexpected: {sr['status']} - {sr['reason']}")
        # weather has a valid name but no description -> healthy, not in findings
        if any("weather" in d for d in sdetail):
            failures.append("weather (valid name, no description) reported as broken")
        # negative: basename matches manifest but no declared name -> NOT [bundled]
        if any("stub" in d and "[bundled]" in d for d in sdetail):
            failures.append("no-fence skill (stub) mislabelled [bundled] from basename")
        if any("user-collection/dogfood" in d and "[bundled]" in d for d in sdetail):
            failures.append("nameless nested skill mislabelled [bundled] from basename")
        if any("user-broken" in d and "[bundled]" in d for d in sdetail):
            failures.append("no-fence user skill mislabelled [bundled]")
        # no-fence skills are NOT broken (Hermes loads them under directory name)
        if any("stub" in d for d in sdetail):
            failures.append("no-fence skill (stub) reported as broken")
        if any("user-broken" in d for d in sdetail):
            failures.append("no-fence skill (user-broken) reported as broken")
        if any("user-collection/dogfood" in d for d in sdetail):
            failures.append("nameless skill (user-collection/dogfood) reported as broken")
        # non-string name IS broken
        if not any("bad-name" in d for d in sdetail):
            failures.append("non-string name (bad-name) not reported")
        # non-string description IS broken
        if not any("bad-desc" in d for d in sdetail):
            failures.append("non-string description (bad-desc) not reported")
        # non-mapping frontmatter IS broken
        if not any("bad-block" in d for d in sdetail):
            failures.append("non-mapping frontmatter (bad-block) not reported")
        # malformed YAML with recoverable name is NOT broken (loader recovers it)
        if any("malformed-yaml" in d for d in sdetail):
            failures.append("malformed-yaml (recoverable name) reported as broken")

        # (3) collision messages carry versions and skip archived copies
        cr = checks.check_commands()
        cdetail = cr.get("detail") or []
        coll = [d for d in cdetail if "normalize to" in d]
        if len(coll) != 1:
            failures.append(f"expected exactly 1 collision, got {len(coll)}")
        elif "v1.2.0" not in coll[0] or "unversioned" not in coll[0]:
            failures.append(f"version info missing from collision: {coll[0]}")
        elif "foo-old" in coll[0]:
            failures.append("archived skill leaked into collision")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("OK: skill-library checks behave as expected (bundled label, hidden-dir skip, versioned collisions)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
