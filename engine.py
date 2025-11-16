# >>> BEGIN ENGINE FILE <<<
# engine.py — BidMule Estimator Core Engine (Phase 2, Upgrade 1.2)
# ---------------------------------------------------------------------
# - Data model for inputs/outputs
# - Core siding quantity & labor calculations
# - Robust HOVER PDF text parsing (name/address + key totals)
# - Region inference (Metro / North CO / Mountains)
# - Scalability: input normalization, single ft/in parser, service fallback
# - Corrected soffit panel math (area-based), constants centralized
# - NEW: Board & Batten nail boxes driven by catalog tables (coverage→panel),
#        configurable battens-per-panel factor, and fastener coefficients.
# - FIXES: Lap reveal drives nominal width for materials; service adapter passes
#          nominal width; materials labels rewritten to correct width.

from __future__ import annotations

import math
from core.rules import ceil_pieces
import re
from dataclasses import dataclass

# --- rules guard (ensures names exist before compute_estimate) ---
try:
    from core.rules import siding_area_rule
except Exception:
    pass
# 
# ============================== CONSTANTS ==============================

LABOR_RATES = {
    "Lap": {"Metro": 3.35, "North CO": 3.50, "Mountains": 3.75},
    "Board & Batten": {"Metro": 3.10, "North CO": 3.35, "Mountains": 3.50},
    "Shake": {"Metro": 4.00, "North CO": 4.00, "Mountains": 4.00},
}

WASTE_BASE_SIDING = 0.20
WASTE_COMPLEXITY = {"Low": 0.00, "Med": 0.03, "High": 0.07}

BOARD_COVERAGE_SF = 7.0            # HardiePlank 8.25" @ 7" exposure
WRAP_ROLL_SF = 1350.0
WRAP_WASTE = 0.20
# If you prefer to drive nail boxes by squares, keep this (currently informational)
NAIL_BOX_PER_SQ = 20.0             # (optional) 1 box / 20 squares
NAILS_PER_BOX = 2500               # legacy Lap/Shake conversion to boxes (B&B pulls from catalog)
COIL_SQ_PER_ROLL_PRIMED = 5.0
COIL_SQ_PER_ROLL_COLORPLUS = 2.5   # per color (body + trim)
COIL_REDUCTION = 0.5               # reduce coil count by 50%
TAPE_PER_WRAP_ROLL = 2

# Soffit constants
SOFFIT_PANEL_AREA_SF = 40.0        # 4x10 panel
SOFFIT_WASTE = 0.10                # modest fitting waste on soffit area

# Labor adders/credits per square
NO_DEMO_CREDIT_PER_SQ = -30.0
EXTRA_LAYER_ADD_PER_SQ = 60.0
BRICK_STUCCO_ADD_PER_SQ = 150.0

# --- Lap reveal ↔ nominal width mapping (Hardie®) ---
# Catalog-standard reveals and their corresponding nominal board widths.
_LAP_REVEAL_TO_NOMINAL = {
    4.0: 5.25,
    5.0: 6.25,
    6.0: 7.25,
    7.0: 8.25,
    8.0: 9.25,
    10.75: 12.0,
}

def _snap_reveal_to_catalog(reveal_in: float | None) -> float:
    """Snap a selected reveal to the nearest catalog-supported value.
    Tolerance is 1/8″ to avoid float fuzz; otherwise fall back to nearest key."""
    if reveal_in is None:
        return 7.0
    try:
        r = float(reveal_in)
    except Exception:
        r = 7.0
    # round to nearest 1/4" first (UI dropdown is discrete, but be safe)
    r = round(r * 4.0) / 4.0
    # pick nearest supported reveal
    closest = min(_LAP_REVEAL_TO_NOMINAL.keys(), key=lambda k: abs(k - r))
    # accept if within 1/8"
    if abs(closest - r) <= 0.125:
        return closest
    return closest




# =================== ENGINE→SIDING SERVICE ADAPTER =====================

def _build_siding_service_query(inp: "JobInputs", out: "JobOutputs"):
    """
    Create a duck-typed 'questionnaire-like' object for the Siding service.
    Uses engine inputs/outputs; fills defaults for not-yet-exposed UI fields.
    """
    from types import SimpleNamespace

    # Defaults per spec until UI exposes these:
    shake_profile = getattr(inp, "shake_profile", None) or "Straight"   # A4: default Straight
    bnb_surface   = getattr(inp, "bnb_surface", None) or "Rustic"       # keep "Rustic" until SM selectable

    # Soffit: >24" → use 4x10 panels; else use 8' boards path (service handles qty math)
    use_panels = bool(getattr(inp, "soffit_depth_gt_24", False))

    # Lap reveal/nominal (snapped to catalog)
    lap_reveal_snapped = _snap_reveal_to_catalog(getattr(inp, "lap_reveal_in", None))
    lap_nominal_in     = _nominal_width_for_reveal(lap_reveal_snapped)

    q = SimpleNamespace(
        # primary selectors
        siding_type=getattr(inp, "siding_type", "Lap"),
        siding_squares=int(getattr(out, "total_sq", 0) or 0),
        finish=getattr(inp, "finish", "ColorPlus"),
        complexity=getattr(inp, "complexity", "Low"),

        # shake-specific
        shake_profile=shake_profile,

        # board & batten-specific
        bnb_surface=bnb_surface,   # "Rustic" | "Smooth" (SM staged)

        # soffit inputs (service will branch on use_panels flag)
        soffit_enabled=bool(getattr(inp, 'soffit_enabled', False)),
        eave_lf=float(getattr(inp, "eave_fascia_ft", 0.0) or 0.0),
        rake_lf=float(getattr(inp, "rake_fascia_ft", 0.0) or 0.0),
        soffit_use_panels_4x10=use_panels,
        soffit_depth_in=30.0 if use_panels else 18.0,  # informational only for now

        # lap-specific (NEW)
        lap_reveal_in=lap_reveal_snapped,
        lap_nominal_width_in=lap_nominal_in,
    )
    return q


