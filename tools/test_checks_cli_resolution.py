"""Behavioral coverage for `hermes` executable resolution in checks.py.

The gates in `tools/` read text, so a resolution bug can ship with every gate
green. These tests build real stub executables and assert which one actually
answered — the failure mode where `PATH` names an install whose console script
cannot exec itself.

Run: python tools/test_checks_cli_resolution.py
"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from unittest import mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

failures = []


_TEMP_DIRS: list[Path] = []


def _load_checks():
    """Import the plugin package under a shim (hyphenated dir can't import).

    The copy has to outlive this call, so the directory is tracked and removed by
    cleanup() at the end of main() rather than by a context manager here.
    """
    td = Path(tempfile.mkdtemp())
    _TEMP_DIRS.append(td)
    pkg = td / "hermes_guide"
    pkg.mkdir()
    for name in ("__init__.py", "checks.py", "constants.py"):
        shutil.copy(REPO / name, pkg / name)
    sys.path.insert(0, str(td))
    import hermes_guide.checks as checks_mod  # noqa: E402

    return checks_mod


def cleanup() -> None:
    """Drop the shim directory and its sys.path entry.

    Without this, every run leaves a copied package behind in TMPDIR and leaves
    the shim importable, which changes resolution for anything imported later in
    the same process.
    """
    for td in _TEMP_DIRS:
        try:
            sys.path.remove(str(td))
        except ValueError:
            pass
        shutil.rmtree(td, ignore_errors=True)
    _TEMP_DIRS.clear()


BAD = "/bad/hermes"
GOOD = "/good/hermes"

checks = _load_checks()
HERMES_EXE = checks.HERMES_EXE  # noqa: F821 — resolved from the plugin under test


def check(name, condition, detail=""):
    if condition:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}{f'  [{detail}]' if detail else ''}")
        failures.append(name)


def _stub(directory, name, body):
    """Write an executable stub script and return its path."""
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _bad_shim(directory, name):
    """A console script whose interpreter line cannot resolve, like a GNU
    `realpath -- "$0"` shim on a host that has no GNU realpath.

    Host-dependent by nature: where GNU realpath *is* present the shim resolves
    and runs. Use `_unusable` for behaviour; keep this for the premise check.
    """
    return _stub(
        directory,
        name,
        "#!/bin/sh\n"
        "'''exec' \"$(dirname -- \"$(realpath -- \"$0\")\")\"/'python3' \"$0\" \"$@\"\n"
        "' '''\n",
    )


def _unusable(directory, name, code=126):
    """A candidate that cannot answer, identically on every host.

    Behavioural tests need the resolver to reject a candidate, not the host to
    lack `realpath`. Both codes a POSIX shell uses for "I could not launch this"
    are exercised.
    """
    return _stub(directory, name,
                 f"#!/bin/sh\necho 'cannot exec' >&2\nexit {code}\n")


def _working(directory, name, marker):
    return _stub(directory, name, f"#!/bin/sh\necho {marker}\nexit 0\n")


def _fake_interpreter(directory):
    """A stand-in for sys.executable living in `directory`."""
    return _working(directory, "python3", "PY-OK")


def test_sibling_outranks_path():
    """The install running the check answers, not one earlier on PATH."""
    with tempfile.TemporaryDirectory() as tmp:
        sibling, other = os.path.join(tmp, "sibling"), os.path.join(tmp, "other")
        os.makedirs(sibling), os.makedirs(other)
        exe = _fake_interpreter(sibling)
        _working(sibling, HERMES_EXE, "SIBLING")
        _working(other, HERMES_EXE, "FROMPATH")

        original_exe, original_path = sys.executable, os.environ["PATH"]
        try:
            sys.executable = exe
            os.environ["PATH"] = other + os.pathsep + original_path
            rc, out, _ = checks._run_hermes(["config", "path"])
        finally:
            sys.executable, os.environ["PATH"] = original_exe, original_path

        check("sibling executable outranks PATH", rc == 0 and "SIBLING" in out,
              f"rc={rc} out={out.strip()!r}")


def test_falls_through_broken_shim():
    """An unusable entry point falls through to the next candidate.

    Both codes a shell uses for "could not launch this" are covered, so the
    resolver is exercised rather than whatever the host lacks.
    """
    for code in (126, 127):
        with tempfile.TemporaryDirectory() as tmp:
            sibling, other = os.path.join(tmp, "sibling"), os.path.join(tmp, "other")
            os.makedirs(sibling), os.makedirs(other)
            exe = _fake_interpreter(sibling)
            _unusable(sibling, HERMES_EXE, code)
            _working(other, HERMES_EXE, "FALLBACK")

            original_exe, original_path = sys.executable, os.environ["PATH"]
            try:
                sys.executable = exe
                os.environ["PATH"] = other + os.pathsep + original_path
                rc, out, _ = checks._run_hermes(["config", "path"])
            finally:
                sys.executable, os.environ["PATH"] = original_exe, original_path

            check(f"unusable candidate (rc={code}) falls through to next",
                  rc == 0 and "FALLBACK" in out, f"rc={rc} out={out.strip()!r}")


def test_non_executable_candidate_falls_through():
    """A candidate that exists but cannot be launched is unusable, not an answer.

    This is the EACCES branch of the errno whitelist: without it a permissions
    problem reports unknown instead of consulting the next install.
    """
    with tempfile.TemporaryDirectory() as tmp:
        sibling, other = os.path.join(tmp, "sibling"), os.path.join(tmp, "other")
        os.makedirs(sibling), os.makedirs(other)
        exe = _fake_interpreter(sibling)
        blocked = _working(sibling, HERMES_EXE, "SHOULD-NOT-RUN")
        os.chmod(blocked, 0o644)  # readable, not executable
        _working(other, HERMES_EXE, "PERM-FALLBACK")

        original_exe, original_path = sys.executable, os.environ["PATH"]
        try:
            sys.executable = exe
            os.environ["PATH"] = other + os.pathsep + original_path
            rc, out, _ = checks._run_hermes(["config", "path"])
        finally:
            sys.executable, os.environ["PATH"] = original_exe, original_path

        check("non-executable candidate falls through",
              rc == 0 and "PERM-FALLBACK" in out and "SHOULD-NOT-RUN" not in out,
              f"rc={rc} out={out.strip()!r}")


def test_path_shape_errnos_fall_through():
    """ENOTDIR/EISDIR/EINVAL must fall through; host pressure must not.

    A candidate can be unusable because of its SHAPE rather than its
    permissions: a path component that is a regular file (ENOTDIR), the
    candidate itself being a directory (EISDIR), an invalid argument (EINVAL).
    A shell reports 126 for "cannot execute" in all of these, so the resolver
    must consult the next candidate.

    These errnos cannot be produced reliably from a test - a symlink to a
    regular file still yields EACCES, not ENOTDIR - so the OS boundary is
    stubbed and the real `_run` / `_run_hermes` decide the outcome. What is
    under test is the resolver's partition, against real errno values.
    """
    import errno as _errno

    def _run_with_oserror(code, label):
        """Resolve two candidates where the first raises OSError(code)."""
        def _raise(cmd, *_a, **_k):
            raise OSError(code, label)

        real_run = checks._run

        def _fake_run(cmd, timeout=20):
            if cmd[0] == GOOD:
                return 0, "PATH-FALLBACK\n", ""
            return real_run(cmd, timeout=timeout)

        with mock.patch.object(checks.subprocess, "run", _raise), \
                mock.patch.object(checks, "_hermes_candidates",
                                  lambda: [BAD, GOOD]), \
                mock.patch.object(checks, "_run", _fake_run):
            return checks._run_hermes(["config", "path"])

    for label, code in (("EISDIR", _errno.EISDIR),
                        ("ENOTDIR", _errno.ENOTDIR),
                        ("EINVAL", _errno.EINVAL),
                        ("EFAULT", _errno.EFAULT),
                        ("ENODEV", _errno.ENODEV),
                        ("EACCES", _errno.EACCES),
                        ("EPERM", _errno.EPERM)):
        rc, out, _ = _run_with_oserror(code, label)
        check(f"{label} candidate falls through to next",
              rc == 0 and "PATH-FALLBACK" in out, f"rc={rc} out={out.strip()!r}")

    # Host pressure is not a verdict on the candidate: falling back there would
    # report another install's config and hooks state as ours.
    for label, code in (("ENOMEM", _errno.ENOMEM),
                        ("EMFILE", _errno.EMFILE),
                        ("ENFILE", _errno.ENFILE),
                        ("EAGAIN", _errno.EAGAIN),
                        ("ENOBUFS", _errno.ENOBUFS),
                        ("EINTR", _errno.EINTR)):
        rc, out, _ = _run_with_oserror(code, label)
        check(f"{label} does not fall through (host state)",
              rc == -1 and "PATH-FALLBACK" not in out, f"rc={rc} out={out.strip()!r}")


def test_broken_shim_reproduces_126():
    """The real failure mode is exit 126 — assert it, so the test above is honest."""
    with tempfile.TemporaryDirectory() as tmp:
        broken = _bad_shim(tmp, HERMES_EXE)
        proc = subprocess.run([broken], capture_output=True, text=True, timeout=30)
        if sys.platform == "darwin" and os.environ.get("PATH", "").find("realpath") < 0:
            check("broken shim exits 126", proc.returncode == 126, f"rc={proc.returncode}")
        else:
            print(f"SKIP  broken shim exits 126 (host provides realpath; rc={proc.returncode})")


def test_real_failure_is_not_retried():
    """A non-zero return from a working executable is Hermes' answer, not a
    reason to try the next install until something looks green."""
    with tempfile.TemporaryDirectory() as tmp:
        sibling, other = os.path.join(tmp, "sibling"), os.path.join(tmp, "other")
        os.makedirs(sibling), os.makedirs(other)
        exe = _fake_interpreter(sibling)
        _stub(sibling, HERMES_EXE, "#!/bin/sh\necho 'REAL-FAILURE'\nexit 3\n")
        _working(other, HERMES_EXE, "OTHER-INSTALL")

        original_exe, original_path = sys.executable, os.environ["PATH"]
        try:
            sys.executable = exe
            os.environ["PATH"] = other + os.pathsep + original_path
            rc, out, _ = checks._run_hermes(["config", "path"])
        finally:
            sys.executable, os.environ["PATH"] = original_exe, original_path

        check("real failure is reported, not retried",
              rc == 3 and "REAL-FAILURE" in out and "OTHER-INSTALL" not in out,
              f"rc={rc} out={out.strip()!r}")


def test_path_only_still_resolves():
    """A host with no sibling entry point still works via PATH."""
    with tempfile.TemporaryDirectory() as tmp:
        lonely = os.path.join(tmp, "lonely")
        elsewhere = os.path.join(tmp, "elsewhere")
        os.makedirs(lonely)
        os.makedirs(elsewhere)
        exe = _fake_interpreter(elsewhere)
        _working(lonely, HERMES_EXE, "PATHONLY")

        original_exe, original_path = sys.executable, os.environ["PATH"]
        try:
            sys.executable = exe
            os.environ["PATH"] = lonely + os.pathsep + original_path
            rc, out, _ = checks._run_hermes(["config", "path"])
        finally:
            sys.executable, os.environ["PATH"] = original_exe, original_path

        check("PATH-only resolution still works", rc == 0 and "PATHONLY" in out,
              f"rc={rc} out={out.strip()!r}")


def test_no_candidate_reports_clearly():
    """No executable anywhere is a stated error, not a silent empty answer."""
    with tempfile.TemporaryDirectory() as tmp:
        elsewhere = os.path.join(tmp, "elsewhere")
        os.makedirs(elsewhere)
        exe = _fake_interpreter(elsewhere)

        # The resolver walks `PATH` itself, so an empty `PATH` is how "no
        # candidate anywhere" is expressed now that `shutil.which` is gone.
        original_exe, original_path = sys.executable, os.environ["PATH"]
        try:
            sys.executable = exe
            os.environ["PATH"] = elsewhere
            rc, out, err = checks._run_hermes(["config", "path"])
        finally:
            sys.executable, os.environ["PATH"] = original_exe, original_path

        check("no candidate is a clear error",
              rc == -127 and HERMES_EXE in err, f"rc={rc} err={err!r}")


def test_every_path_entry_is_a_candidate():
    """A broken first `hermes` on PATH must not hide a working one behind it.

    The production failure this pins: macOS before 13 has no `realpath(1)`, so
    the install venv's pip console script exited 126, `shutil.which` returned
    only that one path, and every check reported "cannot resolve
    $HERMES_HOME" while a healthy `hermes` sat further down PATH. Resolution
    must reach it.
    """
    with tempfile.TemporaryDirectory() as tmp:
        broken_dir = os.path.join(tmp, "broken")
        working_dir = os.path.join(tmp, "working")
        os.makedirs(broken_dir), os.makedirs(working_dir)
        exe = _fake_interpreter(working_dir)
        _unusable(broken_dir, HERMES_EXE, 126)
        _working(working_dir, HERMES_EXE, "DEEP-ON-PATH")

        original_exe, original_path = sys.executable, os.environ["PATH"]
        try:
            sys.executable = exe
            os.environ["PATH"] = broken_dir + os.pathsep + working_dir + os.pathsep + original_path
            rc, out, _ = checks._run_hermes(["config", "path"])
        finally:
            sys.executable, os.environ["PATH"] = original_exe, original_path

        check("working hermes behind a broken PATH entry is reached",
              rc == 0 and "DEEP-ON-PATH" in out, f"rc={rc} out={out.strip()!r}")


def test_path_walk_is_deduplicated():
    """The same directory twice in PATH costs one attempt, not two."""
    with tempfile.TemporaryDirectory() as tmp:
        lonely = os.path.join(tmp, "lonely")
        os.makedirs(lonely)
        _working(lonely, HERMES_EXE, "ONCE")

        original_path = os.environ["PATH"]
        try:
            os.environ["PATH"] = os.pathsep.join([lonely, lonely, original_path])
            found = checks._path_hermes_executables()
        finally:
            os.environ["PATH"] = original_path

        # Candidates come back resolved (see _path_hermes_executables), so
        # compare resolved values on both sides.
        target = os.path.realpath(os.path.join(lonely, HERMES_EXE))
        count = sum(1 for p in found if os.path.realpath(p) == target)
        check("repeated PATH entry appears once", count == 1, f"found={found!r}")


def test_unset_path_searches_os_defpath():
    """PATH unset must search os.defpath, as shutil.which does.

    `os.environ.get("PATH", "")` collapses "unset" into "explicitly empty", so
    the walk searched only the current directory and reported a hermes sitting
    in a default directory as missing. An explicitly empty PATH is a DIFFERENT
    state -- one empty component, meaning cwd -- and must not gain the defaults.

    os.defpath points at /bin:/usr/bin, which are not writable and hold no
    hermes, so it is redirected at a temp dir; otherwise the assertion holds
    vacuously and the test passes even with the bug present.
    """
    with tempfile.TemporaryDirectory() as tmp:
        defpath_dir = os.path.join(tmp, "defpath-bin")
        os.makedirs(defpath_dir)
        _working(defpath_dir, HERMES_EXE, "DEFPATH")
        in_defpath = os.path.join(defpath_dir, HERMES_EXE)

        cwd_dir = os.path.join(tmp, "cwd")
        os.makedirs(cwd_dir)

        saved_defpath = os.defpath
        saved_path = os.environ.get("PATH")
        was_set = "PATH" in os.environ
        saved_cwd = os.getcwd()
        try:
            os.defpath = defpath_dir
            os.chdir(cwd_dir)

            os.environ.pop("PATH", None)
            unset_found = checks._path_hermes_executables()
            check("unset PATH consults os.defpath",
                  os.path.realpath(in_defpath) in {os.path.realpath(p) for p in unset_found},
                  f"found={unset_found!r}")

            # An explicitly empty PATH is one empty component (cwd), and must
            # NOT acquire the default directories.
            os.environ["PATH"] = ""
            empty_found = checks._path_hermes_executables()
            check("explicitly empty PATH stays off os.defpath",
                  os.path.realpath(in_defpath) not in
                  {os.path.realpath(p) for p in empty_found},
                  f"found={empty_found!r}")
        finally:
            os.chdir(saved_cwd)
            os.defpath = saved_defpath
            if was_set:
                os.environ["PATH"] = saved_path
            else:
                os.environ.pop("PATH", None)


def test_symlinked_duplicates_collapse_to_one_attempt():
    """Two PATH entries symlinking to ONE hermes must cost one attempt.

    `abspath` normalises `.`/`..` but leaves symlinks intact, so a realpath key
    is required: `~/.local/bin/hermes` and a versioned bin dir can both be on
    PATH and both point at the same binary. Launching it twice also means
    waiting out its timeout twice.
    """
    with tempfile.TemporaryDirectory() as tmp:
        real_dir = os.path.join(tmp, "real")
        os.makedirs(real_dir)
        _working(real_dir, HERMES_EXE, "REAL")
        real = os.path.join(real_dir, HERMES_EXE)

        first_dir = os.path.join(tmp, "a")
        second_dir = os.path.join(tmp, "b")
        os.makedirs(first_dir)
        os.makedirs(second_dir)
        for d in (first_dir, second_dir):
            os.symlink(real, os.path.join(d, HERMES_EXE))

        original_path = os.environ["PATH"]
        try:
            os.environ["PATH"] = os.pathsep.join([first_dir, second_dir])
            found = checks._path_hermes_executables()
        finally:
            os.environ["PATH"] = original_path

        check("symlinked duplicate collapses to one candidate",
              len(found) == 1, f"found={found!r}")


def test_empty_path_component_searches_current_directory():
    """`PATH=:/usr/bin` must find `./hermes` — an empty component means cwd.

    POSIX (and the equivalent Windows behaviour) reads an empty PATH component
    as the current directory, and shutil.which maps it to os.curdir. Treating
    it as nothing to skip drops that rung, so an install invoked as `./hermes`
    becomes undiscoverable.
    """
    with tempfile.TemporaryDirectory() as tmp:
        cwd_dir = os.path.join(tmp, "cwd")
        os.makedirs(cwd_dir)
        _working(cwd_dir, HERMES_EXE, "CWD-INSTALL")

        original_cwd = os.getcwd()
        original_path = os.environ["PATH"]
        try:
            os.chdir(cwd_dir)
            os.environ["PATH"] = ":" + original_path
            found = checks._path_hermes_executables()
        finally:
            os.chdir(original_cwd)
            os.environ["PATH"] = original_path

        # Compare resolved paths: on macOS the temp dir arrives under /var but
        # the walk returns /private/var (getcwd resolves the symlink), so a
        # literal join would never match.
        target = os.path.realpath(os.path.join(cwd_dir, HERMES_EXE))
        check("empty PATH component searches current directory",
              any(os.path.realpath(p) == target for p in found),
              f"found={found[:4]!r}")


def test_non_file_path_entry_is_ignored():
    """A directory named `hermes` on PATH is not a candidate.

    PATH entries can hold anything; only a regular file can be exec'd, so a
    directory or a dangling name must not become an attempt.
    """
    with tempfile.TemporaryDirectory() as tmp:
        decoy_dir = os.path.join(tmp, "decoy")
        os.makedirs(os.path.join(decoy_dir, HERMES_EXE))  # a DIRECTORY named hermes

        original_path = os.environ["PATH"]
        try:
            os.environ["PATH"] = decoy_dir + os.pathsep + original_path
            found = checks._path_hermes_executables()
        finally:
            os.environ["PATH"] = original_path

        check("directory named hermes is not a candidate",
              not any(os.path.isdir(p) for p in found), f"found={found!r}")


def test_timeout_is_deadline_not_per_attempt():
    """The sum of per-attempt budgets never exceeds the caller's timeout."""
    timeouts = []
    clock = [1000.0]

    def _recording_run(cmd, timeout=20):
        timeouts.append(timeout)
        clock[0] += timeout  # advance by the attempt duration
        return 126, "", "cannot exec"

    with mock.patch.object(checks, "_hermes_candidates",
                          lambda: ["/a/hermes", "/b/hermes", "/c/hermes"]), \
         mock.patch.object(checks, "_run", _recording_run), \
         mock.patch.object(checks.time, "monotonic", lambda: clock[0]):
        checks._run_hermes(["config", "path"], timeout=15)

    total = sum(timeouts)
    check("timeout is a deadline (sum of attempts <= timeout)",
          total <= 15.0 and len(timeouts) == 3,
          f"attempts={timeouts} total={total:.1f}s")


def test_timeout_does_not_fall_through():
    """A candidate that hangs (TimeoutExpired) is not retried elsewhere.

    _run converts TimeoutExpired to -1 (via its generic except Exception
    branch). -1 is outside _NOT_EXECUTABLE, so _run_hermes returns immediately
    without trying the second candidate.
    """
    attempts = []

    def _hanging_run(cmd, timeout=20):
        attempts.append(cmd[0])
        return -1, "", "Command timed out"

    with mock.patch.object(checks, "_hermes_candidates",
                          lambda: ["/hang/hermes", "/good/hermes"]), \
         mock.patch.object(checks, "_run", _hanging_run):
        rc, out, err = checks._run_hermes(["config", "path"], timeout=15)

    check("timeout does not fall through to second candidate",
          len(attempts) == 1 and attempts[0] == "/hang/hermes",
          f"attempts={attempts}")
    check("timeout returns -1 (not a real answer)",
          rc == -1, f"rc={rc}")


def main():
    test_sibling_outranks_path()
    test_falls_through_broken_shim()
    test_non_executable_candidate_falls_through()
    test_path_shape_errnos_fall_through()
    test_broken_shim_reproduces_126()
    test_real_failure_is_not_retried()
    test_path_only_still_resolves()
    test_no_candidate_reports_clearly()
    test_every_path_entry_is_a_candidate()
    test_path_walk_is_deduplicated()
    test_non_file_path_entry_is_ignored()
    test_unset_path_searches_os_defpath()
    test_symlinked_duplicates_collapse_to_one_attempt()
    test_empty_path_component_searches_current_directory()
    test_timeout_is_deadline_not_per_attempt()
    test_timeout_does_not_fall_through()

    cleanup()

    print()
    if failures:
        print(f"FAILED {len(failures)}: {', '.join(failures)}")
        return 1
    print("OK: hermes executable resolution behaves as specified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
