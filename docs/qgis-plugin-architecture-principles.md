# QGIS plugin architecture principles for qfit

This document is the durable reference for architectural decisions in qfit.

It complements `docs/architecture.md`.

- `docs/architecture.md` explains qfit's **current target shape** and placement rules.
- this document explains the **general principles** behind that shape, especially:
  - when to use native QGIS/PyQGIS directly
  - when to keep behavior under plugin control
  - how qfit interprets **hexagonal / ports-and-adapters** architecture in practice

The goal is not purity for its own sake.
The goal is to make qfit easier to evolve, easier to test, and more reliable in real user workflows.

## 1. Core principle

> Use QGIS/PyQGIS as the GIS and layout platform, but keep business logic, critical rendering logic, and export-sensitive behavior under plugin control whenever native QGIS behavior is hard to test, version-fragile, or unreliable in headless or automated workflows.

Short version:

> **Native where robust, custom where correctness matters.**

## 2. What this means in qfit

qfit is a QGIS plugin, so QGIS is the host platform and GIS engine.
We should take advantage of that.

But qfit is also a product with its own behavior, workflows, and quality bar.
We should not outsource correctness to framework internals we cannot reliably validate.

In practical terms:

- use QGIS aggressively for standard GIS plumbing
- do not blindly assume the most native implementation is the best production implementation
- keep correctness-critical behavior under qfit control when native behavior is brittle, underdocumented, or export-fragile

## 3. What QGIS should usually own

Use native QGIS/PyQGIS capabilities for platform-level concerns such as:

- project and layer integration
- CRS and geometry operations
- data-provider access
- map canvas interaction
- selection/editing hooks and signals
- task scheduling / background work
- print layout framework
- atlas/page iteration
- standard symbology and labeling when behavior is stable enough

These are the places where QGIS gives the most leverage and least reinvention.

## 4. What qfit should usually own

Keep these concerns in plugin-managed code when they are important to correctness, repeatability, or product quality:

- business rules and domain logic
- transformations and derived data
- workflow orchestration
- export-sensitive rendering
- deterministic charting / generated graphics
- fallback behavior across QGIS versions
- validation rules and acceptance checks
- packaging of runtime dependencies needed for real production use

If a feature must behave consistently across machines, QGIS versions, and headless export paths, qfit should strongly prefer owning that behavior.

## 5. Native vs custom: production decision rule

A native QGIS implementation is a good production choice only if it is:

- stable across the supported QGIS versions
- testable without relying entirely on manual GUI inspection
- reliable on real data, not only synthetic fixtures
- robust in export / automation / headless execution paths
- debuggable when it fails
- visually and functionally good enough for the product

If one or more of those is false, prefer:

1. a qfit-controlled implementation, or
2. a qfit-controlled fallback behind a native-first interface

## 6. qfit's interpretation of hexagonal architecture

qfit is **not** trying to become a framework demo.
It is still one plugin, one repository, and one deployable unit.

So when we say **hexagonal architecture** or **ports and adapters**, we mean something pragmatic:

- UI should not own the workflows
- application/workflow code should express intent clearly
- provider-neutral logic should stay easier to test than QGIS-heavy code
- external dependencies should be isolated behind seams when that helps clarity or testability
- we add ports/adapters when they solve a real problem, not to satisfy a pattern name

### Preferred dependency direction

```text
UI -> application/workflow -> domain + ports -> infrastructure adapters
```

### In qfit terms

- **UI** = dock widget, dialogs, widget bindings, message rendering
- **application/workflow** = orchestration services, controllers, request/result objects, use-case style entry points
- **domain** = provider-neutral activity logic, summaries, classification, calculations, planning logic
- **ports** = small application-facing contracts where a seam improves clarity or testability
- **infrastructure adapters** = Strava integration, GeoPackage persistence, QGIS settings access, QGIS layer operations, Mapbox/QGIS-specific runtime behavior

Concretely in the current repo, that mostly maps to:

- `activities/application` + `activities/domain`
- `providers/domain` + `providers/infrastructure`
- `visualization/application` + `visualization/infrastructure`
- `atlas/` for publish/export workflows and atlas-owned helpers/infrastructure
- `ui/` for dock-widget wiring helpers
- `validation/` for export-sensitive validation harnesses

