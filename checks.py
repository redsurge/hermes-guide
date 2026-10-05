"""Deterministic, read-only health checks.

Every check returns an envelope:

    {"status": "healthy" | "informational" | "broken" | "unknown",
     "reason": str, "detail": ...}

- `healthy`       — nothing to act on.
- `informational` — intentional/expected state worth a glance (e.g. a plugin
  discovered but not opted in). Not a failure.
- `broken`        — something that will cause real breakage.
- `unknown`       — could not determine (path/env unavailable).

Checks are read-only by design: they resolve paths, read files, parse them, and
shell out to `hermes ... doctor`-style read-only commands. They never mutate
config, enable/disable anything, or auto-fix.
"""

import importlib
import json
import os
import re
import subprocess
import sys

import yaml

from . import constants

HERMES_EXE = "hermes.exe" if sys.platform == "win32" else "hermes"

# `_run` reports a missing binary as -127, not 127, and a candidate that exists
# but cannot be launched as -126. These mean "this candidate is unusable", not
# "Hermes said no", so they alone justify trying the next one. -1 stays out: it is
# the generic unexpected failure, where we cannot tell a launch problem from a
# real one, so it is reported rather than silently retried elsewhere.
_NOT_EXECUTABLE = (-127, -126, 126, 127)

# Wall-clock budget for the two `hermes` subcommands the checks shell out to.
#
# These are per-CANDIDATE, not per-call: `_run_hermes` may try more than one
# entry point before one answers. The floor has to clear a cold `hermes`
# start on a loaded host. Measured on a macOS 12.7 install where `hermes
# config path` took 12-25 s across runs, so a 15 s budget made every check
# report "cannot resolve $HERMES_HOME" through no fault of the install - the
# answer arrived a few seconds after the deadline. `config path` pays full
# interpreter start plus config load; `hooks doctor` runs the same boot path
# and enumerates hooks, so it gets the larger budget rather than the 30 s that
# left it close to the edge.
_CONFIG_PATH_TIMEOUT = 60
_HOOKS_DOCTOR_TIMEOUT = 90

# Errno values that mean "this path cannot be launched here", mirroring
# _NOT_EXECUTABLE on the exception path. Anything outside this set is host or
# process state (out of memory, fd exhaustion, interrupted, timed out), not a
# verdict on the candidate, so it must NOT trigger a fallback to another install.
#
# ENOEXEC   wrong binary format, e.g. a console script whose shebang cannot resolve
# ELOOP     symlink cycle
# ENAMETOOLONG / ETXTBSY / E2BIG   path or argument too long, text file busy
# EACCES / EPERM   present but not executable
# EISDIR    the candidate is a directory
# ENOTDIR   a component of the candidate path is a regular file (stale layout)
# EFAULT    bad address; EINVAL   invalid argument, e.g. exec of a directory
# ENODEV    the backing device disappeared
import errno as _errno

_CANDIDATE_UNUSABLE_ERRNOS = frozenset({
    _errno.ENOEXEC,
    _errno.ELOOP,
    _errno.ENAMETOOLONG,
    _errno.ETXTBSY,
    _errno.E2BIG,
    _errno.EACCES,
    _errno.EPERM,
    _errno.EISDIR,
    _errno.ENOTDIR,
    _errno.EFAULT,
    _errno.EINVAL,
    _errno.ENODEV,
})


def _run(cmd, timeout=20):
    """Run a subprocess; return (returncode, stdout, stderr) as separate strings."""
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
        )
        return out.returncode, out.stdout or "", out.stderr or ""
    except FileNotFoundError:
        return -127, "", f"{cmd[0]}: command not found on PATH"
    except PermissionError as exc:
        # The file exists but cannot be executed (EACCES/EPERM). That makes this
        # candidate unusable, not the install broken, so it must be reported as
        # such or the next candidate is never tried.
        return -126, "", f"{cmd[0]}: permission denied ({exc.errno})"
    except OSError as exc:
        # Only errnos that mean THIS FILE cannot be launched qualify. Host-level
        # pressure (ENOMEM, EMFILE, ENFILE, EAGAIN, ENOBUFS, EINTR) says nothing
        # about the candidate: treating those as "unusable" would fall through to
        # another install and report ITS config and hooks state as ours, which is
        # exactly the misreport this resolver exists to prevent.
        if exc.errno in _CANDIDATE_UNUSABLE_ERRNOS:
            return -126, "", f"{cmd[0]}: cannot execute ({exc.errno}): {exc.strerror}"
        return -1, "", repr(exc)
    except Exception as exc:
        return -1, "", repr(exc)


