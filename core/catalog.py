# core/catalog.py — catalog loader + helpers

# core/catalog.py — catalog loader + helpers

import json, os
from dataclasses import dataclass
from typing import Any, Dict

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(APP_DIR, "config", "catalog.json")

# ---------- simple in-process cache ----------
_CATALOG_CACHE = None
_CATALOG_MTIME = None

@dataclass
class Catalog:
    raw: Dict[str, Any]

    @property
    def version(self) -> str:
        return self.raw.get("version", "0.0.0")

    def overhead_rate_default(self) -> float:
        return float(self.raw.get("overhead_rate_default", 0.20))

    def gm_target_for(self, trade: str) -> float:
        return float(self.raw.get("gm_targets", {}).get(trade, 0.35))

    def commission_cfg(self) -> Dict[str, float]:
        return self.raw.get("commission", {})

    def item_cost(self, item: str, region: str,
                  *, finish: str | None = None,
                  fascia_width_in: int | None = None) -> float:
        """
        Resolve three variant modes safely:
          1) finish-keyed: items[item].cost[finish][region]
          2) width-keyed fascia: items['fascia_12ft'].cost['w{width}'][region]
          3) simple tiered: items[item].cost[region]
        Raise a descriptive KeyError if path missing — never return silent zeros.
        """
        items = self.raw.get("items", {})
        if item not in items:
            raise KeyError(f"Unknown item '{item}' in catalog")
        rec = items[item]
        cost = rec.get("cost")
        if not isinstance(cost, dict):
            raise KeyError(f"Item '{item}' has no 'cost' dict in catalog")

        # fascia width keyed
        if item == "fascia_12ft" and fascia_width_in:
            key = f"w{min(12, max(4, int(fascia_width_in)))}"
            tier = cost.get(key)
            if not isinstance(tier, dict) or region not in tier:
                raise KeyError(f"Missing fascia price for {key}/{region}")
            return float(tier[region])

        # finish keyed
        if finish and finish in cost:
            tier = cost.get(finish)
            if not isinstance(tier, dict) or region not in tier:
                raise KeyError(f"Missing {item} price for finish={finish} region={region}")
            return float(tier[region])

        # simple tiered
        if region in cost:
            return float(cost[region])

        raise KeyError(f"Missing {item} price for region={region}")

    def assembly(self, name: str) -> dict:
        return self.raw.get("assemblies", {}).get(name, {})

def _read_catalog_from_disk() -> Catalog:
    if not os.path.exists(CATALOG_PATH):
        raise FileNotFoundError(f"Missing catalog at {CATALOG_PATH}")
    with open(CATALOG_PATH, "r") as f:
        data = json.load(f)
    return Catalog(data)

def load_catalog() -> Catalog:
    global _CATALOG_CACHE, _CATALOG_MTIME
    try:
        mtime = os.path.getmtime(CATALOG_PATH)
    except OSError:
        mtime = None

    if _CATALOG_CACHE is None or _CATALOG_MTIME != mtime:
        _CATALOG_CACHE = _read_catalog_from_disk()
        _CATALOG_MTIME = mtime
    return _CATALOG_CACHE

def reload_catalog() -> Catalog:
    """
    Force cache invalidation + re-read from disk.
    """
    global _CATALOG_CACHE, _CATALOG_MTIME
    _CATALOG_CACHE = None
    _CATALOG_MTIME = None
    return load_catalog()
