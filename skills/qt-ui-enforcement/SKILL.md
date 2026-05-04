---
name: qt-ui-enforcement
description: Use as a strict PR review or audit gate for Qt, PyQt, or QGIS UI changes. Prefer this over qt-workflow-ux when deciding whether to approve, request changes, or reject UI work involving layout, panels, buttons, navigation, or workflow behavior.
---

# Qt UI Enforcement

Use this skill as a review gate for Qt/PyQt/QGIS UI changes. Be strict: reject or request redesign when the interface becomes ambiguous, inconsistent, or hard to scale for expert workflows.

## Core classification rule

Every UI element must be exactly one of:

1. **Navigation** — where the user is or which workflow is selected.
2. **Action** — what the user can do now.
3. **Status** — what happened, what is running, or what is missing.
4. **Input** — what the user configures before acting.

If an element mixes roles, request a structural redesign before accepting styling tweaks.

## Mandatory checks

### 1. Navigation

Reject if navigation:

- uses `QPushButton`, `QToolButton`, or button-like chrome
- looks like an action row
- uses primary/accent color, filled green, or danger styling for selected state
- depends on color alone to communicate selected/current state

Expected patterns:

- `QListWidget`, `QTreeWidget`, tabs, or an equivalent selection-list pattern
- neutral selected background
- bold selected label
- status exposed in text or tooltip, not only color

### 2. Button hierarchy

Reject if:

- more than one primary button is visible in one section
- the primary button is not the obvious recommended action
- primary styling is used for navigation, selection, status, or destructive actions
- destructive action looks like primary
- button meaning depends on border color, outline style, or shade of grey

Required action roles:

| Type | Meaning |
| --- | --- |
| Primary | Main recommended action |
| Secondary | Normal supporting action |
| Tertiary | Low-priority supplemental action |
| Destructive | Risky or data-loss action |

### 3. Action ordering

Within a section, actions must be ordered:

```text
secondary actions
primary action last/rightmost
destructive action separated
```

Reject action rows that mix unrelated workflows or place destructive actions beside normal actions without separation.

### 4. Input-before-action flow

Reject if:

- users are asked to run an action before seeing the inputs that determine it
- essential inputs are hidden in advanced sections
- advanced options materially change output but are not summarized
- disabled actions lack nearby prerequisite copy or tooltip guidance

### 5. Status and feedback

Reject if:

- result/status text is far from the action or workflow it describes
- normal success/progress feedback is only modal
- errors are vague, color-only, or do not name a recovery step
- status is styled like navigation or an action

Expected inline feedback examples:

- `No data loaded. Load data before running analysis.`
- `Exporting atlas PDF…`
- `Export completed: 42 pages written.`
- `Missing input: choose an output folder before exporting.`

## Review procedure

1. Inventory changed widgets as navigation, actions, status, and inputs.
2. Count primary actions per visible section.
3. Check action order and destructive-action separation.
4. Verify navigation cannot be mistaken for actions.
5. Verify the UI remains understandable without color or border semantics.
6. Confirm tests or screenshots cover visible behavior changes when practical.

## Decision language

Use clear review outcomes:

- **Approve** when the UI satisfies the classification, hierarchy, ordering, and feedback checks.
- **Request changes** when a mandatory check fails.
- **Comment** when the issue is a non-blocking consistency improvement.

When requesting changes, name the failed rule and propose the smallest structural fix, not just a color change.
