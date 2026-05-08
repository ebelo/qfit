# qfit design system

This document defines qfit's UI design system for QGIS dock panels, dialogs, and workflow pages.

It is intentionally practical: use it during UI implementation and PR review to keep the plugin coherent without turning qfit into a custom UI framework.


## UI contract (must be respected)

Any qfit UI change must:

- follow the button system defined below, with at most one primary action per section
- clearly separate navigation, actions, and status/result feedback
- keep presentation/free text fluid at narrow dock widths instead of widening the panel
- be understandable without relying on color alone
- pass the mandatory review checklist in this document before merge

PRs that violate these rules must be rejected or revised before merge. Existing UI that does not yet satisfy the contract should be corrected in small, focused slices rather than normalized as a precedent.

## Design tokens

Use shared tokens instead of one-off visual values. Prefer the constants in `ui/tokens.py` when implementing reusable UI helpers.

### Spacing scale

| Token | Value | Use |
| --- | ---: | --- |
| XS | 4 px | Tight label/control gaps, compact icon spacing |
| S | 8 px | Field spacing and action-row gaps |
| M | 12 px | Internal spacing inside a section |
| L | 16 px | Separation between related sections |
| XL | 24 px | Separation between major workflow groups |

Rules:

- Field spacing = S.
- Section internal spacing = M.
- Section spacing = L or XL.
- Avoid arbitrary spacing values unless a native Qt/QGIS control requires a specific margin.
- Local-first right-panel pages use M page margins, M spacing between top-level page content blocks, and S spacing inside each page-content layout.
- Local-first right-panel content is top-aligned. Do not distribute controls vertically to fill the available dock height; leaving empty space at the bottom is preferred to tab-to-tab spacing drift.

### Typography

- Use the QGIS / Qt default font.
- Title text: bold.
- Section heading: bold.
- Field label: default weight.
- Instruction/helper text: regular style, default or slightly smaller, with muted color only as supporting emphasis.
- Tool feedback text: italic and muted when it reports generated facts, workflow results, empty states, or non-blocking status detail.
- Semantic badges/pills may remain regular/bold because their component shape and text already communicate status.
- Warnings and errors should stay regular by default for readability and urgency; use semantic color, status copy, a pill/badge, or a dialog/message bar depending on severity.
- No all-caps labels.

Instruction text tells the user what to do next; keep it visually stable and regular. Tool feedback tells the user what qfit observed, computed, loaded, cleared, or exported; render it quieter in italic. Do not rely on italic alone for meaning: pair feedback with placement, copy, color, or a status component.

Use this text-voice split for normal inline copy:

| Voice | Example use | Treatment |
| --- | --- | --- |
| Instruction/helper | What to do next, field guidance, prerequisites | Regular, muted if secondary |
| Informational feedback | Loaded counts, active filters, empty states, export summaries | Italic, muted |
| Warning | Recoverable problem or degraded output | Regular, warning token/pill and explicit warning copy |
| Error | Blocking failure or action that could not complete | Regular, danger token or blocking dialog/message bar |

So regular text is not the only distinction between information and errors: warnings/errors must carry semantic warning/error treatment in addition to position and wording.

### Status categories

Use these categories consistently in state names, tests, and copy:

- empty
- ready
- running
- success
- warning
- error

Rules:

- Always pair status color with text.
- Status copy must name the state or next step; color alone is not enough.
- Use inline status for normal workflow feedback and reserve dialogs/message bars for blocking errors or destructive confirmations.

## Button system

qfit has exactly four button types:

| Type | Style | Meaning |
| --- | --- | --- |
| Primary | Filled qfit accent color | Main recommended action for the section |
| Secondary | Default/neutral Qt button | Standard actions that support the section |
| Tertiary | Subtle/text treatment, optional | Low-priority or supplemental actions |
| Destructive | Explicit danger treatment | Risky or data-loss actions |

Hard rules:

- R1 — One primary button per section: at most one primary button may be visible in a section at a time.
- R2 — Primary is only for actions: it must not be used for navigation, selection, or state indication.
- R3 — Navigation is not buttons: Data / Map / Analysis / Atlas / Settings must use a list or tab selection pattern and must not use button styling.
- R4 — No color-only meaning: the UI must remain understandable without color.
- R5 — No outline-based semantics: do not encode meaning only through border color, width, or outline style.
- R6 — Destructive is never primary: destructive actions must be visually distinct, explicitly worded, and separated from normal workflow actions.

Action layout inside each section:

1. Secondary actions.
2. Primary action last/rightmost in horizontal rows or last/bottom in vertical stacks.
3. Destructive action in a visually separated row or group.

Wizard-page buttons must go through the shared helpers in
`ui/dockwidget/action_row.py`: `style_primary_action_button`,
`style_secondary_action_button`, and `style_destructive_action_button`.
Secondary buttons intentionally keep the native Qt button treatment; only
primary and destructive actions receive qfit-specific chrome.

## Navigation pattern

The left local-first navigation is selection, not an action row.

Navigation must:

- render selected/current page with highlighted neutral background and bold text
- render unselected pages neutrally
- avoid the filled qfit accent treatment reserved for primary actions
- avoid button borders, raised-button chrome, and outline semantics
- expose page status in text or tooltip, not only in color

## Reusable UI components

### Workflow section

Structure:

1. Title.
2. Optional readiness/status summary.
3. Optional helper text explaining the next decision.
4. Content fields or controls.
5. Actions.
6. Result/status feedback from those actions.

Usage rules:

- Keep instructions above the actions they explain.
- Keep action results below the action row that produced them.
- Do not hide essential workflow controls in advanced sections.

### Action row

Structure:

- Related actions in one row or stacked group.
- Secondary actions first.
- Primary action last.
- Destructive action separated from the normal row.

Usage rules:

- Use one action row per coherent decision point.
- Do not mix navigation controls into an action row.
- Tooltips on disabled buttons must name the missing prerequisite.

### Inline status block

Structure:

- Short status title or sentence.
- Optional follow-up detail.

Usage rules:

- Keep it close to the UI it describes.
- Use concrete copy: what happened, what is missing, or what to do next.
- Render status detail and generated-result feedback in muted italic text unless the text is inside a semantic pill/badge.
- Do not italicize warning or error messages by default; preserve a direct regular style and pair it with warning/error semantics.
- Do not use color or icon alone as the status.

### Presentation/free-text labels

Presentation text includes helper copy, summaries, inline status detail, and generated facts such as atlas selection/page-count text.

Usage rules:

- Treat presentation text as fluid copy, not as a fixed-width control.
- Enable word wrapping for labels whose content can vary or become long.
- Allow the label to shrink with the dock by clearing artificial minimum widths; in Qt this usually means `setMinimumWidth(0)` plus a horizontal size policy that does not force the `sizeHint()` width.
- Prefer wrapping over truncation when the full sentence explains state, prerequisites, or export consequences.
- Keep compact single-line text only for stable labels, short field names, buttons, and intentionally terse badges/pills.

### Advanced section

Structure:

- Collapsible section with a clear title.
- Closed by default unless it contains required fields.
- Summary shown when advanced settings are modified.

Usage rules:

- Advanced settings must not interrupt the default workflow.
- If an advanced setting changes output materially, summarize its active state near the workflow result.

## Example — Correct action hierarchy

Data page action hierarchy:

- Secondary: `Load stored map layers`
- Secondary: `Sync saved routes`
- Primary: `Sync activities`
- Destructive: `Clear local database…` in a separated destructive row

## Rendering validation

Any PR affecting map rendering, heatmaps, atlas layout, or exports must include the relevant validation evidence:

- screenshot of the changed UI
- screenshot of the rendered map, if map output changes
- exported PDF sample or inspection note, if atlas/export output changes

Green CI is required, but rendering/export-sensitive work is not done until the output has been self-validated.

## 1. Field study: QGIS and Qt UI/UX best practices

### 1.1 Design for QGIS as the host application

qfit lives inside QGIS, so its UI should feel like a focused QGIS plugin rather than a standalone web app embedded in a dock.

General principles:

- Respect QGIS dock-widget patterns: compact vertical workflows, clear group boxes, predictable resizing, and no surprise modal interruptions for routine tasks.
- Prefer native Qt widgets over custom controls unless a custom control clearly improves usability.
- Keep GIS concepts explicit: layers, basemaps, filters, CRS-sensitive outputs, and exports should be named in terms QGIS users recognize.
- Avoid fighting the host theme. Use modest styling for hierarchy and affordance, but keep controls compatible with light/dark themes and platform defaults.
- Assume users may keep the dock narrow while working on the map canvas. Layouts must remain usable at constrained widths.

### 1.2 Use Qt layouts as the source of truth

Qt UI is most reliable when hierarchy is expressed through layouts, not manual sizing.

Best practices:

- Use vertical page/section layouts for top-level workflow order.
- Use form layouts for label-field pairs.
- Use horizontal layouts only for short, related action rows or compact paired controls.
- Avoid fixed widths except where a widget truly needs a stable minimum.
- Let labels wrap when helper, summary, status, or other presentation text can become long.
- Do not let long free-text labels dictate the dock width; make them shrinkable and wrap within the available layout width.
- Keep margins and spacing consistent inside a section; use larger separation between sections than between fields in the same section.
- Keep tab order aligned with visual reading order.

### 1.3 Configuration before action

Users should make choices before being asked to run an action.

Best practices:

- Show configuration fields first.
- Put action buttons below the fields they operate on.
- Keep actions close to their configuration, but visually separated enough that they read as actions.
- Do not put primary actions above the inputs that determine their effect.
- Avoid hidden state for primary workflows. If a control is central to the task, keep it visible.

### 1.4 Make action hierarchy obvious

QGIS plugins often accumulate many buttons. qfit should make button priority clear.

Best practices:

- Each page or section should have at most one primary action.
- Secondary actions should support the primary flow without competing with it.
- Destructive actions must be visually and textually distinct, and should require confirmation when data loss is possible.
- Button labels should be verbs plus objects: `Load stored map layers`, `Apply filters`, `Export atlas PDF`.
- Avoid vague labels such as `Run`, `OK`, `Process`, or `Submit` unless the surrounding context makes the action unambiguous.

Interactive state conventions:

- Default secondary buttons use the native/default neutral treatment so they read as actions without competing with the primary action.
- Hover state should visibly confirm clickability with a subtle neutral fill and a pointing-hand cursor.
- Selected/current navigation items use neutral selection styling, not the filled qfit accent treatment reserved for primary actions.
- The recommended next action in a panel is the primary action: filled qfit accent, clear label, bold text, and placed last/rightmost in the action row.
- Do not communicate recommendation, selection, hover, warning, or disabled state with color alone; pair state with placement, label, tooltip, icon, or nearby helper/status copy.

### 1.5 Prefer explicit state over surprise behavior

QGIS workflows often involve external state: selected layers, stored GeoPackages, credentials, rendered outputs, and map canvas changes.

Best practices:

- Show status near the workflow it describes.
- Distinguish empty, ready, running, success, warning, and error states.
- Disable unavailable actions and explain the prerequisite in a tooltip or nearby helper text.
- Do not silently ignore user input. If a field is invalid, explain how to fix it.
- Do not hide important configuration after applying it unless there is a strong reason.

### 1.6 Keep feedback proportional

Feedback should help users keep moving without interrupting them unnecessarily.

Best practices:

- Use inline status text for normal progress and recoverable problems.
- Use message bars or dialogs for blocking errors, destructive confirmations, or actions that require user attention.
- Report long-running work with progress or clear running state when practical.
- Keep success messages specific: say what changed or where output was written.
- Avoid noisy success popups for routine actions.

### 1.7 Accessibility and keyboard basics

qfit should remain usable with normal Qt accessibility expectations.

Best practices:

- Every field needs a clear label.
- Related controls should be grouped under a meaningful section title.
- Focus order should match reading order.
- Disabled controls should expose why they are unavailable.
- Text contrast should remain readable under QGIS theme changes.
- Do not rely on color alone to communicate errors or status.
- Keep keyboard operation possible for primary workflows.

### 1.8 Progressive disclosure without hiding the main flow

Advanced options are useful, but they should not obscure the common path.

