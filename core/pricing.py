# core/pricing.py — job rollup + guardrails + commission + (NEW) material catalogs/constants

from dataclasses import dataclass
from typing import List, Literal, Dict, Tuple
from core.catalog import load_catalog
from trades.registry import TradeCost, LineItem

# ---------------------------------------------------------------------
# Existing types for commission/rollup
# ---------------------------------------------------------------------

Band = Literal["LOW", "TARGET", "HIGH"]

@dataclass
class JobCost:
    trade: str
    cogs: float
    overhead_rate: float
    target_gm: float
    revenue_target: float
    projected_profit: float

@dataclass
class CommissionResult:
    band: Band
    gm_actual: float
    commission_base: float
    commission_adjustment: float
    commission_total: float

def summarize_job_costs(trade_cost: TradeCost, trade_name: str,
                        overhead_rate: float | None = None,
                        target_gm: float | None = None):
    """
    Computes revenue target at given target_gm and overhead_rate, and returns
    commission calculated at that same revenue target (guardrail preview).
    """
    cat = load_catalog()
    ovr = overhead_rate if overhead_rate is not None else cat.overhead_rate_default()
    tgt = target_gm if target_gm is not None else cat.gm_target_for(trade_name)

    cogs = float(trade_cost.material_cost + trade_cost.labor_cost)

    # Revenue needed to hit target GM while paying overhead on revenue:
    # revenue = COGS / (1 - overhead - target_gm)
    denom = (1.0 - ovr - tgt)
    revenue = cogs / denom if denom > 0 else cogs

    profit = revenue - cogs - (ovr * revenue)

    job = JobCost(
        trade=trade_name, cogs=round(cogs, 2),
        overhead_rate=ovr, target_gm=tgt,
        revenue_target=round(revenue, 2),
        projected_profit=round(profit, 2)
    )

    # --- Commission preview at the revenue_target price (NEW RULE) ---
    # GM fraction at this price:
    gm_dollars = revenue - (cogs + ovr * revenue)
    gm_actual = gm_dollars / revenue if revenue > 0 else 0.0

    # Band per your spec: <30% = LOW, ~=30% = TARGET, >30% = HIGH
    eps = 1e-6
    if gm_actual + eps < 0.30:
        band: Band = "LOW"
    elif gm_actual - eps > 0.30:
        band = "HIGH"
    else:
        band = "TARGET"

    # Commission Rule:
    # - 0% of revenue for GM <= 20%
    # - Linear ramp from 20%→30%: commission_base_rate = (GM - 0.20), capped at 0.10
    # - For GM >= 30%: 10% of revenue + 1/3 of profit above 30% GM
    if gm_actual <= 0.20 + eps:
        commission_base_rate = 0.0
        commission_bonus_rate = 0.0
    elif gm_actual < 0.30 - eps:
        # Linear ramp: 0.00 at 20% → 0.10 at 30%
        commission_base_rate = min(max(gm_actual - 0.20, 0.0), 0.10)
        commission_bonus_rate = 0.0
    else:
        # Base 10% at/above 30% GM
        commission_base_rate = 0.10
        # Profit above the 30% threshold (fraction):
        # profit_above_30 = (gm_actual - 0.30) * revenue
        # Rep receives 1/3 of that as a fraction of revenue:
        commission_bonus_rate = max(gm_actual - 0.30, 0.0) / 3.0

    commission_base = commission_base_rate * revenue
    commission_adjustment = commission_bonus_rate * revenue
    commission_total = max(0.0, commission_base + commission_adjustment)

    comm = CommissionResult(
        band=band,
        gm_actual=gm_actual,
        commission_base=commission_base,
        commission_adjustment=commission_adjustment,
        commission_total=commission_total
    )

    return job, comm


# =====================================================================
# NEW: Material catalogs & shared constants used by Siding calculations
# =====================================================================

# Units
UOM_EA = "EA"

# Finishes and profile enumerations
Finish = Literal["ColorPlus", "Primed", "Dream"]
ShakeProfile = Literal["Straight", "Staggered"]

@dataclass(frozen=True)
class CatalogItem:
    name: str
    price: float
    uom: str = UOM_EA

# ------------------------- SHINGLE / SHAKE ----------------------------
# Names and prices exactly as provided (SKUs intentionally omitted).
SHAKE_ITEMS: Dict[Tuple[ShakeProfile, Finish], CatalogItem] = {
    ("Straight",  "ColorPlus"): CatalogItem('15.25"x4\' Straight Color Plus', 21.59),
    ("Staggered", "ColorPlus"): CatalogItem('15.25"x4\' Staggered Color Plus', 18.49),
    ("Straight",  "Primed"):    CatalogItem('15.25"x4\' Straight Primed',      19.69),
    ("Staggered", "Primed"):    CatalogItem('15.25"x4\' Staggered Primed',     17.09),
    ("Straight",  "Dream"):     CatalogItem('15.25"X4\' Straight Dream',       32.89),
    ("Staggered", "Dream"):     CatalogItem('15.25"X4\' Staggered Dream',      28.29),
}

