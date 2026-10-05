#!/usr/bin/env python3
"""F5 regression: a portable ``plugin.json``-only plugin must be discovered.

``_read_plugin_manifest`` originally accepted only ``plugin.yaml``/``plugin.yml``,
so any enabled plugin that ships only a portable Agent Plugin ``plugin.json``
(manifest schema ``agent-plugins.org``) was reported as
"enabled but no matching plugin manifest was found" — a false positive on a
plugin Hermes itself loads and lists (e.g. pstack v0.14.8).

Hermes's own ``scan_directory`` resolves all three forms, so the check must too.

Guards:

1. A directory with only ``plugin.json`` (valid ``name``) is discovered by name.
2. A directory with only ``plugin.json`` (missing/empty ``name``) falls back to
   the directory basename — same contract as the YAML path.
3. A directory with only ``plugin.json`` (malformed JSON) returns None and is
   not reported as a plugin (matches Hermes's fail-open behaviour).
4. A directory with ``plugin.yaml`` still wins over ``plugin.json`` when both
   are present (YAML first in the resolution order).
5. A directory with neither manifest nor ``plugin.json`` returns None.

Uses a synthetic ``$HERMES_HOME`` and never invokes the ``hermes`` CLI.

Run: python3 tools/test_portable_plugin_manifest.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str]) -> int:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as td:
        pkg = Path(td) / "hermes_guide"
        pkg.mkdir()
        for name in ("__init__.py", "checks.py", "constants.py"):
            shutil.copy(REPO / name, pkg / name)
        sys.path.insert(0, td)

        import hermes_guide.checks as checks  # noqa: E402

        # (1) portable plugin.json with a name -> discovered by name
        d = Path(td) / "portable"
        _write(d / "plugin.json", json.dumps({"name": "portable-plugin", "version": "1.0.0"}))
        if checks._read_plugin_manifest(str(d)) != "portable-plugin":
            failures.append("portable plugin.json name not discovered")

        # (2) portable plugin.json without a name -> basename fallback
        d2 = Path(td) / "no-name"
        _write(d2 / "plugin.json", json.dumps({"version": "1.0.0"}))
        if checks._read_plugin_manifest(str(d2)) != "no-name":
            failures.append("portable plugin.json without name did not fall back to basename")

        # (2b) portable plugin.json with empty name -> basename fallback
        d2b = Path(td) / "empty-name"
        _write(d2b / "plugin.json", json.dumps({"name": "", "version": "1.0.0"}))
        if checks._read_plugin_manifest(str(d2b)) != "empty-name":
            failures.append("portable plugin.json with empty name did not fall back to basename")

        # (2c) YAML plugin.yaml with empty name -> basename fallback
        d2c = Path(td) / "yaml-empty-name"
        _write(d2c / "plugin.yaml", "name: \"\"\nversion: 1.0.0\n")
        if checks._read_plugin_manifest(str(d2c)) != "yaml-empty-name":
            failures.append("plugin.yaml with empty name did not fall back to basename")

        # (3) malformed plugin.json -> None (not a plugin)
        d3 = Path(td) / "bad-json"
        _write(d3 / "plugin.json", "{ not json")
        if checks._read_plugin_manifest(str(d3)) is not None:
            failures.append("malformed plugin.json was treated as a plugin")

        # (4) plugin.yaml wins over plugin.json when both present
        d4 = Path(td) / "both"
        _write(d4 / "plugin.yaml", "name: yaml-wins\nversion: 1.0.0\n")
        _write(d4 / "plugin.json", json.dumps({"name": "json-loses", "version": "1.0.0"}))
        if checks._read_plugin_manifest(str(d4)) != "yaml-wins":
            failures.append("plugin.yaml did not win over plugin.json")

        # (5) no manifest at all -> None
        d5 = Path(td) / "empty"
        d5.mkdir(parents=True, exist_ok=True)
        if checks._read_plugin_manifest(str(d5)) is not None:
            failures.append("manifest-less directory was treated as a plugin")

        # (6) behavioral: an enabled portable plugin is not reported missing
        home = Path(td) / "home"
        plugins = home / "plugins"
        _write(plugins / "portable-only/plugin.json",
               json.dumps({"name": "portable-only", "version": "1.0.0"}))
        config = home / "config.yaml"
        _write(config, "plugins:\n  enabled:\n    - portable-only\n  disabled: []\n")

        checks._cache.clear()
        checks._hermes_config_path = lambda: str(config)
        checks._hermes_home_from_library = lambda: str(home)
        checks._bundled_plugins_dir = lambda: None

        result = checks.check_plugins()
        if result.get("status") == "broken":
            failures.append(f"enabled portable plugin wrongly reported missing: {result!r}")
        # On healthy the detail is the sorted enabled list (expected to contain
        # the name); on informational it is a list of notes. Only the notes
        # portion must not mention the enabled plugin.
        detail = result.get("detail")
        notes = []
        if isinstance(detail, list) and result.get("status") == "informational":
            notes = [str(d) for d in detail]
        elif isinstance(detail, list) and result.get("status") == "healthy":
            notes = []  # detail is the enabled list, not findings
        joined = " | ".join(notes)
        if "portable-only" in joined:
            failures.append(f"enabled portable plugin should not appear in notes: {joined}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1

    print("OK: portable plugin.json plugins are discovered (F5)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))