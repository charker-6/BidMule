# trades/registry.py — trade pricing via catalog assemblies

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
      - integer/float literals in strings, e.g. "1"
    """
    if expr.replace(".", "", 1).isdigit():
        return float(expr)
    if expr.startswith("outputs."):
        key = expr.split(".", 1)[1]
        return float(getattr(outputs, key, 0.0))
    return 0.0

def price_trade(trade: str, inputs: JobInputs, outputs: JobOutputs) -> TradeCost:
    cat = load_catalog()
    asm = cat.assembly(trade)
    lis: List[LineItem] = []
    mat_total = 0.0

    region = inputs.region
    finish = inputs.finish
    fascia_w = inputs.fascia_width_in

    # Helper to append one line item
    def _append_line(item_key: str, qty: float, *, finish_keyed: bool = False, fascia_keyed: bool = False):
        nonlocal mat_total, lis
        if not qty:
            return
        uom = cat.raw.get("items", {}).get(item_key, {}).get("uom", "")
        unit_cost = cat.item_cost(
            item_key, region,
            finish=finish if finish_keyed else None,
            fascia_width_in=fascia_w if fascia_keyed else None
        )
        ext = unit_cost * qty
        lis.append(LineItem(item_key, qty, uom, unit_cost, ext))
        mat_total += ext

    # Main assembly includes
    for inc in asm.get("includes", []):
        item = inc["item"]
        qty_expr = inc.get("qty", "0")
        qty = _qty_from_expr(qty_expr, inputs, outputs)

        # Skip zero-qty
        if not qty:
            continue

        # Special handling: substitute planks for generic "siding_sf"
        if item == "siding_sf" and inputs.siding_type == "Lap":
            # Default SKU for Lap @ 8.25 width
            sku = "plank_8_25_cm_colorplus" if finish == "ColorPlus" else "plank_8_25_cm_primed"
            board_qty = int(round(getattr(outputs, "boards", 0) or 0))
            _append_line(sku, board_qty, finish_keyed=False)
            continue

        # Enforce minimum 2 for all trim piece sizes (4/6/8/12)
        if item in ("trim4_12ft", "trim6_12ft", "trim8_12ft", "trim12_12ft"):
            try:
                qty = max(2, int(round(qty)))
            except Exception:
                qty = 2

        # Standard items
        _append_line(
            item, qty,
            finish_keyed=bool(inc.get("finish_keyed")),
            fascia_keyed=bool(inc.get("fascia_width_keyed"))
        )

    # ColorPlus extras (e.g., touchup kits)
    if finish == "ColorPlus":
        for ex in asm.get("colorplus_extras", []):
            item = ex["item"]
            qty = _qty_from_expr(ex.get("qty", "1"), inputs, outputs)
            if qty:
                _append_line(item, qty, finish_keyed=False)

    labor_total = float(outputs.labor_cost)

    return TradeCost(trade=trade, material_cost=round(mat_total, 2),
                     labor_cost=round(labor_total, 2), line_items=lis)