def _path_hermes_executables():
    """Every `hermes` on `PATH`, in search order, deduplicated.

    `shutil.which` returns only the FIRST match, so a resolver that stops there
    cannot fall through when that one entry point is present but unusable - a
    pip console script whose trampoline needs a utility this host lacks (macOS
    before 13 has no `realpath(1)`) exits 126 and the check answers for no
    install even though a working `hermes` sits further down `PATH`. Walking
    the whole `PATH` is what makes the fall-through contract meaningful.
    """
    found = []
    seen = set()
    # An UNSET PATH and an explicitly EMPTY one are different states. Unset
    # means "use the system default", so search os.defpath -- which is what
    # shutil.which does. Empty means one empty component, i.e. the current
    # directory, and must NOT gain the default directories. Reading the
    # variable with a "" default conflates them and searches only `.`.
    raw_path = os.environ.get("PATH")
    search = os.defpath if raw_path is None else raw_path
    for directory in search.split(os.pathsep):
        # An EMPTY PATH component means the current directory in POSIX (and the
        # equivalent Windows behaviour), so `PATH=:/usr/bin` searches `./`. Map it
        # to os.curdir, as shutil.which does; dropping empty components instead
        # makes a PATH-only install in the working directory undiscoverable.
        candidate = os.path.join(directory or os.curdir, HERMES_EXE)
        if not os.path.isfile(candidate):
            continue
        # Dedupe on the RESOLVED target, not the abspath: abspath only
        # normalises `.`/`..` and leaves symlinks intact, so two PATH entries
        # that symlink to one hermes both survive and the same binary is
        # launched -- and waited on -- twice. realpath() collapses them.
        # Store the resolved path, not PATH's spelling. A relative candidate
        # (the empty-component `./hermes` case) would otherwise be resolved
        # against whatever cwd the CALLER has by launch time, not the cwd it
        # was discovered from -- so it is stored absolute, and dedup keys off
        # the same value.
        resolved = os.path.realpath(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        found.append(resolved)
    return found


def _hermes_candidates():
    """Candidate `hermes` executables, most authoritative first.

    The install executing this check is the one whose answers are true, so its
    own entry point (beside `sys.executable`) outranks whatever `PATH` happens
    to resolve. A second install earlier on `PATH` must not answer for us.

    After that sibling, EVERY `hermes` on `PATH` is a candidate in search order.
    One unusable entry point must not exhaust the list: the resolver's own
    contract is "the most authoritative executable that works", and it can only
    keep that promise if a working install is reachable after a broken one.
    """
    bindir = os.path.dirname(os.path.abspath(sys.executable))
    ordered = [os.path.join(bindir, HERMES_EXE) if bindir else None]
    ordered.extend(_path_hermes_executables())
    return [path for path in dict.fromkeys(ordered) if path and os.path.exists(path)]


def _run_hermes(args, timeout=20):
    """Run `hermes <args>` against the most authoritative executable that works.

    Falls through candidates only on `_NOT_EXECUTABLE` (missing, or present but
    not launchable); any other non-zero return is Hermes' own answer and is
    reported as-is, so a real failure is never retried against a different
    install until it looks green.
    """
    candidates = _hermes_candidates()
    if not candidates:
        return -127, "", f"{HERMES_EXE}: not found beside this interpreter or on PATH"
    rc, stdout, stderr = -127, "", ""
    for exe in candidates:
        rc, stdout, stderr = _run([exe, *args], timeout=timeout)
        if rc not in _NOT_EXECUTABLE:
            return rc, stdout, stderr
    return rc, stdout, stderr


# Per-run memoization (cleared at the start of every run_all() so each
# invocation re-resolves fresh, but within one run the expensive resolutions —
# the `hermes config path` subprocess, the config.yaml read, and the skills
# walk — happen exactly once instead of once per check).
_cache: dict = {}


def _hermes_home_from_library():
    """Derive $HERMES_HOME from ``hermes_constants`` — no subprocess.

    The plugin runs inside Hermes, so ``hermes_constants`` is importable and
    ``get_hermes_home()`` returns the same path ``hermes config path`` would.
    This eliminates the ``config path`` subprocess (~8-25 s) in the common case.
    Returns None when the import fails (e.g. outside a live Hermes process).
    """
    try:
        from hermes_constants import get_hermes_home

        home = get_hermes_home()
        if home and os.path.isdir(home):
            return home
    except Exception:
        pass
    return None


def _hermes_config_path():
    if "config_path" not in _cache:
        # Fast path: construct from library-derived home (no subprocess)
        home = _hermes_home_from_library()
        if home:
            config = os.path.join(home, "config.yaml")
            if os.path.isfile(config):
                _cache["config_path"] = config
                return _cache["config_path"]
        # Slow path: fall back to `hermes config path` subprocess
        rc, stdout, _ = _run_hermes(["config", "path"], timeout=_CONFIG_PATH_TIMEOUT)
        lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
        # Use stdout only (never stderr) — the path is printed to stdout.
        _cache["config_path"] = lines[-1] if rc == 0 and lines else None
    return _cache["config_path"]


def _hermes_home():
    """Resolve $HERMES_HOME, preferring the library (fast) over the CLI (slow)."""
    # Fast path: derive from hermes_constants (no subprocess)
    home = _hermes_home_from_library()
    if home:
        return home
    # Slow path: fall back to `hermes config path` subprocess
    path = _hermes_config_path()
    return os.path.dirname(path) if path else None


def _read_config():
    """Return (path, data) for the active config; data is None on parse failure."""
    path = _hermes_config_path()
    if not path:
        return None, None
    if "config_data" not in _cache:
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
            # A non-mapping root (list/scalar) is malformed for our purposes.
            _cache["config_data"] = loaded if isinstance(loaded, dict) else None
        except Exception:
            _cache["config_data"] = None
    return path, _cache["config_data"]


def frontmatter(path):
    """Extract the frontmatter mapping from a SKILL.md.

    Mirrors Hermes' ``parse_frontmatter``: returns ``{}`` for no-fence input
    (the loader registers such skills under their directory name), and ``None``
    only for a non-mapping frontmatter block (list/scalar root) so callers
    never call ``.get()`` on an unusable value.
    """
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except Exception:
        return None
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        fm = yaml.safe_load(parts[1])
    except Exception:
        # Mirror Hermes' parse_frontmatter fallback: recover key:value lines
        # from malformed YAML so a recoverable `name:` is not lost.
        fm = {}
        for line in parts[1].strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                fm[key.strip()] = value.strip()
    return fm if isinstance(fm, dict) else None


def _plugin_skill_names():
    """Names shipped by this plugin (repo skills/*/SKILL.md frontmatter `name`).

    Falls back to the directory basename when frontmatter is unreadable — the
    hub installs by directory name, so that is the fallback users see too.
    """
    if "plugin_skills" in _cache:
        return _cache["plugin_skills"]
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")
    names = set()
    if os.path.isdir(root):
        for dirpath, dirnames, filenames in os.walk(root):
            if "SKILL.md" in filenames:
                fm = frontmatter(os.path.join(dirpath, "SKILL.md"))
                # Same unvalidated-YAML hazard as `check_skills`: a mapping
                # or sequence `name` is unhashable, so `names.add` would raise
                # TypeError instead of naming the bad file. A non-string name
                # falls back to the directory basename, and the count/provenance
                # guards report the malformed file separately.
                raw = (fm or {}).get("name")
                names.add(raw if isinstance(raw, str) and raw else os.path.basename(dirpath))
    _cache["plugin_skills"] = names
    return names


def _iter_skills():
    """Yield (skill_dir_path, frontmatter_or_None) for every SKILL.md, cached.

    Skips hidden/archive directories (``.archive``, ``.curator_backups``,
    ``.hub``) that Hermes uses for internal bookkeeping but does not load as
    skills — mirroring the loader so archived/backup copies never produce
    false positives.
    """
    if "skills" not in _cache:
        home = _hermes_home()
        out = []
        if home:
            skills_root = os.path.join(home, "skills")
            if os.path.isdir(skills_root):
                for dirpath, dirnames, filenames in os.walk(skills_root):
                    dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                    if "SKILL.md" in filenames:
                        out.append((dirpath, frontmatter(os.path.join(dirpath, "SKILL.md"))))
        _cache["skills"] = out
    return _cache["skills"]


def _bundled_skill_names():
    """Return the set of Hermes-bundled skill names from ``.bundled_manifest``.

    The manifest is Hermes' authoritative ``name:hash`` record of skills it
    ships and updates. Skills in this set are Hermes-managed, so their issues
    are not user-fixable (an update overwrites them) and are labelled
    distinctly instead of prompting the user to edit them.
    """
    if "bundled_names" not in _cache:
        home = _hermes_home()
        names = set()
        if home:
            manifest = os.path.join(home, "skills", ".bundled_manifest")
            if os.path.isfile(manifest):
                try:
                    with open(manifest, "r", encoding="utf-8") as f:
                        for line in f:
                            name = line.split(":", 1)[0].strip()
                            if name:
                                names.add(name)
                except Exception:
                    # Unreadable/malformed manifest — treat as empty (best-effort;
                    # fail open toward user-actionable labels).
                    names = set()
        _cache["bundled_names"] = names
    return _cache["bundled_names"]


def _as_name_set(value):
    """Normalize a config value (list or scalar string) into a set of names.

    Guards against a scalar ``plugins.enabled: my-plugin`` — ``set("my-plugin")``
    would explode into single characters and produce bogus findings. Non-list,
    non-string values (bool/int/float/dict) are ignored, mirroring Hermes's
    list-only ``plugins.enabled`` handling instead of crashing on ``set(True)``.
    """
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set, frozenset)):
        # Keep only string names: malformed entries (dicts, ints, ...) must not
        # reach set()/sorted() and crash the diagnostic.
        return {v for v in value if isinstance(v, str)}
    # bool/int/float/dict/… are ignored (Hermes requires a list for `enabled`).
    return set()


