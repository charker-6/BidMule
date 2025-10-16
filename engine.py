# engine.py — Regis Estimator Core Engine (Phase 2, Upgrade 1 finalized, clean)
# ---------------------------------------------------------------------
# - Data model for inputs/outputs
# - Core siding quantity & labor calculations
# - Robust HOVER PDF text parsing (name/address + key totals)
# - Region inference (Metro / North CO / Mountains)

from __future__ import annotations
import math
import re
from dataclasses import dataclass

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
NAIL_BOX_PER_SQ = 20.0             # 1 box / 20 squares
COIL_SQ_PER_ROLL_PRIMED = 5.0
COIL_SQ_PER_ROLL_COLORPLUS = 2.5   # per color (body + trim)
COIL_REDUCTION = 0.5               # reduce coil count by 50%
TAPE_PER_WRAP_ROLL = 2

# Labor adders/credits per square
NO_DEMO_CREDIT_PER_SQ = -30.0
EXTRA_LAYER_ADD_PER_SQ = 60.0
BRICK_STUCCO_ADD_PER_SQ = 150.0

# =============================== HELPERS ===============================

def ft_in_to_ft(txt: str) -> float:
    """
    Convert strings like 261'11" or 159'8" to decimal feet.
    Accepts plain numbers as feet. Returns 0.0 if not parseable.
    """
    m = re.match(r"^\s*(\d+)\s*'\s*(\d+)\s*(?:\"|in)?\s*$", str(txt) or "", re.I)
    if m:
        return float(m.group(1)) + float(m.group(2)) / 12.0
    try:
        return float(txt)
    except Exception:
        return 0.0

# ============================== DATA MODEL =============================
from dataclasses import dataclass

@dataclass
class JobInputs:
    # Identity
    customer_name: str
    address: str

    # Region & system
    region: str                  # "Metro" | "North CO" | "Mountains"
    siding_type: str             # "Lap" | "Board & Batten" | "Shake"
    finish: str                  # "ColorPlus" | "Primed"
    body_color: str              # free text if ColorPlus else "Primed White"
    trim_color: str              # "Arctic White","Timber Bark","Cobblestone","Iron Gray","Primed"
    complexity: str              # "Low" | "Med" | "High"

    # Site conditions
    demo_required: bool
    extra_layers: int            # >= 0
    substrate: str               # "Wood" | "Brick" | "Stucco" | "Other"

    # HOVER quantities (Areas → Siding/Other table)
    facades_sf: float
    trim_siding_sf: float

    # Roofline lengths (for soffit/fascia)
    eave_fascia_ft: float
    rake_fascia_ft: float
    soffit_depth_gt_24: bool

    # Trim derivation
    openings_perimeter_ft: float
    outside_corners_ft: float
    inside_corners_ft: float
    fascia_width_in: int         # 4, 6, 8, 12

    # OSB options
    osb_selected: bool
    osb_area_override_sf: float | None



from dataclasses import dataclass

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

# ============================== CORE ENGINE ============================

# Try rule registry; fall back to local defaults if unavailable
try:
    from core.rules import siding_area_rule, fascia_piece_length_lf, ceil_pieces
except Exception:
    def siding_area_rule() -> str:
        return "max"
    def fascia_piece_length_lf() -> float:
        return 12.0  # BM-F-012 default
    import math as _math
    def ceil_pieces(total_lf: float, piece_len_lf: float) -> int:
        if piece_len_lf <= 0:
            return 0
        return int(_math.ceil(max(0.0, float(total_lf)) / float(piece_len_lf)))

# ========================= Board/Panel/Nail Logic ========================
# ========================= (questionable) ========================


def _planks_for_area(area_sf: float, exposure_in: float) -> int:
    """
    Hardie chart behavior matches rounding to nearest integer.
    One 12' plank covers (exposure_in) square feet.
    """
    if exposure_in <= 0:
        return 0
    return max(0, int(round(float(area_sf or 0.0) / exposure_in)))

def _nails_for_area(area_sf: float, exposure_in: float) -> int:
    """
    From Hardie chart: nails per 100 sf are approx 10 / exposure_in * 100.
    So nails per sf ~= 10 / exposure_in. Use rounding to match table.
    """
    if exposure_in <= 0:
        return 0
    return max(0, int(round(float(area_sf or 0.0) * (10.0 / exposure_in))))


