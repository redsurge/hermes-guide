#!/usr/bin/env python3
"""Regression: check envelopes must stay informative.

Two defects are pinned below. Both made a diagnostic *less* useful than the
input it was given:

1. `check_commands` rendered the literal string ``vunversioned`` for a skill
   with no ``version`` frontmatter — a bare ``f"v{value}"`` over a missing
   value. Reproduced against a real install before fixing.
2. `check_hooks` returned the malformed-allowlist envelope *instead of* the
   `hermes hooks doctor` findings, so when both fired the hook problems were
   silently dropped.

No Hermes binary and no $HERMES_HOME: the plugin package is loaded through a
shim and the cases monkeypatch the two boundaries (`_run`,
`_check_allowlist_json`) plus the filesystem walks.

Run: python3 tools/test_check_envelopes.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

MARK_BAD = "\u2717"   # U+2717 BALLOT X
MARK_WARN = "\u26a0"  # U+26A0 WARNING SIGN


def _load_checks():
    """Import checks.py under a valid package name (the repo dir has hyphens)."""
    td = Path(tempfile.mkdtemp())
    pkg = td / "hermes_guide"
    pkg.mkdir()
    for name in ("__init__.py", "checks.py", "constants.py"):
        shutil.copy(REPO / name, pkg / name)
    sys.path.insert(0, str(td))
    import hermes_guide.checks as checks  # noqa: E402

    return checks


def case_version_label(checks):
    """The label helper never emits `vunversioned`."""
    assert checks._version_label("1.2.3") == "v1.2.3"
    assert checks._version_label(" 1.2.3 ") == "v1.2.3"
    assert checks._version_label("") == "unversioned"
    assert checks._version_label(None) == "unversioned"
    assert checks._version_label("   ") == "unversioned"
    for value in (None, "", "   "):
        assert "vunversioned" not in checks._version_label(value)
    print("OK: version labels render `v1.2.3` / `unversioned`, never `vunversioned`")


def case_collision_message(checks):
    """A versionless first owner renders as `unversioned`, not `vunversioned`."""
    checks._hermes_home_from_library = lambda: "/fake/home"
    checks._rel_path = lambda path, base: path  # POSIX-safe on the Windows leg too
    checks._builtin_command_names = lambda: set()
    checks._iter_skills = lambda: [
        ("/fake/home/skills/requesting-code-review", {"name": "requesting-code-review"}),
        (
            "/fake/home/skills/software-development/requesting-code-review",
            {"name": "requesting-code-review", "version": "2.0.0"},
        ),
    ]

    env = checks.check_commands()
    detail = env.get("detail") or []
    text = " ".join(str(d) for d in detail)
    assert env["status"] == "informational", env
    assert "vunversioned" not in text, text
    assert "unversioned" in text, text
    assert "v2.0.0" in text, text
    print("OK: slug-collision message renders `unversioned` / `v2.0.0`")


def case_hooks_merges_doctor_findings(checks):
    """A malformed allowlist must not drop the hooks-doctor findings."""
    doctor_out = (
        "Shell hooks\n"
        f"  {MARK_BAD} broken-hook   exit code 3\n"
        f"  {MARK_WARN} slow-hook     timeout\n"
    )
    checks._run = lambda cmd, timeout=20: (0, doctor_out, "")
    checks._check_allowlist_json = lambda: {
        "status": "broken",
        "reason": "shell-hooks-allowlist.json is not valid JSON",
        "detail": "/fake/home/shell-hooks-allowlist.json",
    }

    env = checks.check_hooks()
    assert env["status"] == "broken", env
    assert "not valid JSON" in env["reason"], env
    assert isinstance(env["detail"], list), env
    joined = " ".join(str(d) for d in env["detail"])
    assert "`hermes hooks doctor`" in joined, joined   # doctor verdict survives
    assert "broken-hook" in joined, joined             # doctor detail survives
    print("OK: malformed allowlist no longer drops the hooks-doctor findings")


def case_hooks_allowlist_alone_when_doctor_healthy(checks):
    """When the doctor is healthy, only the allowlist finding is reported."""
    checks._run = lambda cmd, timeout=20: (0, "All shell hooks look healthy", "")
    checks._check_allowlist_json = lambda: {
        "status": "broken",
        "reason": "shell-hooks-allowlist.json is not valid JSON",
        "detail": "/fake/home/shell-hooks-allowlist.json",
    }

    env = checks.check_hooks()
    assert env["status"] == "broken", env
    assert env["detail"] == ["/fake/home/shell-hooks-allowlist.json"], env
    print("OK: healthy doctor + malformed allowlist reports the allowlist alone")


def case_hooks_unaffected_when_allowlist_fine(checks):
    """No allowlist problem -> the doctor envelope passes through unchanged."""
    doctor_out = f"  {MARK_BAD} broken-hook   exit code 3\n"
    checks._run = lambda cmd, timeout=20: (0, doctor_out, "")
    checks._check_allowlist_json = lambda: None

    env = checks.check_hooks()
    assert env["status"] == "broken", env
    assert "hooks doctor" in env["reason"], env
    assert isinstance(env["detail"], str), env
    print("OK: doctor envelope unchanged when the allowlist is fine")


def main() -> int:
    checks = _load_checks()
    failures: list[str] = []
    for case in (
        case_version_label,
        case_collision_message,
        case_hooks_merges_doctor_findings,
        case_hooks_allowlist_alone_when_doctor_healthy,
        case_hooks_unaffected_when_allowlist_fine,
    ):
        try:
            case(checks)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{case.__name__}: {exc}")
            print(f"FAIL: {case.__name__}: {exc}")
    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nOK: 5 check-envelope case(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
