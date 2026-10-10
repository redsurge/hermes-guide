#!/usr/bin/env python3
"""Fail when the issue-template surface and the docs that describe it diverge.

Three defects in this repo's history were the same shape: a doc named a path
the reporter could not actually use.

* CONTRIBUTING.md told a reporter to pick ``config.yml`` as one of three
  templates. It is the chooser, not a form, so selecting it does nothing.
* CONTRIBUTING.md said a question is not a defect report, then pointed at
  the issue tracker -- while ``blank_issues_enabled: false`` meant there was
  no such route. A reader had nowhere to go.
* A contact link to ``https://github.com.attacker.example`` passed a
  substring test for ``github.com``.

Stdlib only, on purpose. Every other gate in this tier is stdlib only
because ``PyYAML`` is installed in a full-gate step, not a fast-tier one --
importing it here breaks every matrix leg on a direct push. So the small,
fixed schema is read directly: :func:`read_chooser` fails *closed* on any line
it does not understand, and forms only need two top-level scalars, which
:func:`top_scalar` reads without parsing the body at all.

Scope: files in the issue-template directory only. Deliberately *not* a
general "every filename in the docs exists" check -- the docs legitimately
name Hermes-side files (``config.yaml`` is ``~/.hermes/config.yaml``, not
this repo's ``.github/ISSUE_TEMPLATE/config.yml``), and ``hermes_constants.py``
lives upstream.

Usage:
    python tools/check_issue_templates.py
    python tools/check_issue_templates.py --selftest
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = Path(".github") / "ISSUE_TEMPLATE"
CHOOSER = "config.yml"
CONTACT_LINKS = "contact_links"
_LINK_KEYS = frozenset({"name", "url", "about"})

# A doc has promised a non-defect route if it says either of these.
_PROMISE = re.compile(r"^##\s+Questions?\b|not a defect report", re.MULTILINE | re.IGNORECASE)
# What counts as offering one: a form or link named for questions.
_ROUTE = re.compile(r"question|discussion|ask|help", re.IGNORECASE)

# The only legitimate destinations for a contact link. A substring test for
# "github.com" would accept github.com.attacker.example.
_GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})

# Docs allowed to describe the reporter-facing surface.
_DOCS = ("CONTRIBUTING.md", "README.md", "AGENTS.md")

# GitHub accepts .yml and .yaml forms. Globbing only one leaves a broken form
# of the other spelling invisible to every check here.
_FORMS = "*.y*ml"


def top_scalar(text: str, key: str) -> str | None:
    """The first top-level ``key: value`` in ``text``, unquoted, or None.

    Forms carry a large body this guard never inspects, so it reads the one
    field it needs instead of parsing the file.

    A ``#`` preceded by whitespace starts a comment in YAML, so ``name: # fill
    this in`` is a null value -- PyYAML returns None for it, and this must too,
    or the guard accepts a form whose chooser entry GitHub will not render.
    """
    pattern = re.compile(rf"^{key}:[ \t]*(.*?)[ \t]*$")
    for line in text.splitlines():
        if not line or line[:1].isspace() or line.lstrip().startswith("#"):
            continue
        match = pattern.match(line)
        if match:
            return _scalar(match.group(1)) or None
    return None


def _scalar(raw: str) -> Any:
    """A YAML scalar, with comments stripped the way YAML strips them."""
    raw = raw.strip()
    if raw.startswith("#"):
        return ""  # a comment is the whole value, so the field is null
    if raw and raw[0] in "\"'":
        end = raw.find(raw[0], 1)
        return raw[1:end] if end > 0 else ""
    raw = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
    if raw in ("true", "True"):
        return True
    if raw in ("false", "False"):
        return False
    return raw


def read_chooser(text: str) -> tuple[dict[str, Any], list[str]]:
    """Parse the chooser's fixed schema. Returns (data, problems).

    Understands exactly: a top-level ``key: value``, a top-level
    ``contact_links:`` followed by ``- key: value`` items with indented
    fields. Anything else becomes a problem rather than a silent omission, so
    a config that grows a feature this reader does not know about is reported
    instead of quietly passing.
    """
    data: dict[str, Any] = {}
    problems: list[str] = []
    links: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_links = False

    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        item = stripped.startswith("- ")
        body = stripped[2:].strip() if item else stripped

        if ":" not in body:
            # Report before registering a link: an unparseable item must not
            # leave an empty dict behind to be reported a second time as a
            # missing-keys failure.
            problems.append(f"line {lineno}: cannot parse {stripped!r}")
            continue
        key, _, raw = body.partition(":")
        key, raw = key.strip(), _scalar(raw.strip())

        if item:
            if not in_links:
                # A list item before any `contact_links:` key is invalid YAML
                # (PyYAML raises), and must not be read as a configured link.
                # Still absorb the item's fields so the single reported cause
                # is not followed by one message per indented line.
                problems.append(f"line {lineno}: list item outside {CONTACT_LINKS}")
                in_links = True
            current = {}
            links.append(current)
            indent = max(indent, 2)

        if item or (in_links and indent > 0):
            if current is None:  # pragma: no cover - a list item opens one above
                problems.append(f"line {lineno}: indented field outside a contact link")
            else:
                current[key] = raw
        elif key == CONTACT_LINKS and raw == "":
            in_links = True
        elif indent == 0:
            data[key] = raw
        else:
            problems.append(f"line {lineno}: unexpected indentation at {stripped!r}")

    if CONTACT_LINKS in data:
        problems.append(f"{CONTACT_LINKS} must be a list of mappings, not a scalar")
    else:
        data[CONTACT_LINKS] = links
    return data, problems


def check_forms(templates: Path) -> list[str]:
    """Every non-chooser template declares name and description.

    GitHub builds the chooser entry from those two fields. A form missing
    either renders blank or is skipped, and the reporter never sees it.
    """
    bad: list[str] = []
    for form in sorted(templates.glob(_FORMS)):
        if form.name == CHOOSER:
            continue
        text = form.read_text(encoding="utf-8")
        for field in ("name", "description"):
            if top_scalar(text, field) is None:
                bad.append(f"{form.name}: missing or empty {field!r} (chooser entry would be blank)")
    return bad


def check_chooser(templates: Path) -> list[str]:
    """Validate the chooser: schema, link hygiene, no duplicate destinations."""
    path = templates / CHOOSER
    if not path.is_file():
        return [f"{CHOOSER}: missing -- GitHub needs it to pick the templates"]

    data, problems = read_chooser(path.read_text(encoding="utf-8"))
    if problems:
        # One root cause, one message. Every check below reads `data`, so
        # running them on a file this reader could not parse would report
        # consequences of the parse failure as separate defects.
        return [f"{CHOOSER}: {p}" for p in problems]
    bad: list[str] = []

    blank = data.get("blank_issues_enabled")
    if not isinstance(blank, bool):
        bad.append(f"{CHOOSER}: blank_issues_enabled must be a bool, got {blank!r}")

    links = data.get(CONTACT_LINKS) or []
    if blank is False and not links:
        bad.append(f"{CHOOSER}: blank issues disabled but no contact_links to reach")

    seen: dict[str, int] = {}
    for i, link in enumerate(links):
        where = f"{CHOOSER}: contact_links[{i}]"
        if set(link) != _LINK_KEYS:
            bad.append(f"{where}: keys must be exactly {sorted(_LINK_KEYS)}, got {sorted(link)}")
            continue
        for field, value in link.items():
            if not isinstance(value, str):
                bad.append(f"{where}: {field!r} must be a string, got {type(value).__name__}")
            elif not value.strip():
                bad.append(f"{where}: empty {field!r}")
        url = link.get("url", "")
        if not isinstance(url, str) or not url.strip():
            continue  # already reported by the field loop above
        parsed = urlparse(url)
        if parsed.scheme != "https":
            bad.append(f"{where}: url must be https, got {url!r}")
        elif (parsed.hostname or "").lower() not in _GITHUB_HOSTS:
            bad.append(f"{where}: url must be on github.com, got host {parsed.hostname!r}")
        seen[url] = seen.get(url, 0) + 1
    for url, n in seen.items():
        if n > 1:
            bad.append(f"{CHOOSER}: {url} offered {n} times; keep one entry per destination")
    return bad


def check_route_exists(repo: Path) -> list[str]:
    """A doc promising questions must not promise a route that is absent.

    Only binding when blank issues are off: with them on a reader can file a
    plain issue, so the promise needs no separate route.
    """
    promising = [
        name
        for name in _DOCS
        if (repo / name).is_file()
        and _PROMISE.search((repo / name).read_text(encoding="utf-8"))
    ]
    if not promising:
        return []

    templates = repo / TEMPLATES
    if not (templates / CHOOSER).is_file():
        return []  # check_chooser already reports the missing chooser
    chooser, _ = read_chooser((templates / CHOOSER).read_text(encoding="utf-8"))
    if chooser.get("blank_issues_enabled") is not False:
        return []

    routes = [
        f"{link.get('name','')} {link.get('url','')} {link.get('about','')}"
        for link in chooser.get(CONTACT_LINKS) or []
    ]
    for form in sorted(templates.glob(_FORMS)):
        if form.name == CHOOSER:
            continue
        # The chooser-visible name only. A reporter sees that, not the filename,
        # so a defect form filed as help.yml offers no question route.
        routes.append(top_scalar(form.read_text(encoding="utf-8"), "name") or "")

    if any(_ROUTE.search(r) for r in routes):
        return []

    return [
        f"{', '.join(promising)} tells the reader a question is not a defect report, but no "
        f"form or contact_links entry accepts one (blank_issues_enabled is False)"
    ]


def check(repo: Path) -> list[str]:
    templates = repo / TEMPLATES
    if not templates.is_dir():
        return [f"{TEMPLATES}: missing"]
    return check_forms(templates) + check_chooser(templates) + check_route_exists(repo)


def selftest() -> int:
    bug_only = "name: Bug\ndescription: d\n"
    link = (
        "blank_issues_enabled: false\n"
        "contact_links:\n"
        "  - name: Hermes core bug\n"
        "    url: https://github.com/NousResearch/hermes-agent/issues\n"
        "    about: Upstream.\n"
    )
    ask_link = (
        "blank_issues_enabled: false\n"
        "contact_links:\n"
        "  - name: Question about a skill\n"
        "    url: https://github.com/redsurge/hermes-guide/discussions\n"
        "    about: Ask here.\n"
    )
    promise = "## Questions\n\nA question is not a defect report.\n"
    https_only = "blank_issues_enabled: false\ncontact_links:\n"

    # (templates, docs, expected failure fragments)
    cases: list[tuple[dict[str, str], dict[str, str], list[str]]] = [
        # --- the #147 defect: docs promise a route, nothing offers one ---
        ({"config.yml": link}, {"CONTRIBUTING.md": promise},
         ["no form or contact_links entry accepts one"]),
        ({"config.yml": link, "bug-report.yml": bug_only}, {"CONTRIBUTING.md": promise},
         ["no form or contact_links entry accepts one"]),
        # --- blank issues on: a plain issue is available, so no route needed ---
        ({"config.yml": "blank_issues_enabled: true\n", "bug-report.yml": bug_only},
         {"CONTRIBUTING.md": promise}, []),
        # --- the promise is satisfied by a link, or by a form ---
        ({"config.yml": ask_link, "bug-report.yml": bug_only},
         {"CONTRIBUTING.md": promise}, []),
        ({"config.yml": link, "question.yml": "name: Question\ndescription: ask away\n"},
         {"CONTRIBUTING.md": promise}, []),
        # --- no promise, so the routes are nobody's problem ---
        ({"config.yml": link}, {"CONTRIBUTING.md": "nothing here\n"}, []),
        # Blank issues off with nowhere to send anyone is still a defect.
        ({"config.yml": "blank_issues_enabled: false\n", "bug-report.yml": bug_only}, {},
         ["no contact_links to reach"]),
        # --- chooser schema ---
        ({"config.yml": "blank_issues_enabled: maybe\n"}, {}, ["must be a bool"]),
        ({"config.yml": https_only + "  - name: A\n    url: http://github.com/o/r\n    about: z\n"}, {},
         ["url must be https"]),
        ({"config.yml": https_only + "  - name: A\n    url: https://example.org/o/r\n    about: z\n"}, {},
         ["must be on github.com"]),
        # A lookalike host must not pass a substring test.
        ({"config.yml": https_only + "  - name: A\n    url: https://github.com.attacker.example/q\n"
                         "    about: z\n"}, {}, ["must be on github.com"]),
        ({"config.yml": https_only + "  - name: A\n    url: https://evil.test/github.com\n"
                         "    about: z\n"}, {}, ["must be on github.com"]),
        ({"config.yml": https_only + "  - name: A\n    url: https://github.com/o/r\n    about: z\n"
                         "  - name: B\n    url: https://github.com/o/r\n    about: z2\n"}, {},
         ["offered 2 times"]),
        ({"config.yml": https_only + "  - name: A\n    url: https://github.com/o/r\n"}, {},
         ["keys must be exactly"]),
        ({"config.yml": "blank_issues_enabled: false\n"}, {},
         ["no contact_links to reach"]),
        # Fail closed: a schema this reader does not know is reported, not skipped.
        ({"config.yml": "blank_issues_enabled: false\nlabels:\n  - one\n"}, {},
         ["cannot parse"]),
        ({}, {}, ["config.yml: missing"]),
        # --- the four findings from review ---
        # A non-string url must be reported, not handed to urlparse.
        ({"config.yml": https_only + "  - name: A\n    url: true\n    about: z\n"}, {},
         ["'url' must be a string, got bool"]),
        # A promise with no chooser at all is check_chooser's finding, not a crash.
        ({"bug-report.yml": bug_only}, {"CONTRIBUTING.md": promise},
         ["config.yml: missing"]),
        # A list item with no `contact_links:` key above it is invalid YAML,
        # and must not be read as a configured link.
        ({"config.yml": "blank_issues_enabled: false\n- name: A\n"
                        "  url: https://github.com/redsurge/hermes-guide/discussions\n"
                        "  about: no key above me\n"}, {},
         ["list item outside contact_links"]),
        # The chooser shows `name`, never the filename: a defect form called
        # help.yml offers no question route.
        ({"config.yml": link, "help.yml": "name: Bug report\ndescription: a defect\n"},
         {"CONTRIBUTING.md": promise}, ["no form or contact_links entry accepts one"]),
        # `name: # fill this in` is null in YAML, so the entry would not render.
        ({"config.yml": link, "bug-report.yml": "name: # fill this in\ndescription: d\n"}, {},
         ["missing or empty 'name'"]),
        # A '#' inside a quoted value is data, not a comment.
        ({"config.yml": https_only + "  - name: A # note\n    url: https://github.com/o/r\n"
                         "    about: z\n"}, {}, []),
        # --- forms ---
        ({"config.yml": link, "bug-report.yml": "description: d\n"}, {},
         ["missing or empty 'name'"]),
        ({"config.yml": link, "bug-report.yml": "name: B\n"}, {},
         ["missing or empty 'description'"]),
        ({"config.yml": link, "bug-report.yml": bug_only}, {}, []),
        # A .yaml form is a form; a broken one must not hide behind the spelling.
        ({"config.yml": link, "bug-report.yaml": "description: d\n"}, {},
         ["missing or empty 'name'"]),
        ({"config.yml": link, "question.yaml": "name: Question\ndescription: ask\n"},
         {"CONTRIBUTING.md": promise}, []),
    ]

    failures = 0
    for templates, docs, expect in cases:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tdir = root / TEMPLATES
            tdir.mkdir(parents=True)
            for name, body in templates.items():
                (tdir / name).write_text(body, encoding="utf-8")
            for name, body in docs.items():
                (root / name).write_text(body, encoding="utf-8")
            got = check(root)

        # An empty `expect` asserts the tree is clean; a non-empty one also
        # rejects unexpected extra failures. Without the first half, every
        # positive case passes no matter what the guard returns.
        if expect:
            bad = [f"missing {e}" for e in expect if not any(e in g for g in got)]
            bad += [f"unexpected {g}" for g in got if not any(e in g for e in expect)]
        else:
            bad = [] if not got else [f"expected a clean tree, got {got}"]
        if bad:
            failures += 1
            print(f"SELFTEST FAIL {sorted(templates)}: " + "; ".join(bad), file=sys.stderr)

    if failures:
        print(f"error: {failures}/{len(cases)} selftest case(s) failed", file=sys.stderr)
        return 1
    print(f"OK: selftest {len(cases)} case(s) passed")
    return 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()

    bad = check(REPO)
    if bad:
        print("FAIL: issue-template surface does not match the docs:", file=sys.stderr)
        for line in bad:
            print(f"  {line}", file=sys.stderr)
        print(
            "\nA reporter must be able to follow the docs literally. If a route\n"
            "changes, update CONTRIBUTING.md and the chooser together.",
            file=sys.stderr,
        )
        return 1

    templates = REPO / TEMPLATES
    chooser, _ = read_chooser((templates / CHOOSER).read_text(encoding="utf-8"))
    n_forms = len([p for p in templates.glob(_FORMS) if p.name != CHOOSER])
    print(
        f"OK: {n_forms} template(s), "
        f"{len(chooser.get(CONTACT_LINKS) or [])} contact link(s), docs agree"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))