def _rewrite_lap_width_on_line_items(items, lap_nominal_in: float, lap_reveal_in: float | None = None):
    """
    Post-process service materials: if a Lap line item label still says a nominal width
    (e.g., 8.25"), rewrite it to the correct nominal width for the chosen reveal.
    Touches only Lap/plank-like SKUs (ignores soffit etc).
    Supports dict line items or objects with textual fields.
    """
    if not items:
        return items

    width_tokens = ["5.25", "6.25", "7.25", "8.25", "9.25", "12"]
    width_re = re.compile(rf'(?<!\d)({"|".join(map(re.escape, width_tokens))})\s*"', re.I)

    def _is_lap_label(text: str) -> bool:
        t = (text or "").lower()
        return ("lap" in t or "hardieplank" in t or "plank" in t) and ("soffit" not in t)

    def _fix_text(text: str) -> str:
        if not text or not _is_lap_label(text):
            return text
        return width_re.sub(f'{_fmt_inches(lap_nominal_in)}"', text)

    for li in items:
        # dict-like
        if isinstance(li, dict):
            for key in ("name", "title", "label", "description", "desc"):
                if key in li and isinstance(li[key], str):
                    li[key] = _fix_text(li[key])
        else:
            # object-like
            for attr in ("name", "title", "label", "description", "desc"):
                if hasattr(li, attr):
                    try:
                        val = getattr(li, attr)
                        if isinstance(val, str):
                            setattr(li, attr, _fix_text(val))
                    except Exception:
                        pass
    return items


def _split_color_coils(line_items, finish: str, body_color: str, trim_color: str):
    """
    Replace any coil line(s) with two color-labeled coil rows when finish is ColorPlus or Woodtone:
      - {Body Color} Trim Coil  qty = ceil(total_coil_qty / 4)
      - {Trim Color} Trim Coil  qty = ceil(total_coil_qty / 4)
    Keep Primed behavior unchanged (return items as-is).
    """
    try:
        fin = (finish or "").strip().lower()
    except Exception:
        fin = ""

    if fin not in ("colorplus", "woodtone"):
        return line_items

    if not line_items:
        return line_items

    # Identify coil rows and aggregate their quantities
    def _is_coil(li):
        txts = []
        for k in ("item","sku","key","code","name","title","label","description","desc"):
            v = None
            if isinstance(li, dict):
                v = li.get(k)
            else:
                v = getattr(li, k, None)
            if isinstance(v, str):
                txts.append(v.lower())
        t = " ".join(txts)
        return ("coil" in t) or ("coil_roll" in t)

    # Extract quantity/unit price from a line item
    def _get_qty(li):
        for k in ("qty","quantity","count","units"):
            if isinstance(li, dict) and k in li:
                try: return float(li[k])
                except Exception: pass
            elif hasattr(li, k):
                try: return float(getattr(li, k))
                except Exception: pass
        return 0.0

    def _set_qty(li, q):
        if isinstance(li, dict):
            li["qty"] = int(q)
        else:
            try: setattr(li, "qty", int(q))
            except Exception: pass

    def _set_label(li, text):
        for k in ("name","title","label","description","desc"):
            if isinstance(li, dict) and k in li and isinstance(li[k], str):
                li[k] = text
                return
            elif hasattr(li, k) and isinstance(getattr(li, k), str):
                try:
                    setattr(li, k, text); return
                except Exception:
                    pass
        # if we had none, inject a 'label' key for dicts
        if isinstance(li, dict):
            li["label"] = text

    def _ensure_uom(li):
        # Prefer 2-char codes; fall back if absent
        if isinstance(li, dict):
            if "uom" in li and li["uom"]:
                return
            li["uom"] = "RL"
        else:
            if not hasattr(li, "uom"):
                try: setattr(li, "uom", "RL")
                except Exception: pass

    coil_total_qty = 0.0
    coil_rows = []
    base_template = None

    for li in list(line_items):
        if _is_coil(li):
            coil_rows.append(li)
            q = max(0.0, _get_qty(li))
            coil_total_qty += q
            if base_template is None:
                base_template = li

    if coil_total_qty <= 0 or not coil_rows or base_template is None:
        return line_items  # nothing to do

    # Remove all original coil rows
    pruned = [li for li in line_items if li not in coil_rows]

    # New per-color quantity
    q_color = int(math.ceil(coil_total_qty / 4.0))
    q_color = max(1, q_color)

    # Build two new coil rows by cloning base_template
    import copy
    body_li = copy.deepcopy(base_template)
    _set_qty(body_li, q_color)
    _set_label(body_li, f"{(body_color or 'Body').strip()} Trim Coil")
    _ensure_uom(body_li)

    trim_li = copy.deepcopy(base_template)
    _set_qty(trim_li, q_color)
    _set_label(trim_li, f"{(trim_color or 'Trim').strip()} Trim Coil")
    _ensure_uom(trim_li)

    pruned.extend([body_li, trim_li])
    return pruned

    # token set we might see in labels (ensure we only replace inch-marked widths)
    width_tokens = ["5.25", "6.25", "7.25", "8.25", "9.25", "12"]
    width_re = re.compile(rf'(?<!\d)({"|".join(map(re.escape, width_tokens))})\s*"', re.I)

    def _is_lap_label(text: str) -> bool:
        t = (text or "").lower()
        return ("lap" in t or "hardieplank" in t or "plank" in t) and ("soffit" not in t)

    def _fix_text(text: str) -> str:
        if not text or not _is_lap_label(text):
            return text
        # Replace ALL width tokens followed by an inch mark with the desired nominal
        return width_re.sub(f'{_fmt_inches(lap_nominal_in)}"', text)

    for li in items:
        # dict-like
        if isinstance(li, dict):
            for key in ("name", "title", "label", "description", "desc"):
                if key in li and isinstance(li[key], str):
                    li[key] = _fix_text(li[key])
        else:
            # object-like
            for attr in ("name", "title", "label", "description", "desc"):
                if hasattr(li, attr):
                    try:
                        val = getattr(li, attr)
                        if isinstance(val, str):
                            setattr(li, attr, _fix_text(val))
                    except Exception:
                        pass
    return items



