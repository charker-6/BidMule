# core/rules.py
from __future__ import annotations
import os, json, math

# Resolve config/app.json relative to project root
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(_THIS_DIR)  # .../ProjectFolder
_APP_JSON = os.path.join(APP_DIR, "config", "app.json")

_CACHE: dict = {}

def _safe_defaults() -> dict:
    return {
        "version": "1.0.0",
        "siding_area_rule": "max",
        "fascia_piece_length_lf": 12.0,
        "rounding": {
            "wrap_rolls": "ceil",
            "tape_rolls": "ceil",
            "nail_boxes": "ceil",
            "coil_rolls": "ceil",
            "trim_pieces": "ceil",
            "labor_cost": "money"
        }
    }

def _load_app_cfg() -> dict:
    """Load and cache config/app.json; fall back to safe defaults if missing or malformed."""
    global _CACHE
    if not os.path.exists(_APP_JSON):
        _CACHE = _safe_defaults()
        _CACHE["_mtime"] = 0.0
        return _CACHE

    mtime = os.path.getmtime(_APP_JSON)
    if _CACHE.get("_mtime") != mtime:
        try:
            with open(_APP_JSON, "r") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("app.json must be an object")
                _CACHE = data
        except Exception:
            _CACHE = _safe_defaults()
        _CACHE["_mtime"] = mtime
    return _CACHE

def siding_area_rule() -> str:
    cfg = _load_app_cfg()
    val = (cfg.get("siding_area_rule") or "max").lower()
    return "sum" if val == "sum" else "max"

def fascia_piece_length_lf() -> float:
    cfg = _load_app_cfg()
    try:
        v = float(cfg.get("fascia_piece_length_lf", 10.0))
        return v if v > 0 else 10.0
    except Exception:
        return 10.0

def ceil_pieces(total_lf: float, piece_len_lf: float) -> int:
    """Ceil up to whole pieces; always returns an int ≥ 0."""
    lf = float(total_lf or 0.0)
    piece = float(piece_len_lf or 0.0)
    if piece <= 0.0:
        piece = 10.0
    return max(0, int(math.ceil(lf / piece)))

def ceil_rolls(qty: float) -> int:
    return max(0, int(math.ceil(float(qty or 0.0))))

def round_money(x: float) -> float:
    return round(float(x or 0.0), 2)