# Shake coverage rules (pre-waste; pieces per square)
SHAKE_PIECES_PER_SQ: Dict[ShakeProfile, int] = {
    "Straight": 43,   # 7" exposure
    "Staggered": 50,  # 6" exposure
}

# ---------------------- BOARD & BATTEN (PANELS) ----------------------
# Default to 4x10 CM; other sizes staged below but not yet shown in UI.
BNB_PANELS_4X10: Dict[Finish, CatalogItem] = {
    "ColorPlus": CatalogItem("4x10 CM Color Plus", 85.77),
    "Primed":    CatalogItem("4x10 CM Primed",     66.99),
    "Dream":     CatalogItem("4x10 CM Dream",     150.79),
}

# Staged alternates (not yet exposed in UI; handy for future selection)
BNB_PANELS_STAGED: Dict[str, float] = {
    "4x10 SM Primed":  78.59,
    "4x10 SM Dream":  154.19,
    "4x10 Sierra 8 Primed": 70.19,
    "4x9 CM Primed":  63.19,
    "4x8 CM Primed":  56.09,
    "4x8 SM Primed":  62.79,
    "4x9 SM Primed":  70.49,
    "4x8 Sierra 8 Primed": 56.19,
    "4x9 Sierra 8 Primed": 63.19,
    "4x8 CM Dream": 120.69,
    "4x8 SM Dream": 123.34,
    "4x10 CM Dream": 150.79,
    "4x10 SM Dream": 154.19,
}

# ---------------------- BOARD & BATTEN (BATTENS) ---------------------
# 12' battens; names exactly as specified. Dream price not provided—if
# requested downstream, fall back to ColorPlus price unless overridden.
BNB_BATTENS: Dict[Tuple[str, Finish], CatalogItem] = {
 ("Rustic", "ColorPlus"): CatalogItem("4/4 2.5 Rustic Color Plus", 12.18),
    ("Smooth", "ColorPlus"): CatalogItem("4/4 2.5 Smooth Color Plus", 12.18),
    ("Rustic", "Primed"):    CatalogItem("4/4 2.5 Rustic Primed",     13.19),
    ("Smooth", "Primed"):    CatalogItem("4/4 2.5 Smooth Primed",     13.19),  # ← add this
    # Dream fallbacks until explicit pricing provided:
    ("Rustic", "Dream"):     CatalogItem("4/4 2.5 Rustic Color Plus", 12.18),
    ("Smooth", "Dream"):     CatalogItem("4/4 2.5 Smooth Color Plus", 12.18),

}

# ---------------------------- CONSTANTS ------------------------------
# Waste factors (match pre-existing Low/Med/High = 20/23/27%)
WASTE_BY_COMPLEXITY: Dict[str, float] = {
    "Low": 0.20,
    "Med": 0.23,
    "High": 0.27,
}

# Board & Batten panel area (4x10) and batten density
BNB_PANEL_SF: float = 40.0
BATTENS_PER_PANEL: float = 3.5  # 12' battens per 4x10 panel (qty basis)

# Soffit logic: 8' boards unless using 4x10 panels for >24" depth
SOFFIT_BOARD_LENGTH_FT: float = 8.0

# ----------------------------- LABOR --------------------------------
# Pulled from your rate sheet items used so far. Expand as needed.
LABOR: Dict[str, float] = {
    "shake_install_per_sf": 4.30,     # applies to both Straight & Staggered
    "demo_extra_layer_per_sf": 0.50,  # removal per SF per extra layer
}

__all__ = [
    # existing exports are implicit; new exports listed for clarity
    "CatalogItem",
    "Finish",
    "ShakeProfile",
    "SHAKE_ITEMS",
    "SHAKE_PIECES_PER_SQ",
    "BNB_PANELS_4X10",
    "BNB_PANELS_STAGED",
    "BNB_BATTENS",
    "WASTE_BY_COMPLEXITY",
    "BNB_PANEL_SF",
    "BATTENS_PER_PANEL",
    "SOFFIT_BOARD_LENGTH_FT",
    "LABOR",
    # existing types
    "JobCost",
    "CommissionResult",
    "summarize_job_costs",
]