def compute_estimate(inp: JobInputs) -> JobOutputs:
    # Siding area rule
    if siding_area_rule() == "sum":
        total_sf = float(inp.facades_sf) + float(inp.trim_siding_sf)
    else:
        total_sf = max(float(inp.facades_sf), float(inp.trim_siding_sf))
    total_sq = math.ceil(total_sf / 100.0)

    # Waste (BM-W-001 already embodied in constants)
    waste_pct = WASTE_BASE_SIDING + WASTE_COMPLEXITY.get(inp.complexity, 0.0)

    # --- BOARD/PLANK METRICS (Lap only, default 8.25 width → 7" exposure) ---
    boards = 0
    exposure_in = 7.0
    if inp.siding_type == "Lap":
        # Round to nearest to replicate Hardie chart
        boards_net = _planks_for_area(total_sf, exposure_in)
        boards = int(math.ceil(boards_net * (1.0 + waste_pct)))

    # Wrap & tape
    wrap_rolls = math.ceil(total_sf / (WRAP_ROLL_SF / (1.0 + WRAP_WASTE)))
    tape_rolls = int(wrap_rolls * TAPE_PER_WRAP_ROLL)

    # Nails — from Hardie chart, then convert to boxes
    nails = _nails_for_area(total_sf, exposure_in)
    NAILS_PER_BOX = 2500  # adjust if you change your supply spec
    nail_boxes = max(1, int(math.ceil((nails * (1.0 + waste_pct)) / float(NAILS_PER_BOX))))

    # Coil (reduced by 50%)
    if inp.finish == "Primed":
        raw_coils = math.ceil(total_sq / COIL_SQ_PER_ROLL_PRIMED)
    else:
        raw_coils = math.ceil(total_sq / COIL_SQ_PER_ROLL_COLORPLUS) * 2  # body + trim
    coil_rolls = max(1, math.ceil(raw_coils * COIL_REDUCTION))

    # Labor single source
    rate = LABOR_RATES.get(inp.siding_type, LABOR_RATES["Lap"]).get(inp.region, 3.35)
    labor_cost = total_sf * rate
    if not inp.demo_required:
        labor_cost += total_sq * NO_DEMO_CREDIT_PER_SQ
    if inp.extra_layers and inp.extra_layers > 0:
        labor_cost += total_sq * EXTRA_LAYER_ADD_PER_SQ * inp.extra_layers
    if inp.substrate.lower() in ("brick", "stucco"):
        labor_cost += total_sq * BRICK_STUCCO_ADD_PER_SQ
    labor_psq = 0.0 if total_sq == 0 else round(labor_cost / float(total_sq), 2)

    # Soffit & fascia (keep current approach; panel sizing paved by catalog)
    total_fascia_lf = float(inp.eave_fascia_ft + inp.rake_fascia_ft)
    soffit_panels = int(round(total_fascia_lf / (10.0 if inp.soffit_depth_gt_24 else 18.0)))
    fascia_pieces = ceil_pieces(total_fascia_lf, fascia_piece_length_lf())

    # 4" trim (corners + openings)
    trim4_lf = (2.0 * inp.outside_corners_ft) + inp.inside_corners_ft + inp.openings_perimeter_ft
    trim4_pieces = math.ceil(trim4_lf / 12.0)

    # Defaults
    paint_quarts = 0 if inp.finish == "Primed" else 2
    window_flash_tape = math.ceil(total_sq / 5.0)
    trim6_def = trim8_def = trim12_def = 2

    # OSB option
    osb_sheets = 0
    osb_framing_boxes = 0
    if inp.osb_selected:
        osb_area = inp.osb_area_override_sf if inp.osb_area_override_sf else total_sf
        osb_sheets = math.ceil(osb_area / 32.0)                  # 4x8 = 32 sf
        osb_framing_boxes = max(1, math.ceil(osb_area / 1000.0)) # 1 box / 10 SQ, min 1

    return JobOutputs(
        total_sf=round(total_sf, 2),
        total_sq=total_sq,
        boards=boards,
        wrap_rolls=wrap_rolls,
        tape_rolls=tape_rolls,
        nail_boxes=nail_boxes,
        coil_rolls=coil_rolls,
        window_flash_tape=window_flash_tape,
        soffit_panels_4x10=soffit_panels,
        fascia_pieces_12ft=fascia_pieces,
        trim4_pieces_12ft=trim4_pieces,
        trim6_pieces_default=trim6_def,
        trim8_pieces_default=trim8_def,
        trim12_pieces_default=trim12_def,
        paint_quarts=paint_quarts,
        labor_rate_per_sf=rate,
        labor_cost=round(labor_cost, 2),
        osb_sheets=osb_sheets,
        osb_framing_boxes=osb_framing_boxes,
        labor_psq=labor_psq,
    )


