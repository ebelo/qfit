# qfit architecture guide

For the higher-level architectural principles behind this guide, also read:

- `docs/qgis-plugin-architecture-principles.md`

qfit is evolving toward a **modular monolith** with pragmatic **ports-and-adapters** boundaries.

That sounds grander than it is.

The intent is simple:

- keep qfit as **one plugin / one repository / one deployable unit**
- organize code by **feature and workflow ownership** instead of a flat pile of technical helpers
- keep the **dock widget thin**
- keep **provider-neutral logic** easier to test than QGIS-heavy code
- isolate external dependencies such as **Strava, GeoPackage persistence, QGIS settings, and QGIS layer operations** behind clearer seams when that buys maintainability

This document is short on purpose. It is meant to guide placement and review decisions, not turn qfit into architecture theater.

## 1. Target shape

The target shape is a modular monolith:

- **single plugin package**
- **single runtime** inside QGIS
- **internally separated responsibilities**

Over time, qfit should trend toward clearer feature areas such as:

- **activities/import**
- **providers**
- **visualization**
- **atlas/publish**
- **settings/configuration**
- **shared/core helpers**

Not every area needs `application/`, `domain/`, and `infrastructure/` subpackages immediately. Prefer gradual, pragmatic extraction.

### Current implemented package map

The codebase now already reflects most of that shape:

- `activities/domain/` — provider-neutral activity models, classification, and query logic
- `activities/application/` — fetch/sync/load workflow services and request/result models
- `providers/domain/` / `providers/infrastructure/` — provider contracts plus Strava-backed adapters
- `visualization/application/` / `visualization/infrastructure/` — visualization/background workflows plus QGIS layer/runtime adapters
- `atlas/` — atlas/export/publish workflows, profile handling, and atlas-owned infrastructure such as PDF assembly
- `ui/` — dock-widget dependency assembly and workflow-section coordination
- `validation/` — validation harnesses and scenario helpers for export-sensitive checks

Some root-level modules still exist as **compatibility shims** so imports remain stable while the migration settles. Those files are transitional; new feature logic should not be added there.

Current deprecated compatibility shims are:

- `activity_classification.py` -> `activities/domain/activity_classification.py`
- `activity_query.py` -> `activities/domain/activity_query.py`
- `models.py` -> `activities/domain/models.py`
- `activity_storage.py` -> `activities/application/activity_storage.py` plus `activities/infrastructure/geopackage/activity_storage.py`
- `layer_manager.py` -> `visualization/infrastructure/qgis_layer_gateway.py`

Migration policy for these shims:

- new in-repo imports should use the canonical package-owned module, never the root shim
- keep root shims as tiny forwarding modules only while external import stability still matters
- once in-repo callers are gone and import stability is no longer needed, delete the shim instead of re-expanding it

## 2. Working layers

Use these layers as a placement heuristic.

### UI layer

Examples:

- `qfit_dockwidget.py`
- dialogs, widget bindings, message rendering, signal wiring

Responsibilities:

- read widget state
- call use cases / controllers / services
- render results, warnings, and errors
- keep immediate UI state coherent

Avoid putting these here unless there is a strong reason:

- Strava orchestration details
- GeoPackage write/load rules
- QGIS layer-manipulation algorithms
- derived activity business rules
- long parameter-mapping chains that really belong in a request object or service

### Application / workflow layer

Examples:

- controllers and orchestration services such as sync/load/export/background-map flows
- request/result objects for main workflows

Responsibilities:

- coordinate a user-facing workflow
- translate UI intent into application steps
- depend on ports/gateways where useful
- return structured results the UI can render

Prefer explicit request/result dataclasses for substantial workflows when they
replace long parameter lists or framework-heavy state. qfit now uses that shape
for load/store, visualization apply, and atlas export orchestration.

This layer should prefer describing *what qfit wants done*, not *how QGIS or Strava does it internally*.

### Domain / core layer

Examples:

- `activities/domain/models.py` for canonical activity models
- `activities/domain/activity_query.py` for activity filtering/querying/sorting/summaries
- `activities/domain/activity_classification.py` for provider-neutral classification and derived metadata
- time/polyline utilities and similar reusable core helpers

Responsibilities:

- hold provider-neutral business rules
- stay easy to test without QGIS
- avoid direct dependency on dock widget code or heavy infrastructure details

### Infrastructure / adapters layer

Examples:

- Strava client/provider adapter
- GeoPackage persistence helpers
- QGIS settings adapter
- QGIS layer loading/styling/temporal wiring
- Mapbox/QGIS-specific basemap integration

Responsibilities:

- talk to external systems and frameworks
- implement ports/gateways when the application layer benefits from a seam
- keep low-level QGIS/GeoPackage/provider details out of provider-neutral logic

## 3. Dependency direction

Preferred direction:

```text
UI -> application/workflow -> domain + ports -> infrastructure adapters
```

Practical rules:

- **UI may depend on application services.**
- **Application code may depend on domain code and small protocols/ports.**
- **Infrastructure may depend on domain types and application contracts when needed.**
- **Domain/core code should not depend on UI modules.**
- **Provider-neutral logic should avoid direct QGIS imports.**
- **Application workflows should not reach deep into Strava/QGIS implementation details when a small seam would make intent clearer.**

