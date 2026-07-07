# qfit Testing Policy

## Principle

qfit supports QGIS 3 and QGIS 4 from one source tree. The plugin runtime
surface must be tested against real QGIS environments before any PR is
merged.

Unit tests without QGIS (the default CI job) catch logic errors, but they
**cannot** catch Qt/PyQGIS import-surface differences between Qt 5 and Qt 6.
That gap has shipped real crashes. Docker QGIS images close it.

## Mandatory test environments

| Environment | Image | Qt version | What it catches |
|---|---|---|---|
| No-QGIS unit tests | `ubuntu-latest` + Python 3.12 | n/a | Full unit suite: logic, architecture, packaging |
| QGIS 3 Docker | `qgis/qgis:3.44.11` | Qt 5 / PyQt5 | QGIS 3 plugin import + runtime smoke + enum probe |
| QGIS 4 Docker | `qgis/qgis:4.2.0` | Qt 6 / PyQt6 | QGIS 4 plugin import + runtime smoke + Qt 6 enum probe |

All three must pass before merge.

## CI enforcement

The `tests.yml` workflow runs three jobs:

1. `unit-tests` — no QGIS (fast, catches logic/architecture)
2. `docker-qgis3` — runtime smoke/probe tests inside `qgis/qgis:3.44.11`
3. `docker-qgis4` — runtime smoke/probe tests inside `qgis/qgis:4.2.0`

The Docker jobs are **required** checks. A PR cannot merge if any of the
three fail.

The Docker jobs intentionally run the QGIS runtime suite, not every pure
unit test. Many pure unit tests install fake `qgis` modules or Qt 5-shaped
stubs so they can run in the no-QGIS job; those tests are covered by
`unit-tests`. The Docker jobs focus on what no-QGIS tests cannot prove:
real plugin imports, QGIS-backed smoke workflows, and Qt/PyQGIS enum
compatibility.

## Smoke import failures are hard errors

`tests/test_qgis_smoke.py` guards the top-level qfit import chain. If the
import of `qfit.qfit_dockwidget` or any other qfit module fails inside a
Docker QGIS environment, the test suite **must fail**, not skip.

The smoke test may still skip when QGIS is genuinely unavailable (e.g. in
the no-QGIS `unit-tests` job), but inside Docker QGIS jobs the skip guard
is removed and import failures propagate as test errors.

## Qt class-scope enum probe

`tests/test_qt6_class_enum_probe.py` resolves every class-scope Qt enum
used at class-body level in qfit source against the real binding. This
catches `QDockWidget.DockWidgetClosable`-style failures that a broad
try/except import can silently swallow.

The probe runs in all environments. On Qt 5 it resolves flat members; on
Qt 6 it resolves nested members. If neither shape is available, the probe
fails.

## Running Docker tests locally

```bash
scripts/docker_test.sh 3            # runtime smoke/probe suite on QGIS 3
scripts/docker_test.sh 4            # runtime smoke/probe suite on QGIS 4
scripts/docker_test.sh 3 -x -q      # custom pytest args on QGIS 3
scripts/docker_test.sh 4 tests/test_qgis_smoke.py  # specific file
```

The script handles container lifecycle, plugin linking, and cleanup. It
requires Docker on the host.

## When to add a Docker test

- Any change that touches Qt enum references, class-body expressions using
  Qt/PyQt classes, or `classFactory()` import paths must pass Docker QGIS 4.
- Any change to packaging or plugin metadata must produce both zip artifacts
  and pass Docker tests on both QGIS versions.
- Rendering/export-sensitive changes still need the rendering-proof checklist
  from `CONTRIBUTING.md` in addition to Docker tests.