def _to_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def _mk_line_item_from_fields(name: str, qty: float, uom: str, unit_cost: float):
    # Prefer the project's LineItem, but provide a safe fallback
    try:
        from trades.registry import LineItem
    except Exception:
        class LineItem:  # minimal fallback
            def __init__(self, name, qty, uom, unit_cost, ext_cost):
                self.name = name
                self.qty = qty
                self.uom = uom
                self.unit_cost = unit_cost
                self.ext_cost = ext_cost
    q = _to_float(qty, 0.0)
    c = _to_float(unit_cost, 0.0)
    return LineItem(name=name, qty=q, uom=uom or "", unit_cost=c, ext_cost=q * c)

def _mk_line_item_from_material(m):
    name = str(getattr(m, "name", "") or "")
    qty  = _to_float(getattr(m, "qty", 0.0) or 0.0)
    uom  = str(getattr(m, "uom", "") or "")
    unit_cost = getattr(m, "unit_cost", None)
    if unit_cost is None:
        unit_cost = getattr(m, "unit_price", 0.0)
    unit_cost = _to_float(unit_cost, 0.0)
    return _mk_line_item_from_fields(name, qty, uom, unit_cost)

def _resolve_program_safe(finish: str, color_program: str | None = None) -> str:
    # Works with legacy (1-arg) and newer (2-arg) catalog functions.
    try:
        from core.catalog import resolve_program_from_finish as _rpf
        import inspect as _ins
        sig = _ins.signature(_rpf)
        if len(sig.parameters) == 1:
            return _rpf(finish)
        try:
            return _rpf(finish, color_program)
        except TypeError:
            return _rpf(finish, color_program=color_program)
    except Exception:
        f = (finish or "").strip().lower()
        return "ColorPlus" if f in ("colorplus", "woodtone") else "Primed"

def _resolve_trim_item_safe(thickness: str, width_in: float, surface: str, program: str,
                            *, region: str | None = None, allow_fallback: bool | None = None):
    # Calls core.catalog.resolve_trim_item with only the args it accepts.
    try:
        from core.catalog import resolve_trim_item as _rti
        import inspect as _ins
        sig = _ins.signature(_rti)
        kwargs = {"thickness": thickness, "width_in": width_in, "surface": surface, "program": program}
        if "region" in sig.parameters and region is not None:
            kwargs["region"] = region
        if "allow_fallback" in sig.parameters and allow_fallback is not None:
            kwargs["allow_fallback"] = allow_fallback
        return _rti(**kwargs)
    except Exception:
        try:
            return _rti(thickness, width_in, surface, program)  # type: ignore[name-defined]
        except Exception:
            return None

def _split_coils_lineitems(lines, finish: str, body_color: str, trim_color: str):
    fin = (finish or "").strip().lower()
    if fin not in ("colorplus", "woodtone") or not isinstance(lines, (list, tuple)):
        return list(lines or [])
    import math
    coil_idxs, total_qty, uom, unit_cost = [], 0.0, "RL", 0.0
    for i, li in enumerate(lines):
        nm = (getattr(li, "name", "") or getattr(li, "label", "") or "").lower()
        if "coil" in nm:
            coil_idxs.append(i)
            total_qty += _to_float(getattr(li, "qty", 0.0), 0.0)
            uom = (getattr(li, "uom", None) or uom)
            unit_cost = _to_float(getattr(li, "unit_cost", unit_cost), unit_cost)
    if not coil_idxs or total_qty <= 0:
        return list(lines)
    pruned = [li for i, li in enumerate(lines) if i not in coil_idxs]
    per_color = max(1, int(math.ceil(total_qty / 4.0)))
    body_label = f"{(body_color or 'Body').strip()} Trim Coil"
    trim_label = f"{(trim_color or 'Trim').strip()} Trim Coil"
    pruned.append(_mk_line_item_from_fields(body_label, per_color, uom, unit_cost))
    pruned.append(_mk_line_item_from_fields(trim_label, per_color, uom, unit_cost))
    return pruned

def _ensure_shake_default_label(lines, siding_type: str):
    # If Shake is selected and a shake/shingle row lacks profile, force default label.
    # Business rule: default SKU label is 'Hardie Straight Edge Shingle'.
    if "shake" not in (siding_type or "").lower():
        return lines
    for li in (lines or []):
        nm = (getattr(li, "name", "") or "").lower()
        if "shake" in nm or "shingle" in nm:
            if all(k not in nm for k in ("straight", "staggered")):
                try: setattr(li, "name", "Hardie Straight Edge Shingle")
                except Exception: pass
            break
    return lines

def _material_cost_total(lines) -> float:
    tot = 0.0
    for li in (lines or []):
        ext = getattr(li, "ext_cost", None)
        if isinstance(ext, (int, float)):
            tot += _to_float(ext, 0.0)
        else:
            tot += _to_float(getattr(li, "qty", 0.0), 0.0) * _to_float(getattr(li, "unit_cost", 0.0), 0.0)
    return round(tot, 2)


from dataclasses import dataclass

@dataclass
class JobInputs:
    customer_name: str
    address: str
    region: str
    siding_type: str
    finish: str
    body_color: str
    trim_color: str
    complexity: str
    demo_required: bool
    extra_layers: int
    substrate: str
    facades_sf: float
    trim_siding_sf: float
    eave_fascia_ft: float
    rake_fascia_ft: float
    soffit_depth_gt_24: bool
    openings_perimeter_ft: float
    outside_corners_ft: float
    inside_corners_ft: float
    fascia_width_in: int
    osb_selected: bool
    osb_area_override_sf: float | None
    lap_reveal_in: float | None = None
    soffit_enabled: bool = True

@dataclass
class JobOutputs:
    total_sf: float
    total_sq: int
    boards: int
    wrap_rolls: int
    tape_rolls: int
    nail_boxes: int
    coil_rolls: int
    window_flash_tape: int
    soffit_panels_4x10: int
    fascia_pieces_12ft: int
    trim4_pieces_12ft: int
    trim6_pieces_default: int
    trim8_pieces_default: int
    trim12_pieces_default: int
    paint_quarts: int
    labor_rate_per_sf: float
    labor_cost: float
    osb_sheets: int
    osb_framing_boxes: int
    labor_psq: float = 0.0
    lap_reveal_in_effective: float | None = None
    lap_nominal_width_in: float | None = None


