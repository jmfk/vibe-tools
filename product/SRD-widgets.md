# DKB-01 — Widget Preset Taxonomy & Design Semantics

## Status

**Design Knowledge Base (DKB)** — Informative, Agent-Readable, Human-Writable

This document defines the **canonical widget preset taxonomy** for the Vibe Design Subsystem. These presets are not final implementations. They are **design-time archetypes** that can be:

* Instantiated
* Configured
* Parameterized
* Cloned
* Extended

Presets serve as **semantic anchors** for:

* The Designer Agent
* The Simulation Runtime
* The Export Pipeline
* Human Designers

---

## 1. Purpose

This DKB establishes a **shared vocabulary of UI intent**. When a user or agent says "form," "table," "command palette," or "prompt input," they are referring to a **known structural pattern** with expected behavior, accessibility rules, layout affordances, and export semantics.

PRDs should reference this DKB to avoid redefining widget meaning, behavior, or scope.

Example PRD reference:

> Must use DKB-01: Core Input Widgets → Date Picker (Preset)

---

## 2. Preset Philosophy

Each widget preset is defined as:

* **Semantic Role** — What this widget *means* in a system
* **Structural Shape** — What children it can contain
* **Behavioral Contract** — What interactions it must support
* **Layout Affordances** — How it behaves inside containers
* **Export Expectation** — What kind of React component it becomes

Presets are **not visual themes**. Styling is a layer above semantics.

---

## 3. Core Input Widgets

These represent **user intent capture**. They must support:

* Focus
* Validation
* Disabled / Readonly states
* Accessibility labeling
* Data binding

### Preset List

* Text Field (single-line)
* Password Field
* Multiline Text Area
* Search Field
* Number Input
* Email Input
* URL Input
* Phone Number Input
* Date Picker
* Time Picker
* Date-Time Picker
* Month Picker
* Year Picker
* Color Picker
* File Upload
* Drag-and-Drop File Input
* Slider
* Range Slider
* Stepper / Spinbox
* Rating Input
* Toggle Switch
* Checkbox
* Checkbox Group
* Radio Button
* Radio Group
* Segmented Control
* Combobox
* Dropdown / Select
* Multi-select
* Tag Input
* Token Input
* Autocomplete
* Typeahead
* OTP / PIN Input
* Signature Pad
* Voice Input Button
* Barcode / QR Scanner Input

### Design Semantics

These widgets:

* Emit **value-change events**
* Support **schema-driven validation**
* Can be auto-populated by simulation data

---

## 4. Buttons & Action Widgets

These represent **explicit user action triggers**.

### Preset List

* Button (Primary)
* Button (Secondary)
* Button (Tertiary / Ghost)
* Icon Button
* Floating Action Button (FAB)
* Split Button
* Dropdown Button
* Toggle Button
* Button Group
* Contextual Action Button
* Link Button
* Copy-to-Clipboard Button
* Back / Forward Button
* Close Button
* Expand / Collapse Button

### Design Semantics

These widgets:

* Emit **intent events**, not just clicks
* May require **confirmation contracts**
* Can be bound to agent or tool actions

---

## 5. Navigation Widgets

These control **spatial and hierarchical movement**.

### Preset List

* Top Navigation Bar
* Bottom Navigation Bar
* Sidebar / Drawer
* Collapsible Sidebar
* Tab Bar
* Tabs (Horizontal)
* Tabs (Vertical)
* Breadcrumbs
* Pagination
* Stepper / Wizard
* Accordion
* Tree View
* Menu
* Mega Menu
* Context Menu
* Hamburger Menu
* Navigation Rail
* Command Palette
* Jump List
* Anchor Navigation (ScrollSpy)

### Design Semantics

These widgets:

* Define **navigation state**
* Can drive **layout transitions**
* Must expose **current position in hierarchy**

---

## 6. Layout & Structural Widgets

These define **spatial logic, not content**.

### Preset List

* Container
* Box
* Stack (Vertical / Horizontal)
* Grid
* Masonry Grid
* Split Pane
* Resizable Pane
* Scroll View
* Virtualized List Container
* Spacer
* Divider
* Separator
* Aspect Ratio Box
* Overlay
* Portal
* Dock Panel
* Canvas
* Viewport
* Safe Area Container

### Design Semantics

These widgets:

* Do not own business logic
* Influence **layout resolution** and **responsiveness rules**
* Are first-class in the layout solver

---

## 7. Display & Content Widgets

These are primarily **read-only or semi-read-only**.

### Preset List

* Text
* Heading (H1–H6)
* Label
* Paragraph
* Badge
* Chip
* Tag
* Avatar
* Avatar Group
* Icon
* Image
* Image Gallery
* Carousel
* Slideshow
* Video Player
* Audio Player
* PDF Viewer
* Markdown Renderer
* Code Block
* Syntax Highlighted Editor (read-only)
* Tooltip
* Popover
* Callout
* Help Bubble
* Inline Hint
* Empty State
* Placeholder / Skeleton
* Watermark

### Design Semantics

These widgets:

* Accept **content bindings**
* Support **loading and empty states**
* Are often paired with data display widgets

---

## 8. Data Display Widgets

These represent **structured and high-density information**.

### Preset List