## 7. Ports and adapters: when to use them

Introduce a port/gateway when at least one of these is true:

- the workflow needs to be tested without the real dependency
- the dependency detail is noisy enough to obscure the workflow
- more than one implementation is plausible now or later
- a QGIS-specific or provider-specific detail is leaking into otherwise provider-neutral code
- a seam would make the intent of the application layer clearer

Good examples in qfit already include:

- `LayerGateway` for visualization/layer operations
- activity storage seams around GeoPackage-backed persistence
- settings access seams
- service-style orchestration around atlas export

Do **not** introduce a port when:

- there is only one tiny stable implementation
- the abstraction makes the workflow harder to read
- the seam exists only to make the code look more "architectural"

## 8. Deterministic rendering policy

qfit should be conservative about delegating correctness-critical rendering to native QGIS internals unless those paths are proven reliable.

This matters most for:

- exported PDFs
- generated charts
- atlas/profile visualizations
- anything that users judge based on final artifacts rather than internal object state

If native rendering is elegant but not deterministic enough, qfit should prefer:

1. plugin-controlled rendering
2. export-safe generated artifacts (SVG/image/etc.)
3. a stable fallback path over a fragile native-only path

## 9. Validation rules for rendering/export features

For rendering-sensitive features, green unit tests and correct object construction are **not sufficient**.

qfit should validate:

- real-data behavior, not synthetic-only fixtures
- exported output, not just layout-item configuration
- headless/export behavior when relevant
- cross-platform/runtime packaging behavior when relevant

Questions to ask:

- does the final PNG/PDF actually show the expected content?
- does the feature still work when packaged and deployed, not just in dev mode?
- does the output remain correct on supported machines and runtimes?

## 10. Version-fragility rule

If a feature depends on QGIS behavior that varies significantly by version, then:

- isolate that dependency behind a small abstraction where practical
- document the limitation explicitly
- provide a qfit-owned fallback when the feature matters to production correctness
- avoid making the fragile path the only supported path

## 11. Practical guidance for new code

When adding or refactoring code, ask these questions in order:

1. Is this UI glue?
   - keep it near the UI layer
2. Is this workflow orchestration?
   - move it into an application/controller/service/use-case style module
3. Is this provider-neutral logic?
   - keep it in domain/core-oriented modules
4. Is this talking directly to QGIS, Strava, GeoPackage, settings, or other external systems?
   - keep it in infrastructure/adapters
5. Is correctness depending on native framework behavior that we cannot trust yet?
   - keep or add a qfit-controlled implementation/fallback

Package ownership matters here too:

- prefer feature-owned packages over adding more generic top-level modules
- treat the remaining flat root-level Python modules as transitional / grandfathered unless a new shared module is explicitly justified
- if a new top-level shared module is truly necessary, document why it is cross-feature and update the architecture guardrails in tests

In other words: root-level compatibility shims may remain for import stability, but real feature logic should continue moving toward the owned package structure above.

## 12. What success looks like in qfit

The architecture is moving in the right direction when:

- `QfitDockWidget` gets thinner, not heavier
- workflows become easier to read without reading raw QGIS details
- domain logic becomes easier to test without QGIS
- infrastructure concerns become easier to swap, fake, or reason about
- exported outputs become more deterministic and less dependent on fragile runtime quirks
- new contributors can tell where code belongs

## 13. Anti-goals

qfit is **not** trying to:

- create interfaces for everything
- hide every PyQGIS call behind layers of ceremony
- perform a big-bang rewrite into perfect hexagonal purity
- sacrifice readability for pattern compliance

This is a pragmatic architecture, not architecture theater.

## 14. One-paragraph policy version

qfit should use PyQGIS aggressively for core GIS platform capabilities, but it should remain conservative about delegating correctness-critical behavior to native QGIS rendering or export internals unless those paths are proven stable in real-world use. Domain logic, derived data, workflow orchestration, and critical exported visuals should stay under qfit control whenever that improves determinism, testability, and cross-version reliability. qfit should continue evolving toward a pragmatic ports-and-adapters structure where UI, workflows, domain logic, and infrastructure concerns are easier to reason about without adding abstraction that does not earn its keep.
