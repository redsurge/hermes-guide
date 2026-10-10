#!/usr/bin/env python3
"""Regression coverage for the hardened check_upstream_drift.py.

The weekly drift watch was hardened to (a) scan upstream git history at
commit granularity, (b) use exact-title dedup so a substring-matching issue
cannot suppress a real alert, (c) fail the run on transport failures, and
(d) block filing when the CI-pin freshness check cannot run, and (e) cap
the report sections without losing the footer, and (f) retry transient
ls-remote failures — exit codes and transport exceptions — in the pin check,
and (g) find the install pin wherever the workflow files keep it,
ignoring unrelated or commented-out clones. Each case below pins one of those behaviors.

No network, no `gh` CLI, no upstream clone: git/gh are monkeypatched.

Run: python3 tools/test_upstream_drift_hygiene.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent


def _load_module():
    """Import the drift script as a module.

    The script does `sys.path.insert(0, REPO_ROOT); import constants`, so we need
    constants.py and checks.py importable from the same dir as the script.
    """
    import importlib
    td = Path(tempfile.mkdtemp())
    # Copy the three plugin sources to the temp root (so `import constants` works)
    for name in ("__init__.py", "checks.py", "constants.py"):
        shutil.copy(REPO / name, td / name)
    # Copy the drift script itself
    shutil.copy(REPO / "tools" / "check_upstream_drift.py",
                td / "check_upstream_drift.py")
    sys.path.insert(0, str(td))
    mod = importlib.import_module("check_upstream_drift")
    return mod


def case_upstream_drift_filed(mod):
    """Upstream drift files a single upstream-titled issue, not two."""
    calls = []

    def fake_file_issue(repo, title, body, label):
        assert label == "drift"
        calls.append((repo, title, body, label))
        return 1

    def fake_list_open_issues(repo, title):
        return []

    def fake_clone():
        return "/tmp/fake-upstream"

    def fake_git(repo_dir, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return "abc1234567890def", "", 0
        if "--format" in args:
            return "abc1234\x1f2026-09-11 06:37:27 -0700\x1ffix(mcp): rename mcp_servers key", "", 0
        return "", "", 0

    def fake_git_log(repo_dir, ref_range, watched=None):
        return [{"sha": "abc1234", "date": "2026-09-11", "subject": "fix(mcp): rename", "files": ["hermes_cli/config.py"]}]

    def fake_verify_facts(repo_dir, head):
        return ["MCP config key: upstream now `mcp`, hermes-guide asserts `mcp_servers`"]

    def fake_verify_ci_pin():
        return [], None

    with mock.patch.object(mod, "clone_upstream", fake_clone), \
         mock.patch.object(mod, "git", fake_git), \
         mock.patch.object(mod, "git_log", fake_git_log), \
         mock.patch.object(mod, "verify_facts", fake_verify_facts), \
         mock.patch.object(mod, "verify_ci_pin", fake_verify_ci_pin), \
         mock.patch.object(mod, "_file_issue", fake_file_issue), \
         mock.patch.object(mod, "_list_open_issues", fake_list_open_issues), \
         mock.patch.dict("os.environ", {"GITHUB_REPOSITORY": "redsurge/hermes-guide",
                                        "DRIFT_DRY_RUN": "", "DRIFT_NO_CAP": ""}):
        rc = mod.main()

    assert rc == 0, f"main returned {rc}, expected 0"
    titles = [c[1] for c in calls]
    assert mod.ISSUE_TITLE_UPSTREAM in titles, f"upstream title not filed: {titles}"
    assert len(calls) == 1, f"expected 1 issue, got {len(calls)}: {titles}"
    body = calls[0][2]
    assert "abc1234" in body
    assert "fix(mcp): rename" in body
    assert "hermes_cli/config.py" in body
    print("OK: upstream drift files one issue with commit and file context")


def case_exact_title_dedup(mod):
    """_list_open_issues matches exact title only — substring does not dedup."""
    # Fake gh CLI returning two issues, one with a substring-matching title.
    fake_api_response = json.dumps([
        {"number": 1, "title": "Upstream schema drift"},  # substring, not exact
        {"number": 2, "title": mod.ISSUE_TITLE_UPSTREAM},  # exact match
    ])
    with mock.patch.object(subprocess, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            "gh", returncode=0, stdout=fake_api_response, stderr="")
        result = mod._list_open_issues("redsurge/hermes-guide", mod.ISSUE_TITLE_UPSTREAM)
    # Only the exact match should survive.
    assert len(result) == 1, f"expected 1 exact match, got {len(result)}: {result}"
    assert result[0]["title"] == mod.ISSUE_TITLE_UPSTREAM
    print("OK: exact-title dedup only (substring does not suppress)")


def case_transport_failure_fails_run(mod):
    """A broken gh call must raise, not silently skip and report success."""
    with mock.patch.object(subprocess, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            "gh", returncode=1, stdout="", stderr="network down")
        try:
            mod._list_open_issues("redsurge/hermes-guide", mod.ISSUE_TITLE_UPSTREAM)
            assert False, "_list_open_issues should have raised"
        except RuntimeError as exc:
            assert "gh issue list failed" in str(exc)
    print("OK: transport failure raises, does not silently skip")


def case_file_issue_skips_when_open(mod):
    """_file_issue returns 0 (no create) when an exact-title issue is already open."""
    calls = []

    def fake_create(repo, title, body, label):
        calls.append((repo, title, body, label))
        return 1

    with mock.patch.object(
        mod, "_list_open_issues",
        return_value=[{"number": 7, "title": mod.ISSUE_TITLE_UPSTREAM}],
    ), \
         mock.patch.object(mod, "_file_issue", side_effect=mod._file_issue) as patched, \
         mock.patch.object(subprocess, "run") as mock_run:
        rc = patched("redsurge/hermes-guide", mod.ISSUE_TITLE_UPSTREAM, "body", "drift")
    assert rc == 0
    assert calls == []
    # gh issue create must never be called when the issue is already open.
    assert mock_run.call_count == 0
    print("OK: _file_issue skips filing when an exact-title issue is open")


def case_git_log_parsing_robust(mod):
    """git_log preserves watched files and deduplicates merge records."""
    fake_output = (
        "abc1234\x1f2026-09-11 06:37:27 -0700\x1ffix(mcp): rename\n"
        "hermes_constants.py\n"
        "abc1234\x1f2026-09-11 06:37:27 -0700\x1ffix(mcp): rename\n"
        "tools/memory_tool_store.py\n"
        "def5678\x1f2026-09-10\x1ffix(skill): tweak"
    )
    with mock.patch.object(subprocess, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            "git", returncode=0, stdout=fake_output, stderr="")
        records = mod.git_log("/tmp/fake", "HEAD~3..HEAD")
    assert len(records) == 2, f"expected 2 records, got {len(records)}: {records}"
    assert records[0]["sha"] == "abc1234"
    assert records[0]["files"] == [
        "hermes_constants.py", "tools/memory_tool_store.py"
    ]
    assert records[1]["sha"] == "def5678"
    command = mock_run.call_args.args[0]
    assert "--diff-merges=separate" in command
    print("OK: git_log preserves and deduplicates merge file context")


def case_pin_failure_fails_closed(mod):
    """A pin-check transport failure blocks issue filing, even with drift."""
    issue_calls = []

    def fake_git(repo_dir, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return "abc1234567890def", "", 0
        if args[:2] == ("log", "--format=%h %ci %s"):
            return "abc1234 2026-09-11 fix(mcp): rename", "", 0
        return "", "", 0

    def fake_file_issue(repo, title, body, label):
        issue_calls.append((repo, title, body, label))
        return 1

    with mock.patch.object(mod, "clone_upstream", return_value="/tmp/fake-upstream"), \
         mock.patch.object(mod, "git", fake_git), \
         mock.patch.object(mod, "verify_facts", return_value=[]), \
         mock.patch.object(
             mod, "verify_ci_pin",
             return_value=([], "could not list upstream tags")), \
         mock.patch.object(
             mod, "scan_upstream_history",
             return_value=([{"sha": "abc1234", "date": "2026-09-11",
                             "subject": "fix(mcp): rename", "files": []}], [])), \
         mock.patch.object(mod, "_file_issue", fake_file_issue), \
         mock.patch.dict("os.environ", {"GITHUB_REPOSITORY": "redsurge/hermes-guide"}):
        rc = mod.main()

    assert rc == 1
    assert issue_calls == []
    print("OK: pin-check failure blocks issue filing")


def case_cap_keeps_newest_drops_oldest(mod):
    """_cap_chars keeps the newest entries and an exact omitted count."""
    entries = [f"- `{i:07d}` 2026-09-01 subject {i}" for i in range(200)]
    with mock.patch.object(mod, "_uncapped", return_value=False):
        out = mod._cap_chars(entries, 500, "- ... and {omitted} older commits omitted.")
    kept = [ln for ln in out.splitlines() if ln.startswith("- `")]
    assert kept, "nothing kept"
    assert kept[0] == entries[0], "newest entry must be kept first"
    assert kept == entries[:len(kept)], "kept entries must be the newest, in order"
    assert f"and {len(entries) - len(kept)} older commits omitted" in out, out[-160:]
    print("OK: cap keeps newest entries with an exact omitted count")


def case_uncapped_returns_everything(mod):
    """DRIFT_NO_CAP=1 returns the full list (what the omission notes promise)."""
    entries = [f"- `{i:07d}` 2026-09-01 subject {i}" for i in range(200)]
    with mock.patch.object(mod, "_uncapped", return_value=True):
        out = mod._cap_chars(entries, 500, "- ... and {omitted} older commits omitted.")
    assert out == "\n".join(entries)
    assert "omitted" not in out
    print("OK: uncapped mode returns the full list")


def case_fit_body_keeps_footer(mod):
    """The size guard trims sections at line boundaries but never the footer."""
    sections = "\n".join(f"- `{i:07d}` 2026-09-01 a very long subject line to reach the limit" for i in range(4000))
    footer = "Compare: https://example.test/compare/aaaa...bbbb\n\nReview the changes."
    out = mod._fit_body(sections, footer)
    assert len(out) <= mod.MAX_BODY_CHARS, f"body {len(out)} > {mod.MAX_BODY_CHARS}"
    assert out.endswith(footer), "footer must survive the guard"
    assert "truncated to fit GitHub's issue-body limit" in out
    assert "DRIFT_NO_CAP=1" in out
    cut = out[: out.index("\n\n[Body truncated")]
    assert cut.endswith("limit"), f"cut mid-line: {cut[-60:]!r}"
    print("OK: size guard keeps the footer and points at the uncapped run")


def case_uncapped_requires_dry_run(mod):
    """DRIFT_NO_CAP=1 alone must not uncap anything (filing stays bounded)."""
    with mock.patch.dict("os.environ", {}, clear=True):
        assert mod._uncapped() is False, "no flags: capped"
        os.environ["DRIFT_NO_CAP"] = "1"
        assert mod._uncapped() is False, "uncapped without dry-run"
        os.environ["DRIFT_DRY_RUN"] = "1"
        assert mod._uncapped() is True, "both flags should enable uncapped"
    print("OK: uncapped mode requires DRIFT_DRY_RUN=1 (filing path stays bounded)")


def case_ls_remote_retries_transient_failures(mod):
    """A flaky ls-remote is retried; persistent failure still fails closed."""
    class _Proc:
        def __init__(self, returncode, stdout=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    calls = []

    def flaky(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) < 3:
            return _Proc(128)
        return _Proc(0, "abc123\trefs/tags/v2026.9.24\n")

    proc = mod._run_ls_remote(runner=flaky, delays=(0.0, 0.0, 0.0))
    assert proc is not None, "third attempt should succeed"
    assert len(calls) == 3, f"expected 3 attempts, got {len(calls)}"

    calls.clear()

    def always_failing(cmd, **kwargs):
        calls.append(cmd)
        return _Proc(128)

    assert mod._run_ls_remote(runner=always_failing, delays=(0.0, 0.0, 0.0)) is None
    assert len(calls) == 3, f"must stop after the last attempt, got {len(calls)}"

    with mock.patch.object(
        mod, "_run_ls_remote",
        return_value=_Proc(0, "abc\trefs/tags/v2026.9.21^{}\nxyz\trefs/tags/v2026.9.24\n"),
    ):
        assert mod.latest_upstream_tag() == "v2026.9.24", "max tag must win; ^{} peeled ref skipped"
    with mock.patch.object(mod, "_run_ls_remote", return_value=None):
        assert mod.latest_upstream_tag() is None, "persistent failure -> None (fail closed)"
    print("OK: ls-remote retries transient failures, still fails closed")


def case_ls_remote_retries_transport_exceptions(mod):
    """Timeout/OSError transport failures retry the same way exit codes do.

    Greptile P2 on PR #124: the retry also handles TimeoutExpired/OSError,
    so a regression there must fail this suite, not just the weekly run.
    """
    class _Proc:
        def __init__(self, returncode, stdout=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    calls = []

    def timeout_then_success(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) < 2:
            raise subprocess.TimeoutExpired(cmd, 60)
        return _Proc(0, "abc123\trefs/tags/v2026.9.24\n")

    proc = mod._run_ls_remote(runner=timeout_then_success, delays=(0.0, 0.0, 0.0))
    assert proc is not None, "a timeout on the first attempt must be retried"
    assert len(calls) == 2, f"expected 2 attempts, got {len(calls)}"

    calls.clear()

    def os_error_forever(cmd, **kwargs):
        calls.append(cmd)
        raise OSError("network unreachable")

    assert mod._run_ls_remote(runner=os_error_forever, delays=(0.0, 0.0, 0.0)) is None
    assert len(calls) == 3, f"persistent transport exceptions must stop after the last attempt, got {len(calls)}"
    print("OK: ls-remote retries TimeoutExpired/OSError and still fails closed")


def case_pin_reads_the_real_tree(mod):
    """The pin lookup finds the real pin wherever the workflows keep it.

    The CI split (#128) moved the `git clone --branch` line from ci.yml to
    reusable-ci.yml: a lookup that reads one hardcoded filename returns None
    here and fails this case. The workflows dir is patched to an absolute
    path so the check does not depend on the runner's working directory.
    """
    workflows = REPO / ".github" / "workflows"
    with mock.patch.object(mod, "WORKFLOWS_DIR", workflows):
        pinned = mod.read_pinned_tag()
    assert pinned is not None, (
        "no install pin found in the repository's real workflows - the lookup "
        "must scan .github/workflows/, not one hardcoded file"
    )
    assert pinned.startswith("v") and pinned[1].isdigit(), (
        f"unexpected pin shape: {pinned!r}"
    )
    texts = "\n".join(p.read_text(encoding="utf-8") for p in workflows.glob("*.y*ml"))
    assert f"--branch {pinned} " in texts, (
        f"lookup returned {pinned!r}, which no workflow file actually clones"
    )
    print(f"OK: pin lookup reads the real workflow tree (found {pinned})")


def case_pin_absent_fails_closed(mod):
    """No `git clone --branch` line anywhere -> None, and verify_ci_pin errors."""
    td = Path(tempfile.mkdtemp())
    try:
        wf = td / "workflows"
        wf.mkdir()
        (wf / "ci.yml").write_text("on: push\n", encoding="utf-8")
        with mock.patch.object(mod, "WORKFLOWS_DIR", wf):
            assert mod.read_pinned_tag() is None, "absent pin must return None"
            mismatches, error = mod.verify_ci_pin()
        assert mismatches == [], f"absent pin must not produce findings: {mismatches}"
        assert error and "could not read" in error, f"absent pin must surface an error: {error!r}"
    finally:
        shutil.rmtree(td)
    print("OK: absent pin fails closed (no findings, error surfaced)")


def case_pin_conflict_fails_closed(mod):
    """Conflicting pins across workflow files -> None, never a coin flip."""
    td = Path(tempfile.mkdtemp())
    try:
        wf = td / "workflows"
        wf.mkdir()
        (wf / "a.yml").write_text(
            "git clone --depth 1 --branch v2026.1.1 "
            "https://github.com/NousResearch/hermes-agent.git d\n",
            encoding="utf-8")
        (wf / "b.yml").write_text(
            "git clone --depth 1 --branch v2026.2.2 "
            "https://github.com/NousResearch/hermes-agent.git d\n",
            encoding="utf-8")
        with mock.patch.object(mod, "WORKFLOWS_DIR", wf):
            assert mod.read_pinned_tag() is None, "conflicting pins must return None"
    finally:
        shutil.rmtree(td)
    print("OK: conflicting pins fail closed")


def case_pin_ignores_unrelated_clones(mod):
    """An unrelated shallow clone must not pollute the pin lookup.

    Macroscope review on PR #149: with the match unscoped, a second
    `git clone --depth 1 --branch main <other-repo>` would join the tag set
    and flip the lookup to None, failing the weekly run instead of
    monitoring the pin. Scoped, the Hermes clone still wins.
    """
    td = Path(tempfile.mkdtemp())
    try:
        wf = td / "workflows"
        wf.mkdir()
        (wf / "reusable-ci.yml").write_text(
            "git clone --depth 1 --branch v2026.9.24 "
            "https://github.com/NousResearch/hermes-agent.git d\n",
            encoding="utf-8")
        (wf / "other.yml").write_text(
            "git clone --depth 1 --branch main https://example.test/tools.git d\n",
            encoding="utf-8")
        with mock.patch.object(mod, "WORKFLOWS_DIR", wf):
            assert mod.read_pinned_tag() == "v2026.9.24", (
                "an unrelated shallow clone must not hide the Hermes pin")
    finally:
        shutil.rmtree(td)
    print("OK: unrelated shallow clones do not pollute the pin lookup")


def case_pin_ignores_commented_clones(mod):
    """A commented-out clone line must not join the tag set.

    Macroscope review on PR #149: the raw-text scan matched `# git clone ...`
    examples too, so a commented-out pin could flip the lookup to None.
    Only executable lines count.
    """
    td = Path(tempfile.mkdtemp())
    try:
        wf = td / "workflows"
        wf.mkdir()
        (wf / "reusable-ci.yml").write_text(
            "git clone --depth 1 --branch v2026.9.24 "
            "https://github.com/NousResearch/hermes-agent.git d\n",
            encoding="utf-8")
        (wf / "notes.yml").write_text(
            "# historical: git clone --depth 1 --branch v2025.1.1 "
            "https://github.com/NousResearch/hermes-agent.git d\n",
            encoding="utf-8")
        with mock.patch.object(mod, "WORKFLOWS_DIR", wf):
            assert mod.read_pinned_tag() == "v2026.9.24", (
                "a commented-out clone must not hide the Hermes pin")
    finally:
        shutil.rmtree(td)
    print("OK: commented-out clone lines are ignored")


def main() -> int:
    mod = _load_module()
    failures: list[str] = []
    for case in (
        case_upstream_drift_filed,
        case_exact_title_dedup,
        case_transport_failure_fails_run,
        case_file_issue_skips_when_open,
        case_git_log_parsing_robust,
        case_pin_failure_fails_closed,
        case_cap_keeps_newest_drops_oldest,
        case_uncapped_returns_everything,
        case_fit_body_keeps_footer,
        case_uncapped_requires_dry_run,
        case_ls_remote_retries_transient_failures,
        case_ls_remote_retries_transport_exceptions,
        case_pin_reads_the_real_tree,
        case_pin_absent_fails_closed,
        case_pin_conflict_fails_closed,
        case_pin_ignores_unrelated_clones,
        case_pin_ignores_commented_clones,
    ):
        try:
            case(mod)
        except Exception as exc:
            failures.append(f"{case.__name__}: {exc}")
            print(f"FAIL: {case.__name__}: {exc}")
    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nOK: 17 upstream-drift hygiene case(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