# --- inline service helpers (v2) ---
def _to_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def _mk_line_item_from_fields(name: str, qty: float, uom: str, unit_cost: float):
    try:
        from trades.registry import LineItem
    except Exception:
        class LineItem:
            def __init__(self, name, qty, uom, unit_cost, ext_cost):
                self.name = name
                self.qty = qty
                self.uom = uom
                self.unit_cost = unit_cost
                self.ext_cost = ext_cost
    q = _to_float(qty, 0.0)
    c = _to_float(unit_cost, 0.0)
    return LineItem(name=name, qty=q, uom=uom or "", unit_cost=c, ext_cost=q * c)

def _mk_line_item_from_material(m):
    name = str(getattr(m, "name", "") or "")
    qty  = _to_float(getattr(m, "qty", 0.0) or 0.0)
    uom  = str(getattr(m, "uom", "") or "")
    unit_cost = getattr(m, "unit_cost", None)
    if unit_cost is None:
        unit_cost = getattr(m, "unit_price", 0.0)
    unit_cost = _to_float(unit_cost, 0.0)
    return _mk_line_item_from_fields(name, qty, uom, unit_cost)

def _resolve_program_safe(finish: str, color_program: str | None = None) -> str:
    try:
        from core.catalog import resolve_program_from_finish as _rpf
        import inspect as _ins
        sig = _ins.signature(_rpf)
        if len(sig.parameters) == 1:
            return _rpf(finish)
        try:
            return _rpf(finish, color_program)
        except TypeError:
            return _rpf(finish, color_program=color_program)
    except Exception:
        f = (finish or "").strip().lower()
        return "ColorPlus" if f in ("colorplus", "woodtone") else "Primed"

def _resolve_trim_item_safe(thickness: str, width_in: float, surface: str, program: str,
                            *, region: str | None = None, allow_fallback: bool | None = None):
    try:
        from core.catalog import resolve_trim_item as _rti
        import inspect as _ins
        sig = _ins.signature(_rti)
        kwargs = {"thickness": thickness, "width_in": width_in, "surface": surface, "program": program}
        if "region" in sig.parameters and region is not None:
            kwargs["region"] = region
        if "allow_fallback" in sig.parameters and allow_fallback is not None:
            kwargs["allow_fallback"] = allow_fallback
        return _rti(**kwargs)
    except Exception:
        try:
            return _rti(thickness, width_in, surface, program)  # type: ignore[name-defined]
        except Exception:
            return None

def _split_coils_lineitems(lines, finish: str, body_color: str, trim_color: str):
    fin = (finish or "").strip().lower()
    if fin not in ("colorplus", "woodtone") or not isinstance(lines, (list, tuple)):
        return list(lines or [])
    import math
    coil_idxs, total_qty, uom, unit_cost = [], 0.0, "RL", 0.0
    for i, li in enumerate(lines):
        nm = (getattr(li, "name", "") or getattr(li, "label", "") or "").lower()
        if "coil" in nm:
            coil_idxs.append(i)
            total_qty += _to_float(getattr(li, "qty", 0.0), 0.0)
            uom = (getattr(li, "uom", None) or uom)
            unit_cost = _to_float(getattr(li, "unit_cost", unit_cost), unit_cost)
    if not coil_idxs or total_qty <= 0:
        return list(lines)
    pruned = [li for i, li in enumerate(lines) if i not in coil_idxs]
    per_color = max(1, int(math.ceil(total_qty / 4.0)))
    body_label = f"{(body_color or 'Body').strip()} Trim Coil"
    trim_label = f"{(trim_color or 'Trim').strip()} Trim Coil"
    pruned.append(_mk_line_item_from_fields(body_label, per_color, uom, unit_cost))
    pruned.append(_mk_line_item_from_fields(trim_label, per_color, uom, unit_cost))
    return pruned

def _ensure_shake_default_label(lines, siding_type: str):
    if "shake" not in (siding_type or "").lower():
        return lines
    for li in (lines or []):
        nm = (getattr(li, "name", "") or "").lower()
        if "shake" in nm or "shingle" in nm:
            if all(k not in nm for k in ("straight", "staggered")):
                try: setattr(li, "name", "Hardie Straight Edge Shingle")
                except Exception: pass
            break
    return lines

def _material_cost_total(lines) -> float:
    tot = 0.0
    for li in (lines or []):
        ext = getattr(li, "ext_cost", None)
        if isinstance(ext, (int, float)):
            tot += _to_float(ext, 0.0)
        else:
            tot += _to_float(getattr(li, "qty", 0.0), 0.0) * _to_float(getattr(li, "unit_cost", 0.0), 0.0)
    return round(tot, 2)