def commission_rate_from_gross_gm(gross_gm: float) -> float:
    g = float(gross_gm)
    if g <= 0.20:
        return 0.0
    if g < 0.30:
        return min(max(g - 0.20, 0.0), 0.10)
    return 0.10 + max(g - 0.30, 0.0) / 3.0
def solve_revenue_from_commission(comm_dollars: float, cogs: float) -> float:
    C = float(cogs)
    K = float(comm_dollars)
    if K <= 0.0:
        return max(C / 0.80, C)
    threshold = C / 7.0
    if K < threshold:
        return (K + C) / 0.80
    return 3.0 * K + C
def solve_revenue_from_profit(profit_dollars: float, cogs: float, overhead_rate: float) -> float:
    P = float(profit_dollars)
    C = float(cogs)
    r = float(overhead_rate)
    R0 = C / 0.70
    P30 = (0.90 - r) * R0 - C
    if P <= P30:
        denom = 0.20 - r
        if abs(denom) < 1e-9:
            return R0
        R = P / denom
        Rmin = C / 0.80
        Rmax = R0
        if R < Rmin:
            R = Rmin
        if R > Rmax:
            R = Rmax
        return R
    denom = (2.0/3.0) - r
    if abs(denom) < 1e-9:
        return 3.0 * P + (2.0/3.0) * C
    return (P + (2.0/3.0) * C) / denom


from core.catalog import load_catalog

def compute_rollup_for_ui(cogs=None, cogs_total=None, target_gm=None, overhead_rate=None, trade_name="Siding"):
    from .catalog import load_catalog
    cat = load_catalog()
    C = float(cogs_total if cogs_total is not None else cogs if cogs is not None else 0.0)
    ovr = float(overhead_rate if overhead_rate is not None else cat.overhead_rate_default())
    tgt = float(target_gm if target_gm is not None else cat.gm_target_for(trade_name))
    denom = max(1e-9, 1.0 - (ovr + tgt))
    revenue = round(C / denom, 2)
    gm_actual = tgt
    if gm_actual < 0.30:
        base_rate = min(max(gm_actual - 0.20, 0.0), 0.10)
        bonus_rate = 0.0
    else:
        base_rate = 0.10
        bonus_rate = max(gm_actual - 0.30, 0.0) / 3.0
    commission_total = round((base_rate + bonus_rate) * revenue, 2)
    overhead_dollars = round(ovr * revenue, 2)
    profit = round(revenue - C - overhead_dollars - commission_total, 2)
    return {
        "cogs": round(C, 2),
        "overhead_rate": ovr,
        "target_gm": tgt,
        "revenue_target": revenue,
        "overhead_dollars": overhead_dollars,
        "projected_profit": profit,
        "commission_total": commission_total,
    }



def compute_totals(material_cost: float,
                   labor_cost: float,
                   target_gm: float | None = None,
                   overhead_rate: float | None = None,
                   trade_name: str = "Siding") -> dict:
    C = float(material_cost or 0.0) + float(labor_cost or 0.0)
    roll = compute_rollup_for_ui(cogs_total=C,
                                 target_gm=target_gm,
                                 overhead_rate=overhead_rate,
                                 trade_name=trade_name)
    return {
        "material_cost": round(float(material_cost or 0.0), 2),
        "labor_cost": round(float(labor_cost or 0.0), 2),
        "cogs": roll["cogs"],
        "overhead_rate": roll["overhead_rate"],
        "target_gm": roll["target_gm"],
        "overhead_dollars": roll["overhead_dollars"],
        "revenue_target": roll["revenue_target"],
        "projected_profit": roll["projected_profit"],
        "commission_total": roll["commission_total"],
    }
def compute_totals(*args, **kwargs):
    cogs_total = None
    if 'cogs_total' in kwargs:
        cogs_total = kwargs['cogs_total']
    elif 'cogs' in kwargs:
        kwargs['cogs_total'] = kwargs.pop('cogs')
    elif 'material_cost' in kwargs or 'labor_cost' in kwargs:
        mc = float(kwargs.get('material_cost', 0.0) or 0.0)
        lc = float(kwargs.get('labor_cost', 0.0) or 0.0)
        kwargs['cogs_total'] = mc + lc
        kwargs.pop('material_cost', None)
        kwargs.pop('labor_cost', None)
    else:
        if len(args) == 3:
            return compute_rollup_for_ui(cogs_total=args[0], target_gm=args[1], overhead_rate=args[2])
        if len(args) == 4:
            return compute_rollup_for_ui(cogs_total=(args[0] + args[1]), target_gm=args[2], overhead_rate=args[3])
    return compute_rollup_for_ui(**kwargs)
