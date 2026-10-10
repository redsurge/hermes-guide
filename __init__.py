"""hermes-guide plugin — executable, read-only Hermes configuration diagnostics.

Complements Hermes's built-in diagnostics (hermes doctor / hermes verify) —
it covers what they don't; it does not replace them.

Exposes:
  - `/hermes-doctor`  slash command  (CLI + gateway sessions)
  - `hermes guide <scope>`  CLI subcommand  (terminal; exit 1 on broken or unknown)

Checks: config, mcp, skills, commands, hooks, plugins, memories — seven
read-only checks implemented in `checks.py`.

Opt-in `proactive: true` runs drift checks on session start/end and logs
findings (observer-only; nothing is injected or modified).
"""

__version__ = "0.6.1"

import logging
import sys

from . import checks

logger = logging.getLogger(__name__)


def _format_result(results):
    """Render check envelopes as a compact, human-readable report."""
    lines = []
    exit_ok = True
    for label, r in results.items():
        status = r.get("status", "unknown")
        if status == "healthy":
            mark = "+"
        elif status == "broken":
            mark = "x"
            exit_ok = False
        elif status == "informational":
            mark = "~"
        else:
            mark = "?"
            exit_ok = False
        lines.append(f"{mark} {label}: {r.get('reason', '')}")
        detail = r.get("detail")
        if detail:
            if isinstance(detail, list):
                for d in detail:
                    lines.append(f"    - {d}")
            elif status != "healthy":
                lines.append(f"    - {detail}")
    return exit_ok, "\n".join(lines) if lines else "(no checks)"


def _handle_doctor(raw_args):
    """`/hermes-doctor` handler — optional scope, e.g. `/hermes-doctor mcp`."""
    scope = raw_args.strip() or None
    try:
        _, text = _format_result(checks.run_all(scope=scope))
    except ValueError as exc:
        # Slash commands have no exit-code contract; surface the error as text.
        return f"error: {exc}"
    return text


def _run_cli(args):
    """`hermes guide <scope>` handler."""
    scope = getattr(args, "scope", None)
    try:
        exit_ok, text = _format_result(checks.run_all(scope=scope))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    print(text)
    sys.exit(0 if exit_ok else 1)


def _setup_cli(subparser):
    subparser.add_argument(
        "scope",
        nargs="?",
        help="optional filter: " + "|".join(checks.labels()),
    )


_version_check_ran = False


def _version_check():
    """Check if a newer version is available; log a warning if so.

    Read-only: uses git ls-remote to query the remote without writing
    local refs. Fails silently when the plugin is not a git clone
    (e.g. copied) or when git is unavailable.
    Rate-limited: runs at most once per process.
    """
    global _version_check_ran
    if _version_check_ran:
        return
    _version_check_ran = True
    try:
        import re
        import subprocess
        from pathlib import Path

        plugin_dir = Path(__file__).resolve().parent
        # Verify this is the root of the plugin's own clone
        top_proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],  # nosec B607
            capture_output=True, text=True, timeout=5, cwd=plugin_dir,
        )
        if top_proc.returncode != 0:
            return
        toplevel = Path(top_proc.stdout.strip())
        if toplevel != plugin_dir:
            return
        # Read remote tags without writing local refs
        proc = subprocess.run(
            ["git", "ls-remote", "--tags", "--sort=v:refname", "origin"],  # nosec B607
            capture_output=True, text=True, timeout=10, cwd=plugin_dir,
        )
        if proc.returncode != 0:
            return
        # Parse tags: only full X.Y.Z, skip prerelease/malformed
        tag_re = re.compile(r"refs/tags/v(\d+\.\d+\.\d+)$")
        versions = []
        for line in proc.stdout.splitlines():
            m = tag_re.search(line)
            if m:
                versions.append(m.group(1))
        if not versions:
            return
        latest = versions[-1]  # sorted by v:refname, last is newest
        # Compare versions
        def parse_ver(v: str) -> tuple[int, int, int]:
            parts = v.split(".")
            return (int(parts[0]), int(parts[1]), int(parts[2]))

        if parse_ver(latest) > parse_ver(__version__):
            logger.warning(
                "hermes-guide: new version available (%s → %s). "
                "Run: hermes plugins update hermes-guide",
                __version__, latest,
            )
    except Exception:
        pass  # nosec B110 - version check is best-effort; never fail a session


def _proactive_check(**_kwargs):
    """Run drift checks at a session boundary; log findings (observer-only)."""
    _version_check()
    for label, r in checks.run_all().items():
        status = r.get("status")
        if status == "broken":
            logger.warning("hermes-guide [%s] broken: %s", label, r.get("reason"))
            detail = r.get("detail")
            if isinstance(detail, list):
                for d in detail:
                    logger.warning("    - %s", d)
        elif status == "informational":
            logger.info("hermes-guide [%s] note: %s", label, r.get("reason"))


def register(ctx):
    ctx.register_command(
        "hermes-doctor",
        handler=_handle_doctor,
        description="Run read-only Hermes configuration health checks",
    )
    ctx.register_cli_command(
        name="guide",
        help="Run read-only Hermes configuration diagnostics",
        setup_fn=_setup_cli,
        handler_fn=_run_cli,
    )

    if ctx.get_config("proactive", False):
        ctx.register_hook("on_session_start", _proactive_check)
        ctx.register_hook("on_session_end", _proactive_check)