This is guidance, not dogma. Small plugins do not benefit from abstracting every function call.

## 4. When to introduce a port or adapter

Introduce a port/gateway when at least one of these is true:

- the workflow needs to be tested without the real external dependency
- the implementation detail is noisy enough to obscure the workflow
- qfit may reasonably gain another implementation later
- a QGIS-specific or provider-specific dependency is leaking into otherwise provider-neutral code

Good candidates in qfit:

- activity provider
- activity storage (now starting to take shape through a small storage port plus the GeoPackage-backed adapter)
- settings/configuration access (now via a small `SettingsPort` with the current QGIS-backed adapter behind it)
- QGIS layer/visualization operations
- atlas export orchestration boundaries

Do **not** introduce a new abstraction just to satisfy a pattern name.

A direct helper call is still fine when:

- there is only one obvious implementation
- the code is tiny and stable
- adding an interface would make the workflow harder to read

## 5. Placement rules for new code

When adding code, ask these questions in order:

1. **Is this UI glue?** Put it near the widget/dialog layer.
2. **Is this a user-facing workflow or orchestration step?** Put it in an application/controller/service area.
3. **Is this provider-neutral business logic?** Put it in a domain/core-oriented module.
4. **Is this talking directly to QGIS, Strava, GeoPackage, or settings storage?** Put it in an infrastructure/adapter-oriented module.
5. **Is this shared across features without being business logic?** Put it in a small shared helper area.

If a module starts mixing two or three of those answers, that is usually a sign it wants extraction.

## 5.1 Package ownership rules for new code

qfit now treats a small set of packages as the default owners for new work:

- `activities/` — activity import, fetch/sync/load flows, provider-neutral activity rules
- `atlas/` — atlas/publish/export workflows and atlas-specific helpers
- `providers/` — provider-facing contracts and provider adapters
- `visualization/` — visualization workflows and QGIS-facing visualization adapters
- `ui/` — dock-widget section coordination, dependency assembly, and other UI-only helpers
- `validation/` — validation harnesses and artifact-checking helpers

The flat top-level Python module layer is now effectively **frozen** except for:

- plugin entrypoints / bootstrap modules (`qfit_plugin.py`, `qfit_dockwidget.py`, dialogs, package `__init__.py`)
- a limited set of grandfathered transitional modules already in the repo
- truly shared helpers that are both feature-neutral and small enough that creating a new package would add ceremony without improving clarity

Practical rule:

> **Do not add a new top-level Python module for feature-specific code.**

If new code belongs to one feature or workflow, put it under that feature package even when the legacy equivalent still exists at the top level.

If you think a new top-level shared module is justified, the PR should do all of the following:

1. explain why the code is truly cross-feature rather than feature-owned,
2. document that choice in this architecture guide / `CONTRIBUTING.md`, and
3. update the architecture-boundary allowlist in `tests/test_architecture_boundaries.py`.

That friction is intentional: it prevents accidental growth of the generic root layer.

## 6. Current architectural priorities

The current architecture work is centered on making the implemented structure easier to understand and harder to regress. In practical terms, high-value directions are:

- thin out `QfitDockWidget`
- use clearer request/result objects for user-facing workflows
- keep ports/adapters boundaries small and explicit where they buy testability
- preserve feature ownership by moving real implementations into owned packages and leaving only narrow compatibility shims at the root when needed
- keep docs and architecture guardrails aligned with the code that now exists on `main`

## 7. Review checklist

Use this quick checklist in PR review:

- Does this change make `QfitDockWidget` heavier or thinner?
- Is provider-neutral logic staying free of unnecessary QGIS coupling?
- Is new workflow logic placed outside the UI when practical?
- Is a new abstraction earning its keep, or just adding ceremony?
- Would a future contributor know where related code belongs?
- Are tests focused on the highest-value non-UI logic?
- If the PR is rendering/export-sensitive, does it include explicit rendering proof instead of relying on green CI alone?

## 8. Rendering-proof rule for export-sensitive changes

For atlas/export/chart/rendering work, reviewers should expect a short PR note that records:

- what dataset or scenario was validated
- which final artifact was checked (PDF, PNG, generated graphic, etc.)
- whether the validation covered interactive behavior, export/headless behavior, or both
- any runtime/packaging assumptions that mattered
- what output was visually/functionally confirmed as correct

The contributor-facing checklist for this lives in `CONTRIBUTING.md`. This section exists to make the same rule visible during architectural review: output-sensitive changes need artifact proof, not only passing tests and apparently-correct object construction.

## 9. Contributor rules

Short version:

- prefer **feature/workflow ownership** over more flat top-level sprawl
- keep **UI glue in the UI**
- keep **business rules out of QGIS-heavy modules** where practical
- isolate **external dependency details** when the seam improves clarity or testability
- favor **small incremental refactors** over large rewrites
- preserve behavior while moving boundaries
- treat new root-level modules as exceptions that require explicit justification and a boundary-test update

If a change makes the code easier to locate, easier to test, and less coupled to the dock widget or raw QGIS details, it is probably moving in the right direction.
