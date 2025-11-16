# trades/registry.py — trade pricing via catalog assemblies
# Contract: defensive, variant-aware, and deterministic.
# - Robust to missing assembly/items; never crashes.
# - Board & Batten expands generic siding area into panels + battens.
# - Lap uses outputs.boards for plank count (preserves original behavior).
# - B&B auto-remaps 5/4 trim to 4/4 family (surface-aware) with min-2 rule.
# - Unit pricing resolved via catalog with optional finish/fascia/surface variants.
# - Labor passes through from outputs; if absent/zero, compute UI-parity fallback.

from dataclasses import dataclass
from typing import List
from core.catalog import load_catalog
from engine import JobInputs, JobOutputs

@dataclass
class LineItem:
    name: str
    qty: float
    uom: str
    unit_cost: float
    ext_cost: float

@dataclass
class TradeCost:
    trade: str
    material_cost: float
    labor_cost: float
    line_items: List[LineItem]

def _qty_from_expr(expr: str, inputs: JobInputs, outputs: JobOutputs) -> float:
    """
    Minimal expression resolver. Supported:
      - "outputs.total_sf", "outputs.wrap_rolls", etc.
      - integer/float literals in strings, e.g. "1" or "2.5"
    """
    s = (expr or "").strip()
    if s.replace(".", "", 1).isdigit():
        try:
            return float(s)
        except Exception:
            return 0.0
    if s.startswith("outputs."):
        key = s.split(".", 1)[1]
        try:
            return float(getattr(outputs, key, 0.0))
        except Exception:
            return 0.0
    return 0.0