# Slug normalization — identical to Hermes agent/skill_bundles.py::_slugify and
# agent/skill_commands.py::scan_skill_commands (same patterns + steps).
_BUNDLE_INVALID_CHARS = re.compile(r"[^a-z0-9-]")
_BUNDLE_MULTI_HYPHEN = re.compile(r"-{2,}")


def _bundle_slug(name):
    """Normalize a skill/bundle name to the hyphenated slash-command slug."""
    if not isinstance(name, str):
        return ""
    cmd = name.lower().replace(" ", "-").replace("_", "-")
    cmd = _BUNDLE_INVALID_CHARS.sub("", cmd)
    return _BUNDLE_MULTI_HYPHEN.sub("-", cmd).strip("-")


def _rel_path(path, base):
    """Return `path` relative to `base` for compact, unambiguous diagnostics."""
    try:
        return os.path.relpath(path, base)
    except ValueError:  # different drives (Windows)
        return path


def _version_label(value):
    """Render a skill version for messages: ``v1.2.3``, or ``unversioned``.

    A bare ``f"v{value}"`` over a missing version produced the string
    "vunversioned" in the collision message — nonsense the user cannot act on.
    """
    text = str(value or "").strip()
    return f"v{text}" if text else "unversioned"


# --- config ---------------------------------------------------------------

def check_config_parses():
    path, data = _read_config()
    if not path:
        return {"status": "unknown", "reason": "`hermes config path` failed", "detail": None}
    if not os.path.exists(path):
        return {"status": "broken", "reason": "config file missing", "detail": path}
    if data is None:
        return {
            "status": "broken",
            "reason": "config.yaml does not parse (or root is not a mapping)",
            "detail": path,
        }
    return {"status": "healthy", "reason": "config.yaml parses", "detail": path}