Best practices:

- Keep primary workflow fields visible.
- Put advanced or rarely used settings in clearly named advanced sections.
- Persist expansion state only when it helps users, not when it creates confusing hidden state.
- Avoid show/hide toggles for essential controls.
- When a section is collapsed, its title should still communicate what is inside.

## 2. qfit-specific design guidance

### 2.1 Product workflow model

qfit's live dock follows the local-first navigation model defined in `ui/application/local_first_navigation.py` and installed by `ui/dockwidget/local_first_composition.py`:

1. **Data** (`data`) — load local GeoPackages or sync Strava activities and routes.
2. **Map** (`map`) — load layers, choose styles, backgrounds, and filters.
3. **Analysis** (`analysis`) — run optional analysis on loaded activity layers.
4. **Atlas** (`atlas`) — configure and export the qfit PDF atlas.
5. **Settings** (`settings`) — review qfit and Strava connection settings.

Use these page keys and titles as the baseline in docs, UI labels, and PR discussion. Legacy wizard section metadata may still exist during migration, but live UI guidance should map back to the local-first pages above.

### 2.2 Standard panel structure

Each qfit panel or workflow page should use this order:

1. Title or concise section heading.
2. One-line page readiness status.
3. Helper or instruction copy that explains the next decision.
4. Configuration fields.
5. Action buttons.
6. Result/status details, warnings, or follow-up hints produced by those actions.

Do not place action buttons before the configuration fields they depend on. Instructional copy belongs above the relevant actions; action outcomes and contextual result summaries belong below the action row that produced them.

### 2.3 Field and form conventions

- Use sentence-case labels: `Activity type`, `Name contains`, `Date from`.
- Keep labels short and specific.
- Use placeholders only for examples, not required instructions.
- Put units in the widget suffix when possible, for example `km`.
- Prefer explicit `From` / `To` pairs for ranges.
- Keep provider-neutral labels where possible; mention Strava only for provider-specific settings.
- Keep field order aligned with the user's mental model: broad filters before narrow filters, required before optional, common before advanced.

### 2.4 Button conventions

qfit button order within a section:

1. Secondary preparation actions, if needed.
2. Primary action last/rightmost in horizontal rows or last/bottom in vertical stacks.
3. Destructive actions separated from normal workflow buttons.

Button rules:

- Use one primary action per workflow section.
- Use specific action labels:
  - `Sync activities`
  - `Load stored map layers`
  - `Apply filters`
  - `Run analysis`
  - `Export atlas PDF`
- Avoid toggles for primary workflow visibility.
- If an action depends on fields, the action belongs below those fields.

### 2.5 Map panel rules

The Map panel is configuration-heavy and must stay predictable.

Rules:

- Map filters are always visible.
- Do not add a show/hide filters control.
- Filter fields appear before filter actions.
- The Map panel action row appears below the filter fields.
- `Load stored map layers` is a preparation action.
- `Apply filters` is the primary filter action.
- Basemap and style configuration should stay visually distinct from activity filters.
- Filter summaries should describe the active subset, not replace the fields.

Recommended Map panel order:

1. Map/layer status summary.
2. Basemap configuration.
3. Style configuration.
4. Filter configuration.
5. `Load stored map layers` / `Apply filters` actions.
6. Filter or layer result status.

### 2.6 Data panel rules

The Data page is the entry point for local-first activity data work.

Rules:

- Make the difference between local loading, provider syncing, storing, and loading map layers explicit.
- Show stored-data state before asking users to load or visualize it.
- Treat Settings / connection readiness as the prerequisite for provider sync actions, but do not block local GeoPackage loading on provider configuration.
- Keep destructive database actions grouped separately from sync/load actions.
- Explain disabled sync/load actions with prerequisite copy.

### 2.7 Analysis panel rules

- Put analysis mode and parameters before `Run analysis`.
- Keep generated-result status visible after running analysis.
- If a mode requires loaded layers or filtered activities, disable the action until prerequisites are met.
- Prefer small mode-specific helper text over long generic instructions.

### 2.8 Atlas / Publish panel rules

