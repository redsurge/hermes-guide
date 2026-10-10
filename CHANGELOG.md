# Changelog

All notable changes to hermes-guide are documented here.

## v0.7.0 (2026-10-10)

### Features

- add changelog generator and proactive version check ([#178](https://github.com/redsurge/hermes-guide/pull/178))
- **diagnosing-cli-tui**: add ConPTY inline mode, expand upstream issue states ([#176](https://github.com/redsurge/hermes-guide/pull/176))
- **skills**: add Report sections to all 17 diagnostic skills (#168) ([#175](https://github.com/redsurge/hermes-guide/pull/175))
- **skills**: add standard diagnosis report format (#168) ([#174](https://github.com/redsurge/hermes-guide/pull/174))
- **skills**: add diagnosing-triage meta-skill ([#173](https://github.com/redsurge/hermes-guide/pull/173))

### Bug Fixes

- address CodeRabbit follow-up findings on version check ([#181](https://github.com/redsurge/hermes-guide/pull/181))
- **triage**: move host-pressure branch before per-surface branches ([#177](https://github.com/redsurge/hermes-guide/pull/177))

### Chores

- **release**: bump to 0.7.0 ([#182](https://github.com/redsurge/hermes-guide/pull/182))

## v0.6.0 (2026-10-07)

### Features

- **skills**: add diagnosing-host-pressure

### Bug Fixes

- **skills**: update 4 broken upstream citations ([#165](https://github.com/redsurge/hermes-guide/pull/165))
- **ci**: use already-cloned Hermes install for citation check ([#164](https://github.com/redsurge/hermes-guide/pull/164))
- **checks**: replace try/except/pass with an early return in the fast path ([#159](https://github.com/redsurge/hermes-guide/pull/159))
- **checks**: treat timeout as a deadline, not per-attempt ([#155](https://github.com/redsurge/hermes-guide/pull/155))
- **tests**: monkeypatch _hermes_home_from_library in memory hygiene test ([#154](https://github.com/redsurge/hermes-guide/pull/154))
- **checks**: stop reporting loader-valid skills as broken ([#152](https://github.com/redsurge/hermes-guide/pull/152))
- **ci**: find the install pin wherever the workflow files keep it ([#149](https://github.com/redsurge/hermes-guide/pull/149))
- resolve issue #119 ([#142](https://github.com/redsurge/hermes-guide/pull/142))
- **checks**: resolve all PATH hermes, raise CLI budgets ([#146](https://github.com/redsurge/hermes-guide/pull/146))
- **ci**: wire the orphan skill-name test, and guard against new orphans ([#139](https://github.com/redsurge/hermes-guide/pull/139))
- **ci**: gate the remaining dependency-requiring CI steps ([#138](https://github.com/redsurge/hermes-guide/pull/138))
- **ci**: gate the MCP shape regression test behind the full tier ([#136](https://github.com/redsurge/hermes-guide/pull/136))
- **ci**: match the plural in the claim judge's OUTCOME vocabulary ([#129](https://github.com/redsurge/hermes-guide/pull/129))
- **ci**: guard the pyproject.toml version literal ([#132](https://github.com/redsurge/hermes-guide/pull/132))
- **checks**: a malformed frontmatter name must not crash check_skills ([#133](https://github.com/redsurge/hermes-guide/pull/133))
- **checks**: resolve the hermes executable instead of trusting PATH ([#125](https://github.com/redsurge/hermes-guide/pull/125))
- **tools**: limit uncapped reports to dry runs; harden the cap tests
- **tools**: never trim the drift report footer; add an uncapped local mode
- **tools**: cap the drift issue body inside GitHub's 65,536-char limit
- **tools**: catch obsolete skill options in the skill-drift guard
- **tools**: keep the skill-drift template in step with the inventory
- **tools**: reject skill version downgrades in the bump guard
- **skills**: container CPU verdict from live signals, not stale counters
- **skills**: close the three container gaps in the host-pressure probe
- **skills**: correct the swap reading, container scope, and timeout wording
- **skills**: correct four wrong readings in the host-pressure probe
- **skills**: drop the literal citation token from the provenance footer
- **skills**: branch swap detection on OS, not on vm_stat being present
- **ci**: match the real /proc load figure instead of a substring test
- **ci**: assert the Linux /proc wiring, not an unreachable stubbed load
- **ci**: run the probe behavioral test on the Linux legs only
- **skills**: correct idle regex, core count, Linux load path, D-threshold, stale-log DOWN claim; add behavioral regression test
- **skills,tests**: correct citation token; fix probe idle parser, linux path, core count, D-threshold, stale-log DOWN claim, README list; add behavioral regression test; wire into CI

### Performance

- **checks**: derive $HERMES_HOME from hermes_constants, skip config path subprocess ([#153](https://github.com/redsurge/hermes-guide/pull/153))

### Documentation

- **skills**: add creation flows and duplicate-consolidation playbook ([#158](https://github.com/redsurge/hermes-guide/pull/158))
- **skills**: add disambiguation boundaries across the diagnosing suite ([#157](https://github.com/redsurge/hermes-guide/pull/157))
- set output style, and make the contributor intro actionable ([#147](https://github.com/redsurge/hermes-guide/pull/147))
- allow release details where a claim depends on them
- keep PR environment lines OS-name-only
- **skills**: fix the documented probe path; restore the plugins version

### CI

- **tools**: add read-only dogfood check against a live Hermes install ([#156](https://github.com/redsurge/hermes-guide/pull/156))
- schedule Dependabot updates for the SHA-pinned actions ([#150](https://github.com/redsurge/hermes-guide/pull/150))
- **tools**: refuse docs that promise a reporter route that does not exist ([#148](https://github.com/redsurge/hermes-guide/pull/148))
- label OS and priority from the PR description ([#130](https://github.com/redsurge/hermes-guide/pull/130))
- split CI into a reusable workflow and machine-check PR validation claims ([#128](https://github.com/redsurge/hermes-guide/pull/128))

### Chores

- build(deps): bump actions/github-script (#151)
- **release**: bump to 0.6.0; guard _plugin_skill_names against an unhashable name ([#135](https://github.com/redsurge/hermes-guide/pull/135))
- build: declare project metadata in pyproject.toml (#131)
- drift: bump upstream baseline to 5000e299; refresh venv facts; retry ls-remote flakes (#124)
- Merge pull request #122 from iap/fix/drift-body-cap
- Merge pull request #115 from iap/fix/self-check-hardening
- Merge pull request #114 from iap/feat/skills-host-pressure
- **repo**: add hermetic gate runner and pre-commit hook

### Refactoring

- **docs**: give each guide one job, and generate their counts ([#141](https://github.com/redsurge/hermes-guide/pull/141))

### Tests

- **tools**: keep the flag tests independent of the shell environment
- **skills**: pin the container CPU decisions with controlled inputs

## v0.5.1 (2026-09-23)

### Bug Fixes

- **checks**: measure memory limits the way the runtime does
- **ci**: bound the routing-coverage check to the Routing section
- **skills**: route the map to the five v0.5.0 skills; guard routing coverage

### Chores

- Merge pull request #113 from iap/chore/release-0.5.1
- **release**: v0.5.1
- Merge pull request #112 from iap/fix/memory-limit-measurement
- Merge pull request #111 from iap/fix/configuration-map-routing-coverage

## v0.5.0 (2026-09-23)

### Features

- **skills**: add diagnosing skills for bot-mode, browser, cron, gateway, voice

### Bug Fixes

- **skills**: describe providers probe in prose, not executable code
- **skills**: replace curl|python probe in diagnosing-providers
- **skills**: remove sudo from ffmpeg install guidance
- **skills**: correcting memory.provider semantics in bot-mode guide
- **skills**: address Greptile review findings for bot-mode, voice, browser, gateway
- **version**: align SECURITY.md and __version__ with plugin.yaml ([#102](https://github.com/redsurge/hermes-guide/pull/102))

### Documentation

- **agents**: align AGENTS.md with CI, layers, and publish surface ([#101](https://github.com/redsurge/hermes-guide/pull/101))

### Chores

- Merge pull request #109 from iap/chore/release-bump-0.5.0
- Merge pull request #110 from iap/drift/baseline-bump-v2026.9.21
- drift: bump upstream baseline to 2f6170bf; re-point two moved citations; CI pin to v2026.9.21
- **release**: bump to 0.5.0
- **skills**: close the provenance-footer gap, flip guard to enforcing

## v0.4.0 (2026-09-16)

### Features

- **ci**: tag-gated releases; audit doc fixes; mypy floor 3.11 ([#72](https://github.com/redsurge/hermes-guide/pull/72))
- **skills**: add diagnosing-providers skill for custom model endpoints ([#69](https://github.com/redsurge/hermes-guide/pull/69))
- **checks**: guide-skill adoption nudge; one-command install-all in README ([#65](https://github.com/redsurge/hermes-guide/pull/65))

### Bug Fixes

- **ci**: reject malformed and empty provenance scans
- **skills**: diagnosing-auth names the current not-found strings
- **checks**: render unversioned correctly and keep hooks-doctor findings
- **skills**: correct stale citations and restore the desktop port-announce facts; add citation-integrity check ([#94](https://github.com/redsurge/hermes-guide/pull/94))
- **skills**: de-obfuscate Bearer token in curl example to pass scanner ([#76](https://github.com/redsurge/hermes-guide/pull/76))
- **checks**: discover portable plugin.json plugins â€” pstack false positive ([#75](https://github.com/redsurge/hermes-guide/pull/75))
- hermes-achievements and kanban are NOT subcategories
- **tools**: count-guard docstring covers CONTRIBUTING.md ([#73](https://github.com/redsurge/hermes-guide/pull/73))
- harden upstream-drift history review and dedup ([#68](https://github.com/redsurge/hermes-guide/pull/68))
- **doctor**: preserve subprocess exception detail in the unknown envelope

### Documentation

- **diagnosing-providers**: document key_cmd precedence and the api_key_env alias ([#92](https://github.com/redsurge/hermes-guide/pull/92))
- corrective pass 2 for the review findings left on merged PRs #80-#84 ([#91](https://github.com/redsurge/hermes-guide/pull/91))
- corrective pass for the review findings left on merged PRs #85-#89 ([#90](https://github.com/redsurge/hermes-guide/pull/90))
- **config-guide**: precision on project-context discovery; citation and labels ([#89](https://github.com/redsurge/hermes-guide/pull/89))
- **diagnosing-desktop**: fix the module pointer; flag unverified timeout numbers ([#88](https://github.com/redsurge/hermes-guide/pull/88))
- **diagnosing-plugins**: correct a nonexistent capability id; annotate the sub-category list ([#86](https://github.com/redsurge/hermes-guide/pull/86))
- **diagnosing-mcp**: cite verified fields; flag four unverifiable specifics
- **diagnosing-hooks**: inline source citations for every number (all verified) ([#85](https://github.com/redsurge/hermes-guide/pull/85))
- **diagnosing-commands**: source pointers for every load-bearing fact (all verified) ([#84](https://github.com/redsurge/hermes-guide/pull/84))
- **diagnosing-skills**: external dirs are read-only upstream; add session_platforms ([#83](https://github.com/redsurge/hermes-guide/pull/83))
- **diagnosing-memory**: provider-list nuance, unverified quote softened, temporary/permanent labels ([#82](https://github.com/redsurge/hermes-guide/pull/82))
- **diagnosing-auth**: fix module path + error strings; verify mechanism at current main ([#81](https://github.com/redsurge/hermes-guide/pull/81))
- **diagnosing-cli-tui**: verify against source + live installs; fix stale facts ([#80](https://github.com/redsurge/hermes-guide/pull/80))
- **diagnosing-path**: verify against source + live layouts; fix stale citations ([#78](https://github.com/redsurge/hermes-guide/pull/78))
- **skills**: state.db size and compaction diagnosis in diagnosing-memory ([#70](https://github.com/redsurge/hermes-guide/pull/70))
- **installing-hermes**: two-step installer â€” avoids the curl|bash critical, adds review-before-run ([#63](https://github.com/redsurge/hermes-guide/pull/63))
- **skills**: add installing-hermes â€” install routes, layouts, NixOS WSL gotchas ([#60](https://github.com/redsurge/hermes-guide/pull/60))

### CI

- **provenance**: require a dated upstream footer per skill
- also trigger on `edited` so a retarget runs checks
- run the workflow on pull requests to any base branch
- verify skill citations against the upstream baseline on every push ([#95](https://github.com/redsurge/hermes-guide/pull/95))
- test python 3.11 + 3.12 matrix (floor tracks upstream) ([#71](https://github.com/redsurge/hermes-guide/pull/71))

### Chores

- Merge pull request #100 from iap/chore/release-bump-0.4.0
- **release**: bump plugin.yaml to 0.4.0
- Merge pull request #99 from iap/ci/skill-provenance-guard
- Merge pull request #98 from iap/fix/diagnosing-auth-not-found-strings
- Merge pull request #97 from iap/fix/plugin-check-envelopes
- Merge pull request #96 from iap/ci/pr-trigger-any-base
- drift: bump upstream baseline to cedf4a3d; CI pin to v2026.9.14 (#93)
- Merge pull request #87 from iap/fix/diagnosing-mcp-verified-fields
- drift: bump upstream baseline to 9326d9cd; verify asserted facts at upstream main (#79)
- Merge pull request #74 from iap/drift/baseline-bump-v2026.9.11
- drift: bump upstream baseline to bf51fee (v2026.9.11)
- Merge pull request #66 from iap/fix/doctor-review-findings
- drift: bump upstream baseline to 8aa219ef; CI pin to v2026.9.7 (#64)
- drift: bump upstream baseline to 22c5684b (schema v41, delegation.compression_threshold_tokens, anthropic_wire auto, plugins memory-hook fallback registrations) (#61)

### Tests

- **ci**: run the check-envelope regression in CI
- lock the guide CLI exit contract (exit 1 iff broken/unknown) ([#67](https://github.com/redsurge/hermes-guide/pull/67))

## v0.3.1 (2026-09-07)

### Bug Fixes

- **test**: isolate the fixture from global git config ([#54](https://github.com/redsurge/hermes-guide/pull/54))
- **ci**: authenticate the tap smoke test (GH_TOKEN) ([#52](https://github.com/redsurge/hermes-guide/pull/52))
- **skills**: teach the entry-dating rule the memories check enforces ([#51](https://github.com/redsurge/hermes-guide/pull/51))
- **skills**: scanner false-positive rewords + auth inspect/tap symptom
- **skills**: clear scanner verdicts blocking tap installs of memory/desktop ([#48](https://github.com/redsurge/hermes-guide/pull/48))

### Documentation

- **agents**: record the multi-environment ownership split ([#57](https://github.com/redsurge/hermes-guide/pull/57))

### CI

- enforce the version-bump guard; skill fact fixes verified against the installed CLI ([#53](https://github.com/redsurge/hermes-guide/pull/53))
- derive the tap smoke test's skill list from the checkout ([#50](https://github.com/redsurge/hermes-guide/pull/50))

### Chores

- bump plugin to 0.3.1 ([#58](https://github.com/redsurge/hermes-guide/pull/58))
- re-baseline upstream drift to 5106e939
- Merge pull request #49 from iap/fix/scanner-false-positives
- re-trigger external review (Greptile did not register on prior head)

## v0.3.0 (2026-09-06)

### Features

- **skills**: add diagnosing-desktop skill
- **memory**: read-only memory hygiene check (memories scope)
- **skills**: add diagnosing-memory skill
- **skills**: add diagnosing-auth â€” hub-install auth failures ([#36](https://github.com/redsurge/hermes-guide/pull/36))
- **guide**: add diagnosing-path skill, expand docs, add naming conventions ([#23](https://github.com/redsurge/hermes-guide/pull/23))
- verify drift-prone MCP facts against upstream in drift CI ([#15](https://github.com/redsurge/hermes-guide/pull/15))
- add upstream schema drift-detection CI ([#11](https://github.com/redsurge/hermes-guide/pull/11))
- distinguish bundled skills, skip archive dirs, show versions in collisions ([#7](https://github.com/redsurge/hermes-guide/pull/7))

### Bug Fixes

- **ci**: run the count guard in CI; exact scope-list comparison
- **drift**: keep workflow WATCH_FILES in sync with checker default
- **memory**: address Greptile review â€” undated counts, empty-store health, narrow mis-target regex, regression tests
- venv-order drift, drift-watcher coverage, repo facts (review follow-up) ([#38](https://github.com/redsurge/hermes-guide/pull/38))
- **plugin**: revert to manifest_version 1 for installer compatibility ([#24](https://github.com/redsurge/hermes-guide/pull/24))
- match the scope filter against check labels exactly ([#17](https://github.com/redsurge/hermes-guide/pull/17))
- reachable allowlist check, plugin-note false positives, constants drift ([#16](https://github.com/redsurge/hermes-guide/pull/16))
- watch official hermes-agent skill content in drift check ([#13](https://github.com/redsurge/hermes-guide/pull/13))
- harden bundle slug, skip model-providers, drop observability ([#9](https://github.com/redsurge/hermes-guide/pull/9))

### Documentation

- **desktop**: scope the torn-bundle heuristic honestly
- **config**: orphaned-settings reference + config-schema drift watch
- **agents**: remove stale duplicate checklist and dead CoC table row
- **auth**: front-load the literal 'Could not fetch' symptom in the description ([#37](https://github.com/redsurge/hermes-guide/pull/37))
- positioning â€” complements the built-in doctor/helpers, never replaces ([#35](https://github.com/redsurge/hermes-guide/pull/35))
- fix polish items from review (follow-up) ([#34](https://github.com/redsurge/hermes-guide/pull/34))
- **hooks,skills**: absorb upstream drift through 64b96bb; re-baseline ([#32](https://github.com/redsurge/hermes-guide/pull/32))
- document hermes -z/--oneshot, align description house-style with practice ([#31](https://github.com/redsurge/hermes-guide/pull/31))
- **skills**: unblock two scanner false positives + resolve active config first ([#29](https://github.com/redsurge/hermes-guide/pull/29))
- **skills**: fix machine-deixis, platform overload, routing gaps; verify access-split wording ([#26](https://github.com/redsurge/hermes-guide/pull/26))
- **skills**: complete README, unify naming, fix claims, add related_skills frontmatter ([#25](https://github.com/redsurge/hermes-guide/pull/25))
- add venv convention to common pitfalls ([#22](https://github.com/redsurge/hermes-guide/pull/22))
- fix CLI subcommand name in plugin docstring (hermes guide) ([#21](https://github.com/redsurge/hermes-guide/pull/21))
- fix skills install identifier and plugin registration claim ([#14](https://github.com/redsurge/hermes-guide/pull/14))

### CI

- promote the windows leg to required ([#47](https://github.com/redsurge/hermes-guide/pull/47))
- **drift**: cover the memory facts (delimiter, char limits) ([#43](https://github.com/redsurge/hermes-guide/pull/43))
- coverage â€” tap-discovery smoke test + windows matrix (experimental) ([#39](https://github.com/redsurge/hermes-guide/pull/39))
- issue/PR templates, PR auto-labeler, label drift issues at creation ([#33](https://github.com/redsurge/hermes-guide/pull/33))

### Chores

- Merge pull request #46 from iap/feat/diagnosing-desktop
- Merge pull request #45 from iap/test/skill-count-guard
- Merge pull request #44 from iap/docs/orphaned-settings
- Merge master into docs/orphaned-settings
- Merge pull request #42 from iap/feat/memory-hygiene-check
- Merge pull request #41 from iap/feat/diagnosing-memory
- Merge pull request #40 from iap/docs/agents-cleanup
- hermes-guide plugin: v0.2.0 manifest (manifest v2) + bundle diagnose-cli-tui skill (#20)
- re-baseline upstream drift to 9ab056d ([#19](https://github.com/redsurge/hermes-guide/pull/19))
- Add MCP shape regression test to CI (#12)
- checks: suppress mypy import-not-found for runtime-only hermes_cli import (#8)
- checks: robust hooks parsing, builtin collision detection, version bump guard
- Fix slug-collision message and flag dead `disabled:` MCP key (#6)
- Fix plugins check to resolve bundled plugins (#5)
- Fix manifest_version to 1 so the plugin installs on Hermes <= 0.20.1 (#4)
- Potential fix for code scanning alert no. 2: Workflow does not contain permissions (#3)
- Enforce read-only contract with a no-mutation CI guard (#2)
- Fix health-check false positives and a crash (#1)
- Add docs self-claim guard and writing-style convention
- Harden checks: dedupe frontmatter parsing, malformed bundles, missing plugins
- README: drop self-claim phrasing
- Document branch naming convention
- Fix CI: install Hermes via editable git install
- Harden plugin: BOM-safe frontmatter, sanitize skill names, drop dead constants, parsed MCP foreign-key check
- Add hermes-guide plugin and skills tap
- Initial commit

### Refactoring

- drop plugin-bundled skills, use skills tap install ([#10](https://github.com/redsurge/hermes-guide/pull/10))

### Tests

- **skills**: enforce skill/check counts across README and AGENTS.md