def build_siding_materials_via_service(inp: "JobInputs", out: "JobOutputs"):
    try:
        from trades.siding.materials import calc_siding_materials
    except Exception as e:
        print("[MATERIALS] Import failed:", e)
        return [], 0.0

    siding_type   = getattr(inp, "siding_type", "Lap")
    finish        = getattr(inp, "finish", "Primed")
    color_program = getattr(inp, "color_program", None)
    complexity    = getattr(inp, "complexity", "Low")
    shake_profile = getattr(inp, "shake_profile", "Straight")
    surface       = getattr(inp, "bnb_surface", "Rustic")

    soffit_enabled  = bool(getattr(inp, "soffit_enabled", False))
    eave_lf         = _to_float(getattr(inp, "eave_fascia_ft", 0.0), 0.0)
    rake_lf         = _to_float(getattr(inp, "rake_fascia_ft", 0.0), 0.0)
    use_panels      = bool(getattr(inp, "soffit_depth_gt_24", False))
    soffit_depth_in = 30.0 if use_panels else 18.0

    mats = calc_siding_materials(
        siding=siding_type,
        squares=_to_float(getattr(out, "total_sq", 0.0), 0.0),
        finish=finish,
        complexity=complexity,
        shake_profile=shake_profile,
        surface=surface,
        soffit_enabled=soffit_enabled,
        eave_lf=eave_lf,
        rake_lf=rake_lf,
        soffit_use_panels_4x10=use_panels,
        soffit_depth_in=soffit_depth_in,
    )

    program        = _resolve_program_safe(finish, color_program)
    region         = getattr(inp, "region", "Metro")
    try:
        stype = str(getattr(inp, "siding_type", "") or "")
        is_bnb = ("board" in stype.lower() and "batten" in stype.lower())
    except Exception:
        is_bnb = False
    trim_thickness = getattr(inp, "trim_thickness", None) or ("4/4" if is_bnb else "5/4")

    width_from_item = {"trim4_12ft": 4, "trim6_12ft": 6, "trim8_12ft": 8, "trim12_12ft": 12}

    line_items = []
    for m in mats:
        name = str(getattr(m, "name", "") or "")
        if trim_thickness == "4/4" and is_bnb and name in width_from_item:
            width_in = width_from_item[name]
            resolved = _resolve_trim_item_safe("4/4", width_in, surface, program,
                                               region=region, allow_fallback=True)
            if resolved:
                sku = (getattr(resolved, "sku", None)
                       or getattr(resolved, "item", None)
                       or getattr(resolved, "label", None)
                       or name)
                uom = getattr(resolved, "uom", None) or getattr(m, "uom", "") or "EA"
                unit_cost = (getattr(resolved, "unit_cost", None)
                             or getattr(resolved, "unit_price", None)
                             or getattr(m, "unit_cost", None)
                             or getattr(m, "unit_price", 0.0))
                line_items.append(_mk_line_item_from_fields(str(sku),
                                                            _to_float(getattr(m, "qty", 0.0), 0.0),
                                                            str(uom),
                                                            _to_float(unit_cost, 0.0)))
                continue
        line_items.append(_mk_line_item_from_material(m))

    try:
        if str(getattr(inp, 'siding_type', 'Lap')).lower().startswith('lap'):
            line_items = _rewrite_lap_width_on_line_items(
                line_items,
                lap_nominal_in=getattr(out, 'lap_nominal_width_in',
                                       _nominal_width_for_reveal(getattr(out, 'lap_reveal_in_effective', 7.0))),
                lap_reveal_in=getattr(out, 'lap_reveal_in_effective', 7.0),
            )
    except Exception:
        pass

    line_items = _split_coils_lineitems(
        line_items,
        finish=finish,
        body_color=getattr(inp, "body_color", getattr(inp, "color_body", "")),
        trim_color=getattr(inp, "trim_color", getattr(inp, "color_trim", "")),
    )

    line_items = _ensure_shake_default_label(line_items, siding_type)

    total = _material_cost_total(line_items)
    return line_items, total


def compute_estimate(inp: JobInputs) -> JobOutputs:
    # Normalize string choices to avoid case/typo issues in lookups
    def _canon(val: str, allowed: tuple[str, ...], default: str) -> str:
        v = (val or "").strip().lower()
        for a in allowed:
            if v == a.lower():
                return a
        return default

    region = _canon(inp.region, ("Metro", "North CO", "Mountains"), "Metro")
    siding_type = _canon(inp.siding_type, ("Lap", "Board & Batten", "Shake"), "Lap")
    finish = _canon(inp.finish, ("ColorPlus", "Primed", "Woodtone"), "ColorPlus")
    complexity = _canon(inp.complexity, ("Low", "Med", "High"), "Low")

    # Siding area rule
    try:
        from core.rules import siding_area_rule
        rule = siding_area_rule()
    except Exception:
        rule = "sum"
    if rule == "sum":
        total_sf = _nz(getattr(inp, "facades_sf", 0.0)) + _nz(getattr(inp, "trim_siding_sf", 0.0))
    else:
        total_sf = max(_nz(getattr(inp, "facades_sf", 0.0)), _nz(getattr(inp, "trim_siding_sf", 0.0)))
    total_sq = int(__import__("math").ceil(total_sf / 100.0))

    # Waste
    waste_pct = float(WASTE_BASE_SIDING) + float(WASTE_COMPLEXITY.get(complexity, 0.0))

    # --- BOARD/PLANK METRICS (Lap only; variable reveal) ---
    exposure_in = _snap_reveal_to_catalog(getattr(inp, "lap_reveal_in", 7.0))
    exposure_in = max(1.0, min(12.0, exposure_in))
    lap_nominal_in = _nominal_width_for_reveal(exposure_in)

    boards = 0
    if siding_type == "Lap":
        boards_net = _planks_for_area(total_sf, exposure_in)
        boards = int(__import__("math").ceil(boards_net * (1.0 + waste_pct)))

    # Wrap & tape
    wrap_rolls = int(__import__("math").ceil(total_sf / (WRAP_ROLL_SF / (1.0 + WRAP_WASTE))))
    tape_rolls = int(wrap_rolls * TAPE_PER_WRAP_ROLL)

    # Nails — default (Lap/Shake). B&B uses catalog-driven nails.
    try:
        from core.catalog import load_catalog
        fdef = load_catalog().fastener_defaults()
        nails_per_box = int(fdef.get("nails_per_box", 7200))
        nail_waste = float(fdef.get("nail_waste_default", 0.10))
    except Exception:
        nails_per_box = NAILS_PER_BOX
        nail_waste = 0.10

    exposure_for_nails = exposure_in if siding_type == "Lap" else 7.0
    nails_generic = _nails_for_area(total_sf, exposure_for_nails)
    nail_boxes = max(1, int(__import__("math").ceil((nails_generic * (1.0 + nail_waste)) / float(nails_per_box))))
    try:
        # B&B override via catalog reference tables
        if _is_bnb(siding_type):
            nail_boxes = calc_bnb_nail_boxes_for_coverage(total_sf)
    except Exception:
        pass

    # Coil (reduced by 50% after rolls math)
    if finish.lower() == "primed":
        raw_coils = int(__import__("math").ceil(total_sq / COIL_SQ_PER_ROLL_PRIMED))
    else:
        raw_coils = int(__import__("math").ceil(total_sq / COIL_SQ_PER_ROLL_COLORPLUS)) * 2  # body + trim
    coil_rolls = max(1, int(__import__("math").ceil(raw_coils * COIL_REDUCTION)))

    # Labor (catalog-first, fallback to legacy constants)
    try:
        from core.catalog import load_catalog
        rate = float(load_catalog().labor_rate_for(siding_type, region))
    except Exception:
        rate = LABOR_RATES.get(siding_type, LABOR_RATES["Lap"]).get(region, 3.35)
    psq = 100.0 * rate

    if not getattr(inp, "demo_required", True):
        psq += NO_DEMO_CREDIT_PER_SQ
    try:
        if int(getattr(inp, "extra_layers", 0) or 0) > 0:
            psq += EXTRA_LAYER_ADD_PER_SQ * int(getattr(inp, "extra_layers", 0) or 0)
    except Exception:
        pass
    try:
        if (getattr(inp, "substrate", "") or "").lower() in ("brick", "stucco"):
            psq += BRICK_STUCCO_ADD_PER_SQ
    except Exception:
        pass

    labor_psq = round(psq, 2)
    labor_cost = round(total_sq * labor_psq, 2)

    # Soffit & fascia — area-based panels with toggle guard
    total_fascia_lf = _nz(getattr(inp, "eave_fascia_ft", 0.0)) + _nz(getattr(inp, "rake_fascia_ft", 0.0))
    soffit_depth_in = 30.0 if getattr(inp, "soffit_depth_gt_24", False) else 18.0
    soffit_area_sf = max(0.0, total_fascia_lf) * (soffit_depth_in / 12.0)
    use_panels = bool(getattr(inp, "soffit_depth_gt_24", False))
    soffit_panels = int(__import__("math").ceil((soffit_area_sf * (1.0 + SOFFIT_WASTE)) / SOFFIT_PANEL_AREA_SF)) if use_panels else 0
    # explicit UI toggle
    try:
        if hasattr(inp, "soffit_enabled") and not bool(getattr(inp, "soffit_enabled")):
            soffit_panels = 0
    except Exception:
        pass

    # Fascia 12' pieces
    try:
        piece_len = fascia_piece_length_lf()  # provided elsewhere; fallback below
    except Exception:
        piece_len = 12.0
    fascia_pieces = ceil_pieces(total_fascia_lf, piece_len)

    # 4" trim (corners + openings)
    trim4_lf = (2.0 * _nz(getattr(inp, "outside_corners_ft", 0.0))) + _nz(getattr(inp, "inside_corners_ft", 0.0)) + _nz(getattr(inp, "openings_perimeter_ft", 0.0))
    trim4_pieces = int(__import__("math").ceil(trim4_lf / 12.0))

    # Defaults
    paint_quarts = 0 if finish.lower() in ("colorplus","woodtone") else 2
    window_flash_tape = int(__import__("math").ceil(total_sq / 5.0))
    trim6_def = trim8_def = trim12_def = 2

    # OSB option
    osb_sheets = 0
    osb_framing_boxes = 0
    if getattr(inp, "osb_selected", False):
        osb_area = _nz(getattr(inp, "osb_area_override_sf", None)) if getattr(inp, "osb_area_override_sf", None) else total_sf
        osb_sheets = int(__import__("math").ceil(osb_area / 32.0))
        osb_framing_boxes = max(1, int(__import__("math").ceil(osb_area / 1000.0)))

    return JobOutputs(
        total_sf=round(total_sf, 2),
        total_sq=total_sq,
        boards=int(boards),
        wrap_rolls=int(wrap_rolls),
        tape_rolls=int(tape_rolls),
        nail_boxes=int(nail_boxes),
        coil_rolls=int(coil_rolls),
        window_flash_tape=int(window_flash_tape),
        soffit_panels_4x10=int(soffit_panels),
        fascia_pieces_12ft=int(fascia_pieces),
        trim4_pieces_12ft=int(trim4_pieces),
        trim6_pieces_default=int(trim6_def),
        trim8_pieces_default=int(trim8_def),
        trim12_pieces_default=int(trim12_def),
        paint_quarts=int(paint_quarts),
        labor_rate_per_sf=float(rate),
        labor_cost=round(float(labor_cost), 2),
        osb_sheets=int(osb_sheets),
        osb_framing_boxes=int(osb_framing_boxes),
        labor_psq=float(labor_psq),
        lap_reveal_in_effective=float(exposure_in),
        lap_nominal_width_in=float(lap_nominal_in),
    )


