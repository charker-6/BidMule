# lore_epoch_seed.py — first epoch seeding (idempotent by law codes and simple duplication guards)
from lorekeeper import (
    append_to_chronicles,
    append_to_advisorcodex,
    append_to_prophecies,
    append_law_once,
)

# chronicle: epoch seeding
append_to_chronicles("epoch seeding", [
    "scope: initialize passive logging and seed baseline records",
    "bitmule: 5 (preparing for 6)",
    "intent: passive, continuous recording without user burden",
])

# advisor codex: icon set entries (save, export/manifest, undo/redo, delete, print, catalog refresh)
append_to_advisorcodex("icon set - primary actions", [
    "save estimate: disk with check mark; confirms persistence",
    "export / manifest: arrow leaving box; bridge to reality",
    "undo / redo: curved arrows; quick correction",
    "delete / remove: trash bin or x over board; immediate clarity",
    "print / render pdf: paper with downward arrow; artifact creation",
    "catalog refresh: rotated arrows; reload local catalog only",
])

# advisor codex: ui motif notes
append_to_advisorcodex("ui motifs", [
    "body color panels mirror siding catalog hierarchy",
    "deltas: triangles; green accepted, red pending",
    "reset to hover: gear glyph; re-parse from source",
    "tone: plain speech; structure carries reverence",
])

# laws index: baseline rules (added once by code)
append_law_once("bm-w-001", "siding waste rule - 20% base, +3% medium, +7% high.")
append_law_once("bm-w-002", "roofing waste rule - 10% default unless roof-specific data dictates otherwise.")
append_law_once("bm-w-003", "gutters waste rule - 10% default for aluminum continuous systems.")
append_law_once("bm-f-012", "fascia length rule - 12 ft standard board length.")
append_law_once("bm-a-001", "anchor law - all code must include anchors and indentation.")
append_law_once("bm-d-001", "determinism doctrine - identical inputs must yield identical outputs.")
append_law_once("bm-l-001", "dual path mandate - law and lore operate in harmony.")
append_law_once("bm-gm-035", "gross margin targets - siding 35%, roofing 35%, gutters 30%.")
append_law_once("bm-v-150", "ventilation baseline - attic net free vent area to meet 1/150 unless code/assembly dictates exception.")

# prophecies: near-term targets registered as guidance only (not a build order)
append_to_prophecies("near-term objectives", [
    "pr-0074: self-standing desktop app (no terminal dependency); pyinstaller or briefcase candidate",
    "pr-0075: roofing + gutters expansion after standalone stability",
    "adaptive parsing: learn template variations with user-verified corrections",
    "eternal directive: beauty may wander; law must remain",
])

print("epoch one seeding complete.")
