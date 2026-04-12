# qfit refactoring roadmap

This document tracks the active engineering roadmap for moving qfit toward a pragmatic hexagonal / ports-and-adapters shape.

It complements, rather than replaces:

- `docs/architecture.md`
- `docs/qgis-plugin-architecture-principles.md`
- `docs/roadmap.md`

The goal is not architecture purity.
The goal is to keep qfit easier to test, safer to evolve, and less dependent on `QfitDockWidget` as a catch-all workflow host.

Assumption for this roadmap:

- qfit is developed and used only by us
- releases are treated as atomic
- compatibility shims are migration scaffolding, not long-term public API commitments

## Status legend

- **Done enough**: the direction is established and multiple meaningful slices have landed
- **In progress**: actively being worked in small PR-sized slices
- **Needs more work**: direction is clear, but the codebase still has meaningful gaps

---

## Snapshot

### Current focus

We are in the middle of a steady UI-thinning / workflow-extraction phase.

Recent slices have focused on:

- moving clear-database text policy out of `QfitDockWidget`
- moving background-map text policy out of `QfitDockWidget`, `BackgroundMapController`, and `VisualApplyService`
- extracting visual-apply status formatting and status-selection policy into `visualization/application/visual_apply_messages.py`
- keeping QGIS mechanics in the existing adapter-heavy paths while making user-facing logic easier to unit test

### Current in-flight slice

- Issue `#420`: extract visual apply status selection policy
- PR `#421`: `refactor: extract visual apply status selection`

---

## 1. Keep thinning `QfitDockWidget`

**Status:** In progress, strong progress

Target:

- every user action should delegate to a small workflow/controller
- the widget should read UI state, call a use case/service/controller, and render the result
- QGIS/data/provider logic should not keep accumulating there

Recent progress:

- dock action dispatch extracted into `ui/application/dock_action_dispatcher.py`
- analysis flow extracted into `analysis/application/analysis_controller.py`
- settings bindings extracted into `configuration/application/dock_settings_bindings.py`
- activity preview / selection / activity-type options extracted into `activities/application/`
- connection status and multiple summary/message builders extracted out of the dock
- clear-database dialog/error/status text extracted into `activities/application/clear_database_messages.py`

What is still true:

- `QfitDockWidget` is thinner than before, but still the main UI orchestration surface
- this remains the most active refactoring lane

---

## 2. Make feature ownership stricter

**Status:** Done enough, keep enforcing

Target:

Keep new feature logic inside feature-owned packages:

- `activities/`
- `visualization/`
- `atlas/`
- `providers/`
- `configuration/`
- `ui/`

and avoid adding feature logic to flat root modules except true entrypoints during the transition.

Recent progress:

- activity workflow/policy logic moved into `activities/application/`
- rendering/background-map logic continues to move into `visualization/application/`
- UI dispatch/orchestration helpers live under `ui/application/`
- configuration/status logic now lives under `configuration/application/`

Rule of thumb:

If a new helper has feature ownership, it should usually not land in a root-level module.

---

## 3. Move policy into application/domain, leave mechanics in adapters

**Status:** In progress, strong progress

Target:

Examples of policy that should live in application/domain:

- render presets
- fallback rules
- layer-choice policy
- visibility intent
- summaries and user-facing workflow text

Examples of mechanics that should stay in adapters/infrastructure:

- `QgsRenderer` construction
- symbols / repainting
- layer-tree integration
- QGIS project/layer mutation
- provider/API calls
- GeoPackage and PDF assembly mechanics

Recent progress:

- rendering policy moved into `visualization/application/render_plan.py`
- layer/application seams added through `visualization/application/layer_gateway.py`
- background-map messages now live in `visualization/application/background_map_messages.py`
- clear-database dialog/error/status text now lives in `activities/application/clear_database_messages.py`

---

## 4. Formalize a few small ports only where they earn their keep

**Status:** In progress, controlled

Ports/seams already moving in the right direction:

- `LayerGateway`
- settings/config access seams
- provider registry / provider-facing boundaries
- atlas/export runtime seam
- load/store workflow request/result seams

Guideline:

Add a port only when it improves clarity, testability, or migration safety.
Do not add ceremony-only interfaces.

---

## 5. Split planning from execution across workflows

**Status:** In progress, good progress

Target:

- application layer builds requests/plans
- infrastructure layer executes them

Established examples:

- atlas planning vs execution split
- rendering plan / apply split
- structured background-map load requests/results
- structured clear-database request building in load workflow

This is a good pattern for future work and should keep expanding where it simplifies testing and review.

---

## 6. Keep provider-neutral logic free of QGIS

**Status:** Done enough, keep expanding

These should stay unit-testable without PyQGIS:

- filtering
- summaries
- classification
- render planning
- export planning
- validation rules
- user-facing workflow text/policy where practical

Recent progress:

- activity preview/query helpers
- activity-type options
- connection status helpers
- layer summary helpers
- clear-database message helpers
- render-planning and visual-apply policy seams
- background-map message helpers

---

## 7. Treat QGIS / Strava / GPKG / PDF assembly as adapters

**Status:** In progress

Target adapters:

- Strava client/provider
- GeoPackage persistence
- QGIS layer loading/styling/temporal wiring
- project integration
- PDF assembly

Current direction:

- provider work is already cleaner than before
- GeoPackage orchestration has dedicated infrastructure ownership
- project/layer styling logic increasingly sits under visualization infrastructure
- PDF assembly remains atlas-owned infrastructure

This direction is correct and should continue.

---

## 8. Add guardrails, not just structure

**Status:** Needs more work

Guardrails we already have:

- architecture-boundary tests
- focused pure unit tests
- QGIS smoke coverage
- SonarCloud / CodeQL / CI enforcement

Guardrails still worth expanding:

- more architecture-boundary tests around module ownership/import direction
- continued QGIS smoke checks for sensitive paths
- artifact-level proof for rendering/export-sensitive work, not only green CI

---

## 9. Remove compatibility shims completely

**Status:** Active rule, now explicit

Principles:

- if a root shim exists only to cushion an internal package move, keep it only until all in-repo callers are migrated
- once migrated, delete it
- no need to preserve old import paths across releases just for historical continuity
- avoid cleanup-only churn mixed into behavior changes, but do not preserve shims indefinitely

Target end state:

- no root-level compatibility shims remain
- root-level modules are limited to true entrypoints or intentionally top-level modules
- feature-owned code lives under feature packages instead of forwarding through flat root modules

Recent precedent:

- provider root shims were retired only after migration work had already landed
- the same end-state should apply to the remaining root forwarders such as workflow, settings, visualization, and geopackage migration shims

---

## Recent merged slices in this roadmap lane

These are representative recent refactoring slices, not a full historical list:

- `#364` / PR `#365`: add visualization render planner
- `#367` / PR `#368`: extract dock settings bindings
- `#369` / PR `#370`: extract activity preview workflow
- `#371` / PR `#372`: extract activity type option building
- `#373` / PR `#374`: extract connection status messaging
- `#375` / PR `#376`: extract activities layer summary text
- `#378` / PR `#379`: extract stored activities summary text
- `#380` / PR `#381`: extract last sync summary text
- `#382` / PR `#383`: extract clear-database summary text
- `#384` / PR `#385`: extract clear-database missing-path error text
- `#386` / PR `#387`: extract clear-database delete-failure status text
- `#388` / PR `#389`: extract clear-database delete-failure error title
- `#390` / PR `#391`: extract clear-database load-workflow error title
- `#392` / PR `#393`: extract clear-database confirmation title
- `#394` / PR `#395`: extract clear-database confirmation body
- `#396` / PR `#397`: extract background-map failure title
- `#398` / PR `#399`: extract background-map failure status
- `#400` / PR `#401`: extract background-map loaded status
- `#402` / PR `#403`: extract background-map cleared status
- `#404` / PR `#405`: extract visual-apply background cleared status
- `#406` / PR `#407`: extract visual-apply background loaded status
- `#408` / PR `#409`: extract combined visual-apply background loaded status
- `#410` / PR `#411`: extract visual-apply background failure status
- `#412` / PR `#413`: extract no-layers visual-apply background failure status
- `#414` / PR `#415`: extract styled-only visual-apply success status
- `#416` / PR `#417`: extract filtered visual-apply status
- `#418` / PR `#419`: extract visual-apply temporal-note status formatting

---

## What to do next

Near-term priority:

1. finish `#420` / PR `#421`
2. continue from message extraction into slightly higher-leverage `VisualApplyService` seams, preferring policy selection helpers or request/result shaping over more one-string-at-a-time changes
3. keep using small PR-sized slices, but avoid getting trapped in string-only refactors if a clearer controller/request/result seam becomes the better next move
4. when a root shim has no remaining in-repo callers, prefer deleting it rather than preserving it for compatibility nostalgia

## Review checklist for future slices

When proposing the next refactoring issue, prefer changes that answer yes to most of these:

- Does this make `QfitDockWidget` thinner?
- Does this move policy out of UI/framework-heavy code?
- Does this keep QGIS mechanics in infrastructure?
- Does this improve unit-testability without PyQGIS?
- Does this preserve strict feature ownership?
- Is this small enough for a reviewable PR?
- Does it avoid unnecessary new abstraction?