- Put document settings before export actions.
- Keep title, subtitle, page size/orientation, and output path grouped as publication settings.
- Treat `Export atlas PDF` as the primary action.
- Show export readiness and last-export status close to the action.
- For export-sensitive changes, validate the exported artifact, not only widget state.

### 2.9 Settings panel rules

The live local-first dock has a dedicated `settings` page. It currently reuses the connection/configuration content, so treat it as the place for durable qfit and provider setup without spreading those controls across daily workflow pages.

Rules:

- Keep durable configuration out of day-to-day workflow panels when possible.
- Group credentials, provider settings, basemap tokens, and advanced runtime preferences separately.
- Show connection readiness before users start provider sync actions from the Data page.
- Keep secret fields protected by default.
- Use provider-specific names only where the setting is truly provider-specific.
- Avoid exposing internal implementation names unless they are useful to users.
- Never show secrets in plain text unless the user explicitly reveals them through a standard password-field affordance.

### 2.10 Status and message language

Use short, concrete status copy.

Good target examples for new or revised copy:

- `Activities stored`
- `No activity layers on the map`
- `Basemap loaded: Outdoors`
- `42 activities match the current filters`
- `Exported atlas PDF`

Existing UI strings may be longer where they double as guidance, such as first-run or navigation summaries. When changing existing copy, prefer incremental alignment with this shorter status style rather than renaming unrelated workflow sections in the same PR.

Avoid vague copy:

- `Done`
- `Failed`
- `Invalid input`
- `Something went wrong`

When something fails, include the next useful step when possible.

### 2.11 Empty states and disabled states

Empty states should explain what is missing and how to proceed.

Examples:

- No credentials: prompt users to configure Strava in Settings.
- No stored activities: prompt users to sync or import data.
- No loaded layers: prompt users to load stored map layers before filtering.
- No atlas pages: explain which data or configuration is required before export.

Disabled actions should not feel broken. Pair disabled state with tooltip or nearby helper text that names the prerequisite.

### 2.12 Advanced options

Advanced options are acceptable when they protect the common path.

Rules:

- Advanced sections should be clearly titled.
- Advanced settings must not interrupt the default workflow.
- If an advanced setting materially changes output, summarize its active state near the workflow result.
- Do not hide essential primary controls inside advanced sections.

### 2.13 Review checklist for qfit UI PRs

This checklist is mandatory for UI PRs.

Buttons:

- [ ] Is there at most one primary button per section?
- [ ] Is the primary clearly the main recommended action?
- [ ] Are secondary buttons neutral/default rather than competing with the primary?
- [ ] Is any navigation styled as a button? If yes, reject or revise.
- [ ] Are destructive actions visually separated and explicitly worded?

Semantics:

- [ ] Can the UI be understood without color?
- [ ] Is any meaning encoded only via borders or outlines? If yes, reject or revise.
- [ ] Are disabled states explained by tooltip or nearby text?

Layout:

- [ ] Does the change follow the live local-first pages: Data, Map, Analysis, Atlas, and Settings?
- [ ] Are configuration fields shown before the actions that use them?
- [ ] Are actions ordered secondary → primary, with destructive actions separated?
- [ ] Are unrelated actions separated?
- [ ] Does focus/reading order match the visual order?
- [ ] Does the layout stay usable in a narrow QGIS dock?

Navigation:

- [ ] Is selection visually distinct from actions?
- [ ] Does navigation avoid filled primary-action styling and button chrome?

Rendering/export:

- [ ] Are rendering/export-sensitive changes validated with screenshots, map output, or exported artifacts when relevant?

Mechanical rejection rules:

- Reject if removing colors makes the UI ambiguous.
- Reject if more than one primary action is visible in a section.
- Reject if navigation elements look like primary or secondary action buttons.

## 3. Implementation notes

- Keep design-system behavior in `ui/` helpers when it is reusable UI glue.
- Keep workflow decisions outside widget classes when practical, following `docs/architecture.md`.
- Prefer small layout updates to broad `.ui` rewrites.
- Add or update tests for UI state rules that can be covered without QGIS.
- For manual QGIS validation, note what was checked and whether the deployed plugin or source checkout was used.