def extract_name_and_address(pdf_text: str) -> tuple[str, str, str, str]:
    try:
        txt = str(pdf_text or "")
    except Exception:
        txt = ""
    import re
    lines = []
    for ln in txt.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        ln = re.sub(r"[ \t]+", " ", ln)
        lines.append(ln)

    ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
    CITY_ST_ZIP_RE = re.compile(r"^\s*([A-Za-z][A-Za-z .'-]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\s*$")
    SUFFIX = ("ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|CT|COURT|CIR|CIRCLE|WAY|PKWY|PARKWAY|"
              "BLVD|HIGHWAY|HWY|TRL|TRAIL|TER|TERRACE|PL|PLACE|LOOP")
    STREET_RE = re.compile(
        r"^\s*\d{1,6}\s+[A-Za-z0-9 .#'-]+(?:\b(" + SUFFIX + r")\.?)\s*(?:#\s*\w+|\bUNIT\b\s*\w+|\bAPT\b\s*\w+)?\s*$",
        re.IGNORECASE,
    )
    MEAS_HDR = re.compile(r"(?i)\b(complete|pro(?:\s+premium)?)\s+measurements\b")
    MODEL_ID = re.compile(r"(?i)\bMODEL\s*ID\s*:\s*\d+")
    PROP_ID  = re.compile(r"(?i)\bPROPERTY\s*ID\s*:\s*\d+")
    DATE_RE  = re.compile(r"\b\d{1,2}\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)\s+\d{4}\b", re.I)

    name = ""
    street = ""
    citystzip = ""
    zip_hint = ""

    for i in range(min(40, max(0, len(lines) - 2))):
        if MEAS_HDR.search(lines[i]):
            if i + 2 < len(lines) and STREET_RE.match(lines[i+1]) and CITY_ST_ZIP_RE.match(lines[i+2]):
                street = lines[i+1]
                citystzip = lines[i+2]
                m = ZIP_RE.search(citystzip)
                zip_hint = m.group(1) if m else ""
            break

    if not citystzip:
        city_idx = None
        for i, ln in enumerate(lines[:120]):
            m = CITY_ST_ZIP_RE.match(ln)
            if m:
                citystzip = f"{m.group(1)}, {m.group(2)} {m.group(3)[:5]}"
                mz = ZIP_RE.search(ln)
                zip_hint = mz.group(1) if mz else ""
                city_idx = i
                break
        if city_idx is not None and city_idx > 0:
            for j in range(city_idx - 1, max(-1, city_idx - 6), -1):
                ln = lines[j]
                if STREET_RE.match(ln):
                    street = ln
                    break

    if not name:
        for i, ln in enumerate(lines):
            if MODEL_ID.search(ln) or PROP_ID.search(ln):
                for k in range(i + 1, min(i + 6, len(lines))):
                    cand = lines[k].strip()
                    if not cand:
                        continue
                    if MODEL_ID.search(cand) or PROP_ID.search(cand):
                        continue
                    if DATE_RE.search(cand):
                        continue
                    if CITY_ST_ZIP_RE.match(cand) or STREET_RE.match(cand):
                        continue
                    name = cand
                    break
                if name:
                    break

    if not name and street:
        try:
            sidx = lines.index(street)
            if sidx > 0:
                cand = lines[sidx - 1].strip()
                if cand and not MEAS_HDR.search(cand) and not CITY_ST_ZIP_RE.match(cand):
                    name = cand
        except Exception:
            pass

    if not street:
        for ln in lines[:160]:
            if STREET_RE.match(ln):
                street = ln
                break

    if not zip_hint:
        for ln in lines[:120]:
            mz = ZIP_RE.search(ln)
            if mz:
                zip_hint = mz.group(1); break

    def _smart_title(s: str) -> str:
        if not s:
            return s
        ss = s.strip()
        if ss.isupper() and len(ss) <= 80:
            try:
                return ss.title()
            except Exception:
                return ss
        return ss

    return (_smart_title(name or ""), street or "", citystzip or "", zip_hint or "")


