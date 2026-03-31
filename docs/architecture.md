# qfit architecture guide

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

This layer should prefer describing *what qfit wants done*, not *how QGIS or Strava does it internally*.

### Domain / core layer

Examples:

- canonical activity models
- activity filtering/querying/sorting/summaries
- activity classification and provider-neutral derived metadata
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
- activity storage
- settings/configuration access
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

## 6. Current architectural priorities

The active migration priorities are tracked in issues #169 through #178. In practical terms, current high-value directions are:

- thin out `QfitDockWidget`
- use clearer request/result objects for main workflows
- isolate settings, storage, and layer operations behind pragmatic seams
- consolidate activity-centric business logic into a clearer core
- keep feature ownership clearer as modules move out of the flat top-level layout

## 7. Review checklist

Use this quick checklist in PR review:

- Does this change make `QfitDockWidget` heavier or thinner?
- Is provider-neutral logic staying free of unnecessary QGIS coupling?
- Is new workflow logic placed outside the UI when practical?
- Is a new abstraction earning its keep, or just adding ceremony?
- Would a future contributor know where related code belongs?
- Are tests focused on the highest-value non-UI logic?

## 8. Contributor rules

Short version:

- prefer **feature/workflow ownership** over more flat top-level sprawl
- keep **UI glue in the UI**
- keep **business rules out of QGIS-heavy modules** where practical
- isolate **external dependency details** when the seam improves clarity or testability
- favor **small incremental refactors** over large rewrites
- preserve behavior while moving boundaries

If a change makes the code easier to locate, easier to test, and less coupled to the dock widget or raw QGIS details, it is probably moving in the right direction.