def price_trade(trade: str, inputs: JobInputs, outputs: JobOutputs) -> TradeCost:
    """
    Price a trade using the catalog assembly + inputs/outputs.
    - Reads assembly 'includes' and optional 'colorplus_extras'.
    - Honors include flags:
        finish_keyed:        resolve price based on finish (ColorPlus/Primed)
        fascia_width_keyed:  resolve price based on fascia_width_in
    - Special cases:
        * 'siding_sf' item expands by siding_type:
            - Lap → plank SKU from outputs.boards (8.25 CM, finish-aware)
            - B&B → 4x10 panels + 12' battens (finish-aware), skip generic 'siding_sf'
        * Auto-remap 5/4 trim to 4/4 family for B&B with surface default, min-2 rule
    - Labor:
        Uses outputs.labor_cost if present; else computes deterministic fallback
        matching the UI math (LABOR_RATES, demo credit, layers, substrate bump).
    """
    cat = load_catalog()
    try:
        asm = cat.assembly(trade) or {}
    except Exception:
        asm = {}

    lis: List[LineItem] = []
    mat_total = 0.0

    region = getattr(inputs, "region", "Metro")
    finish = getattr(inputs, "finish", "ColorPlus")
    fascia_w = getattr(inputs, "fascia_width_in", 8)

    # Pull trim-family defaults from catalog (for surface-aware 4/4)
    try:
        trim_fams = cat.trim_families() or {}
    except Exception:
        trim_fams = {}
    use_trim_family = "4/4" if (str(getattr(inputs, "siding_type", "")).strip().lower()
                                in ("board & batten", "board and batten", "board &amp; batten")) else "5/4"
    surface_default_44 = (trim_fams.get("4/4", {}) or {}).get("surface_default", "Rustic")

    # Helper to append one line item
    def _append_line(item_key: str, qty: float,
                     *, finish_keyed: bool = False,
                     fascia_keyed: bool = False,
                     surface_keyed: bool = False,
                     surface_value: str | None = None):
        nonlocal mat_total, lis
        try:
            q = float(qty or 0.0)
        except Exception:
            q = 0.0
        if q <= 0.0:
            return

        try:
            uom = str(cat.raw.get("items", {}).get(item_key, {}).get("uom", "") or "")
        except Exception:
            uom = ""

        # Resolve price with optional variant dimensions
        try:
            unit_cost = float(cat.item_cost(
                item_key,
                region,
                finish=(finish if finish_keyed else None),
                fascia_width_in=(fascia_w if fascia_keyed else None),
                surface=(surface_value if surface_keyed else None),
            ) or 0.0)
        except Exception:
            unit_cost = 0.0

        ext = float(q) * float(unit_cost)
        lis.append(LineItem(item_key, float(q), uom, float(unit_cost), float(ext)))
        mat_total += float(ext)

    # --- convenience (trim-keys map for 4/4 family) ---
    TRIM_44_MAP = {
        "trim4_12ft":  "trim44_4_12ft",
        "trim6_12ft":  "trim44_6_12ft",
        "trim8_12ft":  "trim44_8_12ft",
        "trim12_12ft": "trim44_12_12ft",
    }

    # --- Board & Batten materials (panels + battens) ---
    def _append_board_and_batten_materials():
        """Expand generic siding area into BB 4x10 panels and 12' battens (finish-aware)."""
        from math import ceil

        # Surface basis: same rule as UI — use max(facades_sf, trim_siding_sf)
        try:
            base_sf = max(float(getattr(inputs, "facades_sf", 0.0) or 0.0),
                          float(getattr(inputs, "trim_siding_sf", 0.0) or 0.0))
        except Exception:
            base_sf = 0.0

        # Waste rule (engine constants if available; else safe fallback)
        try:
            from engine import WASTE_BASE_SIDING, WASTE_COMPLEXITY
            complexity = str(getattr(inputs, "complexity", "Low") or "Low")
            waste = float(WASTE_BASE_SIDING) + float(WASTE_COMPLEXITY.get(complexity, 0.0))
        except Exception:
            complexity = str(getattr(inputs, "complexity", "Low") or "Low")
            waste = 0.20 + (0.03 if complexity == "Med" else (0.07 if complexity == "High" else 0.00))

        sf_with_waste = base_sf * (1.0 + float(waste))
        panels = int(ceil(sf_with_waste / 40.0))   # 4×10 = 40 sf per panel
        battens = int(ceil(max(0, panels) * 3.0)) # ~3 battens per panel

        if panels > 0:
            _append_line("bb_panel_4x10", panels, finish_keyed=True)
        if battens > 0:
            _append_line("bb_batten_12ft", battens, finish_keyed=True)

    # --- includes expansion ---
    includes = []
    try:
        includes = list(asm.get("includes", []) or [])
    except Exception:
        includes = []

    for inc in includes:
        try:
            item = inc["item"]
        except Exception:
            continue

        qty_expr = inc.get("qty", "0")
        qty = _qty_from_expr(qty_expr, inputs, outputs)

        # Skip zero-qty
        if not qty:
            continue

        # --- Special handling: siding area expansion ---
        if item == "siding_sf":
            st = (str(getattr(inputs, "siding_type", "") or "").strip().lower())
            if st == "lap":
                # Lap → planks (8.25 CM) based on outputs.boards (preserve original behavior)
                sku = "plank_8_25_cm_colorplus" if finish == "ColorPlus" else "plank_8_25_cm_primed"
                try:
                    board_qty = int(round(float(getattr(outputs, "boards", 0) or 0)))
                except Exception:
                    board_qty = 0
                if board_qty > 0:
                    _append_line(sku, board_qty, finish_keyed=False)
                # Do not append a generic 'siding_sf' row
                continue
            elif st in ("board & batten", "board and batten", "board &amp; batten"):
                # B&B → expand to panels + battens (no generic 'siding sf' row)
                _append_board_and_batten_materials()
                continue
            # Shake (or anything else) falls through to generic 'siding_sf' pricing (assembly-driven)

        # --- Auto-map trim to 4/4 when B&B is selected ---
        if use_trim_family == "4/4" and item in TRIM_44_MAP:
            mapped = TRIM_44_MAP[item]
            # Respect min-2 rule and use surface-aware resolution
            try:
                qty_safe = max(2, int(round(float(qty))))
            except Exception:
                qty_safe = 2
            _append_line(
                mapped, qty_safe,
                finish_keyed=True,
                surface_keyed=True,
                surface_value=surface_default_44,
            )
            continue

        # Enforce minimum 2 for all 5/4 trim piece sizes
        if item in ("trim4_12ft", "trim6_12ft", "trim8_12ft", "trim12_12ft"):
            try:
                qty = max(2, int(round(float(qty))))
            except Exception:
                qty = 2

        # Standard items (finish/fascia width keyed per assembly flags)
        _append_line(
            item, qty,
            finish_keyed=bool(inc.get("finish_keyed")),
            fascia_keyed=bool(inc.get("fascia_width_keyed")),
        )

    # ColorPlus extras (e.g., touchup kits)
    if finish == "ColorPlus":
        for ex in (asm.get("colorplus_extras", []) or []):
            try:
                item = ex["item"]
            except Exception:
                continue
            qty = _qty_from_expr(ex.get("qty", "1"), inputs, outputs)
            if qty:
                _append_line(item, qty, finish_keyed=False)

    # ---- Labor passthrough + fallback (UI-parity) ----
    try:
        labor_total = float(getattr(outputs, "labor_cost", 0.0) or 0.0)
    except Exception:
        labor_total = 0.0

    if labor_total <= 0.0:
        # Derive total squares from outputs or inputs
        try:
            total_sq = float(
                getattr(outputs, "total_sq", 0.0)
                or getattr(outputs, "total_squares", 0.0)
                or 0.0
            )
        except Exception:
            total_sq = 0.0

        if total_sq <= 0.0:
            # Derive from SF if outputs don’t carry squares
            try:
                base_sf = max(float(getattr(inputs, "facades_sf", 0.0) or 0.0),
                              float(getattr(inputs, "trim_siding_sf", 0.0) or 0.0))
            except Exception:
                base_sf = 0.0
            total_sq = round(base_sf / 100.0, 2) if base_sf > 0 else 0.0

        # Compose $/SQ using the same constants and policy as the UI
        try:
            from engine import LABOR_RATES, NO_DEMO_CREDIT_PER_SQ, EXTRA_LAYER_ADD_PER_SQ, BRICK_STUCCO_ADD_PER_SQ
        except Exception:
            LABOR_RATES = {"Lap": {"Metro": 3.35}}
            NO_DEMO_CREDIT_PER_SQ = 0.0
            EXTRA_LAYER_ADD_PER_SQ = 0.0
            BRICK_STUCCO_ADD_PER_SQ = 0.0

        try:
            stype = str(getattr(inputs, "siding_type", "Lap"))
            base_sf_rate = float(LABOR_RATES.get(stype, LABOR_RATES.get("Lap", {})).get(region, 3.35))
        except Exception:
            base_sf_rate = 3.35

        psq = 100.0 * base_sf_rate  # convert $/SF to $/SQ

        try:
            demo_required = bool(getattr(inputs, "demo_required", True))
        except Exception:
            demo_required = True
        if not demo_required:
            try:
                psq += float(NO_DEMO_CREDIT_PER_SQ)
            except Exception:
                pass

        try:
            layers = int(getattr(inputs, "extra_layers", 0) or 0)
            psq += float(EXTRA_LAYER_ADD_PER_SQ) * max(0, layers)
        except Exception:
            pass

        try:
            substrate = str(getattr(inputs, "substrate", "") or "").lower()
            if substrate in ("brick", "stucco"):
                psq += float(BRICK_STUCCO_ADD_PER_SQ)
        except Exception:
            pass

        labor_total = round(float(psq) * float(total_sq), 2)

    return TradeCost(
        trade=trade,
        material_cost=round(float(mat_total), 2),
        labor_cost=round(float(labor_total), 2),
        line_items=lis,
    )
