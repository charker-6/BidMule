# core/pricing.py — job rollup + guardrails + commission

from dataclasses import dataclass
from typing import List, Literal
from core.catalog import load_catalog
from trades.registry import TradeCost, LineItem

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
