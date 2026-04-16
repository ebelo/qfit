# Contributing to qfit

## Code Quality Rules

Before making non-trivial structural changes, also read:

- `docs/architecture.md` — qfit-specific architectural boundaries, dependency direction, and placement rules
- `docs/qgis-plugin-architecture-principles.md` — general QGIS plugin principles plus qfit's pragmatic hexagonal / ports-and-adapters interpretation


All PRs must pass the following before merging:

### SonarCloud (mandatory gate)
- **Never merge if SonarCloud Code Analysis shows `fail`.**
- After pushing, poll `gh pr checks <N>` until all checks complete.
- If SonarCloud fails, retrieve the issues:
  ```bash
  curl -s "https://sonarcloud.io/api/issues/search?projectKeys=ebelo_qfit&pullRequest=<N>&resolved=false" \
    | python3 -c "import json,sys; [print(i['severity'], i['message'], '@', i['component']) for i in json.load(sys.stdin)['issues']]"
  ```
- Fix every flagged issue, commit, push, and wait for re-check before merging.
- Common issues: duplicate string literals (extract to local constant), broad `except Exception` without logging.

### Test coverage (mandatory)
- **New behaviour** → write unit tests that cover it.
- **Bug fix** → add a regression test that would have caught the bug before the fix.
- **Refactor** → all existing tests must still pass; add tests for any previously untested paths.
- Run tests: `python3 -m pytest tests/ -x -q`
- Tests live in `tests/` and must not import QGIS (mock it where needed).

### Tests must pass
- `python3 -m pytest tests/ -x -q` must be green before opening a PR.

### Rendering-proof checklist (mandatory for export-sensitive PRs)
For changes that affect rendered/exported output — especially atlas PDFs, cover pages, table-of-contents pages, profiles, charts, or packaging/runtime-dependent export behaviour — green CI alone is **not** enough.

Include a short validation note in the PR covering the relevant items below:

- **Real-data check:** validated against representative real data when the feature depends on realistic geometry/content, not only synthetic fixtures.
- **Artifact proof:** verified the final exported artifact that users actually consume (for example PDF or PNG), not just intermediate object state or layout configuration.
- **Interactive vs export path:** noted whether the change was checked only interactively, only in export/headless flow, or in both paths when that distinction matters.
- **Packaging/runtime note:** if the feature depends on runtime-packaged pieces (for example `pypdf`, native profile support, SVG generation, or version-specific QGIS behavior), documented what environment/path was checked.
- **Expected output statement:** recorded what “correct output” means for this change so reviewers know what was actually validated.

Use a concise PR note such as:

```markdown
## Rendering proof
- Data: real atlas export dataset / synthetic fixture / both
- Artifact checked: exported PDF page(s), cover page, TOC page, profile graphic, etc.
- Path checked: interactive / export / headless
- Runtime note: packaged plugin dev install / local source checkout / specific QGIS version
- Result: what was visually/functionally confirmed
```

If the change is **not** rendering-sensitive, say so briefly in the PR rather than leaving the question ambiguous.

## Architecture rules

Keep these rules lightweight and practical:

- Prefer feature/workflow ownership over adding more unrelated top-level modules.
- Do not add new top-level Python modules for feature-specific code; prefer the owning feature package (`activities/`, `atlas/`, `providers/`, `visualization/`, `ui/`, `validation/`).
- Treat existing root-level modules as grandfathered transitional modules unless the code is truly shared across features.
- If you touch a transitional root module that now only forwards imports, prefer moving the real implementation in the owned package and keep the root file as a thin compatibility shim instead of re-expanding it.
- Deprecated compatibility shims currently include `activity_classification.py`, `activity_query.py`, `models.py`, `activity_storage.py`, and `layer_manager.py`; new in-repo imports should target their package-owned replacements instead.
- If a new top-level shared module is genuinely needed, document the reason and update `tests/test_architecture_boundaries.py` in the same PR.
- Keep `QfitDockWidget` and other UI classes focused on widget wiring, input mapping, and result rendering.
- Put workflow orchestration into controllers/services/use cases instead of the dock widget where practical.
- Keep provider-neutral activity logic free of direct UI imports and avoid unnecessary QGIS coupling.
- Isolate Strava, GeoPackage, QGIS settings, and QGIS layer details behind clearer seams when that improves clarity or testability.
- Do not add interface/adapter boilerplate unless it solves a real workflow or testing problem.
- Favor small, behavior-preserving refactors over big-bang rewrites.

Preferred dependency direction:

```text
UI -> application/workflow -> domain + ports -> infrastructure adapters
```

Architecture guardrails live in `tests/test_architecture_boundaries.py`. Keep them small, readable, and high-signal.

### Commit style
- `fix: <description> (#<issue>)` for bug fixes
- `feat: <description>` for new features
- `chore:` / `refactor:` / `test:` as appropriate

## Workflow
1. `git checkout main && git pull`
2. `git checkout -b fix/issue-<N>` (or `feat/<slug>`)
3. Implement, test (including new tests), commit
4. `git push -u origin <branch>`
5. `gh pr create --base main --head <branch>`
6. Wait for **all** CI checks including SonarCloud to pass
7. `gh pr merge --merge --delete-branch`