def extract_hover_totals(pdf_text: str) -> dict:
    import re, math
    def _num_to_float(s: str) -> float:
        try:
            return float(s.replace(",", ""))
        except Exception:
            return 0.0

    NUM = r"([\d,]+(?:\.\d+)?)"
    _len_ftin       = re.compile(r"(\d+'\s*\d{1,2}\")")
    _len_with_unit  = re.compile(rf"{NUM}\s*(?:lf|linear\s*feet|ft|feet)\b", re.I)
    _area_with_unit = re.compile(rf"{NUM}\s*(?:sf|sq\s*feet|square\s*feet|ft²|ft2)\b", re.I)
    _bare_number    = re.compile(rf"^\s*{NUM}\s*$")

    def _scan_area(lines, idx, lookahead=8) -> float:
        if idx is None or idx < 0:
            return 0.0
        end = min(idx + 1 + lookahead, len(lines))
        m0 = _area_with_unit.search(lines[idx])
        if m0:
            return _num_to_float(m0.group(1))
        for j in range(idx + 1, end):
            m = _area_with_unit.search(lines[j])
            if m:
                return _num_to_float(m.group(1))
        return 0.0

    def _scan_len_strict(lines, idx, lookahead=8) -> float:
        if idx is None or idx < 0:
            return 0.0
        end = min(idx + 1 + lookahead, len(lines))
        line0 = lines[idx]
        m = _len_ftin.search(line0)
        if m:
            s = m.group(1)
            mm = re.match(r"^(\d+)'\s*(\d{1,2})\"", s)
            if mm:
                return float(mm.group(1)) + float(mm.group(2))/12.0
        m = _len_with_unit.search(line0)
        if m:
            return _num_to_float(m.group(1))
        for j in range(idx + 1, end):
            line = lines[j]
            m = _len_ftin.search(line)
            if m:
                s = m.group(1)
                mm = re.match(r"^(\d+)'\s*(\d{1,2})\"", s)
                if mm:
                    return float(mm.group(1)) + float(mm.group(2))/12.0
            m = _len_with_unit.search(line)
            if m:
                return _num_to_float(m.group(1))
        return 0.0

    def _scan_len_within_block(lines, start, end, prefer_line_idx=None, allow_bare=True, bare_min=1, bare_max=10000) -> float:
        if prefer_line_idx is not None and start <= prefer_line_idx < end:
            v = _scan_len_strict(lines, prefer_line_idx, lookahead=1)
            if v:
                return v
        for j in range(start, end):
            v = _scan_len_strict(lines, j, lookahead=1)
            if v:
                return v
        if allow_bare:
            for j in range(start, end):
                m = _bare_number.match(lines[j])
                if m:
                    n = _num_to_float(m.group(1))
                    if bare_min <= n <= bare_max:
                        return n
        return 0.0

    def _find_first(low_lines, variants):
        for i, l in enumerate(low_lines):
            if any(v in l for v in variants):
                return i
        return None

    def _find_under_block(low_lines, start_idx, end_labels, lookahead=30):
        if start_idx is None or start_idx < 0:
            return (-1, -1)
        end = min(len(low_lines), start_idx + 1 + lookahead)
        for j in range(start_idx + 1, end):
            if any(lbl in low_lines[j] for lbl in end_labels):
                end = j
                break
        return (start_idx, end)

    raw_lines = [l for l in (pdf_text.splitlines() if isinstance(pdf_text, str) else []) if l.strip()]
    lines = [re.sub(r"[ \t]+", " ", l) for l in raw_lines]
    low = [l.lower() for l in lines]

    facades_idx = _find_first(low, ["facades", "total siding", "wall area", "siding area"])
    trim_idx    = _find_first(low, ["trim / siding", "trim touching siding", "trim area", "siding & trim only"])
    facades_sf = _scan_area(lines, facades_idx, lookahead=10)
    trim_siding_sf = _scan_area(lines, trim_idx, lookahead=10)

    eave_fascia = 0.0
    rake_fascia = 0.0

    eaves_idx = _find_first(low, ["eaves fascia", "eave fascia", "eaves", "total eaves", "eave length"])
    if eaves_idx is not None:
        s, e = _find_under_block(low, eaves_idx,
                                 end_labels=["rakes", "corners", "siding waste", "soffit", "roof", "drip edge", "area", "openings"],
                                 lookahead=40)
        if s != -1:
            eave_fascia = _scan_len_within_block(lines, s, e, allow_bare=True, bare_max=5000)

    rakes_idx = _find_first(low, ["rakes fascia", "rake fascia", "rakes", "gable length", "rake length", "gables"])
    if rakes_idx is not None:
        s, e = _find_under_block(low, rakes_idx,
                                 end_labels=["eaves", "corners", "siding waste", "soffit", "roof", "drip edge", "area", "openings"],
                                 lookahead=40)
        if s != -1:
            rake_fascia = _scan_len_within_block(lines, s, e, allow_bare=True, bare_max=5000)

    openings_perim = 0.0
    totper_idx = _find_first(low, ["total perimeter"])
    if totper_idx is not None:
        v_same = _scan_len_strict(lines, totper_idx, lookahead=3)
        if not v_same:
            v_same = _scan_len_within_block(lines, totper_idx, min(totper_idx + 6, len(lines)),
                                            allow_bare=True, bare_max=5000)
        openings_perim = v_same

    if openings_perim == 0.0:
        openings_hdr = _find_first(low, ["openings"])
        if openings_hdr is not None:
            s, e = _find_under_block(low, openings_hdr,
                                     end_labels=["corners", "siding waste", "soffit", "eaves", "rakes", "roof", "drip edge", "area"],
                                     lookahead=40)
            if s != -1:
                perim_row = None
                for j in range(s, e):
                    if ("perim" in low[j]) or ("perimeter" in low[j]):
                        perim_row = j
                        break
                if perim_row is not None:
                    openings_perim = _scan_len_within_block(lines, s, e, prefer_line_idx=perim_row, allow_bare=True, bare_max=5000)

    outside = 0.0
    inside  = 0.0
    corners_hdr = _find_first(low, ["corners", "corner lengths", "corner length"])
    if corners_hdr is not None:
        s, e = _find_under_block(low, corners_hdr,
                                 end_labels=["siding waste", "soffit", "eaves", "rakes", "roof", "drip edge", "area", "openings"],
                                 lookahead=40)
        if s != -1:
            out_idx = _find_first(low[s:e], ["outside"])
            in_idx  = _find_first(low[s:e], ["inside"])
            if out_idx is not None:
                outside = _scan_len_within_block(lines, s + out_idx, min(e, s + out_idx + 6), allow_bare=True, bare_max=5000)
            if in_idx is not None:
                inside = _scan_len_within_block(lines, s + in_idx, min(e, s + in_idx + 6), allow_bare=True, bare_max=5000)
            if outside == 0.0:
                for j in range(s, e):
                    if "outside" in low[j]:
                        v = _scan_len_strict(lines, j, lookahead=1)
                        if not v:
                            m = _bare_number.search(lines[j])
                            if m:
                                v = _num_to_float(m.group(1))
                        if 0 < v <= 5000:
                            outside = v; break
            if inside == 0.0:
                for j in range(s, e):
                    if "inside" in low[j]:
                        v = _scan_len_strict(lines, j, lookahead=1)
                        if not v:
                            m = _bare_number.search(lines[j])
                            if m:
                                v = _num_to_float(m.group(1))
                        if 0 < v <= 5000:
                            inside = v; break

    return dict(
        facades_sf=round(facades_sf, 2),
        trim_siding_sf=round(trim_siding_sf, 2),
        eave_fascia=round(eave_fascia, 2),
        rake_fascia=round(rake_fascia, 2),
        openings_perim=round(openings_perim, 2),
        outside=round(outside, 2),
        inside=round(inside, 2),
        corners_seen=(corners_hdr is not None),
    )


