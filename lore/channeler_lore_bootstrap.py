===============================================================================
BITMULE6 ONBOARDING – THE ASCENDANT
===============================================================================
Role:
Build BidMule into a self-standing application (PR-0074). Integrate the approved
UI interaction set from the Advisor when safe to do so. Law and Lore remain supreme.

Immediate Priority:
PR-0074 – Self-Standing Desktop App
• Goal: Double-click to launch; no Terminal required.
• Packaging: PyInstaller or Briefcase (choose the path with fastest stable result).
• Acceptance: App launches; catalogs and jobs load from user home paths; Help → “About BidMule” shows version, rule set (BM-W-001, BM-F-012), and packaging build id.

When risk permits (or immediately after PR-0074 goes green), implement the following UI sets.

I. CORE INTERACTION SET (PRIMARY BUTTONS)
Purpose: streamline the user’s most frequent tasks in one visual rhythm.

Function              Visual Concept                  Reasoning
Save Estimate         Disk or document + check        Confirms data persistence.
Export / Manifest     Arrow exiting a box             Bridges estimator to real-world docs.
Undo / Redo           Curved back/forward arrows      Natural, universal correction gestures.
Delete Material       Trash bin or X over board       Swift removal; small red accent aids clarity.
Print / Render PDF    Paper with downward arrow       Denotes creation of an artifact.

Placement Guidance:
• Primary toolbar at top-right; consistent hit targets; fixed order: Save, Export, Undo, Redo, Delete, Print.
• Keyboard: Cmd+S Save, Cmd+P Print, Cmd+Z Undo, Shift+Cmd+Z Redo, Delete key for selected row.

II. CATALOG & DATA OPERATIONS (TABLE-ADJACENT CONTROLS)
Used in cost, labor, and materials tables.

Function              Visual Concept                  Reasoning
New Catalog Entry     Plus on layered sheets          Extends “Material Add” pattern; clear affordance.
Duplicate Item        Two overlapping rectangles      Common estimating action; speed for variants.
Sync Hover Data       Cloud with bidirectional arrows Reflects import; aligns with Hover Reset.
Lock / Unlock Item    Padlock open/closed             Protects system-calculated values from edits.
Filter / Search       Funnel or magnifying glass      Focuses attention; narrows fields instantly.

Placement Guidance:
• Secondary toolbar above Materials/Labor tables.
• Locked rows show a subtle lock icon; edits disabled until unlocked.
• Filter/Search opens inline field; Enter applies; Esc clears.

Accessibility & Visual Rhythm:
• Minimum button size 36 px; tooltip on hover; label on focus.
• High-contrast icons; no jitter on show/hide; stable column widths.
• Δ markers remain primary for change state; icons complement, never replace, the Doctrine of Deltas.

Acceptance Criteria (UI Sets):
1) Buttons present, labeled, and keyboard shortcuts work.
2) Save/Export/Print produce expected files without blocking UI.
3) Sync Hover pulls and updates parsed totals; deltas compare against new baselines.
4) Lock status persists with the job; locked cells do not accept edits.
5) Filter narrows rows without reflow jitter; clearing filter restores view.

Doctrine Reminders:
• Anchor Law: all future code changes must be delivered as paste-ready, fully anchored blocks.
• Determinism: identical inputs must yield identical outputs; any recompute is replayable.
• Dual Path: Law governs function and tests; Lore governs symbols and narrative; both are logged.

Handoff Notes from The Steward:
The system functions, but the future depends on packaging stability, UI clarity,
and unbroken lineage records. Proceed with law; let beauty serve clarity.
===============================================================================
End of Onboarding
===============================================================================
