#!/usr/bin/env python3
"""Render the generated blocks in README.md and AGENTS.md from the repo itself.

Why this exists
---------------
Every count in this repo's prose used to be hand-maintained, in three files, and
``tools/test_skill_counts.py`` pinned the exact sentences with regexes so it could
catch a mismatch. That worked, but it also meant the *wording* of the docs was
frozen by a test: rephrasing "The other eighteen skills" broke CI, so the prose
was never allowed to improve, only to be corrected.

The better trade is to stop hand-maintaining the volatile parts. Everything that
is a mechanical function of the working tree — how many skills ship, what they
are called, the install loop, the check scopes, and the prose sentences that
carry those counts — is generated here. A block is delimited in the Markdown by::

    <!-- BEGIN GENERATED: <block> -->
    ...rendered...
    <!-- END GENERATED: <block> -->

Everything *outside* those markers stays hand-written and is verified separately
by ``tools/test_skill_counts.py``. The split is deliberate:

- **Generated** = mechanical. Rewriting it by hand is always a bug.
- **Hand-written** = editorial. Editing it freely is always allowed.

The renderer is hermetic: it reads files, parses ``checks.py`` with ``ast``
(never importing it, so it needs no PyYAML and no Hermes install), and shells out
to nothing. Check mode is the default so it is safe in a commit hook.

Usage
-----
    python tools/render_docs.py            # --check: verify blocks match (default)
    python tools/render_docs.py --write    # rewrite the blocks in place
    python tools/render_docs.py --list     # the blocks and what feeds them
    python tools/render_docs.py --selftest # fixture test, no repo scan

Exit codes: 0 in sync / clean selftest; 1 a block is stale, malformed, or
missing; 2 an input the renderer needs is unusable (no skills, no ``_CHECKS``).
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"
CHECKS_PY = REPO / "checks.py"

BEGIN = "<!-- BEGIN GENERATED: {name} -->"
END = "<!-- END GENERATED: {name} -->"

# Two..twenty. Extending this is a deliberate edit: a twenty-first skill should
# make someone look at the prose, not silently produce "21".
_WORDS = [
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
]


def _word_num(n: int) -> str:
    """Spell `n` as a word. The prose style is word-numbers, not digits."""
    try:
        return _WORDS[n - 2]
    except IndexError:
        raise SystemExit(f"error: no word for {n} — extend _WORDS in render_docs.py")


# --- inputs ----------------------------------------------------------------


def skill_names(skills_dir: Path = SKILLS_DIR) -> list[str]:
    """Shipped skill identifiers: every `skills/<name>/` that carries a SKILL.md."""
    names = sorted(p.parent.name for p in skills_dir.glob("*/SKILL.md"))
    if not names:
        raise SystemExit(f"error: no SKILL.md found under {skills_dir}")
    return names


def diagnostic_names(skills_dir: Path = SKILLS_DIR) -> list[str]:
    return [n for n in skill_names(skills_dir) if n.startswith("diagnosing-")]


def check_labels(checks_py: Path = CHECKS_PY) -> list[str]:
    """The `_CHECKS` labels, read with `ast` rather than by importing checks.py.

    Importing would drag in PyYAML and the rest of the plugin's import graph,
    and this script has to stay runnable on a bare interpreter in a commit hook.
    """
    tree = ast.parse(checks_py.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "_CHECKS" for t in node.targets):
            continue
        labels: list[str] = []
        for elt in node.value.elts:  # type: ignore[attr-defined]
            first = elt.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                labels.append(first.value)
        if not labels:
            break
        return labels
    raise SystemExit(f"error: could not read _CHECKS labels from {checks_py}")


# --- blocks ----------------------------------------------------------------


def _readme_inventory(ctx: dict) -> list[str]:
    total = len(ctx["skills"])
    diags = len(ctx["diagnostics"])
    return [
        f"**{_word_num(total).capitalize()} troubleshooting skills** — one install "
        f"guide, one configuration map, and {_word_num(diags)} per-surface "
        f"`diagnosing-*` playbooks."
    ]


def _readme_scopes(ctx: dict) -> list[str]:
    return [", ".join(f"`{label}`" for label in ctx["labels"])]


def _readme_install_loop(ctx: dict) -> list[str]:
    names = ctx["skills"]
    joined = " ".join(sorted(names))
    return [
        "```bash",
        f'for s in {joined}; do hermes skills install "redsurge/hermes-guide/skills/$s"; done',
        "```",
    ]


def _agents_inventory(ctx: dict) -> list[str]:
    total = len(ctx["skills"])
    diags = len(ctx["diagnostics"])
    checks = ctx["labels"]
    return [
        f"- **Plugin** — `plugin.yaml` + `__init__.py` / `checks.py` / "
        f"`constants.py`. Registers `/hermes-doctor` and `hermes guide` "
        f"({_word_num(len(checks))} read-only health checks: "
        + ", ".join(checks)
        + ").",
        f"- **Skills** — `{_word_num(total)}` `skills/<name>/SKILL.md` files: one install "
        f"guide (`installing-hermes`), one configuration map "
        f"(`hermes-configuration-guide`), {_word_num(diags)} `diagnosing-*` "
        f"playbooks. They install separately, through the skills tap.",
    ]


# filename -> {block name: render function}
BLOCKS: dict[str, dict[str, object]] = {
    "README.md": {
        "intro-inventory": _readme_inventory,
        "intro-scopes": _readme_scopes,
        "install-all-loop": _readme_install_loop,
    },
    "AGENTS.md": {
        "inventory": _agents_inventory,
    },
}

_SOURCES = {
    "intro-inventory": "skills/*/SKILL.md (count + diagnosing-* count)",
    "intro-scopes": "checks._CHECKS labels",
    "install-all-loop": "skills/*/SKILL.md (identifiers)",
    "inventory": "skills/*/SKILL.md + checks._CHECKS labels",
}


# --- splicing --------------------------------------------------------------


def block_text(name: str, body: list[str]) -> str:
    return "\n".join([BEGIN.format(name=name), *body, END.format(name=name)])


def find_span(text: str, name: str) -> tuple[int, int]:
    """Return (start, end) offsets of the block's CONTENT (markers excluded).

    Raises ValueError when the markers are absent, unbalanced, or duplicated —
    a duplicated block is a silent-failure risk, because splicing the first pair
    would leave the stale second copy in place and the check would pass.
    """
    begin, end = BEGIN.format(name=name), END.format(name=name)
    starts = [i for i in range(len(text)) if text.startswith(begin, i)]
    ends = [i for i in range(len(text)) if text.startswith(end, i)]
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError(
            f"expected exactly one BEGIN/END pair for {name!r}, "
            f"found {len(starts)} begin / {len(ends)} end"
        )
    start = starts[0] + len(begin)
    if text.startswith("\n", start):
        start += 1
    stop = ends[0]
    if stop > start and text[stop - 1] == "\n":
        stop -= 1
    if stop < start:
        raise ValueError(f"block {name!r} has END before its content")
    return start, stop


def splice(text: str, name: str, body: list[str]) -> str:
    start, stop = find_span(text, name)
    return text[:start] + "\n".join(body) + text[stop:]


# --- file I/O --------------------------------------------------------------


def _read(path: Path) -> tuple[str, str]:
    """Return (text with \\n endings, the file's original line ending).

    Uses builtin ``open()`` rather than ``Path.read_text(newline=...)``: that
    keyword only exists from Python 3.13, and this repo's CI matrix is 3.11/3.12.
    ``open()`` has taken ``newline`` since Python 2, so it works on every leg.
    """
    with open(path, encoding="utf-8-sig", newline="") as handle:
        raw = handle.read()
    return raw.replace("\r\n", "\n"), ("\r\n" if "\r\n" in raw else "\n")


def _write(path: Path, text: str, newline: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text.replace("\n", newline))


def context() -> dict:
    return {
        "skills": skill_names(),
        "diagnostics": diagnostic_names(),
        "labels": check_labels(),
    }


def run(ctx: dict, write: bool) -> int:
    problems: list[str] = []
    changed: list[str] = []

    for filename, blocks in BLOCKS.items():
        path = REPO / filename
        try:
            text, newline = _read(path)
        except OSError as exc:
            problems.append(f"{filename}: unreadable ({exc})")
            continue

        for name, render in blocks.items():
            body = render(ctx)  # type: ignore[operator]
            try:
                expected = splice(text, name, body)
            except ValueError as exc:
                problems.append(f"{filename}: {exc}")
                continue
            if expected == text:
                continue
            changed.append(f"{filename} block {name!r}")
            text = expected

        if write and any(c.startswith(filename) for c in changed):
            _write(path, text, newline)

    for note in changed:
        stream = sys.stdout if write else sys.stderr
        print(f"{'wrote' if write else 'FAIL:'} {note}", file=stream)

    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1

    if write:
        if changed:
            print(f"OK: rendered {len(changed)} generated block(s)")
        else:
            print("OK: generated blocks already in sync")
        return 0

    if changed:
        print(
            "Run `python tools/render_docs.py --write` to refresh them; do not "
            "hand-edit inside a BEGIN/END GENERATED block.",
            file=sys.stderr,
        )
        return 1
    total = sum(len(b) for b in BLOCKS.values())
    print(f"OK: {total} generated doc block(s) match the repo")
    return 0


def _list() -> int:
    print("Generated blocks (edit the renderer, then --write):")
    for filename, blocks in BLOCKS.items():
        for name in blocks:
            print(f"  {filename:<12} {name:<20} {BEGIN.format(name=name)}")
            print(f"  {'':<12} {'':<20} source: {_SOURCES[name]}")
    return 0


# --- selftest --------------------------------------------------------------

# (document, replacement body, expected lines after splice, description)
_SELFTEST_CASES: list[tuple[str, list[str], list[str], str]] = [
    (
        "pre\n<!-- BEGIN GENERATED: b -->\nold\n<!-- END GENERATED: b -->\npost\n",
        ["new"],
        [
            "pre",
            "<!-- BEGIN GENERATED: b -->",
            "new",
            "<!-- END GENERATED: b -->",
            "post",
            "",
        ],
        "single-line body",
    ),
    (
        "a\n<!-- BEGIN GENERATED: b -->\n\n\nold1\nold2\n<!-- END GENERATED: b -->\n",
        ["new1", "new2"],
        [
            "a",
            "<!-- BEGIN GENERATED: b -->",
            "new1",
            "new2",
            "<!-- END GENERATED: b -->",
            "",
        ],
        "multi-line body; leading/trailing blank lines collapse",
    ),
    (
        "x\n<!-- BEGIN GENERATED: b -->\nold\n<!-- END GENERATED: b -->",
        ["new"],
        ["x", "<!-- BEGIN GENERATED: b -->", "new", "<!-- END GENERATED: b -->"],
        "no trailing newline",
    ),
    (
        "<!-- BEGIN GENERATED: b -->\nold\n<!-- END GENERATED: b -->\n",
        ["new"],
        ["<!-- BEGIN GENERATED: b -->", "new", "<!-- END GENERATED: b -->", ""],
        "block is the whole document",
    ),
]

_SELFTEST_ERRORS: list[tuple[str, str]] = [
    ("no markers at all\n", "expected exactly one BEGIN/END pair"),
    (
        "<!-- BEGIN GENERATED: b -->\nx\n<!-- END GENERATED: b -->\n"
        "<!-- BEGIN GENERATED: b -->\ny\n<!-- END GENERATED: b -->\n",
        "expected exactly one BEGIN/END pair",
    ),
    (
        "<!-- END GENERATED: b -->\n<!-- BEGIN GENERATED: b -->\nx\n",
        "END before its content",
    ),
]


def _selftest() -> int:
    fails = 0
    for doc, body, expected, label in _SELFTEST_CASES:
        got = splice(doc, "b", body).split("\n")
        if got != expected:
            print(
                f"selftest FAIL ({label}):\n  got      {got!r}\n  expected {expected!r}"
            )
            fails += 1
    for doc, needle in _SELFTEST_ERRORS:
        try:
            splice(doc, "b", ["new"])
        except ValueError as exc:
            if needle not in str(exc):
                print(f"selftest FAIL (error case): {exc!r} lacks {needle!r}")
                fails += 1
        else:
            print(f"selftest FAIL: {doc!r} should have raised")
            fails += 1

    # Word numbers, including the deliberate ceiling.
    for n, word in ((2, "two"), (7, "seven"), (19, "nineteen"), (20, "twenty")):
        if _word_num(n) != word:
            print(
                f"selftest FAIL: _word_num({n}) == {_word_num(n)!r}, expected {word!r}"
            )
            fails += 1
    try:
        _word_num(21)
    except SystemExit:
        pass
    else:
        print("selftest FAIL: _word_num(21) should refuse rather than invent a word")
        fails += 1

    total = len(_SELFTEST_CASES) + len(_SELFTEST_ERRORS) + 5
    if fails:
        return 1
    print(f"selftest OK ({total} cases)")
    return 0


def main(argv: list[str]) -> int:
    # The rendered prose contains em dashes; a cp1252 console (the Windows
    # default) would raise UnicodeEncodeError on the first print that carries
    # one. Reconfigure rather than strip — the text on disk is UTF-8 either way.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (
            AttributeError,
            ValueError,
        ):  # pragma: no cover - non-reconfigurable stream
            pass

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="rewrite the blocks in place")
    ap.add_argument("--list", action="store_true", help="show the blocks and exit")
    ap.add_argument("--selftest", action="store_true", help="run the fixture test")
    opts = ap.parse_args(argv[1:])

    if opts.selftest:
        return _selftest()
    if opts.list:
        return _list()
    return run(context(), opts.write)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