# --- MCP ------------------------------------------------------------------

def _parse_enabled(value, default=True):
    """Mirror Hermes hermes_cli/tools_config.py::_parse_enabled_flag.

    Hermes treats ``enabled: false``, ``"false"``, ``"no"``, ``"off"``, and ``0``
    as disabled; matching this avoids flagging disabled servers as broken.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


def check_mcp_servers_shape():
    path, data = _read_config()
    if not path or data is None:
        return {"status": "unknown", "reason": "cannot read config", "detail": path}

    broken = []
    notes = []
    # Check parsed top-level keys (not raw text) so comments/strings don't
    # trigger false "foreign key" findings.
    for key in constants.FOREIGN_MCP_KEYS:
        if key in data:
            broken.append(
                f"foreign key `{key}` present (silently not read; use `{constants.CONFIG_MCP_SERVERS}`)"
            )

    servers = data.get(constants.CONFIG_MCP_SERVERS)
    if servers is None:
        servers = {}
    if isinstance(servers, dict):
        for name, entry in servers.items():
            if not isinstance(entry, dict):
                broken.append(f"`{constants.CONFIG_MCP_SERVERS}.{name}` is not a mapping")
                continue
            if "disabled" in entry:
                notes.append(
                    f"`{constants.CONFIG_MCP_SERVERS}.{name}` uses `disabled:` "
                    f"(not read by Hermes; server stays enabled) — set `enabled: false` to disable"
                )
            if not _parse_enabled(entry.get("enabled")):
                notes.append(f"`{constants.CONFIG_MCP_SERVERS}.{name}` is disabled (skipped)")
                continue
            if not entry.get(constants.MCP_STDIO_KEY) and not entry.get(constants.MCP_HTTP_KEY):
                broken.append(
                    f"`{constants.CONFIG_MCP_SERVERS}.{name}` has neither "
                    f"`{constants.MCP_STDIO_KEY}` nor `{constants.MCP_HTTP_KEY}`"
                )
    else:
        broken.append(
            f"`{constants.CONFIG_MCP_SERVERS}` must be a mapping, got {type(servers).__name__}"
        )

    if broken:
        return {"status": "broken", "reason": f"{len(broken)} MCP issue(s)", "detail": broken + notes}
    if notes:
        return {"status": "informational", "reason": f"{len(notes)} note(s)", "detail": notes}
    return {"status": "healthy", "reason": "MCP servers well-formed", "detail": list(servers.keys()) if isinstance(servers, dict) else []}


# --- skills ---------------------------------------------------------------

def check_skills():
    home = _hermes_home()
    if not home:
        return {"status": "unknown", "reason": "cannot resolve $HERMES_HOME", "detail": None}
    skills_root = os.path.join(home, "skills")
    if not os.path.isdir(skills_root):
        return {"status": "healthy", "reason": "no skills directory", "detail": skills_root}

    findings = []
    seen = 0
    bundled = _bundled_skill_names()
    for dirpath, fm in _iter_skills():
        seen += 1
        # Label [bundled] only from the skill's declared name (what Hermes
        # keys the manifest on). The directory basename is not reliable
        # ownership evidence — two skills at different depths can share a
        # basename — so an unreadable/nameless skill is never inferred to be
        # bundled.
        name = fm.get("name") if fm else None
        # `name` is unvalidated YAML: a mapping or sequence value is unhashable,
        # so `name in bundled` raises TypeError and crashes the whole check.
        # Only a real string can match a bundled name; anything else is simply
        # not bundled, and the missing-`name` finding below reports it.
        tag = " [bundled]" if isinstance(name, str) and name in bundled else ""
        if fm is None:
            # Non-mapping frontmatter block (list/scalar root) — the loader
            # cannot use this.
            findings.append(f"{dirpath}: SKILL.md has non-mapping frontmatter{tag}")
            continue
        # Only report what the loader genuinely cannot use: a `name` or
        # `description` that is present but not a non-empty string. Missing
        # `name` is fine (the loader falls back to the directory name);
        # missing `description` is fine (the loader falls back to the first
        # body line).
        for req in ("name", "description"):
            if req in fm:
                val = fm[req]
                if not isinstance(val, str) or not val.strip():
                    findings.append(f"{dirpath}: frontmatter `{req}` is not a non-empty string{tag}")

    if findings:
        return {"status": "broken", "reason": f"{len(findings)} skill issue(s)", "detail": findings}

    # Guide-skill adoption nudge — informational only, never fails the check:
    # the plugin repo ships skills/ alongside checks.py; compare their names
    # against what Hermes discovered under $HERMES_HOME/skills and surface the
    # missing ones with a one-command installer.
    guide_names = _plugin_skill_names()
    if guide_names:
        installed = set()
        for dirpath, fm in _iter_skills():
            installed.add((fm or {}).get("name") or os.path.basename(dirpath.rstrip(os.sep)))
        missing = sorted(guide_names - installed)
        if missing:
            loop = " ".join(missing)
            cmd = f'for s in {loop}; do hermes skills install "iap/hermes-guide/skills/$s"; done'
            return {
                "status": "informational",
                "reason": (
                    f"{seen} skill(s) present with valid frontmatter; "
                    f"guide skills: {len(guide_names) - len(missing)}/{len(guide_names)} installed — "
                    f"install the rest: {cmd}"
                ),
                "detail": skills_root,
            }

    return {"status": "healthy", "reason": f"{seen} skill(s) present with valid frontmatter", "detail": skills_root}


# --- commands -------------------------------------------------------------

def _builtin_command_names():
    """Return the set of built-in slash-command names and aliases from Hermes core.

    Best-effort: returns an empty set if the import fails (e.g. running outside
    a live Hermes environment), in which case the builtin-collision check is
    silently skipped rather than false-positives.
    """
    try:
        from hermes_cli.commands import COMMAND_REGISTRY  # type: ignore[import-not-found]

        names = set()
        for cmd in COMMAND_REGISTRY:
            names.add(cmd.name)
            for alias in cmd.aliases or ():
                names.add(alias)
        return names
    except Exception:
        return set()


def check_commands():
    """Detect skill-bundle slug collisions, malformed bundle files, and builtin shadowing."""
    home = _hermes_home()
    if not home:
        return {"status": "unknown", "reason": "cannot resolve $HERMES_HOME", "detail": None}

    skill_slugs = set()
    skill_slug_owners: dict[str, str] = {}  # slug -> first skill dir (first-wins, mirrors Hermes)
    skill_slug_versions: dict[str, str] = {}  # slug -> version string of first owner
    collisions = []
    for dirpath, fm in _iter_skills():
        if fm and fm.get("name"):
            s = _bundle_slug(fm.get("name"))
            if s:
                skill_slugs.add(s)
                if s in skill_slug_owners:
                    collisions.append(
                        f"skill `{_rel_path(skill_slug_owners[s], home)}` "
                        f"({_version_label(skill_slug_versions.get(s))}) and "
                        f"`{_rel_path(dirpath, home)}` ({_version_label(fm.get('version'))}) "
                        f"both normalize to `/{s}` (first wins)"
                    )
                else:
                    skill_slug_owners[s] = dirpath
                    skill_slug_versions[s] = str(fm.get("version") or "").strip()

    # Skill-vs-builtin collisions: a skill whose slug matches a built-in command
    # name is silently shadowed (built-in wins). Surface this so the user can
    # rename the skill before wondering why `/<name>` behaves unexpectedly.
    builtin_names = _builtin_command_names()
    if builtin_names:
        for dirpath, fm in _iter_skills():
            if fm and fm.get("name"):
                s = _bundle_slug(fm.get("name"))
                if s and s in builtin_names:
                    collisions.append(
                        f"skill `{_rel_path(dirpath, home)}` (/{s}) shadows a built-in command "
                        f"(builtin wins — rename the skill or expect the builtin behavior)"
                    )

    malformed = []
    bundle_slugs: dict[str, str] = {}  # slug -> first bundle stem (bundle-vs-bundle first-wins)
    bundles_root = os.path.join(home, "skill-bundles")
    if os.path.isdir(bundles_root):
        for fn in sorted(os.listdir(bundles_root)):
            if not fn.endswith((".yaml", ".yml")):
                continue
            stem = fn.rsplit(".", 1)[0]
            bundle_path = os.path.join(bundles_root, fn)
            try:
                with open(bundle_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
            except Exception as exc:
                malformed.append(f"bundle `{stem}` failed to parse: {exc}")
                continue

            # Mirror Hermes agent/skill_bundles.py::_load_bundle_file: a bundle
            # must be a mapping with a non-empty `skills` list and a resolvable
            # name/slug, otherwise Hermes skips it during slash-command discovery.
            if not isinstance(loaded, dict):
                malformed.append(f"bundle `{stem}` is not a mapping (skipped by Hermes)")
                continue

            skills = loaded.get("skills") or []
            if not isinstance(skills, list):
                malformed.append(f"bundle `{stem}`: `skills` is not a list (skipped by Hermes)")
            elif not [s for s in skills if str(s).strip()]:
                malformed.append(f"bundle `{stem}` has an empty `skills` list (skipped by Hermes)")

            name = str(loaded.get("name") or stem).strip()
            if not name:
                malformed.append(f"bundle `{stem}` has no usable name (skipped by Hermes)")
                continue
            slug = _bundle_slug(name)
            if not slug:
                malformed.append(f"bundle `{stem}` yields an empty slug (skipped by Hermes)")
                continue

            if slug in bundle_slugs:
                collisions.append(
                    f"bundle `{stem}` (/{slug}) shadows bundle "
                    f"`{bundle_slugs[slug]}` (/{slug}) (first wins)"
                )
            else:
                bundle_slugs[slug] = stem

            if slug in skill_slugs:
                collisions.append(f"bundle `{stem}` (/{slug}) shadows skill `/{slug}` (bundle wins)")

    if malformed:
        return {"status": "broken", "reason": f"{len(malformed)} malformed bundle(s)", "detail": malformed + collisions}
    if collisions:
        return {"status": "informational", "reason": f"{len(collisions)} slug collision(s)", "detail": collisions}
    return {"status": "healthy", "reason": "no slug collisions or malformed bundles", "detail": None}


# --- hooks ----------------------------------------------------------------

def _check_allowlist_json():
    """Return a broken envelope if ``shell-hooks-allowlist.json`` is present but
    not valid JSON; otherwise ``None`` (no finding).

    Independent of the ``hermes hooks doctor`` summary wording: a malformed
    allowlist is broken even when doctor reports healthy or an unrecognized
    summary.
    """
    home = _hermes_home()
    if not home:
        return None
    allowlist = os.path.join(home, "shell-hooks-allowlist.json")
    if not os.path.exists(allowlist):
        return None
    try:
        with open(allowlist, "r", encoding="utf-8") as f:
            json.load(f)
    except Exception:
        return {
            "status": "broken",
            "reason": "shell-hooks-allowlist.json is not valid JSON",
            "detail": allowlist,
        }
    return None


def check_hooks():
    # `hermes hooks doctor` exits 0 even with problems, so we parse its output
    # (rc is not a reliable signal — it is 0 in all cases). Count the U+2717 /
    # U+26A0 markers emitted per hook rather than matching the summary line's
    # exact wording.
    rc, stdout, _ = _run_hermes(["hooks", "doctor"], timeout=_HOOKS_DOCTOR_TIMEOUT)
    if rc != 0 or not stdout.strip():
        return {
            "status": "unknown",
            "reason": f"`hermes hooks doctor` unavailable or failed (rc={rc})",
            "detail": None,
        }
    if "No shell hooks configured" in stdout:
        result = {"status": "healthy", "reason": "no shell hooks configured", "detail": None}
    else:
        # U+2717 and U+26A0 are the only stable per-hook markers in the output.
        markers = re.findall(r"\s+[✗⚠]", stdout)
        if markers:
            result = {
                "status": "broken",
                "reason": f"`hermes hooks doctor` reported {len(markers)} finding(s)",
                "detail": stdout.strip()[:2000],
            }
        elif "All shell hooks look healthy" in stdout:
            result = {"status": "healthy", "reason": "hooks doctor passed", "detail": None}
        else:
            # Output ran but matched no known summary pattern — treat as unknown
            # rather than falsely healthy in case Hermes changed its wording.
            result = {
                "status": "unknown",
                "reason": "`hermes hooks doctor` output matched no known summary pattern",
                "detail": stdout.strip()[:2000],
            }
    # A malformed allowlist is real breakage regardless of the doctor's verdict —
    # but it must not *replace* the doctor's findings. Returning the allowlist
    # envelope alone silently dropped them, hiding the very problems the user is
    # diagnosing. Merge both instead.
    allowlist_result = _check_allowlist_json()
    if allowlist_result is None:
        return result
    detail = [allowlist_result.get("detail")]
    if result.get("status") in ("broken", "unknown"):
        detail.append(f"`hermes hooks doctor`: {result.get('reason')}")
        extra = result.get("detail")
        if isinstance(extra, list):
            detail.extend(extra)
        elif extra:
            detail.append(str(extra))
    return {
        "status": "broken",
        "reason": allowlist_result.get("reason"),
        "detail": detail,
    }


# --- plugins --------------------------------------------------------------

def _bundled_plugins_dir():
    """Resolve the bundled plugins directory the loader scans, or None.

    Uses Hermes' own resolver so nested category layouts (browser/, image_gen/,
    model-providers/, platforms/, ...) resolve exactly as the loader does. The
    import is dynamic (importlib) so it stays mypy-clean and the check still
    runs when imported outside a live Hermes process (e.g. in a unit test).
    """
    try:
        resolver = getattr(importlib.import_module("hermes_cli.plugins"), "get_bundled_plugins_dir")
        return str(resolver())
    except Exception:
        return None


def _read_plugin_manifest(d):
    """Return a directory plugin's manifest ``name``, or None if none exists.

    Accepts ``plugin.yaml`` then ``plugin.yml`` (mirroring
    ``plugins_cmd._read_manifest_info``), then falls back to portable
    ``plugin.json`` Agent Plugin packages — Hermes's own ``scan_directory``
    resolves all three, so a ``plugin.json``-only plugin that is enabled and
    loaded must not be reported as missing. The portable schema is a flat
    mapping with a top-level ``name`` (see ``hermes_cli.agent_plugins``).
    """
    for ext in ("plugin.yaml", "plugin.yml"):
        manifest_file = os.path.join(d, ext)
        if os.path.isfile(manifest_file):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = yaml.safe_load(f) or {}
                name = manifest.get("name")
            except Exception:
                name = None
            if not name:
                name = os.path.basename(d)
            return name
    portable = os.path.join(d, "plugin.json")
    if os.path.isfile(portable):
        try:
            with open(portable, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            # Malformed JSON / unreadable file: not a usable plugin manifest.
            return None
        if isinstance(manifest, dict):
            name = manifest.get("name")
            if not name:
                name = os.path.basename(d)
            return name
    return None


def _collect_plugin_ids(root, prefix, depth, skip_names, seen):
    """Recursively collect discoverable plugin identifiers, mirroring
    ``plugins_cmd._scan_level``: a plugin resolves by its manifest ``name`` or
    its path-derived ``key`` (``<category>/<dirname>``). Both are added to
    *seen* so ``plugins.enabled`` matches by name or key alike."""
    if not root or not os.path.isdir(root):
        return
    for d in sorted(os.listdir(root)):
        dpath = os.path.join(root, d)
        if not os.path.isdir(dpath):
            continue
        if depth == 0 and skip_names and d in skip_names:
            continue
        name = _read_plugin_manifest(dpath)
        if name is not None:
            key = f"{prefix}/{d}" if prefix else name
            seen.add(name)
            seen.add(key)
            continue
        if depth >= 1:
            continue
        sub_prefix = f"{prefix}/{d}" if prefix else d
        _collect_plugin_ids(dpath, sub_prefix, depth + 1, set(), seen)


def check_plugins():
    path, data = _read_config()
    home = _hermes_home()
    if not path or data is None or not home:
        return {"status": "unknown", "reason": "cannot read config", "detail": path}

    plugins_cfg = data.get("plugins")
    plugins_cfg = plugins_cfg if isinstance(plugins_cfg, dict) else {}
    enabled = _as_name_set(plugins_cfg.get("enabled"))
    disabled = _as_name_set(plugins_cfg.get("disabled"))

    plugins_root = os.path.join(home, "plugins")
    skip = set(constants.PLUGIN_SUBCATEGORY_DIRS)

    # Collect every plugin the loader can see — the user dir *and* the bundled
    # dir (with its category sub-layouts) — by both manifest name and key. This
    # is what makes enabled bundled plugins (e.g. `disk-cleanup`,
    # `kilocode-provider`) resolvable instead of being falsely flagged missing.
    known: set[str] = set()
    _collect_plugin_ids(plugins_root, "", 0, set(), known)
    # Subcategory dirs resolve by their own selection keys (memory.provider,
    # context.engine, image_gen.provider, --provider), never plugins.enabled, so
    # their contents are not discoverable ids. Names come from constants.py,
    # which is the single source of truth for values that drift upstream.
    _collect_plugin_ids(
        _bundled_plugins_dir(), "", 0, set(constants.PLUGIN_SUBCATEGORY_DIRS), known
    )

    broken = []
    for name in sorted(enabled):
        if name in skip:
            continue  # sub-category dirs use their own selection keys, not plugins.enabled
        if name not in known:
            broken.append(f"`{name}` is enabled but no matching plugin manifest was found")

    notes = []
    if os.path.isdir(plugins_root):
        for entry in sorted(os.listdir(plugins_root)):
            if entry in skip or entry.startswith(".") or entry == "__pycache__":
                continue
            dpath = os.path.join(plugins_root, entry)
            if not os.path.isdir(dpath):
                continue
            manifest_name = _read_plugin_manifest(dpath)
            if manifest_name is None:
                # No manifest — not a plugin. Hermes does not load it either, so
                # reporting a stray state/vendor directory would be noise.
                continue
            # Match on the manifest name, which is what `plugins.enabled` keys
            # on; the directory basename is not a reliable identifier.
            if manifest_name not in enabled and manifest_name not in disabled:
                notes.append(f"`{manifest_name}` discovered but not enabled (opt-in)")

    if broken:
        return {"status": "broken", "reason": f"{len(broken)} enabled plugin(s) missing or broken", "detail": broken + notes}
    if notes:
        return {"status": "informational", "reason": f"{len(notes)} plugin(s) not enabled", "detail": notes}
    return {"status": "healthy", "reason": "plugins consistent with enable list", "detail": sorted(enabled)}


# --- memory ---------------------------------------------------------------

_MEM_USER_LEAD = re.compile(
    # "User <pref/identity-verb> …" reads as a user-profile fact; bare "User …"
    # does not ("User authentication uses OAuth" is a legitimate agent note),
    # so the profile keyword must follow "user" directly.
    r"^\s*(?:the\s+)?user\s+"
    r"(?:prefers?|wants?|likes?|dislikes?|hates?|loves?|identity|gets?|has|"
    r"works?|rejects?|uses?|understands?|demands?|merges?|avoids?|tolerates?|"
    r"expects?|does)\b",
    re.IGNORECASE,
)
_MEM_DATE_LEAD = re.compile(r"^\s*\[\d{4}-\d{2}-\d{2}\]")
_WS_NORM = re.compile(r"[\s\W_]+", re.UNICODE)


def _mem_tokens(entry):
    """Normalize an entry into a token set for near-duplicate comparison."""
    return frozenset(_WS_NORM.split(_WS_NORM.sub(" ", entry.lower()).strip())) - {""}


def _memory_limit(data, store):
    """Return the configured char limit for a store (defaults mirror upstream)."""
    mem_cfg = data.get(constants.CONFIG_MEMORY_SECTION) if isinstance(data, dict) else None
    key = "memory_char_limit" if store == "MEMORY.md" else "user_char_limit"
    default = constants.MEMORY_CHAR_LIMIT_DEFAULT if store == "MEMORY.md" else constants.USER_CHAR_LIMIT_DEFAULT
    if isinstance(mem_cfg, dict):
        value = mem_cfg.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    return default


def check_memory_hygiene():
    """Read-only hygiene audit of the built-in memory stores (MEMORY.md/USER.md).

    Complements `hermes memory status` (which reports provider/store health)
    with content-level findings: over-limit stores, exact/near-duplicate
    entries, user-preference entries mis-targeted into the agent-notes store,
    and an undated dynamic store. Never mutates anything.
    """
    home = _hermes_home()
    if not home:
        return {"status": "unknown", "reason": "cannot resolve $HERMES_HOME", "detail": None}
    _, data = _read_config()

    memories_dir = os.path.join(home, "memories")
    broken = []
    notes = []
    missing = []
    stores_present = 0

    for store in constants.BUILTIN_MEMORY_STORES:
        store_path = os.path.join(memories_dir, store)
        if not os.path.isfile(store_path):
            missing.append(store)
            continue
        stores_present += 1
        try:
            with open(store_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as exc:
            broken.append(f"{store}: unreadable ({type(exc).__name__})")
            continue

        entries = [e.strip() for e in text.split(f"\n{constants.MEMORY_ENTRY_DELIMITER}\n") if e.strip()]
        limit = _memory_limit(data, store)
        # Match the runtime's own measurement: Hermes counts the delimiter-joined
        # entries (memory_tool_store.py: `len(ENTRY_DELIMITER.join(entries))`),
        # not the raw file bytes. Using `len(text)` counted trailing separators /
        # stray whitespace and could report "over limit" for a store the runtime
        # would still accept.
        size = len(f"\n{constants.MEMORY_ENTRY_DELIMITER}\n".join(entries))

        if size > limit:
            broken.append(
                f"{store}: {size}/{limit} chars — over limit; "
                "writes will be rejected or evicted (consolidate: remove/merge stale entries)"
            )
        elif size > 0.85 * limit:
            notes.append(f"{store}: {size}/{limit} chars — approaching limit")

        # Exact duplicates (the tool's own rejection is exact-match, so these
        # can only appear via replace/manual edits — still worth flagging).
        exact_dups = sorted({e for e in entries if entries.count(e) > 1})
        for e in exact_dups[:3]:
            broken.append(f"{store}: exact duplicate entry ({e[:60]}…) — remove one copy")

        # Near-duplicates: normalized token-set overlap on entries >20 chars.
        tokenized = [(i, _mem_tokens(e)) for i, e in enumerate(entries) if len(e) > 20]
        reported_pairs = set()
        near_dups = 0
        for a in range(len(tokenized)):
            for b in range(a + 1, len(tokenized)):
                ia, ta = tokenized[a]
                ib, tb = tokenized[b]
                if not ta or not tb:
                    continue
                overlap = len(ta & tb) / len(ta | tb)
                if overlap >= 0.8 and (ia, ib) not in reported_pairs:
                    reported_pairs.add((ia, ib))
                    near_dups += 1
                    if near_dups <= 3:
                        notes.append(
                            f"{store}: entries #{ia + 1} and #{ib + 1} are near-duplicates "
                            f"({overlap:.0%} overlap) — merge into one"
                        )
        if near_dups > 3:
            notes.append(f"{store}: {near_dups} near-duplicate pair(s) total")

        # Mis-target: user-profile facts in the agent-notes store. Only checked
        # on MEMORY.md — USER.md leading with "User" is correct, not a finding.
        if store == "MEMORY.md":
            mis_targets = [e for e in entries if _MEM_USER_LEAD.match(e)]
            for e in mis_targets[:3]:
                notes.append(
                    f"{store}: entry reads like a user-profile fact ({e[:50]}…) — "
                    "it belongs in USER.md (target=user), where it loads for every session too"
                )
            if len(mis_targets) > 3:
                notes.append(f"{store}: {len(mis_targets)} user-profile entry(ies) total")

        # Dynamic store benefits from entry dates (staleness tracking): report
        # every undated entry, not just an all-undated store.
        if store == "MEMORY.md" and entries:
            undated = [e for e in entries if not _MEM_DATE_LEAD.match(e)]
            if len(undated) == len(entries):
                notes.append(
                    f"{store}: no entry has a [YYYY-MM-DD] date prefix — "
                    "dating entries makes staleness checkable"
                )
            elif undated:
                notes.append(
                    f"{store}: {len(undated)} of {len(entries)} entries lack a "
                    "[YYYY-MM-DD] date prefix — dating entries makes staleness checkable"
                )

    if broken:
        return {"status": "broken", "reason": f"{len(broken)} memory issue(s)", "detail": broken + notes}
    if stores_present == 0:
        return {"status": "healthy", "reason": "no memory files yet (nothing to audit)", "detail": memories_dir}
    for store in missing:
        notes.append(f"{store}: not created yet (Hermes creates it on first write)")
    if notes:
        return {"status": "informational", "reason": f"{len(notes)} memory note(s)", "detail": notes}
    return {"status": "healthy", "reason": "memory stores within limits, no hygiene findings", "detail": memories_dir}


# --- runner ---------------------------------------------------------------

_CHECKS = [
    ("config", check_config_parses),
    ("mcp", check_mcp_servers_shape),
    ("skills", check_skills),
    ("commands", check_commands),
    ("hooks", check_hooks),
    ("plugins", check_plugins),
    # Label is "memories" (the $HERMES_HOME/memories/ directory the check
    # audits) — "memory" is reserved by constants.PLUGIN_SUBCATEGORY_DIRS and
    # the F3 guard forbids it as a literal here.
    ("memories", check_memory_hygiene),
]


def labels():
    """Return the valid check labels in report order (scope validation + CLI help)."""
    return [label for label, _ in _CHECKS]


def run_all(scope=None):
    """Run every check, or exactly the one named by ``scope``.

    Each check is isolated: a crash in one check surfaces as a `broken`
    envelope instead of aborting the whole report (a diagnostic tool must
    survive the broken inputs it exists to diagnose).

    ``scope`` must equal one of the check labels. An unrecognized scope raises
    ``ValueError`` naming the valid ones — matching on a substring would let
    ``s`` silently run four checks and a typo report success.
    """
    _cache.clear()
    valid = labels()
    if scope is not None and scope not in valid:
        raise ValueError(f"unknown scope {scope!r}; valid scopes: {', '.join(valid)}")
    results = {}
    for label, fn in _CHECKS:
        if scope is not None and scope != label:
            continue
        try:
            results[label] = fn()
        except Exception as exc:
            results[label] = {
                "status": "broken",
                "reason": f"check crashed ({type(exc).__name__}: {exc})",
                "detail": None,
            }
    return results