* Table
* Data Grid
* Tree Table
* Pivot Table
* List
* Definition List
* Key–Value List
* Timeline
* Activity Feed
* Log Viewer
* Change History Viewer
* Diff Viewer
* JSON Viewer
* YAML Viewer
* XML Viewer
* Chart (Bar)
* Chart (Line)
* Chart (Area)
* Chart (Pie / Donut)
* Chart (Scatter)
* Chart (Radar)
* Chart (Heatmap)
* Chart (Gantt)
* Chart (Sankey)
* Chart (Histogram)
* Sparkline
* KPI Tile / Metric Card
* Dashboard Panel

### Design Semantics

These widgets:

* Bind to **datasets, not single values**
* Support **sorting, filtering, and pagination hooks**
* May expose **export and snapshot behavior**

---

## 9. Feedback & Status Widgets

These express **system truth to the user**.

### Preset List

* Alert
* Toast / Snackbar
* Notification Center
* Banner
* Inline Error Message
* Validation Message
* Progress Bar
* Progress Circle
* Loading Spinner
* Skeleton Loader
* Success Indicator
* Warning Indicator
* Error Indicator
* Status Pill
* Health Indicator
* Connection Status
* Sync Status
* Retry Panel

### Design Semantics

These widgets:

* Reflect **system state**
* Should be **non-blocking by default**
* Can be agent-driven or system-driven

---

## 10. Modal & Overlay Widgets

These represent **context interruption layers**.

### Preset List

* Modal Dialog
* Confirmation Dialog
* Alert Dialog
* Bottom Sheet
* Side Sheet
* Fullscreen Dialog
* Lightbox
* Popover Dialog
* Drawer Modal
* Command Dialog

### Design Semantics

These widgets:

* Suspend or redirect interaction flow
* Must define **escape and dismissal contracts**

---

## 11. Forms & Form Infrastructure

These are **composite, schema-driven systems**.

### Preset List

* Form
* Fieldset
* Form Section
* Form Step
* Inline Form
* Wizard Form
* Dynamic Form
* Schema-driven Form
* Validation Summary
* Submit Bar
* Reset Button
* Autosave Indicator

### Design Semantics

These widgets:

* Own **data lifecycle**
* Define **submission contracts**
* Interface with validation engines

---

## 12. Selection & Organization Widgets

These support **classification and filtering**.

### Preset List

* Filter Panel
* Faceted Filter
* Search with Filters
* Sort Control
* Grouping Control
* Tag Selector
* Category Picker
* Tree Selector
* Hierarchical Dropdown
* Dual Listbox (Transfer List)
* Reorderable List
* Drag Handle

### Design Semantics

These widgets:

* Manipulate **views of datasets**, not datasets themselves

---

## 13. Editing & Creation Widgets

These represent **high-power authoring tools**.

### Preset List

* Rich Text Editor
* Markdown Editor
* Code Editor
* Diff Editor
* Visual Canvas Editor
* Node Graph Editor
* Flowchart Editor
* Diagram Editor
* Timeline Editor
* Formula Editor
* Spreadsheet Grid
* Inline Editor
* Contenteditable Block

### Design Semantics

These widgets:

* Own **internal state machines**
* Require **undo/redo contracts**
* Often integrate toolchains

---

## 14. System & Meta Widgets

These expose **platform-level capabilities**.

### Preset List

* Settings Panel
* Preferences Pane
* Keyboard Shortcut Overlay
* Debug Panel
* Inspector Panel
* Permissions Prompt
* Feature Flag Toggle
* Environment Switcher
* Theme Switcher
* Language Selector
* Accessibility Controls
* Zoom Controls

### Design Semantics

These widgets:

* Interface with **host system APIs**
* May be restricted by security policy

---

## 15. Mobile-Specific Widgets

These reflect **touch-first interaction models**.

### Preset List

* Pull-to-Refresh
* Swipe Actions
* Bottom Tab Bar
* Floating Toolbar
* Gesture Area
* Haptic Feedback Trigger
* Camera View
* Map View
* Location Picker
* Compass
* Gyroscope View

---

## 16. AI / Agent-Oriented Widgets

These define **human–agent interaction surfaces**.

### Preset List

* Prompt Input
* Prompt History
* Agent Status Panel
* Streaming Output View
* Token Usage Meter
* Cost Meter
* Reasoning Trace Viewer
* Tool Invocation Log
* Editable Generated Content
* Human-in-the-loop Approval Panel
* Confidence / Uncertainty Indicator
* Retry / Regenerate Control

### Design Semantics

These widgets:

* Must expose **agent state** and **confidence**
* Support **intervention and override contracts**

---

## 17. Agent Usage Contract

Agents using this DKB:

* Must select the **closest semantic preset** before generating custom widgets
* Should prefer **composition over invention**
* Must annotate deviations from preset semantics

---

## 18. Export Mapping Principles

Each preset should map to:

* A React component archetype
* A styling contract
* An accessibility contract
* A test harness template

---

## 19. Versioning

* DKB-01 is versioned independently of PRDs
* Preset additions are **backward-compatible by default**
* Semantic changes require a major version bump

---

## 20. Long-Term Direction

This taxonomy is intended to evolve into a **UI semantic standard** where:

* Agents reason in presets
* Designers compose in presets
* Code exports enforce presets

At that point, UI becomes a **typed language**, not a collection of divs.

---
<details>
<summary>Metadata</summary>

```yaml
id: SRD-widgets
title: "DKB-01 \u2014 Widget Preset Taxonomy & Design Semantics"
type: FEATURE
status: backlog
group: null
depends_on: []
created_at: '2026-01-17T22:38:42.102419'
updated_at: '2026-01-17T22:40:12.030950'
```
</details>

<!-- vibe-id: SRD-widgets -->