def auto_region_from_address(street_line: str, city_state_zip: str, zip_code: str) -> str:
    """
    Region inference with catalog/region helper fallback.
    804xx/816xx -> Mountains
    805xx/806xx -> North CO
    else        -> Metro
    """
    try:
        from core.region import auto_region_from_address as _canon_region
        return _canon_region(street_line, city_state_zip, zip_code)
    except Exception:
        pass
    z = "".join(ch for ch in str(zip_code or "") if ch.isdigit())
    if len(z) < 3:
        return "Metro"
    try:
        p3 = int(z[:3])
    except Exception:
        return "Metro"
    if p3 in (804, 816):
        return "Mountains"
    if p3 in (805, 806):
        return "North CO"
    return "Metro"


def ft_in_to_ft(txt: str) -> float:
    """
    Convert strings like 261'11" or 159' 8" to decimal feet.
    Accepts plain numbers as feet. Returns 0.0 if not parseable.
    """
    import re as _re
    s = str(txt) if txt is not None else ""
    m = _re.match(r"^\s*(\d+)\s*'\s*(\d{1,2})\s*(?:\"|in)?\s*$", s, _re.I)
    if m:
        try:
            return float(m.group(1)) + float(m.group(2)) / 12.0
        except Exception:
            return 0.0
    try:
        return float(s.replace(',', ''))
    except Exception:
        return 0.0


def _nz(x) -> float:
    """Clamp None/NaN/negatives to 0.0 for safety; return float."""
    try:
        v = float(x)
        if v != v or v < 0:  # NaN check and negatives
            return 0.0
        return v
    except Exception:
        return 0.0



def _nominal_width_for_reveal(reveal_in):
    r = _snap_reveal_to_catalog(reveal_in)
    try:
        return _LAP_REVEAL_TO_NOMINAL[r]
    except Exception:
        try:
            rr = float(r)
        except Exception:
            rr = 7.0
        return 12.0 if rr >= 9.5 else round(rr + 1.25, 2)


def _fmt_inches(x):
    try:
        s = f"{float(x):.2f}".rstrip("0").rstrip(".")
        return s
    except Exception:
        return str(x)


# --- restored minimal helpers (safe append) ---
def _planks_for_area(area_sf: float, exposure_in: float) -> int:
    try:
        if float(exposure_in) <= 0: return 0
        cov = float(exposure_in)
        return max(0, int(round(float(area_sf or 0.0) / cov)))
    except Exception:
        return 0

def _nails_for_area(area_sf: float, exposure_in: float) -> int:
    try:
        if float(exposure_in) <= 0: return 0
        return max(0, int(round(float(area_sf or 0.0) * (10.0 / float(exposure_in)))))
    except Exception:
        return 0

def _is_bnb(s: str) -> bool:
    s = (s or '').lower()
    return ('board' in s) and ('batten' in s)

def _load_catalog_safe():
    try:
        from core.catalog import load_catalog
        return load_catalog()
    except Exception:
        return None