# ========================= PDF TEXT EXTRACTION ========================

def extract_name_and_address(pdf_text: str) -> tuple[str, str, str, str]:
    """
    Return (name, street_line, city_state_zip, zip_code).
    Robust: finds name under Model ID, then scans forward to the FIRST street-pattern line
    and the next 'City, CO ZIP' line (no fixed offsets).
    """
    def norm(s: str) -> str:
        s = s.strip()
        s = re.sub(r"(?i)^complete\s+measurements.*$", "", s)
        s = re.sub(r"[\u00A0\u2000-\u200D]", " ", s)
        s = re.sub(r"[\u2010-\u2015]", "-", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        return s

    def cut_name_tail(s: str) -> str:
        s = re.sub(r"[-–—\*]\s*\d.*$", "", s)
        s = re.sub(r"\d{1,2}\s+[A-Za-z]{3,}\s+\d{4}.*$", "", s)
        s = re.sub(r"\d{4}-\d{2}-\d{2}.*$", "", s)
        s = re.sub(r"\d{1,2}:\d{2}.*$", "", s)
        return s.strip()

    lines = [norm(l) for l in pdf_text.splitlines() if l.strip()]

    name = "Unknown Name"
    street_line = ""
    city_state_zip = ""
    zip_code = "00000"

    street_pat = re.compile(
        r"\b\d{3,6}\s+[A-Za-z0-9\s\.\-']+\s+(Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Trail|Place|Pl)\b",
        re.I,
    )
    city_pat = re.compile(r",\s*CO\b", re.I)

    name_idx = -1
    for i, line in enumerate(lines):
        if re.match(r"(?i)^property\s*id", line):
            for j in range(i + 1, min(i + 8, len(lines))):
                if re.match(r"(?i)^model\s*id", lines[j]):
                    for k in range(j + 1, min(j + 8, len(lines))):
                        if not lines[k].strip():
                            continue
                        raw = lines[k].strip()
                        cleaned = cut_name_tail(norm(raw))
                        m = re.match(r"([A-Z][a-zA-Z']+)(?:\s+([A-Z][a-zA-Z']+))?", cleaned)
                        if m:
                            name = " ".join([g for g in m.groups() if g])
                        else:
                            name = cleaned.split(" ")[0].title() if cleaned else "Unknown Name"
                        name_idx = k
                        break
                    break
            break

    start_idx = name_idx + 1 if name_idx >= 0 else 0
    street_idx = -1
    for idx in range(start_idx, min(start_idx + 15, len(lines))):
        if street_pat.search(lines[idx]):
            street_line = norm(lines[idx])
            street_idx = idx
            break

    if street_idx != -1:
        for idx in range(street_idx + 1, min(street_idx + 10, len(lines))):
            if city_pat.search(lines[idx]):
                city_state_zip = norm(lines[idx])
                mzip = re.search(r"\b(\d{5})(?:-\d{4})?\b", city_state_zip)
                if mzip:
                    zip_code = mzip.group(1)
                break

    if not street_line:
        for i, line in enumerate(lines):
            if street_pat.search(line):
                street_line = norm(line)
                if i + 1 < len(lines) and city_pat.search(lines[i + 1]):
                    city_state_zip = norm(lines[i + 1])
                    mzip = re.search(r"\b(\d{5})(?:-\d{4})?\b", city_state_zip)
                    if mzip:
                        zip_code = mzip.group(1)
                break

    return name, (street_line or "Unknown Address"), city_state_zip, zip_code

# ======================== HOVER TOTALS PARSER =========================
_NUM = r"([\d,]+(?:\.\d+)?)"

def _num_to_float(s: str) -> float:
    try:
        return float(s.replace(",", ""))
    except Exception:
        return 0.0

# Patterns
_len_ftin       = re.compile(r"(\d+'\s*\d{1,2}\")")  # e.g., 113'6" or 113' 6"
_len_with_unit  = re.compile(rf"{_NUM}\s*(?:lf|linear\s*feet|ft|feet)\b", re.I)
_area_with_unit = re.compile(rf"{_NUM}\s*(?:sf|sq\s*feet|square\s*feet|ft²|ft2)\b", re.I)
_bare_number    = re.compile(rf"^\s*{_NUM}\s*$")  # table cell with just a number

def ft_str_to_ft(s: str) -> float:
    s = s.strip()
    m = re.match(r"^\s*(\d+)'\s*(\d{1,2})\"\s*$", s)
    if m:
        return float(m.group(1)) + float(m.group(2)) / 12.0
    try:
        return float(s)
    except Exception:
        return 0.0

def _scan_area(lines: list[str], idx: int, lookahead: int = 8) -> float:
    """Find area with explicit units near idx."""
    if idx is None or idx < 0:
        return 0.0
    end = min(idx + 1 + lookahead, len(lines))
    # same line first
    m0 = _area_with_unit.search(lines[idx])
    if m0:
        return _num_to_float(m0.group(1))
    # following lines
    for j in range(idx + 1, end):
        m = _area_with_unit.search(lines[j])
        if m:
            return _num_to_float(m.group(1))
    return 0.0

def _scan_len_strict(lines: list[str], idx: int, lookahead: int = 8) -> float:
    """LF only if explicit units or ft'in\" form near idx."""
    if idx is None or idx < 0:
        return 0.0
    end = min(idx + 1 + lookahead, len(lines))
    # same line first
    line0 = lines[idx]
    m = _len_ftin.search(line0)
    if m:
        return ft_str_to_ft(m.group(1))
    m = _len_with_unit.search(line0)
    if m:
        return _num_to_float(m.group(1))
    # following lines
    for j in range(idx + 1, end):
        line = lines[j]
        m = _len_ftin.search(line)
        if m:
            return ft_str_to_ft(m.group(1))
        m = _len_with_unit.search(line)
        if m:
            return _num_to_float(m.group(1))
    return 0.0

def _scan_len_within_block(lines: list[str], start: int, end: int,
                           prefer_line_idx: int | None = None,
                           allow_bare: bool = True,
                           bare_min: float = 1, bare_max: float = 10000) -> float:
    """
    Inside a known block, try strict LF first; optionally accept a bare numeric
    cell (common when units are only in the column header).
    """
    # 1) strict (prefer a specific row if provided)
    if prefer_line_idx is not None and start <= prefer_line_idx < end:
        v = _scan_len_strict(lines, prefer_line_idx, lookahead=1)
        if v:
            return v
    for j in range(start, end):
        v = _scan_len_strict(lines, j, lookahead=1)
        if v:
            return v
    # 2) optional bare numeric fallback (bounded)
    if allow_bare:
        for j in range(start, end):
            m = _bare_number.match(lines[j])
            if m:
                n = _num_to_float(m.group(1))
                if bare_min <= n <= bare_max:
                    return n
    return 0.0

def _find_first(low_lines: list[str], label_variants: list[str]) -> int | None:
    for i, l in enumerate(low_lines):
        if any(v in l for v in label_variants):
            return i
    return None

def _find_under_block(low_lines: list[str], start_idx: int,
                      end_labels: list[str], lookahead: int = 30) -> tuple[int, int]:
    """Return [start, end) window under a section header; stop at next header or lookahead."""
    if start_idx is None or start_idx < 0:
        return (-1, -1)
    end = min(len(low_lines), start_idx + 1 + lookahead)
    for j in range(start_idx + 1, end):
        if any(lbl in low_lines[j] for lbl in end_labels):
            end = j
            break
    return (start_idx, end)

def extract_hover_totals(pdf_text: str) -> dict:
    """
    Extract key totals from HOVER first pages.
    Returns floats in feet or square feet; missing values are 0.0.
    """
    raw_lines = [l for l in pdf_text.splitlines() if l.strip()]
    # preserve line order, normalize inner spacing only
    lines = [re.sub(r"[ \t]+", " ", l) for l in raw_lines]
    low = [l.lower() for l in lines]

    # ----------------- Areas -----------------
    facades_idx = _find_first(low, [
        "facades", "total siding", "wall area", "siding area"
    ])
    trim_idx    = _find_first(low, [
        "trim / siding", "trim touching siding", "trim area", "siding & trim only"
    ])
    facades_sf = _scan_area(lines, facades_idx, lookahead=10)
    trim_siding_sf = _scan_area(lines, trim_idx, lookahead=10)

    # ----------------- Eaves / Rakes -----------------
    eave_fascia = 0.0
    rake_fascia = 0.0

    eaves_idx = _find_first(low, [
        "eaves fascia", "eave fascia", "eaves", "total eaves", "eave length"
    ])
    if eaves_idx is not None:
        s, e = _find_under_block(
            low, eaves_idx,
            end_labels=["rakes", "corners", "siding waste", "soffit", "roof", "drip edge", "area", "openings"],
            lookahead=40
        )
        if s != -1:
            # allow bare numeric (common in column-only units)
            eave_fascia = _scan_len_within_block(lines, s, e, allow_bare=True, bare_max=5000)

    rakes_idx = _find_first(low, [
        "rakes fascia", "rake fascia", "rakes", "gable length", "rake length", "gables"
    ])
    if rakes_idx is not None:
        s, e = _find_under_block(
            low, rakes_idx,
            end_labels=["eaves", "corners", "siding waste", "soffit", "roof", "drip edge", "area", "openings"],
            lookahead=40
        )
        if s != -1:
            rake_fascia = _scan_len_within_block(lines, s, e, allow_bare=True, bare_max=5000)

    # ----------------- Openings Perimeter -----------------
    # Prefer a dedicated “Total Perimeter” row if present.
    openings_perim = 0.0
    # First try an explicit “Total Perimeter” section that HOVER prints
    totper_idx = _find_first(low, ["total perimeter"])
    if totper_idx is not None:
        v_same = _scan_len_strict(lines, totper_idx, lookahead=3)
        if not v_same:
            # numbers might be in the next few rows/columns
            v_same = _scan_len_within_block(lines, totper_idx, min(totper_idx + 6, len(lines)),
                                            allow_bare=True, bare_max=5000)
        openings_perim = v_same

    if openings_perim == 0.0:
        # Fallback to the Openings block and search for a “perim/perimeter” row
        openings_hdr = _find_first(low, ["openings"])
        if openings_hdr is not None:
            s, e = _find_under_block(
                low, openings_hdr,
                end_labels=["corners", "siding waste", "soffit", "eaves", "rakes", "roof", "drip edge", "area"],
                lookahead=40
            )
            if s != -1:
                perim_row = None
                for j in range(s, e):
                    if ("perim" in low[j]) or ("perimeter" in low[j]):
                        perim_row = j
                        break
                if perim_row is not None:
                    openings_perim = _scan_len_within_block(
                        lines, s, e, prefer_line_idx=perim_row, allow_bare=True, bare_max=5000
                    )

    # ----------------- Corners (Inside / Outside) -----------------
    outside = 0.0
    inside  = 0.0
    corners_hdr = _find_first(low, ["corners", "corner lengths", "corner length"])
    if corners_hdr is not None:
        s, e = _find_under_block(
            low, corners_hdr,
            end_labels=["siding waste", "soffit", "eaves", "rakes", "roof", "drip edge", "area", "openings"],
            lookahead=40
        )
        if s != -1:
            # try explicit rows
            out_idx = _find_first(low[s:e], ["outside"])
            in_idx  = _find_first(low[s:e], ["inside"])
            if out_idx is not None:
                outside = _scan_len_within_block(
                    lines, s + out_idx, min(e, s + out_idx + 6),
                    allow_bare=True, bare_max=5000
                )
            if in_idx is not None:
                inside = _scan_len_within_block(
                    lines, s + in_idx, min(e, s + in_idx + 6),
                    allow_bare=True, bare_max=5000
                )
            # if still zero, allow a simple “Outside Corners … <number>” on same line
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

    corners_seen = corners_hdr is not None

    return dict(
        facades_sf=round(facades_sf, 2),
        trim_siding_sf=round(trim_siding_sf, 2),
        eave_fascia=round(eave_fascia, 2),
        rake_fascia=round(rake_fascia, 2),
        openings_perim=round(openings_perim, 2),
        outside=round(outside, 2),
        inside=round(inside, 2),
        corners_seen=corners_seen,
    )

# ======================== REGION INFERENCE ===========================

def auto_region_from_address(street_line: str, city_state_zip: str, zip_code: str) -> str:
    """
    Region inference priority:
      1) City keyword: Boulder or Golden -> Mountains
      2) ZIP >= 80501 -> North CO
      3) Else -> Metro
    """
    blob = f"{street_line} {city_state_zip}".lower()
    if "boulder, co" in blob or "golden, co" in blob:
        return "Mountains"

    try:
        z = int(zip_code)
    except Exception:
        z = 0

    if z >= 80501:
        return "North CO"
    return "Metro"
