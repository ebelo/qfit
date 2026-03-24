# Contributing to qfit

## Code Quality Rules

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
