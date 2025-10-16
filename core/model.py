# core/model.py
from dataclasses import dataclass, field
from typing import List

@dataclass
class LineItem:
    sku: str
    description: str
    quantity: float
    unit: str
    unit_cost: float
    ext_cost: float
    trade: str
    notes: str = ""

@dataclass
class TradeCost:
    material_cost: float
    labor_cost: float
    line_items: List[LineItem] = field(default_factory=list)

@dataclass
class JobCost:
    trade: str
    material_cost: float
    labor_cost: float
    cogs: float
    overhead_rate: float
    target_gm: float
    revenue_target: float
    overhead_dollars: float
    projected_profit: float
