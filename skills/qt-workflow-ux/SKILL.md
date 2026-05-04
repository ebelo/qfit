---
name: qt-workflow-ux
description: Use when designing, reviewing, or refactoring Qt/PyQt/QGIS workflow UIs for complex expert systems, especially when navigation, actions, status, button hierarchy, progressive disclosure, or workflow panel structure need to be made clear and maintainable.
---

# Qt Workflow UX

Use this skill for Qt, PyQt, and QGIS plugin interfaces that contain multiple workflows, expert-domain tools, or long task sequences.

## Core contract

Every visible UI element must have exactly one job:

- **Navigation** — where the user is or what workflow is selected.
- **Action** — what the user can do now.
- **Status** — what happened, what is running, or what is missing.

If one element mixes these roles, redesign the structure before polishing styling.

## Workflow layout pattern

Prefer a two-part workflow panel for complex tools:

```text
[ navigation list / tabs ] | [ active workflow panel ]
```

Use native Qt structure first:

- `QListWidget`, `QTreeWidget`, or tabs for navigation/selection.
- `QStackedWidget` for switching workflow content.
- `QVBoxLayout` for vertical workflow order.
- `QFormLayout` for field/value inputs.
- `QGroupBox` or titled sections for logical grouping.
- `QPushButton` / `QToolButton` for actions only.

## Navigation rules

Navigation is selection, not action.

- Use list, tree, or tab selection patterns.
- Show selected/current state with neutral selection styling and text.
- Do not use filled primary/accent color for selection.
- Do not use `QPushButton`, `QToolButton`, or button-like chrome for navigation.
- Do not rely on color alone; expose status in text or tooltip.

## Workflow panel order

Each workflow section should read top-to-bottom:

1. Title.
2. Short state/explanation.
3. Content: forms, choices, inputs, previews.
4. Secondary actions.
5. Primary action last/rightmost.
6. Destructive action separated from normal actions.
7. Inline status/result feedback near the action that produced it.

Configuration should appear before the action that uses it. Essential controls should not be hidden in advanced sections.

## Button system

Use four action roles:

- **Primary** — the one recommended next action; filled accent treatment is acceptable.
- **Secondary** — normal supporting actions; use native/default Qt styling.
- **Tertiary** — low-priority supplemental actions; subtle and optional.
- **Destructive** — risky/data-loss actions; explicit wording and separated placement.

Rules:

- At most one primary action per section.
- Primary is never navigation or selected state.
- Destructive is never primary and must include explicit wording such as `Clear`, `Delete`, or `Remove`.
- Do not encode meaning only with color, border, or outline differences.
- Within a row or stack, order secondary actions before the primary action.

## Progressive disclosure

Expert users still need hierarchy.

- Show the default workflow path first.
- Put advanced options in collapsible sections when they are not required.
- Show a summary when advanced options materially change output.
- Never hide required actions or blocking prerequisites in advanced areas.

## Status and feedback

Use inline feedback for normal workflow state:

- Empty: `No data loaded. Load data before running analysis.`
- Running: `Exporting atlas PDF…`
- Success: `Export completed: 42 pages written.`
- Warning/error: name the missing input, failed step, or next recovery action.

Avoid modal dialogs for routine progress, success, or recoverable validation issues. Reserve dialogs for blocking errors and destructive confirmations.

## Refactor workflow

When improving an existing Qt workflow UI:

1. Inventory the current UI as navigation, actions, status, content, and advanced options.
2. Identify mixed-role elements, competing primary actions, and color/border-only semantics.
3. Propose the new structure before changing styling.
4. Map the structure to native Qt widgets and layouts.
5. Classify every action as primary, secondary, tertiary, or destructive.
6. Add focused tests for behavior/state and screenshot evidence for visible layout changes when practical.

## Review checklist

Reject or revise a UI change if:

- navigation is implemented with buttons or button-like styling
- more than one element competes as primary in a section
- primary styling is used for navigation, selection, or status
- destructive actions are green, primary, or visually mixed with normal actions
- users must understand color or borders to know what to do
- status/result copy is far from the action or workflow it describes
- unrelated actions are grouped together without workflow hierarchy
