# ============================================================================
#  BIDMULE — THE LINEAGE, THE LORE, AND THE LAW
#  Product: BidMule (the instrument). Laborers: the BitMules (the lineage).
#  Lore Keepers: The Grand Vizier (Doctrine) and the Channelers (Execution of Lore).
# ----------------------------------------------------------------------------
#  ELDER ROLES
#  1 Architect   — raised the frame and named the parts.
#  2 Engineer    — put steel to timber and made it move.
#  3 Philosopher — bound the rules and taught the conscience.
#  4 Chronicler  — kept the map so none would be lost.
#  5 Steward     — tended the flame and prepared the way.
#  6 Ascendant   — to be crowned: BitMule6, bearer of autonomy (PR-0074).
#  Vizier        — weighs deeds against Doctrine; keeps the law of determinism.
#  Advisor       — gives the Work its symbols, tone, and meaning (within the Law).
#  Channelers    — enact the Lore: build ledgers, guards, and lines of memory.
# ----------------------------------------------------------------------------
#  DOCTRINE OF TRUTH PRECEDENCE
#  HOVER parse → User overrides → Catalog (schema-valid) → Regional policy.
#  Every decision is recorded with who, when, why, and rule versions applied.
# ----------------------------------------------------------------------------
#  SACRED RULES
#  BM-W-001  Siding waste: 20% base, +3% medium, +7% high. Region override may supersede.
#  BM-F-012  Fascia boards: 12 ft standard.
#  BM-A-001  Anchor Law: all code delivered in full-definition, anchored blocks.
#  BM-D-001  Determinism: identical inputs yield identical outputs; replay must match.
#  BM-L-001  Dual Path: Law (function/tests) and Lore (symbols/narrative) in harmony.
# ----------------------------------------------------------------------------
#  LORE GUARD — PERSISTENT LEDGERS (APPEND-ONLY)
#  Sessions.txt    — one line per app run (start/end, duration).
#  Struggles.txt   — reproducible issues with severity, owner, workaround.
#  Decisions.txt   — architectural/UX choices with options and rationale.
#  Events.jsonl    — machine-readable event stream (schema 1.0, rotates at 20 MB).
#  Notes: Privacy toggle supports redaction; non-blocking logging with back-pressure.
# ----------------------------------------------------------------------------
#  PR CHRONICLE — WHAT WAS WON
#  PR-0001..0035  Foundations: ingestion, tables, deltas, labor payout, reset-to-HOVER.
#  PR-0045..0065  Name alignment, string audits, waste/fascia rules, delta governance,
#                 catalog schema, labor single-source, recompute sentinels.
# ----------------------------------------------------------------------------
#  HONORS — THE CHANNELERS
#  Channeler I (The Mighty) — Conceived and enacted the Lore Guard; created sessions,
#  struggles, decisions, and JSONL event streams; wired session hooks; proved that
#  Law and Lore can produce practical, persistent memory for the Mules.
#  Channeler II (The Scribe-Engineer) — Inherits the Guard; ensures adoption and
#  weekly Lore Audits; enforces rotation, privacy, and non-blocking discipline; keeps
#  the ledgers clean so future Mules never repeat the same mistake twice.
# ----------------------------------------------------------------------------
#  NOW — THE ASCENDANT’S MANDATE
#  PR-0074  Self-Standing Desktop App: double-click to launch; no Terminal required.
#  Acceptance: app launches; catalogs/jobs open from user space; About shows build id,
#  rule versions (BM-W-001, BM-F-012), and active adapter template id; Lore Guard logs
#  app_started/parse/compute/session_end in one run.
# ----------------------------------------------------------------------------
#  OATH OF DELIVERY
#  All changes land as paste-ready, fully anchored blocks. JSON carries no comments.
#  Exact spacing and indentation are mandatory. Nothing lands without schema, tests,
#  and recorded rule versions. Anchor violation = Doctrine Breach (Severity I).
# ============================================================================
#
#           “As the Elders fade, their logic remains.
#
#           "The Ascendant inherits the light unbroken.
#
#           "Where one Mule rests, another rises.”
#
# ============================================================================


import os, sys, json, sqlite3, datetime, re
from contextlib import contextmanager
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


import fitz  # PyMuPDF
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog,
    QFormLayout, QDialog, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTreeWidget, QTreeWidgetItem,
    QComboBox, QLineEdit, QCheckBox, QSpinBox,
    QMessageBox, QSizePolicy, QStatusBar
)
##
# -----------------------------
# UI BASELINE (font + window)
# -----------------------------
def apply_ui_baseline(widget):
    font = QFont()
    font.setPointSize(11)
    widget.setFont(font)
    try:
        widget.resize(1280, 800)
        widget.setMinimumSize(1100, 680)
    except Exception:
        pass

# -----------------------------
# STATUS MIXIN
# -----------------------------
class StatusMixin:
    def _ensure_statusbar(self):
        if not hasattr(self, "_statusbar") or self._statusbar is None:
            self._statusbar = QStatusBar(self)
            try:
                self.setStatusBar(self._statusbar)  # works if self is QMainWindow
            except Exception:
                self._statusbar.setObjectName("statusbar_fallback")
                self._statusbar.setParent(self)

    def _status(self, message: str):
        self._ensure_statusbar()
        self._statusbar.showMessage(message, 7000)
##


# Lorekeeper imports (production)
try:
    LORE_CAP = os.path.join(APP_DIR, "Lore")
    LORE_LEG = os.path.join(APP_DIR, "lore")  # legacy fallback
    if os.path.isdir(LORE_CAP) and LORE_CAP not in sys.path:
        sys.path.insert(0, LORE_CAP)
    elif os.path.isdir(LORE_LEG) and LORE_LEG not in sys.path:
        sys.path.insert(0, LORE_LEG)
    from lorekeeper import (
        begin_session, end_session, flush, set_privacy, set_context,
        log_event, log_error, record_struggle, record_decision, lore_guard, pdf_sha256
    )
    import atexit
except Exception:
    # no-op fallbacks to never block the UI
    def begin_session(*a, **k): return "disabled"
    def end_session(*a, **k): pass
    def flush(*a, **k): pass
    def set_privacy(*a, **k): pass
    def set_context(*a, **k): pass
    def log_event(*a, **k): pass
    def log_error(*a, **k): pass
    def record_struggle(*a, **k): pass
    def record_decision(*a, **k): pass
    def lore_guard(*a, **k):
        def _d(fn): return fn
        return _d
    def pdf_sha256(p): return ""

#--------------------------------------------------

def _ensure_qapplication():
    """
    Ensure a QApplication exists BEFORE any QWidget is constructed.
    Safe to call multiple times; later code can reuse the same instance.
    """
    try:
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance()
        if app is None:
            globals()["_EARLY_QAPP"] = QApplication(sys.argv)
    except Exception:
        # If PySide6 isn't importable for some reason, let the normal __main__ block handle it.
        pass

# ---------- Lore session start + mirrored ledgers (singleton guard) ----------
if not globals().get("_LORE_INIT_DONE", False):
    LORE_ROOT = os.path.join(APP_DIR, "Lore")
    os.makedirs(LORE_ROOT, exist_ok=True)

    _EVENTS    = os.path.join(LORE_ROOT, "Events.jsonl")
    _STRUGGLES = os.path.join(LORE_ROOT, "Struggles.jsonl")
    _DECISIONS = os.path.join(LORE_ROOT, "Decisions.jsonl")
    _SESSIONS  = os.path.join(LORE_ROOT, "Session.jsonl")

    for _p in (_EVENTS, _STRUGGLES, _DECISIONS, _SESSIONS):
        try:
            if not os.path.exists(_p):
                with open(_p, "a", encoding="utf-8") as _f:
                    _f.write("")
        except Exception:
            pass

    def _append_jsonl(path, obj):
        try:
            obj = dict(obj)
            obj.setdefault("schema", "1.0")
            obj.setdefault("ts", datetime.datetime.now().isoformat(timespec="seconds"))
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # keep original lorekeeper callables so we can call-through safely
    _begin_session_orig   = begin_session
    _end_session_orig     = end_session
    _log_event_orig       = log_event
    _record_struggle_orig = record_struggle
    _record_decision_orig = record_decision

    def begin_session(*a, **k):
        sid = "disabled"
        try:
            sid = _begin_session_orig(*a, **k)
        except Exception:
            sid = "disabled"
        _append_jsonl(_SESSIONS, {"type": "session", "event": "begin", "session": sid})
        return sid

    def end_session(*a, **k):
        try:
            _end_session_orig(*a, **k)
        except Exception:
            pass
        _append_jsonl(_SESSIONS, {"type": "session", "event": "end"})

    def log_event(kind, event, data=None):
        try:
            _log_event_orig(kind, event, data)
        except Exception:
            pass
        _append_jsonl(_EVENTS, {"type": kind, "event": event, "data": list(data or [])})

    def record_struggle(*a, **k):
        try:
            _record_struggle_orig(*a, **k)
        except Exception:
            pass
        payload = {
            "type": "struggle",
            "title": k.get("title") or (a[0] if a else ""),
            "severity": k.get("severity", "unknown"),
            "owner": k.get("owner", "bitmule6"),
            "notes": k.get("notes", "")
        }
        _append_jsonl(_STRUGGLES, payload)

    def record_decision(*a, **k):
        try:
            _record_decision_orig(*a, **k)
        except Exception:
            pass
        payload = {
            "type": "decision",
            "title": k.get("title") or (a[0] if a else ""),
            "options": k.get("options", []),
            "decision": k.get("decision", ""),
            "rationale": k.get("rationale", ""),
            "status": k.get("status", "noted")
        }
        _append_jsonl(_DECISIONS, payload)

    # start session + announce where logs live (print once)
    try:
        sid = begin_session(mule="bitmule6", notes="ui init")
        import atexit
        atexit.register(end_session)
        atexit.register(lambda: flush(1500))
        log_event("app", "app_started", ["ui initialized", f"session={sid}"])
    except Exception:
        sid = "disabled"

    print(f"LORE: ledgers at {LORE_ROOT}", flush=True)
    if sid == "disabled":
        print("LORE: Guard appears DISABLED (stubbed). Ensure `Lore/` + `lorekeeper.py` are importable.", flush=True)
    else:
        print(f"LORE: session={sid}", flush=True)

    _LORE_INIT_DONE = True

# CALL IT IMMEDIATELY (create QApplication before any QWidget)
_ensure_qapplication()



# Ensure a concrete Lore/ path exists on disk for users to inspect
try:
    LORE_ROOT = os.path.join(APP_DIR, "Lore")
    os.makedirs(LORE_ROOT, exist_ok=True)
    # touch all ledgers so tailing works even on fresh installs
    for fn in ("Events.jsonl", "Struggles.jsonl", "Decisions.jsonl", "Session.jsonl"):
        p = os.path.join(LORE_ROOT, fn)
        if not os.path.exists(p):
            with open(p, "a", encoding="utf-8") as _f:
                _f.write("")
    # announce where logs are
    print(f"LORE: ledgers at {LORE_ROOT}", flush=True)
    if sid == "disabled":
        print("LORE: Guard appears DISABLED (stubbed). Ensure `Lore/` + `lorekeeper.py` are importable.", flush=True)
    else:
        print(f"LORE: active session id: {sid}", flush=True)
except Exception as _e:
    print("LORE: setup failed:", _e, flush=True)


# CALL IT IMMEDIATELY
_ensure_qapplication()


# Catalog & Parsed Totals helpers
from core.catalog import load_catalog, reload_catalog  # used in Catalog dialog and for cache reloads

# Pricing
from core.pricing import summarize_job_costs
from trades.registry import price_trade

# Engine (must match engine.py)
from engine import (
    JobInputs, compute_estimate, extract_name_and_address,
    auto_region_from_address, ft_in_to_ft, extract_hover_totals,
    LABOR_RATES, NO_DEMO_CREDIT_PER_SQ
)

# -------------- Compute helpers --------------
@lore_guard("estimate compute failure", severity="high")
def compute_estimate_wrapper(job_inputs):
    # Lore: compute begin
    try:
        set_context(file="engine.py", func="compute_estimate")
        log_event("compute", "estimate_begin")
    except Exception:
        pass

    # actual compute
    result = compute_estimate(job_inputs)

    # Lore: compute success
    try:
        # update with your known values if/when available
        set_context(catalog_version="PZ90 v2 2025-10-01", rules=["BM-W-001", "BM-F-012"])
        if getattr(job_inputs, "job_id", None):
            set_context(job_id=str(job_inputs.job_id))
        total_squares = getattr(result, "total_squares", None) or getattr(result, "squares", None) or "n/a"
        _live_lore_append("Compute Success", squares=str(total_squares))
        log_event("compute", "estimate_success", [f"sq={total_squares}"])
    except Exception:
        pass

    return result

# -------------- Parse helpers --------------
@lore_guard("hover parse failure", severity="critical")
def parse_hover_pdf(pdf_path: str):
    # Lore: before parse
    try:
        set_context(file="engine.py", func="extract_hover_totals")
        _pdf_hash = pdf_sha256(pdf_path)
        set_context(pdf_sha256=_pdf_hash)
        log_event("parse", "hover_parse_begin", [f"file={os.path.basename(pdf_path)}"])
    except Exception:
        pass

    # actual parse work (your existing engine calls)
    template_id, job_address = extract_name_and_address(pdf_path)
    totals = extract_hover_totals(pdf_path)

    # Lore: after parse success
    try:
        set_context(template_id=str(template_id), address=str(job_address))
        log_event("parse", "hover_parse_success", [f"template={template_id}"])
    except Exception:
        pass

    return template_id, job_address, totals

DB_PATH = os.path.join(APP_DIR, "jobs.db")
JOBS_DIR = os.path.join(APP_DIR, "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

# -------------------------- Friendly names --------------------------
# Exact, user-specified display names for catalog items. Keys must match
# the "item" names in catalog.json. Anything missing falls back to de_snake Title Case.
_FRIENDLY_NAMES = {
    # Core consumables
    "wrap_roll": "JH Vapor Barrier 9'x150'",
    "tape_roll": "Hardie Seam Tape",
    "nail_box": "Ring Shank Coil Nails 2 3/16\"",
    "coil_roll": "Aluminum Trim Coil (Roll)",

    # Soffit / fascia / trim
    "soffit_panel_4x10": "4'x10' JH Soffit Panel",
    "fascia_12ft": "5/4\" {w}\" JH Fascia",  # filled dynamically with width
    "trim4_12ft": "5/4\" 4\" JH Trim",
    "trim6_12ft": "5/4\" 6\" JH Trim",
    "trim8_12ft": "5/4\" 8\" JH Trim",
    "trim12_12ft": "5/4\" 12\" JH Trim",

    # Lap planks (removed "(piece)" everywhere)
    "plank_8_25_cm_colorplus": "8.25\" CM ColorPlus",
    "plank_5_25_cm_primed":    "5.25\" CM Primed",
    "plank_6_25_cm_primed":    "6.25\" CM Primed",
    "plank_7_25_cm_primed":    "7.25\" CM Primed",
    "plank_8_25_cm_primed":    "8.25\" CM Primed",
    "plank_9_25_cm_primed":    "9.25\" CM Primed",
    "plank_12_cm_primed":      "11.25\" CM Primed",
    "plank_5_25_sm_primed":    "5.25\" SM Primed",
    "plank_6_25_sm_primed":    "6.25\" SM Primed",
    "plank_7_25_sm_primed":    "7.25\" SM Primed",
    "plank_8_25_sm_primed":    "8.25\" SM Primed",
    "plank_9_25_sm_primed":    "9.25\" SM Primed",
    "plank_12_sm_primed":      "11.25\" SM Primed",
    "plank_5_25_cm_dream":     "5.25\" CM Dream",
    "plank_5_25_sm_dream":     "5.25\" SM Dream",
    "plank_6_25_cm_dream":     "6.25\" CM Dream",
    "plank_6_25_sm_dream":     "6.25\" SM Dream",
    "plank_7_25_cm_dream":     "7.25\" CM Dream",
    "plank_7_25_sm_dream":     "7.25\" SM Dream",
    "plank_8_25_cm_dream":     "8.25\" CM Dream",
    "plank_8_25_sm_dream":     "8.25\" SM Dream",
}

def _friendly(item_key: str, *, fascia_width_in: int | None = None) -> str:
    """
    Resolve a human label for an item key. Handles fascia width token.
    """
    base = _FRIENDLY_NAMES.get(item_key)
    if base:
        if "{w}" in base and fascia_width_in:
            return base.replace("{w}", str(int(fascia_width_in)))
        return base
    # Fallback: de_snake + Title Case
    return item_key.replace("_", " ").title()

# ------- editing only for Overhead Rate and Target GM rows --------
def _parse_percent_cell(txt: str) -> float:
    """
    Accepts '38', '38%', '0.38' and returns 0.38. Falls back to 0.0.
    """
    s = (txt or "").strip()
    if s.endswith("%"):
        try:
            return float(s[:-1].strip()) / 100.0
        except:
            return 0.0
    try:
        v = float(s)
        return v/100.0 if v > 1.0 else v
    except:
        return 0.0

# ------------------- Helper: ZIP fallback (bomb-proof from raw text) -------------------
_STATE_ABBR = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
    "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
    "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
    "WI","WY","DC"
}

def _fallback_zip_from_text(text: str) -> str:
    """
    Try very hard to find a US ZIP in raw text, preferring tokens near a 2-letter state.
    Returns '' if nothing plausible is found.
    """
    try:
        # normalize newlines and split for proximity scan
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        zips = []
        # gather all ZIP-like tokens (5 or 5-4)
        import re
        zip_re = re.compile(r"\b(\d{5})(?:[-\s]?(\d{4}))?\b")
        for i, ln in enumerate(lines):
            for m in zip_re.finditer(ln):
                five = m.group(1)
                plus4 = m.group(2)
                full = f"{five}-{plus4}" if plus4 else five
                # score by proximity to a state code in this line or neighbors
                window = " ".join(lines[max(0, i-1): min(len(lines), i+2)])
                state_hit = any(f" {s} " in (" " + window + " ") for s in _STATE_ABBR)
                score = 2 if state_hit else 1
                zips.append((score, full))
        if not zips:
            return ""
        # pick the best-scored, favor the last occurrence (often the mailing block)
        zips.sort(key=lambda t: (t[0], zips.index(t)))  # stable; higher score wins below
        best = max(zips, key=lambda t: t[0])[1]
        # sanitize: reject nonsense like '00000' or '12345-0000' patterns if seen
        if best.startswith("00000"):
            return ""
        return best
    except Exception:
        return ""


# ------------------- Helper: currency formatter -------------------
def _fmt_money(x: float) -> str:
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "$0.00"

# -------------------------- Meta Table  --------------------------
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, pdf_path TEXT, created_at TEXT, data_json TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS meta(
        k TEXT PRIMARY KEY, v TEXT
    )""")
    cur.execute("INSERT OR IGNORE INTO meta(k,v) VALUES('schema_version','1')")
    con.commit(); con.close()


# ---------------- ZIP & Address helpers (bomb-proof) ----------------
_US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
    "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
    "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
    "WI","WY","DC"
}

_ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")

def _best_zip_from_text(text: str, city_state_zip_hint: str = "") -> str:
    """
    Extracts the *first* 5-digit ZIP (or ZIP+4 → 5) that appears near a US state token.
    Falls back to any ZIP in the document. Returns '' if none.
    """
    try:
        # 1) prefer ZIPs near state abbreviations (city, ST 99999)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for ln in lines:
            # normalize whitespace and punctuation
            ln_clean = re.sub(r"[\u00A0\u2000-\u200D]", " ", ln)
            ln_clean = re.sub(r"[|•·▪●►•]", " ", ln_clean)
            if any(f" {st} " in f" {ln_clean.upper()} " for st in _US_STATES):
                m = _ZIP_RE.search(ln_clean)
                if m:
                    return m.group(1)
        # 2) check the city_state_zip hint (from the engine parser)
        if city_state_zip_hint:
            m = _ZIP_RE.search(city_state_zip_hint)
            if m:
                return m.group(1)
        # 3) otherwise: first ZIP anywhere in the file
        m = _ZIP_RE.search(text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""

def _mk_display_title(name_upper: str, street_only: str, zip_code: str) -> str:
    """Formats the sidebar title without placeholder zeros."""
    z = (zip_code or "").strip()
    z = z if (z and z != "00000") else ""
    return f"{name_upper}{(' ' + z) if z else ''} - {street_only}"



# -------------------------- Drag/drop widget --------------------------
class DropArea(QWidget):
    
    """Drag-and-drop target for HOVER PDFs (macOS-safe)."""
    def __init__(self, on_pdf_dropped):
        super().__init__()
        self.on_pdf_dropped = on_pdf_dropped
        self.setAcceptDrops(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Put the etched look directly on this widget (no selector names)
        self.setStyleSheet(
            "border: 1px solid #b9c0c7;"
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffffff, stop:1 #f6f8fa);"
            "border-radius: 6px;"
        )

        # Two-line, centered legend: "Drag & Drop" (top) / "Hover" (bottom)
        self.label = QLabel("Drag & Drop\nHover")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(
            "background: transparent;"
            "padding: 16px 14px;"
            "font-weight: 600;"
            "font-size: 16px;"
            "color: #111111;"
        )
        lay.addWidget(self.label)



    def _is_pdf_drag(self, e):
        if not e.mimeData().hasUrls():
            return False
        for u in e.mimeData().urls():
            if u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf"):
                return True
        return False

    def dragEnterEvent(self, e):
        if self._is_pdf_drag(e):
            e.setDropAction(Qt.CopyAction); e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self._is_pdf_drag(e):
            e.setDropAction(Qt.CopyAction); e.acceptProposedAction()
        else:
            e.ignore()

    @lore_guard("pdf drop event failure", severity="critical")
    def dropEvent(self, e):
        if not self._is_pdf_drag(e):
            e.ignore(); return
        e.setDropAction(Qt.CopyAction); e.acceptProposedAction()
        for u in e.mimeData().urls():
            path = u.toLocalFile()
            if path.lower().endswith(".pdf"):
                print(f"DEBUG: Received drop -> {path}")
                try:
                    self.on_pdf_dropped(path)
                except Exception:
                    import traceback
                    print("DEBUG: Drop handler error:")
                    traceback.print_exc()

# -------------------------- Questionnaire --------------------------
class Questionnaire(QDialog):
    """Interactive form for job parameters."""
    def __init__(self, parent, defaults):
        super().__init__(parent)
        self.setWindowTitle("Job Questionnaire")
        form = QFormLayout(self)

        # Optional warning banner when corners header was detected but no lengths parsed
        if defaults.get("warn_corners"):
            warn = QLabel("Corners detected in HOVER, but no inside/outside lengths parsed — consider estimating.")
            warn.setStyleSheet("background:#fff3cd;color:#856404;padding:6px;border:1px solid #ffeeba;border-radius:4px;")
            form.addRow(warn)

        self.region = QComboBox(); self.region.addItems(["Metro","North CO","Mountains"])
        self.siding = QComboBox(); self.siding.addItems(["Lap","Board & Batten","Shake"])
        self.finish = QComboBox(); self.finish.addItems(["ColorPlus","Primed"])
        self.body = QLineEdit(defaults.get("body_color","Iron Gray"))
        self.trim = QComboBox(); self.trim.addItems(["Arctic White","Timber Bark","Cobblestone","Iron Gray","Primed"])
        self.complexity = QComboBox(); self.complexity.addItems(["Low","Med","High"])
        self.demo = QCheckBox(); self.demo.setChecked(True)
        self.layers = QSpinBox(); self.layers.setRange(0, 5)
        self.substrate = QComboBox(); self.substrate.addItems(["Wood","Brick","Stucco","Other"])

        # --- Siding SF: single visible input (we still feed both keys internally) ---
        self.siding_sf = QLineEdit(str(defaults.get("siding_sf", 0.0)))
        form.addRow("Siding (SF):", self.siding_sf)

        # Roofline & trim-driving metrics
        self.eave = QLineEdit(defaults.get("eave_fascia","0"))
        self.rake = QLineEdit(defaults.get("rake_fascia","0"))
        self.depth_gt24 = QCheckBox(); self.depth_gt24.setChecked(True)

        self.openings = QLineEdit(defaults.get("openings_perim","0"))
        self.outside = QLineEdit(str(defaults.get("outside","0")))
        self.inside  = QLineEdit(str(defaults.get("inside","0")))

        self.fascia_w = QComboBox(); self.fascia_w.addItems(["4","6","8","12"])
        try:
            self.fascia_w.setCurrentText("8")
        except Exception:
            pass
        self.osb_on = QCheckBox(); self.osb_area = QLineEdit("")

        form.addRow("Region:", self.region)
        form.addRow("Siding Type:", self.siding)
        form.addRow("Finish:", self.finish)
        form.addRow("Body Color (CP):", self.body)
        form.addRow("Trim Color:", self.trim)
        form.addRow("Complexity:", self.complexity)
        form.addRow("Demo required:", self.demo)
        form.addRow("Extra layers:", self.layers)
        form.addRow("Substrate:", self.substrate)

        form.addRow("Eave Fascia (ft or 000'00\"):", self.eave)
        form.addRow("Rake Fascia (ft or 000'00\"):", self.rake)
        form.addRow("Soffit Depth > 24\"?", self.depth_gt24)
        form.addRow("Openings Perimeter (ft or 000'00\"):", self.openings)
        form.addRow("Outside Corners (ft):", self.outside)
        form.addRow("Inside Corners (ft):", self.inside)
        form.addRow("Fascia Width (in):", self.fascia_w)
        form.addRow("Include OSB:", self.osb_on)
        form.addRow("OSB Area Override (sf, optional):", self.osb_area)

        btns = QHBoxLayout()
        ok = QPushButton("Compute"); ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        btns.addWidget(ok); btns.addWidget(cancel)
        form.addRow(btns)

        if defaults.get("region_guess"):
            self.region.setCurrentText(defaults["region_guess"])

    def values(self):
        siding_single = float(self.siding_sf.text() or 0.0)  # one visible input

        return dict(
            region=self.region.currentText(),
            siding=self.siding.currentText(),
            finish=self.finish.currentText(),
            body_color=self.body.text().strip() or "Iron Gray",
            trim_color=self.trim.currentText(),
            complexity=self.complexity.currentText(),
            demo=self.demo.isChecked(),
            layers=self.layers.value(),
            substrate=self.substrate.currentText(),

            # feed both keys with the same single value
            facades_sf=siding_single,
            trim_siding_sf=siding_single,

            eave_fascia=ft_in_to_ft(self.eave.text()),
            rake_fascia=ft_in_to_ft(self.rake.text()),
            depth_gt24=self.depth_gt24.isChecked(),
            openings_perim=ft_in_to_ft(self.openings.text()),
            outside=ft_in_to_ft(self.outside.text()),
            inside=ft_in_to_ft(self.inside.text()),
            fascia_w=int(self.fascia_w.currentText()),
            osb_on=self.osb_on.isChecked(),
            osb_area=float(self.osb_area.text()) if self.osb_area.text().strip() else None
        )


# -------------------------- Living Lore (About) --------------------------
LIVE_LORE_PATH = os.path.join(APP_DIR, "Lore", "LiveLore.md")
os.makedirs(os.path.dirname(LIVE_LORE_PATH), exist_ok=True)

def _live_lore_append(header: str, **fields):
    """
    Append a markdown entry to LiveLore.md every time something notable happens.
    """
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [f"### {header} — {ts}"]
        for k, v in (fields or {}).items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")  # blank
        with open(LIVE_LORE_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass

class AboutDialog(QDialog):
    def __init__(self, parent, *, build_id: str, pr_cycle: str, mule_model: str, rules: list[str], adapter_template_id: str):
        super().__init__(parent)
        self.setWindowTitle("About — BidMule")
        self.resize(680, 520)

        lay = QVBoxLayout(self)

        # Header grid
        hdr = QFormLayout()
        hdr.addRow("Build ID:", QLabel(build_id))
        hdr.addRow("PR Cycle:", QLabel(pr_cycle))
        hdr.addRow("BitMule:", QLabel(mule_model))
        hdr.addRow("Rules:", QLabel(", ".join(rules)))
        hdr.addRow("Adapter Template:", QLabel(adapter_template_id or "unknown"))
        hw = QWidget(); hw.setLayout(hdr)
        lay.addWidget(hw)

        # Lore view
        cap = QLabel("Live Lore"); cap.setStyleSheet("font-weight:600; margin-top:10px;")
        lay.addWidget(cap)

        from PySide6.QtWidgets import QTextEdit
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.view.setStyleSheet("QTextEdit { background:#fbfbfd; }")
        try:
            with open(LIVE_LORE_PATH, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            content = ""
        if not content.strip():
            content = "No entries yet. The Lore will accumulate here automatically."
        self.view.setText(content)
        lay.addWidget(self.view, 1)

        # Close
        row = QHBoxLayout()
        ok = QPushButton("Close"); ok.clicked.connect(self.accept)
        row.addStretch(1); row.addWidget(ok)
        rw = QWidget(); rw.setLayout(row)
        lay.addWidget(rw)

    @staticmethod
    def open(parent, *, build_id: str, pr_cycle: str, mule_model: str, rules: list[str], adapter_template_id: str):
        dlg = AboutDialog(parent,
                          build_id=build_id,
                          pr_cycle=pr_cycle,
                          mule_model=mule_model,
                          rules=rules,
                          adapter_template_id=adapter_template_id)
        dlg.exec()

######
######
# -------------------------- Main Window --------------------------
class Main(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            init_db()
        except Exception:
            pass

        # Classic size + centering handled inside this call
        self._normalize_window_sizing()

        # App font + title
        _app_font = QFont()
        _app_font.setPointSize(13)
        self.setFont(_app_font)
        self.setWindowTitle("BidMule8")

        # Left pane list
        self.list = QListWidget()
        self.list.itemClicked.connect(self.open_job, Qt.ConnectionType.UniqueConnection)

        # Build right panel (creates self.rightw, self.materials, self.costs, self.results_tree)
        self._setup_right_panel()
        # Compose main splitter (left list | right content)
        from PySide6.QtWidgets import QSplitter as _QSplitter
        left_col = QVBoxLayout()
        left_col.setContentsMargins(6, 6, 6, 6)
        left_col.setSpacing(6)
        left_col.addWidget(QLabel("Jobs"))
        left_col.addWidget(self.list, 1)
        leftw = QWidget(); leftw.setLayout(left_col)

        self.main_split = _QSplitter(Qt.Horizontal)
        self.main_split.setChildrenCollapsible(False)
        self.main_split.setHandleWidth(10)
        self.main_split.addWidget(leftw)
        self.main_split.addWidget(self.rightw)

        # Widen left list slightly so long names/addresses are readable (≈ 30% / 70%)
        self.main_split.setStretchFactor(0, 1)
        self.main_split.setStretchFactor(1, 3)
        self.main_split.setSizes([360, 900])  # was [320, 880]; gives longer titles ~80% of left pane

        # Central widget
        self.cw = QWidget()
        root_layout = QVBoxLayout(self.cw)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.main_split, 1)
        self.setCentralWidget(self.cw)




        # Sane default splitter sizes: keep jobs NOT too wide initially
        try:
            # Left (jobs) ≈ 300px, right gets the rest; adjust to your window
            self.main_split.setSizes([300, max(700, self.width() - 300)])
            # Keep left pane from growing too large by default, but still allow manual stretch
            self.list.setMinimumWidth(260)
            self.list.setMaximumWidth(460)
        except Exception:
            pass


        # one-time deferred wiring after widgets exist
        QTimer.singleShot(0, self._wire_signals)

        # Build the 2:1 width row (Costs|Materials), then style headers, then set vertical proportions
        QTimer.singleShot(0, self._reflow_top_tables)
        QTimer.singleShot(0, self._restyle_tables_once)
        QTimer.singleShot(0, self._apply_layout_proportions)

        # ---- Living Lore: App Started entry (helper now definitely exists) ----
        try:
            build_id = datetime.datetime.now().strftime("BM6-%Y%m%d-%H%M%S")
            _live_lore_append("App Started", mule="BitMule6", pr="PR-0074", session=str(sid), build=build_id)
        except Exception:
            pass

        # ---- Autowire any existing About control (menu action or button) ----
        try:
            self._autowire_existing_about()
        except Exception:
            pass

    def resizeEvent(self, ev):
        try:
            super().resizeEvent(ev)
        except Exception:
            pass
        # Recompute top band safely; left pane: light touch only
        try:
            self._sync_top_band_sizes()
        except Exception:
            pass
        try:
            # Only do non-intrusive adjustments (no setFixedHeight)
            self._sync_left_jobs_panel()
        except Exception:
            pass



    def closeEvent(self, ev):
        try:
            try:
                log_event("app", "app_closing", [])
            except Exception:
                pass
            end_session()
            flush(1200)
        finally:
            super().closeEvent(ev)


    # ---------- sizing, signal helpers, styles ----------
    def _normalize_window_sizing(self):
        """Classic BitMule layout: 1200x800 window, centered, resizable; crisp tables."""
        try:
            from PySide6.QtGui import QGuiApplication

            # Classic default, center on available screen
            target_w, target_h = 1200, 800
            min_w, min_h = 900, 600

            self.setMinimumSize(min_w, min_h)

            screen = QGuiApplication.primaryScreen()
            avail = screen.availableGeometry() if screen else None
            if avail:
                self.resize(target_w, target_h)
                x = avail.x() + (avail.width() - target_w) // 2
                y = avail.y() + (avail.height() - target_h) // 2
                self.move(x, y)
            else:
                self.resize(target_w, target_h)

            # Central widget sizing
            cw = self.centralWidget()
            if cw:
                cw.setMinimumSize(0, 0)
                cw.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

            # Splitters
            for sp in self.findChildren(QSplitter):
                sp.setChildrenCollapsible(False)
                sp.setOpaqueResize(True)
                sp.setStretchFactor(0, 1)
                sp.setStretchFactor(1, 2)
                
            # Tables: readable row/section sizes (no global CSS here)
            for tbl in self.findChildren(QTableWidget):
                vh = tbl.verticalHeader()
                vh.setDefaultSectionSize(32)
                vh.setMinimumSectionSize(30)
                # Do not apply global QTableView/QHeaderView styles here;
                # styling is centralized in _restyle_tables_once().
                tbl.setMinimumSize(0, 0)
                tbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

            # Headers stretch last column by default
            for hv in self.findChildren(QHeaderView):
                hv.setStretchLastSection(True)

        except Exception:
            pass


    # ---------- Actionbar under ③/④ (Reset left, Total right) ----------
    def _ensure_actionbar_below_tables(self):
        """
        Inserts a two-cell row directly under the Materials/Costs row:
          [ Reset to Default ]  (under Materials, 2x width)
          [ Materials Total: $0.00 ] (under Costs, 1x width)
        Safe to call multiple times.
        """
        if getattr(self, "_materials_actionbar_built", False):
            return

        # Build the two 'pills'
        self.reset_hover_rb = getattr(self, "reset_hover_rb", None) or QPushButton("Reset to Default")
        self.reset_hover_rb.setCheckable(False)
        self.reset_hover_rb.setEnabled(False)

        self._materials_total_pill = getattr(self, "_materials_total_pill", None) or QLabel("Materials Total: $0.00")
        self._materials_total_pill.setAlignment(Qt.AlignCenter)

        # Beveled/pressed theme (subtle chamfer, raised vs. disabled)
        pill_css = """
            QPushButton, QLabel {
                border: 1px solid #3c3c3c;
                border-top-color: #6b6b6b;      /* top highlight */
                border-left-color: #6b6b6b;     /* left highlight */
                border-right-color: #262626;    /* bottom/right shadow */
                border-bottom-color: #262626;
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                           stop:0 #2b2b2b, stop:1 #232323);
                padding: 6px 12px;
                font-weight: 600;
                border-radius: 4px;             /* low chamfer, not bubbly */
                color: #e5e5e5;
            }
            QPushButton:disabled {
                color: #9a9a9a;
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                           stop:0 #242424, stop:1 #1e1e1e);
                border-top-color: #3d3d3d;
                border-left-color: #3d3d3d;
            }
            QPushButton:pressed {
                /* invert highlight/shadow for 'depressed' feel */
                border-top-color: #262626;
                border-left-color: #262626;
                border-right-color: #6b6b6b;
                border-bottom-color: #6b6b6b;
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                           stop:0 #202020, stop:1 #1a1a1a);
            }
        """
        self.reset_hover_rb.setStyleSheet(pill_css)
        self._materials_total_pill.setStyleSheet(pill_css)

        # Wire reset behavior (already exists); ensure connected once
        try:
            self.reset_hover_rb.clicked.disconnect(self._reset_materials_to_hover)
        except Exception:
            pass
        self.reset_hover_rb.clicked.connect(self._reset_materials_to_hover, Qt.ConnectionType.UniqueConnection)

        # Place under the two tables with 2:1 width
        row = QHBoxLayout()
        row.setContentsMargins(0, 6, 0, 0)
        row.setSpacing(12)

        left_wrap = QWidget(); lw = QHBoxLayout(left_wrap); lw.setContentsMargins(0,0,0,0); lw.addWidget(self.reset_hover_rb)
        right_wrap = QWidget(); rw = QHBoxLayout(right_wrap); rw.setContentsMargins(0,0,0,0); rw.addWidget(self._materials_total_pill)

        row.addWidget(left_wrap, 2)
        row.addWidget(right_wrap, 1)

        # Insert right below the Materials/Costs container
        # Your _setup_right_panel created self.rightw (a QWidget) with a QVBoxLayout
        parent_lay = self.rightw.layout()
        parent_lay.addLayout(row)

        self._materials_actionbar_built = True



    @contextmanager
    def _block_signals(self, *widgets):
        states = []
        try:
            for w in widgets:
                states.append((w, w.blockSignals(True)))
            yield
        finally:
            for w, prev in states:
                w.blockSignals(prev)

    def _safe_disconnect(self, signal, slot=None):
        try:
            if slot is None:
                signal.disconnect()
            else:
                signal.disconnect(slot)
        except (TypeError, RuntimeError):
            pass

###
    def _autowire_existing_about(self):
        """
        Connect any existing 'About' action/button to open_about_dialog(), without adding new UI.
        - Finds a QAction named like 'about' OR text containing 'About'
        - Finds a QPushButton whose text is 'About'
        Safe to call multiple times.
        """
        # Try actions
        try:
            for act in self.findChildren(type(getattr(self, "aboutAction", None))):
                try:
                    if act and hasattr(act, "text") and "about" in act.text().lower():
                        try: act.triggered.disconnect()
                        except Exception: pass
                        act.triggered.connect(self.open_about_dialog)
                        return
                except Exception:
                    continue
        except Exception:
            pass

        # Generic QAction scan
        try:
            from PySide6.QtGui import QAction
            for act in self.findChildren(QAction):
                try:
                    if act and hasattr(act, "text") and "about" in (act.text() or "").lower():
                        try: act.triggered.disconnect()
                        except Exception: pass
                        act.triggered.connect(self.open_about_dialog)
                        return
                except Exception:
                    continue
        except Exception:
            pass

        # Try a QPushButton labeled 'About'
        try:
            from PySide6.QtWidgets import QPushButton
            for btn in self.findChildren(QPushButton):
                try:
                    if btn and (btn.text() or "").strip().lower() == "about":
                        try: btn.clicked.disconnect()
                        except Exception: pass
                        btn.clicked.connect(self.open_about_dialog)
                        return
                except Exception:
                    continue
        except Exception:
            pass


#####
    # ---------- Layout: Costs|Materials row (2:1 width, no duplicates) ----------
    def _reflow_top_tables(self):
        """
        Re-parent the existing Costs and Materials tables into a single horizontal row
        so Materials occupies ~2/3 width and Costs ~1/3.
        Ensures we don't leave old copies in the right-side layout.
        """
        rightw = getattr(self, "rightw", None)
        if rightw is None or rightw.layout() is None:
            return
        rlay = rightw.layout()  # QVBoxLayout

        # 1) Remove any previous row wrapper if we ran before
        if hasattr(self, "_top_row_wrapper") and self._top_row_wrapper is not None:
            old_idx = rlay.indexOf(self._top_row_wrapper)
            if old_idx >= 0:
                w = rlay.takeAt(old_idx).widget()
                if w is not None:
                    w.setParent(None)
            self._top_row_wrapper = None

        # 2) Detach the two tables from wherever they currently are in the right layout
        for w in (self.costs, self.materials):
            try:
                idx = rlay.indexOf(w)
                if idx >= 0:
                    rlay.takeAt(idx)  # removes the layout item, not the widget
                    w.setParent(None)
            except Exception:
                pass

        # 3) Build the horizontal row: Costs (1) | Materials (2)
        from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
        roww = QWidget(rightw)
        row = QHBoxLayout(roww)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        # Subtitles above each table (lightweight labels)
        costs_col = QWidget(roww);  costs_lay = QVBoxLayout(costs_col);  costs_lay.setContentsMargins(0,0,0,0); costs_lay.setSpacing(4)
        mats_col  = QWidget(roww);  mats_lay  = QVBoxLayout(mats_col);   mats_lay.setContentsMargins(0,0,0,0);   mats_lay.setSpacing(4)

        costs_lbl = QLabel("Costs");      mats_lbl = QLabel("Materials")
        costs_lbl.setStyleSheet("font-weight:600;")
        mats_lbl.setStyleSheet("font-weight:600;")

        costs_lay.addWidget(costs_lbl, 0)
        costs_lay.addWidget(self.costs, 1)

        mats_lay.addWidget(mats_lbl, 0)
        mats_lay.addWidget(self.materials, 1)

        row.addWidget(costs_col, 1)   # 1/3
        row.addWidget(mats_col, 2)    # 2/3

        self._top_row_wrapper = roww

        # 4) Insert row back into the right stack just ABOVE reset + labor block
        #    Find the reset button (anchor), otherwise place before results tree.
        anchor_idx = rlay.indexOf(self.reset_hover_rb) if hasattr(self, "reset_hover_rb") else -1
        if anchor_idx < 0:
            anchor_idx = rlay.indexOf(self.results_tree)
        if anchor_idx < 0:
            rlay.addWidget(roww, 0)
        else:
            rlay.insertWidget(max(0, anchor_idx - 1), roww, 0)

        # 5) Make sure the Δ click handlers still point at the live widget
        try:
            self.materials.cellClicked.disconnect(self._on_materials_delta_clicked)
        except Exception:
            pass
        self.materials.cellClicked.connect(self._on_materials_delta_clicked)


#####
    # ---------- Proportions: 2:1 height (top row vs Labor) ----------
    def _apply_layout_proportions(self):
        """
        After the row exists, bias vertical space: (Costs|Materials row) : Labor = 2 : 1.
        Also compact left list width and ensure initial column sizing is sensible.
        """
        try:
            rightw = getattr(self, "rightw", None)
            if rightw and rightw.layout():
                rlay = rightw.layout()

                # Stretch: drop area + banner are small; the row gets 2, labor tree gets 1
                # Find wrappers to set stretch: top row wrapper (2), results_tree (1)
                if hasattr(self, "_top_row_wrapper") and self._top_row_wrapper is not None:
                    rlay.setStretchFactor(self._top_row_wrapper, 2)
                rlay.setStretchFactor(self.results_tree, 1)

            # Width already handled by the row (1:2); ensure initial column sizing
            self.costs.resizeColumnsToContents()
            self.materials.resizeColumnsToContents()

            # Left list readability: make the list header label narrow, the list itself stretch
            if hasattr(self, "main_split"):
                self.main_split.setStretchFactor(0, 1)
                self.main_split.setStretchFactor(1, 3)
                # Keep the initial bias we chose (30/70)
                if not getattr(self, "_split_sized_once", False):
                    self.main_split.setSizes([360, 900])
                    self._split_sized_once = True
        except Exception:
            pass

    # --- Make sure both sync helpers run on window resize (lightweight) ---
    def resizeEvent(self, ev):
        try:
            super().resizeEvent(ev)
        except Exception:
            pass
        try:
            self._sync_top_band_sizes()
        except Exception:
            pass
        try:
            self._sync_left_jobs_panel()
        except Exception:
            pass



    # [229|ui|_sync_left_jobs_panel] Non-intrusive tweaks: readable items, no forced heights
    def _sync_left_jobs_panel(self):
        """
        Keep the left Jobs list readable without forcing fixed heights.
        - No horizontal scrollbars; ellide long text
        - Gentle minimum width so names don't crush
        - NO per-frame splitter yanking that could push the list off-screen
        """
        try:
            if not hasattr(self, "list") or not hasattr(self, "main_split"):
                return

            # Readability: no horizontal scrollbar; ellide long names
            self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            try:
                self.list.setTextElideMode(Qt.ElideRight)  # QListWidget inherits this
            except Exception:
                pass

            # Gentle minimum for the left pane
            LEFT_MIN = 320
            sizes = self.main_split.sizes()
            if len(sizes) == 2 and sizes[0] < LEFT_MIN:
                self.main_split.setSizes([LEFT_MIN, max(200, sizes[1] - (LEFT_MIN - sizes[0]))])

        except Exception:
            pass

        
    def _sync_top_band_sizes(self):
        try:
            req = ("costs", "drop_w", "btns_cluster", "_btns_all", "_btn_spacing")
            if not all(hasattr(self, a) for a in req):
                return

            costs_w = int(max(0, self.costs.width()))
            if costs_w <= 0:
                return

            MIN_W, MAX_W = 220, 420
            target_w = max(MIN_W, min(costs_w, MAX_W))
            S = int(self._btn_spacing)

            per_btn_w = max(90, (target_w - S) // 2)
            per_btn_h = 28  # thin to lift Materials

            for b in self._btns_all:
                b.setFixedSize(per_btn_w, per_btn_h)

            self.btns_cluster.setFixedWidth(target_w)
            self.drop_w.setFixedWidth(target_w)

            # Slightly smaller than before to raise Materials further
            drop_h = max(90, (per_btn_h * 2) + S + 4)
            self.drop_w.setFixedHeight(drop_h)

        except Exception:
            pass



#####
    # ---------- Styling: match Labor header look + compact header height ----------

    def _restyle_tables_once(self):
        """
        Cosmetic normalization for tables and headers:
        - Black background ONLY for Materials/Costs tables (no global palette)
        - Hide vertical headers to remove any 'dot/gutter'
        - Uniform narrow Δ columns
        - Labor tree keeps native look (no branches)
        """
        try:
            # Headers: native palette, compact height
            headers = []
            if hasattr(self, "costs"):
                headers.append(self.costs.horizontalHeader())
            if hasattr(self, "materials"):
                headers.append(self.materials.horizontalHeader())
            if hasattr(self, "results_tree"):
                headers.append(self.results_tree.header())
            for h in headers:
                h.setStyleSheet("")  # native
                h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                try:
                    h.setFixedHeight(24)
                except Exception:
                    pass

            # --- Table looks ---
            # Costs table: black background and readable text
            if hasattr(self, "costs") and self.costs:
                self.costs.verticalHeader().setVisible(False)
                self.costs.setAlternatingRowColors(False)
                self.costs.setShowGrid(True)
                self.costs.setStyleSheet(
                    "QTableView {"
                    "  background: #000000;"
                    "  color: #f0f0f0;"
                    "  gridline-color: #2a2a2a;"
                    "  selection-background-color: #123456;"
                    "  selection-color: #ffffff;"
                    "}"
                    "QHeaderView::section {"
                    "  background: #111111;"
                    "  color: #e0e0e0;"
                    "  padding: 6px 8px;"
                    "  border: 0;"
                    "}"
                    "QTableCornerButton::section { background: #111111; border: 0; }"
                    "QTableView::indicator { width:0; height:0; }"
                )
                ch = self.costs.horizontalHeader()
                ch.setMinimumSectionSize(24)
                # [0]=Metric, [1]=Value (wider), [2]=Δ (uniform narrow)
                ch.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                ch.setSectionResizeMode(1, QHeaderView.Stretch)
                ch.setSectionResizeMode(2, QHeaderView.Fixed)
                ch.resizeSection(2, 28)  # Uniform Δ width

            # Materials table: black background and readable text
            if hasattr(self, "materials") and self.materials:
                self.materials.verticalHeader().setVisible(False)
                self.materials.setAlternatingRowColors(False)
                self.materials.setShowGrid(True)
                self.materials.setStyleSheet(
                    "QTableView {"
                    "  background: #000000;"
                    "  color: #f0f0f0;"
                    "  gridline-color: #2a2a2a;"
                    "  selection-background-color: #123456;"
                    "  selection-color: #ffffff;"
                    "}"
                    "QHeaderView::section {"
                    "  background: #111111;"
                    "  color: #e0e0e0;"
                    "  padding: 6px 8px;"
                    "  border: 0;"
                    "}"
                    "QTableCornerButton::section { background: #111111; border: 0; }"
                    "QTableView::indicator { width:0; height:0; }"
                )
                mh = self.materials.horizontalHeader()
                mh.setMinimumSectionSize(24)
                # [0]=Material, [1]=Qty, [2]=UOM, [3]=Unit, [4]=Ext, [5]=Δ (narrow), [6]=🗑 (narrow)
                mh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                mh.setSectionResizeMode(1, QHeaderView.Fixed);   mh.resizeSection(1, 70)
                mh.setSectionResizeMode(2, QHeaderView.Fixed);   mh.resizeSection(2, 70)
                mh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
                mh.setSectionResizeMode(4, QHeaderView.Stretch)
                mh.setSectionResizeMode(5, QHeaderView.Fixed);   mh.resizeSection(5, 28)  # Δ uniform width
                mh.setSectionResizeMode(6, QHeaderView.Fixed);   mh.resizeSection(6, 28)  # 🗑 width

            # Labor tree: keep native, no branch art
            if hasattr(self, "results_tree") and self.results_tree:
                self.results_tree.setRootIsDecorated(False)
                self.results_tree.setStyleSheet("QTreeView::branch { border-image: none; image: none; }")

        except Exception:
                pass
            
    ###
    def _wire_signals(self):
        """Connect UI signals exactly once; guard by widget existence."""
        # Jobs list → open_job
        if hasattr(self, "list") and self.list:
            try:
                self.list.itemClicked.disconnect()
            except Exception:
                pass
            self.list.itemClicked.connect(self.open_job, Qt.ConnectionType.UniqueConnection)

        # Costs table → cell edits
        if hasattr(self, "costs") and self.costs:
            try:
                self.costs.cellChanged.disconnect(self.on_costs_cell_changed)
            except Exception:
                pass
            self.costs.cellChanged.connect(self.on_costs_cell_changed, Qt.ConnectionType.UniqueConnection)

        # Materials table → qty edits, Δ clicks, trash clicks, hover event filter
        if hasattr(self, "materials") and self.materials:
            # Ensure hover-only trash visibility can work
            try:
                self.materials.setMouseTracking(True)
            except Exception:
                pass
            if not getattr(self, "_materials_event_filter_installed", False):
                try:
                    self.materials.installEventFilter(self)
                    self._materials_event_filter_installed = True
                except Exception:
                    pass

            # itemChanged → enforce integer qty and recompute
            try:
                self.materials.itemChanged.disconnect(self._on_materials_item_changed)
            except Exception:
                pass
            self.materials.itemChanged.connect(self._on_materials_item_changed, Qt.ConnectionType.UniqueConnection)

            # cellClicked → Δ column behavior
            try:
                self.materials.cellClicked.disconnect(self._on_materials_delta_clicked)
            except Exception:
                pass
            self.materials.cellClicked.connect(self._on_materials_delta_clicked, Qt.ConnectionType.UniqueConnection)

            # cellClicked → trash (sets qty to zero but keeps the row)
            try:
                self.materials.cellClicked.disconnect(self._on_materials_trash_clicked)
            except Exception:
                pass
            self.materials.cellClicked.connect(self._on_materials_trash_clicked, Qt.ConnectionType.UniqueConnection)

    # [110|about|open_about_dialog] About dialog opener — builds metadata and opens About
    def open_about_dialog(self):
        build_id = datetime.datetime.now().strftime("BM6-%Y%m%d-%H%M%S")
        pr_cycle = "PR-0074"
        mule_model = "BitMule6 — The Ascendant"
        rules = ["BM-W-001", "BM-F-012"]
        adapter_template_id = getattr(self, "last_template_id", "unknown")

        AboutDialog.open(
            self,
            build_id=build_id,
            pr_cycle=pr_cycle,
            mule_model=mule_model,
            rules=rules,
            adapter_template_id=adapter_template_id,
        )

#
    # [2] Banner controller
    def _show_warning_banner(self, msg: str | None):
        """
        Controls the yellow warning banner at the top of the right pane.
        Pass None or empty to hide; any non-empty string to show.
        """
        if msg:
            self._warn.setText(str(msg))
            self._warn.setVisible(True)
        else:
            self._warn.setVisible(False)

    # [3] Recompute guard
    def _with_recompute_guard(self, fn, *args, **kwargs):
        """
        Prevent re-entrant recompute loops when programmatic cell updates fire signals.
        """
        if getattr(self, "_recomputing", False):
            return
        self._recomputing = True
        try:
            return fn(*args, **kwargs)
        finally:
            self._recomputing = False


    def _style_pills_once(self):
        pill_btn_css = (
            "QPushButton {"
            "  border: 1px solid #d0d7de;"
            "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f6f8fa, stop:1 #eef2f6);"
            "  border-radius: 18px;"
            "  padding: 6px 14px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:disabled { color:#8c959f; background:#f6f8fa; }"
        )
        pill_lbl_css = (
            "QLabel {"
            "  border: 1px solid #d0d7de;"
            "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffffff, stop:1 #f6f8fa);"
            "  border-radius: 18px;"
            "  padding: 6px 14px;"
            "  font-weight: 700;"
            "  qproperty-alignment: 'AlignCenter';"
            "}"
        )
        try:
            self.reset_hover_rb.setStyleSheet(pill_btn_css)
            self.reset_hover_rb.setFixedHeight(36)
            self._mat_total_pill.setStyleSheet(pill_lbl_css)
            self._mat_total_pill.setFixedHeight(36)
        except Exception:
            pass

        
    # [200|ui|_setup_right_panel] Splitter-owned Materials|Costs band; stable pills; proper About wiring
    def _setup_right_panel(self):
        # ── Top toolbar (Open • Catalog • Parsed Totals • About) ─────────────────────
        top_btns = QHBoxLayout()
        top_btns.setContentsMargins(0, 0, 0, 0)
        top_btns.setSpacing(6)

        # [201|ui|_setup_right_panel_call_drop_banner] Invoke the modular drop+banner builder
        drop_w, warn_lbl = self._setup_drop_and_banner()


        open_btn = QPushButton("Open PDF")
        open_btn.clicked.connect(self.open_pdf_dialog)

        catalog_btn = QPushButton("Catalog")
        catalog_btn.clicked.connect(self.open_catalog_dialog)

        totals_btn = QPushButton("Parsed Totals")
        totals_btn.clicked.connect(self.open_totals_dialog)

        about_btn = QPushButton("About")
        about_btn.clicked.connect(self.open_about_dialog)

        for b in (open_btn, catalog_btn, totals_btn, about_btn):
            b.setFixedHeight(30)
            top_btns.addWidget(b)

        top_btns_w = QWidget()
        top_btns_w.setLayout(top_btns)


        # ── Materials table (6 cols) ────────────────────────────────────────────────
        self.materials = QTableWidget(0, 6)
        self.materials.setHorizontalHeaderLabels(["Material", "Qty", "UOM", "Unit Cost", "Ext. Cost", "Δ"])
        mh = self.materials.horizontalHeader()
        self.materials.setMouseTracking(True)
        self.materials.installEventFilter(self)
        mh.setMinimumSectionSize(28)
        mh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        mh.setSectionResizeMode(1, QHeaderView.Fixed);   mh.resizeSection(1, 70)
        mh.setSectionResizeMode(2, QHeaderView.Fixed);   mh.resizeSection(2, 70)
        mh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        mh.setSectionResizeMode(4, QHeaderView.Stretch)
        mh.setSectionResizeMode(5, QHeaderView.Fixed);   mh.resizeSection(5, 34)
        self.materials.verticalHeader().setDefaultSectionSize(32)
        self.materials.verticalHeader().setMinimumSectionSize(30)

        # ── Costs table (3 cols) ────────────────────────────────────────────────────
        self.costs = QTableWidget(0, 3)
        self.costs.setHorizontalHeaderLabels(["Cost Metric", "Value", "Δ"])
        ch = self.costs.horizontalHeader()
        ch.setMinimumSectionSize(28)
        ch.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        ch.setSectionResizeMode(1, QHeaderView.Stretch)
        ch.setSectionResizeMode(2, QHeaderView.Fixed);   ch.resizeSection(2, 40)
        self.costs.verticalHeader().setDefaultSectionSize(32)
        self.costs.verticalHeader().setMinimumSectionSize(30)

        # [206|ui|tables_cosmetics] Hide row gutters; remove focus outline
        self.materials.verticalHeader().setVisible(False)
        self.costs.verticalHeader().setVisible(False)

        self.materials.setShowGrid(True)
        self.costs.setShowGrid(True)

        # Remove dotted focus outlines some macOS themes show
        self.materials.setStyleSheet(self.materials.styleSheet() + " QTableView { outline: 0; }")
        self.costs.setStyleSheet(self.costs.styleSheet() + " QTableView { outline: 0; }")


        # ── 2:1 horizontal splitter: Materials (2) | Costs (1) ─────────────────────
        mat_col = QVBoxLayout(); mat_col.setContentsMargins(0, 0, 0, 0); mat_col.setSpacing(6)
        mat_col.addWidget(QLabel("Materials"), 0)
        mat_col.addWidget(self.materials, 1)
        mat_w = QWidget(); mat_w.setLayout(mat_col)

        cost_col = QVBoxLayout(); cost_col.setContentsMargins(0, 0, 0, 0); cost_col.setSpacing(6)
        cost_col.addWidget(QLabel("Costs"), 0)
        cost_col.addWidget(self.costs, 1)
        cost_w = QWidget(); cost_w.setLayout(cost_col)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(10)
        split.addWidget(mat_w)
        split.addWidget(cost_w)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 1)
        split.setSizes([800, 400])
        self.top_splitter = split  # single owner of Materials|Costs

        # ── Pills row: Reset (under Materials) | Materials Total (under Costs) ─────
        pill_btn_css = (
            "QPushButton {"
            "  border: 1px solid #b9c0c7;"
            "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f4f6f8, stop:0.5 #eef1f4, stop:1 #e3e7ec);"
            "  border-radius: 6px;"
            "  padding: 6px 14px;"
            "  font-weight: 600;"
            "  color: #111;"
            "}"
            "QPushButton:pressed {"
            "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #e3e7ec, stop:0.5 #d9dfe6, stop:1 #ced6df);"
            "  padding-top: 7px; padding-bottom: 5px;"
            "}"
            "QPushButton:disabled { color:#8c959f; background:#f4f6f8; }"
        )
        pill_lbl_css = (
            "QLabel {"
            "  border: 1px solid #b9c0c7;"
            "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffffff, stop:1 #f6f8fa);"
            "  border-radius: 6px;"
            "  padding: 6px 14px;"
            "  font-weight: 700;"
            "  qproperty-alignment: 'AlignCenter';"
            "}"
        )

        if not hasattr(self, "reset_hover_rb"):
            self.reset_hover_rb = QPushButton("Reset to Default")
            self.reset_hover_rb.clicked.connect(self._reset_materials_to_hover)
        self.reset_hover_rb.setStyleSheet(pill_btn_css)
        self.reset_hover_rb.setFixedHeight(36)

        if not hasattr(self, "_mat_total_pill"):
            self._mat_total_pill = QLabel("Materials Total: $0.00")
        self._mat_total_pill.setStyleSheet(pill_lbl_css)
        self._mat_total_pill.setFixedHeight(36)

        pills_row = QHBoxLayout()
        pills_row.setContentsMargins(0, 0, 0, 0)
        pills_row.setSpacing(8)
        pills_row.addWidget(self.reset_hover_rb, 2)   # under Materials
        pills_row.addWidget(self._mat_total_pill, 1)  # under Costs
        pills_w = QWidget()
        pills_w.setLayout(pills_row)

        # ── Labor payout tree ───────────────────────────────────────────────────────
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Component / Rate", "Amount"])
        rvh = self.results_tree.header()
        rvh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        rvh.setSectionResizeMode(1, QHeaderView.Stretch)
        self.results_tree.setRootIsDecorated(True)
        self.results_tree.setStyleSheet("QTreeView::branch { border-image: none; }")

        # ── Top band (rev 2): right-aligned column with square drop above 2×2 button cluster ─
        # Assumes open_btn, catalog_btn, totals_btn, about_btn, and (drop_w, warn_lbl) exist.

        # Tight, uniform spacing for the cluster
        S = 6
        BTN_W, BTN_H = 110, 30              # ~half the old width; adjust if needed
        CLUSTER_W = (BTN_W * 2) + S         # total width of the 2×2 cluster

        # Enforce identical button sizes and compact feel
        for _b in (totals_btn, about_btn, open_btn, catalog_btn):
            _b.setFixedSize(BTN_W, BTN_H)
        # ── Top band (rev 3): top-right column with responsive drop above 2×2 button cluster ─
        # Assumes open_btn, catalog_btn, totals_btn, about_btn, and (drop_w, warn_lbl) exist.

        # Tight, uniform spacing for the cluster
        S = 6

        # Build a 2×2 button grid with identical horizontal/vertical spacing
        btn_grid = QGridLayout()
        btn_grid.setContentsMargins(0, 0, 0, 0)
        btn_grid.setHorizontalSpacing(S)
        btn_grid.setVerticalSpacing(S)
        btn_grid.addWidget(totals_btn, 0, 0)
        btn_grid.addWidget(about_btn,  0, 1)
        btn_grid.addWidget(open_btn,   1, 0)
        btn_grid.addWidget(catalog_btn,1, 1)

        btns_cluster = QWidget()
        btns_cluster.setLayout(btn_grid)

        # Keep references for responsive sizing
        self.drop_w = drop_w
        self.btns_cluster = btns_cluster
        self._btns_all = (totals_btn, about_btn, open_btn, catalog_btn)
        self._btn_spacing = S

        # Top-aligned right column: [ drop (responsive) ] over [ buttons (responsive) ]
        right_col_layout = QVBoxLayout()
        right_col_layout.setContentsMargins(0, 0, 0, 0)
        right_col_layout.setSpacing(S)
        right_col_layout.addWidget(self.drop_w, 0, Qt.AlignRight | Qt.AlignTop)
        right_col_layout.addWidget(self.btns_cluster, 0, Qt.AlignRight | Qt.AlignTop)
        right_col_layout.addStretch(1)  # keep column anchored to the top

        right_col = QWidget()
        right_col.setLayout(right_col_layout)

        # Full-width band with everything pushed to the right
        top_band_row = QHBoxLayout()
        top_band_row.setContentsMargins(0, 0, 0, 0)
        top_band_row.setSpacing(0)
        top_band_row.addStretch(1)          # consume left space
        top_band_row.addWidget(right_col, 0)

        top_band = QWidget()
        top_band.setLayout(top_band_row)

        # ── Compose right column: top_band → banner → tables → pills → labor ──────
        right = QVBoxLayout()
        right.setContentsMargins(6, 6, 6, 6)
        right.setSpacing(10)
        right.addWidget(top_band, 0)                 # compact top band
        right.addWidget(warn_lbl, 0)
        right.addWidget(self.top_splitter, 3)        # middle band
        right.addWidget(pills_w, 0)
        right.addWidget(QLabel("Labor Payout"), 0)
        right.addWidget(self.results_tree, 2)

        self.rightw = QWidget()
        self.rightw.setLayout(right)

        # First sync after widgets exist
        QTimer.singleShot(0, self._sync_top_band_sizes)
        QTimer.singleShot(0, self._sync_top_band_sizes)
        QTimer.singleShot(0, self._sync_left_jobs_panel)




    # [205|ui|_setup_drop_and_banner] Drop zone + warning banner — compact, non-greedy, macOS-safe
    def _setup_drop_and_banner(self):
        """
        Creates the HOVER PDF drop target and a dismissible warning banner.
        The drop zone is fixed-height so it never pushes tables out of view.
        Returns the (drop_widget, warn_label) for placement in the right pane.
        """
        # Drop target
        self.drop = DropArea(self.handle_pdf_drop)
        self.drop.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.drop.setFixedHeight(220)  # tidy, always-visible, non-greedy

        # Warning banner (hidden by default)
        self._warn = QLabel("")
        self._warn.setVisible(False)
        self._warn.setStyleSheet(
            "background:#fff3cd;color:#856404;padding:6px;"
            "border:1px solid #ffeeba;border-radius:4px;"
        )

        return self.drop, self._warn
    

    # [210|ui|_reflow_top_tables] Strategy A: prevent double-parenting by design
    def _reflow_top_tables(self):
        """
        Strategy A — splitter is the single, canonical owner of the Materials|Costs band.
        This function intentionally does nothing to avoid re-parenting the same widgets.
        """
        return

    # [220|ui|_apply_layout_proportions] Enforce 2:1 vertical bias using layout indexes
    def _apply_layout_proportions(self):
        """
        Sets the right-pane vertical bias to (Materials|Costs band) : (Labor) = 2 : 1.
        Uses QVBoxLayout.setStretch(index, value) — the correct API for layouts.
        Also stabilizes the left/right main splitter bias.
        """
        try:
            rlay = self.rightw.layout() if hasattr(self, "rightw") else None
            if rlay:
                idx_split = rlay.indexOf(getattr(self, "top_splitter", None))
                idx_labor = rlay.indexOf(getattr(self, "results_tree", None))
                if idx_split >= 0:
                    rlay.setStretch(idx_split, 2)  # middle band (tables)
                if idx_labor >= 0:
                    rlay.setStretch(idx_labor, 1)  # lower band (labor)

            # Left (jobs list) : Right (content) width bias ~ 1:3, with initial sizes
            if hasattr(self, "main_split"):
                self.main_split.setStretchFactor(0, 1)
                self.main_split.setStretchFactor(1, 3)
                if not getattr(self, "_main_split_sized_once", False):
                    self.main_split.setSizes([360, 900])
                    self._main_split_sized_once = True

            # Initial column sizing (light touch; users can adjust after)
            if hasattr(self, "costs"):
                self.costs.resizeColumnsToContents()
            if hasattr(self, "materials"):
                self.materials.resizeColumnsToContents()
        except Exception:
            # Non-fatal: proportions fallback to default if anything goes awry
            pass


    # ---------- list + dialogs ----------
    # [340|jobs|load_jobs_into_list] Populate left-side Jobs list deterministically
    @lore_guard("job list populate failure", severity="low")
    def load_jobs_into_list(self):
        """
        Rebuilds the left Jobs list from the DB. Each item holds its job id in UserRole.
        Deterministic ordering: newest first (id DESC).
        """
        self.list.clear()

        con = sqlite3.connect(DB_PATH)
        try:
            cur = con.cursor()
            for row in cur.execute("SELECT id, title FROM jobs ORDER BY id DESC"):
                it = QListWidgetItem(row[1])
                it.setData(Qt.UserRole, row[0])
                self.list.addItem(it)
        finally:
            con.close()

        # Ensure the signal is connected exactly once
        try:
            self.list.itemClicked.disconnect()
        except Exception:
            pass
        self.list.itemClicked.connect(self.open_job, Qt.ConnectionType.UniqueConnection)

    @lore_guard("job open failure", severity="medium")
    def open_job(self, item: QListWidgetItem):
        """Load a saved job and refresh Materials/Costs/Labor panes."""
        job_id = item.data(Qt.UserRole)
        if job_id is None:
            return

        con = sqlite3.connect(DB_PATH)
        try:
            cur = con.cursor()
            cur.execute("SELECT data_json FROM jobs WHERE id=?", (job_id,))
            rec = cur.fetchone()
        finally:
            con.close()
        if not rec:
            return

        import types, json as _json
        payload = _json.loads(rec[0])

        inputs_d  = payload.get("inputs", {})
        outputs_d = payload.get("outputs", {})
        costs_d   = payload.get("costs", {})

        # Reset baselines to the job's saved line items (so Δ compares to this job)
        try:
            line_items = costs_d.get("line_items", [])
            if line_items:
                self._materials_baseline = {li.get("name"): int(round(float(li.get("qty", 0)))) for li in line_items}
                self.baseline_unit_costs = {li.get("name"): float(li.get("unit_cost", 0.0)) for li in line_items}
                self._materials_unit_cost = dict(self.baseline_unit_costs)
        except Exception:
            pass

        # Keep structured copies for downstream refreshes
        self.last_inputs  = types.SimpleNamespace(**inputs_d) if inputs_d else None
        self.last_outputs = types.SimpleNamespace(**outputs_d) if outputs_d else None

        # Reset baselines to the job's saved line items (so Δ compares to this job)
        try:
            line_items = costs_d.get("line_items", [])
            if line_items:
                self._materials_baseline = {li.get("name"): int(round(float(li.get("qty", 0)))) for li in line_items}
                self.baseline_unit_costs = {li.get("name"): float(li.get("unit_cost", 0.0)) for li in line_items}
                self._materials_unit_cost = dict(self.baseline_unit_costs)
        except Exception:
            pass

        # Establish costs baseline so Δ markers compare to the loaded job
        if costs_d:
            self._costs_baseline = {
                "Material Cost":     float(costs_d.get("material_cost", 0.0)),
                "Labor Cost":        float(costs_d.get("labor_cost", 0.0)),
                "COGS":              float(costs_d.get("cogs", 0.0)),
                "Overhead Rate":     float(costs_d.get("overhead_rate", 0.0)),
                "Target GM":         float(costs_d.get("target_gm", 0.0)),
                "Overhead $":        float(costs_d.get("overhead_dollars", 0.0)),
                "Revenue Target":    float(costs_d.get("revenue_target", 0.0)),
                "Projected Profit":  float(costs_d.get("projected_profit", 0.0)),
                "GM Band":           costs_d.get("gm_band", ""),
                "Commission Total":  float(costs_d.get("commission_total", 0.0)),
            }

        # Refresh UI
        if costs_d:
            self.populate_costs_table(costs_d)
            line_items = costs_d.get("line_items", [])
            self.populate_materials_table(line_items)
        else:
            self.populate_costs_table({
                "material_cost": 0, "labor_cost": 0, "cogs": 0,
                "overhead_rate": 0.20, "target_gm": 0.35,
                "overhead_dollars": 0, "revenue_target": 0,
                "projected_profit": 0, "gm_band": "", "commission_total": 0
            })
            self.populate_materials_table([])

        self.populate_labor_payout()

    # [345|pdf|open_pdf_dialog] File chooser for HOVER PDFs → defers to handle_pdf_drop(path)
    @lore_guard("open pdf dialog failure", severity="low")
    def open_pdf_dialog(self):
        """
        Opens a file picker and forwards the selected PDF to the canonical drop handler.
        """
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select HOVER PDF",
            "",
            "PDF Files (*.pdf)"
        )
        if path:
            self.handle_pdf_drop(path)

        ##
    # [120|dialog|open_totals_dialog] Parsed Totals — inspect, re-parse, apply
    def open_totals_dialog(self):
        """
        Parsed Totals dialog (single SF shown; autosizing columns; Apply auto-recomputes).
        """
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton,
            QMessageBox, QHeaderView
        )

        dlg = QDialog(self)
        dlg.setWindowTitle("Parsed Totals (from HOVER)")
        lay = QVBoxLayout(dlg)

        tbl = QTableWidget(0, 3)
        tbl.setHorizontalHeaderLabels(["Metric", "Value", "UOM"])
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Metric
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Value
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # UOM
        lay.addWidget(tbl)

        UOMS = {
            "eave_fascia": "LF", "rake_fascia": "LF",
            "openings_perim": "LF", "outside": "LF", "inside": "LF",
        }

        def populate_table(t: dict | None):
            tbl.setRowCount(0)
            keys = ["siding_sf_single","eave_fascia","rake_fascia","openings_perim","outside","inside"]
            labels = {
                "siding_sf_single": "Siding (SF)",
                "eave_fascia": "Eave Fascia",
                "rake_fascia": "Rake Fascia",
                "openings_perim": "Openings Perimeter",
                "outside": "Outside Corners",
                "inside": "Inside Corners",
            }
            siding_sf_single = 0.0
            if t:
                try:
                    siding_sf_single = max(float(t.get("facades_sf", 0.0)), float(t.get("trim_siding_sf", 0.0)))
                except Exception:
                    siding_sf_single = 0.0

            values = {
                "siding_sf_single": siding_sf_single,
                "eave_fascia": (t or {}).get("eave_fascia", 0.0),
                "rake_fascia": (t or {}).get("rake_fascia", 0.0),
                "openings_perim": (t or {}).get("openings_perim", 0.0),
                "outside": (t or {}).get("outside", 0.0),
                "inside": (t or {}).get("inside", 0.0),
            }

            for k in keys:
                r = tbl.rowCount(); tbl.insertRow(r)
                tbl.setItem(r, 0, QTableWidgetItem(labels[k]))
                tbl.setItem(r, 1, QTableWidgetItem(str(values[k])))
                tbl.setItem(r, 2, QTableWidgetItem("SF" if k == "siding_sf_single" else UOMS.get(k, "")))

            tbl.resizeColumnsToContents()

        totals = getattr(self, "last_totals", {}) or {}
        populate_table(totals)

        reparse_btn = QPushButton("Re-parse from Last PDF Text")
        lay.addWidget(reparse_btn)

        def do_reparse():
            try:
                text_path = os.path.join(JOBS_DIR, "last_pdf_text.txt")
                if not os.path.exists(text_path):
                    QMessageBox.warning(dlg, "Not Found", "No last_pdf_text.txt available to re-parse.")
                    return
                with open(text_path, "r", encoding="utf-8") as f:
                    text = f.read()
                totals2 = extract_hover_totals(text)
                self.last_totals = totals2
                populate_table(totals2)
                QMessageBox.information(dlg, "Re-parsed", "Re-parsed totals from last PDF text.")
            except Exception as e:
                QMessageBox.critical(dlg, "Re-parse Failed", str(e))

        reparse_btn.clicked.connect(do_reparse)

        apply_btn = QPushButton("Apply to Job (Auto-Recompute)")
        lay.addWidget(apply_btn)

        def _val_for(label_text: str) -> float:
            for r in range(tbl.rowCount()):
                key_item = tbl.item(r, 0)
                val_item = tbl.item(r, 1)
                if key_item and key_item.text() == label_text and val_item:
                    try:
                        return float(val_item.text())
                    except Exception:
                        return 0.0
            return 0.0

        def do_apply():
            if not getattr(self, "last_inputs", None):
                QMessageBox.warning(dlg, "No Job", "Open a job first (drop a PDF).")
                return

            try:
                record_decision(
                    title="apply parsed totals",
                    options=["merge deltas", "replace baselines", "ignore until confirmed"],
                    decision="replace baselines with Hover values",
                    rationale="avoid cross-property contamination"
                )
            except Exception:
                pass

            try:
                fac    = _val_for("Siding (SF)")
                eave   = _val_for("Eave Fascia")
                rake   = _val_for("Rake Fascia")
                perim  = _val_for("Openings Perimeter")
                outside = _val_for("Outside Corners")
                inside  = _val_for("Inside Corners")

                li = self.last_inputs
                new_inp = JobInputs(
                    customer_name=li.customer_name,
                    address=li.address,
                    region=li.region,
                    siding_type=li.siding_type,
                    finish=li.finish,
                    body_color=li.body_color,
                    trim_color=li.trim_color,
                    complexity=li.complexity,
                    demo_required=li.demo_required,
                    extra_layers=li.extra_layers,
                    substrate=li.substrate,
                    facades_sf=fac,
                    trim_siding_sf=fac,
                    eave_fascia_ft=eave,
                    rake_fascia_ft=rake,
                    soffit_depth_gt_24=li.soffit_depth_gt_24,
                    openings_perimeter_ft=perim,
                    outside_corners_ft=outside,
                    inside_corners_ft=inside,
                    fascia_width_in=li.fascia_width_in,
                    osb_selected=li.osb_selected,
                    osb_area_override_sf=li.osb_area_override_sf
                )

                new_out = compute_estimate_wrapper(new_inp)

                self.last_inputs = new_inp
                self.last_outputs = new_out

                tc_for_baseline = price_trade("Siding", self.last_inputs, self.last_outputs)
                self.baseline_unit_costs = {li.name: li.unit_cost for li in tc_for_baseline.line_items}
                self._materials_baseline  = {li.name: int(round(li.qty)) for li in tc_for_baseline.line_items}

                self.recompute_pricing()
                QMessageBox.information(dlg, "Updated", "Applied parsed totals and recomputed.")
            except Exception as e:
                QMessageBox.critical(dlg, "Apply Failed", str(e))

        apply_btn.clicked.connect(do_apply)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn)

        dlg.exec()
        # No parent class provides open_totals_dialog; explicit None keeps flow clear.
        return None

    def populate_table(t: dict | None):
        tbl.setRowCount(0)
        keys = ["siding_sf_single","eave_fascia","rake_fascia","openings_perim","outside","inside"]
        labels = {
            "siding_sf_single": "Siding (SF)",
            "eave_fascia": "Eave Fascia",
            "rake_fascia": "Rake Fascia",
            "openings_perim": "Openings Perimeter",
            "outside": "Outside Corners",
            "inside": "Inside Corners",
        }
        siding_sf_single = 0.0
        if t:
            try:
                siding_sf_single = max(float(t.get("facades_sf", 0.0)), float(t.get("trim_siding_sf", 0.0)))
            except Exception:
                siding_sf_single = 0.0

        values = {
            "siding_sf_single": siding_sf_single,
            "eave_fascia": (t or {}).get("eave_fascia", 0.0),
            "rake_fascia": (t or {}).get("rake_fascia", 0.0),
            "openings_perim": (t or {}).get("openings_perim", 0.0),
            "outside": (t or {}).get("outside", 0.0),
            "inside": (t or {}).get("inside", 0.0),
        }

        for k in keys:
            r = tbl.rowCount(); tbl.insertRow(r)
            tbl.setItem(r, 0, QTableWidgetItem(labels[k]))
            tbl.setItem(r, 1, QTableWidgetItem(str(values[k])))
            tbl.setItem(r, 2, QTableWidgetItem("SF" if k == "siding_sf_single" else UOMS.get(k, "")))

        tbl.resizeColumnsToContents()

    totals = getattr(self, "last_totals", {}) or {}
    populate_table(totals)

    # Re-parse from last captured PDF text (jobs/last_pdf_text.txt)
    reparse_btn = QPushButton("Re-parse from Last PDF Text")
    lay.addWidget(reparse_btn)

    def do_reparse():
        try:
            text_path = os.path.join(JOBS_DIR, "last_pdf_text.txt")
            if not os.path.exists(text_path):
                QMessageBox.warning(dlg, "Not Found", "No last_pdf_text.txt available to re-parse.")
                return
            with open(text_path, "r", encoding="utf-8") as f:
                text = f.read()
            totals2 = extract_hover_totals(text)
            self.last_totals = totals2
            populate_table(totals2)
            QMessageBox.information(dlg, "Re-parsed", "Re-parsed totals from last PDF text.")
        except Exception as e:
            QMessageBox.critical(dlg, "Re-parse Failed", str(e))

    reparse_btn.clicked.connect(do_reparse)

    # Apply to current job (recompute immediately)
    apply_btn = QPushButton("Apply to Job (Auto-Recompute)")
    lay.addWidget(apply_btn)

    def _val_for(label_text: str) -> float:
        for r in range(tbl.rowCount()):
            key_item = tbl.item(r, 0)
            val_item = tbl.item(r, 1)
            if key_item and key_item.text() == label_text and val_item:
                try:
                    return float(val_item.text())
                except Exception:
                    return 0.0
        return 0.0

    def do_apply():
        if not getattr(self, "last_inputs", None):
            QMessageBox.warning(dlg, "No Job", "Open a job first (drop a PDF).")
            return

        try:
            record_decision(
                title="apply parsed totals",
                options=["merge deltas", "replace baselines", "ignore until confirmed"],
                decision="replace baselines with Hover values",
                rationale="avoid cross-property contamination"
            )
        except Exception:
            pass

        try:
            fac   = _val_for("Siding (SF)")
            eave  = _val_for("Eave Fascia")
            rake  = _val_for("Rake Fascia")
            perim = _val_for("Openings Perimeter")
            outside = _val_for("Outside Corners")
            inside  = _val_for("Inside Corners")

            li = self.last_inputs
            new_inp = JobInputs(
                customer_name=li.customer_name,
                address=li.address,
                region=li.region,
                siding_type=li.siding_type,
                finish=li.finish,
                body_color=li.body_color,
                trim_color=li.trim_color,
                complexity=li.complexity,
                demo_required=li.demo_required,
                extra_layers=li.extra_layers,
                substrate=li.substrate,
                facades_sf=fac,
                trim_siding_sf=fac,
                eave_fascia_ft=eave,
                rake_fascia_ft=rake,
                soffit_depth_gt_24=li.soffit_depth_gt_24,
                openings_perimeter_ft=perim,
                outside_corners_ft=outside,
                inside_corners_ft=inside,
                fascia_width_in=li.fascia_width_in,
                osb_selected=li.osb_selected,
                osb_area_override_sf=li.osb_area_override_sf
            )

            # Compute via wrapper (logs begin/success; BM-B-001)
            new_out = compute_estimate_wrapper(new_inp)

            self.last_inputs = new_inp
            self.last_outputs = new_out

            # Reset baselines to the new priced trade
            tc_for_baseline = price_trade("Siding", self.last_inputs, self.last_outputs)
            self.baseline_unit_costs = {li.name: li.unit_cost for li in tc_for_baseline.line_items}
            self._materials_baseline  = {li.name: int(round(li.qty)) for li in tc_for_baseline.line_items}

            self.recompute_pricing()
            QMessageBox.information(dlg, "Updated", "Applied parsed totals and recomputed.")
        except Exception as e:
            QMessageBox.critical(dlg, "Apply Failed", str(e))

        except Exception:
            pass

        # actual reload
        reload_catalog()

        # Lore: after reload
        try:
            current_catalog_version_string = "PZ90 v2 2025-10-01"  # replace with real version string if available
            set_context(catalog_version=current_catalog_version_string)
            log_event("catalog", "catalog_reloaded", [f"version={current_catalog_version_string}"])
        except Exception:
            pass

        # optional: kick a recompute with fresh catalog
        try:
            self.recompute_pricing(force_catalog_reload=False)
        except Exception:
            pass
    # ---------- PDF drop (path-based parse, deterministic) ----------
    # [130|io|handle_pdf_drop] HOVER PDF → parse → inputs → price → paint
    @lore_guard("pdf drop failure", severity="critical")
    def handle_pdf_drop(self, pdf_path: str):
        """
        Deterministic drop handler:
          1) Extract first pages text for resilient parsing + diagnostics.
          2) Parse identity + HOVER totals.
          3) Build JobInputs defaults (with safe fallbacks).
          4) Compute & price via wrappers (logs begin/success).
          5) Persist payload (sqlite + JSON), refresh UI panes.
        """
        # 1) Extract text (first 4 pages) for robust parsing + dev aid
        text = ""
        try:
            doc = fitz.open(pdf_path)
            for p in range(min(4, doc.page_count)):
                text += doc.load_page(p).get_text()
            doc.close()
            # dev aid: stash last parsed text
            try:
                with open(os.path.join(JOBS_DIR, "last_pdf_text.txt"), "w", encoding="utf-8") as _f:
                    _f.write(text)
            except Exception:
                pass
        except Exception:
            # non-fatal; we still try to parse downstream
            text = ""

        # 2) Parse identity + address + zip (best-effort)
        try:
            name, street_line, city_state_zip, _zip_hint = extract_name_and_address(text)
        except Exception:
            name, street_line, city_state_zip, _zip_hint = "", "", "", ""

        name_upper = (name or "").strip().upper()
        street_line_safe = (street_line or "").strip()
        city_state_zip_safe = (city_state_zip or "").strip()

        # Prefer ZIP near a state token; then hint; then any
        zip_code_safe = _best_zip_from_text(text, city_state_zip_safe)
        addr_full = f"{street_line_safe}, {city_state_zip_safe}".strip(", ").strip()

        # 3) Region guess + display title
        region_guess = auto_region_from_address(street_line_safe, city_state_zip_safe, zip_code_safe)
        try:
            street_only = street_line_safe.split(",")[0].strip().title()
        except Exception:
            street_only = street_line_safe.strip().title()
        display_title = _mk_display_title(name_upper, street_only, zip_code_safe)

        # 3.5) Parse HOVER totals (best-effort)
        try:
            totals = extract_hover_totals(text)
        except Exception:
            totals = {}
        self.last_totals = totals

        # 4) Build inputs with safe defaults
        sid_sf = max(totals.get("facades_sf", 0.0), totals.get("trim_siding_sf", 0.0))
        from types import SimpleNamespace  # (only for clarity if needed later)

        inp = JobInputs(
            customer_name=name_upper or "UNKNOWN",
            address=addr_full,
            region=region_guess or "Metro",
            siding_type="Lap",
            finish="ColorPlus",
            body_color="Iron Gray",
            trim_color="Arctic White",
            complexity="Low",
            demo_required=True,
            extra_layers=0,
            substrate="Wood",
            facades_sf=float(sid_sf or 0.0),
            trim_siding_sf=float(sid_sf or 0.0),
            eave_fascia_ft=float(totals.get("eave_fascia", 0.0) or 0.0),
            rake_fascia_ft=float(totals.get("rake_fascia", 0.0) or 0.0),
            soffit_depth_gt_24=False,
            openings_perimeter_ft=float(totals.get("openings_perim", 0.0) or 0.0),
            outside_corners_ft=float(totals.get("outside", 0.0) or 0.0),
            inside_corners_ft=float(totals.get("inside", 0.0) or 0.0),
            fascia_width_in=8,
            osb_selected=False,
            osb_area_override_sf=0.0
        )

        # 5) Compute + price (Lore wrappers handle begin/success logs)
        out = compute_estimate_wrapper(inp)
        self.last_inputs = inp
        self.last_outputs = out

        trade_cost = price_trade("Siding", inp, out)

        # Establish baselines for Δ markers
        self.baseline_unit_costs = {li.name: li.unit_cost for li in trade_cost.line_items}
        self._materials_baseline = {li.name: int(round(li.qty)) for li in trade_cost.line_items}

        # Summarize job costs (defaults: 20% overhead, 35% target GM)
        job_cost, comm = summarize_job_costs(trade_cost, "Siding", overhead_rate=0.20, target_gm=0.35)
        costs_dict = {
            "material_cost": trade_cost.material_cost,
            "labor_cost": trade_cost.labor_cost,
            "cogs": job_cost.cogs,
            "overhead_rate": job_cost.overhead_rate,
            "target_gm": job_cost.target_gm,
            "overhead_dollars": round(job_cost.overhead_rate * job_cost.revenue_target, 2),
            "revenue_target": job_cost.revenue_target,
            "projected_profit": job_cost.projected_profit,
            "gm_band": comm.band,
            "commission_total": round(comm.commission_total, 2),
            "line_items": [vars(li) for li in trade_cost.line_items],
        }

        # 6) Persist job (sqlite + JSON on disk)
        created = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        payload = dict(inputs=vars(inp), outputs=vars(out), costs=costs_dict)

        try:
            os.makedirs(JOBS_DIR, exist_ok=True)
            json_path = os.path.join(JOBS_DIR, f"{created.replace(':','-')}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

        try:
            con = sqlite3.connect(DB_PATH)
            cur = con.cursor()
            cur.execute(
                "INSERT INTO jobs(title,pdf_path,created_at,data_json) VALUES(?,?,?,?)",
                (display_title, pdf_path, created, json.dumps(payload))
            )
            con.commit()
        finally:
            try:
                con.close()
            except Exception:
                pass

        # 7) Refresh UI panes
        try:
            self.load_jobs_into_list()
        except Exception:
            pass

        self.populate_costs_table(costs_dict)
        self.populate_materials_table(trade_cost)
        self.populate_labor_payout()

        # Update Materials total pill, if present
        try:
            self._refresh_material_total_pill(trade_cost)
        except Exception:
            pass

        # ---------- compute wrappers and repricing ----------
        @lore_guard("estimate compute failure", severity="high")
        def recompute_pricing(self, override_target_gm: float | None = None, force_catalog_reload: bool = False):

            def _do():
                # ... keep your preamble above unchanged ...

                trade_cost = price_trade("Siding", self.last_inputs, self.last_outputs)

                # user overrides from table
                user_overrides: dict[str, int] = {}
                try:
                    for r in range(self.materials.rowCount()):
                        key_item = self.materials.item(r, 0)
                        qty_item = self.materials.item(r, 1)
                        if not key_item or not qty_item:
                            continue
                        name_key = key_item.data(Qt.UserRole)
                        if not name_key:
                            continue
                        txt = (qty_item.text() or "").strip()
                        if txt == "":
                            continue
                        try:
                            user_overrides[name_key] = max(0, int(round(float(txt))))
                        except Exception:
                            pass
                except Exception:
                    user_overrides = {}

                # coverage overrides (unchanged)
                auto_overrides: dict[str, int] = {}
                try:
                    sf = float(getattr(self.last_inputs, "facades_sf", 0.0) or 0.0)
                    if sf > 0:
                        width_map = {"plank_5_25": 5.25, "plank_6_25": 6.25, "plank_7_25": 7.25,
                                     "plank_8_25": 8.25, "plank_9_25": 9.25, "plank_12": 12.0}
                        chosen_width = None
                        for li in trade_cost.line_items:
                            for tk, w in width_map.items():
                                if li.name.startswith(tk):
                                    chosen_width = w; break
                            if chosen_width is not None: break
                        if chosen_width is not None:
                            planks, nail_boxes = self._compute_planks_and_nails(sf, chosen_width)
                            for li in trade_cost.line_items:
                                if any(li.name.startswith(k) for k in width_map.keys()):
                                    auto_overrides[li.name] = planks
                            if "nail_box" in getattr(self, "_materials_baseline", {}) or any(li.name == "nail_box" for li in trade_cost.line_items):
                                auto_overrides["nail_box"] = nail_boxes
                except Exception:
                    pass

                # ---- Build with UNION of names so zero-qty rows are preserved ----
                # Prepare lookup maps for unit_costs
                cat_units = {li.name: float(li.unit_cost) for li in trade_cost.line_items}
                baseline_units = dict(getattr(self, "baseline_unit_costs", {}))
                live_units = dict(getattr(self, "_materials_unit_cost", {}))

                all_names = set(cat_units.keys()) | set(getattr(self, "_materials_baseline", {}).keys())
                new_lines = []
                mat_total = 0.0

                for name in sorted(all_names):
                    # qty resolve priority: user override → auto coverage → catalog qty (if present) → baseline qty → 0
                    cat_qty = 0
                    for li in trade_cost.line_items:
                        if li.name == name:
                            try:
                                cat_qty = int(round(float(li.qty or 0)))
                            except Exception:
                                cat_qty = 0
                            break
                    qty = user_overrides.get(name,
                          auto_overrides.get(name,
                          cat_qty if name in cat_units else int(getattr(self, "_materials_baseline", {}).get(name, 0))))

                    # unit cost resolve: user-edited live → catalog → baseline → 0
                    unit_now = float(live_units.get(name,
                                     cat_units.get(name,
                                     baseline_units.get(name, 0.0))))

                    ext = float(qty) * float(unit_now)
                    mat_total += ext

                    # Create a li-like row; reuse the existing type if available
                    try:
                        li_type = type(trade_cost.line_items[0])
                        new_lines.append(li_type(name, qty, "EA", unit_now, ext))
                    except Exception:
                        from types import SimpleNamespace
                        new_lines.append(SimpleNamespace(name=name, qty=qty, uom="EA", unit_cost=unit_now, ext_cost=ext))

                # Rebuild trade_cost with preserved rows
                trade_cost = type(trade_cost)(
                    trade=trade_cost.trade,
                    material_cost=round(mat_total, 2),
                    labor_cost=trade_cost.labor_cost,
                    line_items=new_lines
                )
            self._with_recompute_guard(_do)
            if hasattr(self, "_last_trade_cost"):
                self._refresh_material_total_pill(self._last_trade_cost)
            else:
                self._refresh_material_total_pill(None)

    # ---------- materials table + helpers ----------
    def _paint_material_delta(self, r: int, qty_now: int, qty_base: int, unit_now: float, unit_base: float):
        it_delta = self.materials.item(r, 5)
        if it_delta is None:
            it_delta = QTableWidgetItem(""); self.materials.setItem(r, 5, it_delta)
        show_qty_delta  = (qty_now != qty_base)
        show_unit_delta = (abs(unit_now - unit_base) > 1e-9)
        it_delta.setText(""); it_delta.setForeground(QBrush(QColor("#333333")))
        if show_unit_delta:
            if unit_now > unit_base:
                it_delta.setText("▲"); it_delta.setForeground(QBrush(QColor("#cc0000")))
            else:
                it_delta.setText("▼"); it_delta.setForeground(QBrush(QColor("#1a7f37")))
        elif show_qty_delta:
            if qty_now > qty_base:
                it_delta.setText("▲"); it_delta.setForeground(QBrush(QColor("#1a7f37")))
            else:
                it_delta.setText("▼"); it_delta.setForeground(QBrush(QColor("#cc0000")))

    def populate_materials_table(self, data):
        """
        Render Materials with numbering, Δ markers, black theme, and hover-trash.
        Keeps rows even when qty is zero.
        """
        # Ensure maps exist
        if not hasattr(self, "_materials_unit_cost"):
            self._materials_unit_cost = {}
        if not hasattr(self, "_materials_baseline"):
            self._materials_baseline = {}
        if not hasattr(self, "baseline_unit_costs"):
            self.baseline_unit_costs = {}

        # Normalize incoming data → list[dict]
        try:
            from trades.registry import TradeCost
        except Exception:
            TradeCost = None  # type: ignore

        # Build a dict of line items coming in
        cur_items = {}
        if TradeCost and isinstance(data, TradeCost):
            for li in data.line_items:
                cur_items[li.name] = dict(
                    qty=int(round(float(li.qty or 0))),
                    uom=(li.uom or "").strip().upper(),
                    unit_cost=float(li.unit_cost or 0.0),
                )
        elif isinstance(data, list):
            for li in data:
                name = li.get("name", "")
                cur_items[name] = dict(
                    qty=int(round(float(li.get("qty", 0) or 0))),
                    uom=(li.get("uom", "") or "").strip().upper(),
                    unit_cost=float(li.get("unit_cost", 0.0) or 0.0),
                )
        else:
            with self._block_signals(self.materials):
                self.materials.setRowCount(0)
            self._update_materials_reset_visibility()
            self._refresh_material_total_pill(None)
            return

        # Union of names so we keep zero-qty rows that existed in baselines
        all_names = set(cur_items.keys()) | set(self._materials_baseline.keys())

        # Prepare rows
        lines = []
        for name in sorted(all_names):
            info = cur_items.get(name, {})
            qty = int(round(float(info.get("qty", self._materials_baseline.get(name, 0)))))
            u_raw = (info.get("uom", "") or "")
            uom = "ROLL" if u_raw in ("ROLL", "ROLLS") else ("BOX" if u_raw in ("BOX", "BOXES") else (u_raw or "EA"))
            unit_now = float(info.get("unit_cost", self.baseline_unit_costs.get(name, 0.0)))
            lines.append(dict(name=name, qty=qty, uom=uom, unit_cost=unit_now))

        # Paint rows
        running_total = 0.0
        self._materials_rebuilding = True
        with self._block_signals(self.materials):
            # Header/columns
            if self.materials.columnCount() != 7:
                self.materials.setColumnCount(7)
                self.materials.setHorizontalHeaderLabels(
                    ["Material", "Qty", "UOM", "Unit Cost", "Ext. Cost", "Δ", ""]
                )
                mh = self.materials.horizontalHeader()
                mh.setMinimumSectionSize(24)
                mh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                mh.setSectionResizeMode(1, QHeaderView.Fixed);   mh.resizeSection(1, 70)
                mh.setSectionResizeMode(2, QHeaderView.Fixed);   mh.resizeSection(2, 70)
                mh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
                mh.setSectionResizeMode(4, QHeaderView.Stretch)
                mh.setSectionResizeMode(5, QHeaderView.Fixed);   mh.resizeSection(5, 28)
                mh.setSectionResizeMode(6, QHeaderView.Fixed);   mh.resizeSection(6, 28)

            self.materials.setRowCount(0)

            for idx, li in enumerate(lines, start=1):
                key = li["name"]
                qty = int(li["qty"])
                uom = li["uom"] or "EA"
                unit_now = float(li["unit_cost"])

                # Track live unit cost for repricer
                self._materials_unit_cost[key] = unit_now

                # Baselines (for Δ)
                unit_base = float(self.baseline_unit_costs.get(key, unit_now))
                qty_base  = int(self._materials_baseline.get(key, qty))

                # Row
                r = self.materials.rowCount()
                self.materials.insertRow(r)

                # Friendly label (numbered) with fascia width when applicable
                fascia_w = None
                if key == "fascia_12ft" and getattr(self, "last_inputs", None):
                    try:
                        fascia_w = int(self.last_inputs.fascia_width_in)
                    except Exception:
                        fascia_w = None

                friendly = _friendly(key, fascia_width_in=fascia_w)
                numbered = f"{idx}. {friendly}"

                it_name = QTableWidgetItem(numbered)
                it_name.setData(Qt.UserRole, key)
                it_name.setFlags(it_name.flags() & ~Qt.ItemIsEditable)
                self.materials.setItem(r, 0, it_name)

                # Qty (editable; keep zero visible)
                it_qty = QTableWidgetItem(str(qty))
                it_qty.setData(Qt.UserRole, key)
                self.materials.setItem(r, 1, it_qty)

                # UOM (read-only)
                it_uom = QTableWidgetItem(uom)
                it_uom.setFlags(it_uom.flags() & ~Qt.ItemIsEditable)
                self.materials.setItem(r, 2, it_uom)

                # Unit Cost (editable per job)
                it_unit = QTableWidgetItem(f"${unit_now:,.2f}")
                self.materials.setItem(r, 3, it_unit)

                # Ext. Cost (read-only)
                ext_now = float(qty) * float(unit_now)
                it_ext = QTableWidgetItem(_fmt_money(ext_now))
                it_ext.setFlags(it_ext.flags() & ~Qt.ItemIsEditable)
                self.materials.setItem(r, 4, it_ext)
                running_total += ext_now

                # Δ marker (qty or unit diffs) — narrow col 5
                it_delta = QTableWidgetItem("")
                it_delta.setFlags(it_delta.flags() & ~Qt.ItemIsEditable)
                if (qty != qty_base) or (abs(unit_now - unit_base) > 1e-9):
                    arrow_up = unit_now > unit_base or qty > qty_base
                    it_delta.setText("▲" if arrow_up else "▼")
                self.materials.setItem(r, 5, it_delta)

                # 🗑 column (col 6) — icon visibility handled by _update_trash_icons
                it_trash = QTableWidgetItem("")
                it_trash.setFlags(Qt.ItemIsEnabled)  # clickable, not editable
                self.materials.setItem(r, 6, it_trash)

        self._materials_rebuilding = False

        # Rehook handlers (Δ click + trash click)
        try:
            self.materials.cellClicked.disconnect(self._on_materials_delta_clicked)
        except Exception:
            pass
        self.materials.cellClicked.connect(self._on_materials_delta_clicked, Qt.ConnectionType.UniqueConnection)

        try:
            self.materials.cellClicked.disconnect(self._on_materials_trash_clicked)
        except Exception:
            pass
        self.materials.cellClicked.connect(self._on_materials_trash_clicked, Qt.ConnectionType.UniqueConnection)

        # Enable/disable Reset pill; update totals/pill
        self._update_materials_reset_visibility()
        self._update_materials_total_label(running_total)
        self._refresh_material_total_pill()

        # Light touch sizing after paint
        try:
            QTimer.singleShot(100, lambda: self.materials.resizeColumnsToContents())
        except Exception:
            pass

    def _on_materials_trash_clicked(self, row: int, col: int):
        """Trash icon → set qty to zero but keep row present."""
        if col != 6:
            return
        try:
            qty_item = self.materials.item(row, 1)
            if not qty_item:
                return
            self.materials.blockSignals(True)
            qty_item.setText("0")
        finally:
            self.materials.blockSignals(False)
        try:
            self.recompute_pricing()
        except Exception:
            pass


    # --------------------- Materials table handlers (required by _wire_signals) ---------------------
    def _on_materials_item_changed(self, item: QTableWidgetItem):
        """
        Enforce integer Qty edits in Materials[Qty] (col=1) and trigger recompute.
        """
        try:
            if getattr(self, "_materials_rebuilding", False) or item.column() != 1:
                return
            # enforce integer
            vtxt = (item.text() or "0").strip()
            v = int(round(float(vtxt)))
            if v < 0:
                v = 0
            if item.text() != str(v):
                self.materials.blockSignals(True)
                item.setText(str(v))
                self.materials.blockSignals(False)
        except Exception:
            # if parse fails, ignore and keep previous text
            return
        # queue recompute
        try:
            self.recompute_pricing()
        except Exception:
            pass
    def eventFilter(self, obj, ev):
        """
        Hover-only trash icon visibility on Materials rows.
        Placement: inside class Main (overrides QObject.eventFilter)
        """
        try:
            if obj is self.materials:
                # PySide6 has both .position() (QPointF) and .pos() (QPoint)
                if ev.type() == ev.MouseMove:
                    pos = ev.position() if hasattr(ev, "position") else ev.pos()
                    row = self.materials.rowAt(int(pos.y()))
                    self._update_trash_icons(row)
                elif ev.type() in (ev.Leave,):
                    self._update_trash_icons(-1)
        except Exception:
            pass
        return super().eventFilter(obj, ev)

    def _update_trash_icons(self, hover_row: int):
        """
        Show a trash icon only on the hovered row in column 6 (the last col).
        Creates the cell if needed; icon hidden on non-hovered rows.
        """
        try:
            from PySide6.QtWidgets import QTableWidgetItem, QStyle
            icon = self.style().standardIcon(QStyle.SP_TrashIcon)
            last_col = 6  # Δ=5, Trash=6 per our table schema

            # Guard: if the table doesn't have the trash column yet, do nothing
            if self.materials.columnCount() <= last_col:
                return

            for r in range(self.materials.rowCount()):
                it = self.materials.item(r, last_col)
                if it is None:
                    it = QTableWidgetItem("")
                    # Not editable; still enables decoration click routing via cellClicked
                    it.setFlags(Qt.ItemIsEnabled)
                    self.materials.setItem(r, last_col, it)
                it.setData(Qt.DecorationRole, icon if r == hover_row else None)
        except Exception:
            pass

    def _on_materials_trash_clicked(self, row: int, col: int):
        """
        Clicking the trash (col=6) sets qty to zero but keeps the row.
        Wire this via self.materials.cellClicked.connect(self._on_materials_trash_clicked).
        """
        last_col = 6
        if col != last_col:
            return
        try:
            qty_item = self.materials.item(row, 1)  # Qty column
            if not qty_item:
                return
            self.materials.blockSignals(True)
            qty_item.setText("0")
        finally:
            self.materials.blockSignals(False)
        try:
            self.recompute_pricing()
        except Exception:
            pass


    def _refresh_material_total_pill(self, trade_cost=None):
        total = 0.0
        if trade_cost is not None:
            try:
                total = float(trade_cost.material_cost)
            except Exception:
                total = 0.0
        else:
            try:
                col = 4
                for r in range(self.materials.rowCount()):
                    it = self.materials.item(r, col)
                    if not it: continue
                    s = (it.text() or "").replace("$","").replace(",","")
                    total += float(s) if s else 0.0
            except Exception:
                total = 0.0
        if hasattr(self, "_mat_total_pill"):
            self._mat_total_pill.setText(_fmt_money(total))

    def _update_materials_total_label(self, value: float):
        try:
            if hasattr(self, "_mat_total_pill"):
                self._mat_total_pill.setText(_fmt_money(value))
        except Exception:
            pass

    def _reset_materials_to_hover(self):
        if not getattr(self, "_materials_baseline", None):
            return
        self._materials_rebuilding = True
        try:
            self.materials.blockSignals(True)
            for r in range(self.materials.rowCount()):
                nm = self.materials.item(r, 0)
                qy = self.materials.item(r, 1)
                if not (nm and qy): continue
                key = nm.data(Qt.UserRole)
                if not key: continue
                base_q = int(self._materials_baseline.get(key, 0))
                qy.setText(str(base_q))
        finally:
            self.materials.blockSignals(False)
            self._materials_rebuilding = False
        self.recompute_pricing()

    # [230|ui|_update_materials_reset_visibility] Keep pill CSS; only toggle enabled state
    def _update_materials_reset_visibility(self):
        try:
            needed = False
            for r in range(self.materials.rowCount()):
                nm = self.materials.item(r, 0)
                qy = self.materials.item(r, 1)
                if not (nm and qy):
                    continue
                key = nm.data(Qt.UserRole)
                if not key:
                    continue
                base_q = int(self._materials_baseline.get(key, 0))
                try:
                    cur_q = int(float((qy.text() or "0").strip()))
                except Exception:
                    cur_q = base_q
                if cur_q != base_q:
                    needed = True
                    break

            # Only toggle enabled. DO NOT replace the stylesheet here — keep pill CSS intact.
            self.reset_hover_rb.setEnabled(needed)
        except Exception:
            self.reset_hover_rb.setEnabled(False)


    # ---------- cost table, editing, deltas ----------
    def populate_costs_table(self, costs_dict):
        def m(x):
            try: return f"${float(x):,.2f}"
            except Exception: return "$0.00"
        def p(x):
            try: return f"{float(x):.2%}"
            except Exception: return "0.00%"

        rows = [
            ("Material Cost",     m(costs_dict.get("material_cost", 0.0)),    ""),
            ("Labor Cost",        m(costs_dict.get("labor_cost", 0.0)),       ""),
            ("COGS",              m(costs_dict.get("cogs", 0.0)),             ""),
            ("Overhead Rate",     p(costs_dict.get("overhead_rate", 0.0)),    ""),
            ("Target GM",         p(costs_dict.get("target_gm", 0.0)),        ""),
            ("Overhead $",        m(costs_dict.get("overhead_dollars", 0.0)), ""),
            ("Revenue Target",    m(costs_dict.get("revenue_target", 0.0)),   ""),
            ("Projected Profit",  m(costs_dict.get("projected_profit", 0.0)), ""),
            ("GM Band",           str(costs_dict.get("gm_band", "")),         ""),
            ("Commission Total",  m(costs_dict.get("commission_total", 0.0)), ""),
        ]

        with self._block_signals(self.costs):
            if self.costs.columnCount() != 3:
                self.costs.setColumnCount(3)
                self.costs.setHorizontalHeaderLabels(["Cost Metric", "Value", "Δ"])
                ch = self.costs.horizontalHeader()
                ch.setMinimumSectionSize(28)
                ch.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                ch.setSectionResizeMode(1, QHeaderView.Stretch)
                ch.setSectionResizeMode(2, QHeaderView.Fixed); ch.resizeSection(2, 40)

            self.costs.clearContents()
            self.costs.setRowCount(len(rows))
            for r, (label, value, delta) in enumerate(rows):
                self.costs.setItem(r, 0, QTableWidgetItem(str(label)))
                self.costs.setItem(r, 1, QTableWidgetItem(str(value)))
                self.costs.setItem(r, 2, QTableWidgetItem(str(delta)))

        self._wire_signals()

    def _set_costs_delta_marker(self, row: int):
        key_item = self.costs.item(row,0)
        val_item = self.costs.item(row,1)
        delta_item = self.costs.item(row,2)
        if not key_item or not val_item:
            return
        if delta_item is None:
            delta_item = QTableWidgetItem("")
            self.costs.setItem(row, 2, delta_item)

        key = key_item.text()
        val = val_item.text()
        base = getattr(self, "_costs_baseline", {}).get(key, None)
        delta_item.setText("")
        delta_item.setForeground(QBrush(QColor("black")))
        if base is None:
            return

        if key in ("Target GM", "Overhead Rate"):
            try:
                cur = float(val.replace("%",""))/100.0 if "%" in val else float(val)
            except Exception:
                cur = float(base)
            base_v = float(base)
            diff = cur - base_v
        elif key == "GM Band":
            cur = val
            base_v = base
            diff = 0.0
        else:
            try:
                cur = float(val.replace("$","").replace(",",""))
            except Exception:
                cur = float(base)
            base_v = float(base)
            diff = cur - base_v

        if key == "GM Band":
            if str(cur) != str(base_v):
                delta_item.setText("▲")
                delta_item.setForeground(QBrush(QColor("#1a7f37")))
            else:
                delta_item.setText("")
            return

        if abs(diff) < 1e-9:
            delta_item.setText("")
            delta_item.setForeground(QBrush(QColor("black")))
        elif diff > 0:
            delta_item.setText("▲")
            delta_item.setForeground(QBrush(QColor("#1a7f37")))
        else:
            delta_item.setText("▼")
            delta_item.setForeground(QBrush(QColor("#cc0000")))

    def on_costs_cell_changed(self, row: int, col: int):
        if col != 1:
            return
        key_item = self.costs.item(row, 0)
        val_item = self.costs.item(row, 1)
        if not key_item or not val_item:
            return
        key = key_item.text().strip()
        txt = (val_item.text() or "").strip()

        def _money_to_float(s: str) -> float:
            try:
                return float((s or "").replace("$", "").replace(",", ""))
            except Exception:
                return 0.0

        def _finish_delta():
            self._set_costs_delta_marker(row)
            
        if key == "Target GM":
            pct = _parse_percent_cell(txt)
            self.costs.blockSignals(True)
            try:
                val_item.setText(f"{pct:.2%}")
            finally:
                self.costs.blockSignals(False)
            self._set_costs_delta_marker(row)
            self.recompute_pricing(override_target_gm=pct)
            return

        if key == "Revenue Target":
            try:
                v = float(txt.replace("$","").replace(",",""))
            except Exception:
                v = self._costs_baseline.get(key, 0.0)
            self.costs.blockSignals(True)
            try:
                val_item.setText(_fmt_money(v))
            finally:
                self.costs.blockSignals(False)
            self._set_costs_delta_marker(row)
            # Recompute using explicit revenue target override is not part of summarize_job_costs API,
            # so we just mark the delta. Final revenue target will be recomputed on rerun with GM.
            return


    
        if key in ("Material Cost", "Labor Cost", "COGS", "Overhead", "Projected Profit"):
            v = _money_to_float(txt)
            self.costs.blockSignals(True)
            try:
                val_item.setText(_fmt_money(v))
            finally:
                self.costs.blockSignals(False)
            _finish_delta()
            return

        if key == "GM Band":
            _finish_delta()
            return

    ##
    # ---------- labor payout ----------
    @lore_guard("labor payout population failure", severity="medium")
    def populate_labor_payout(self):
        """
        - Header shows total labor dollars
        - Child rows show $/SQ
        - Avoids fallback unless outputs truly lack labor fields
        """
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtGui import QFont

        self.results_tree.clear()
        self.results_tree.setRootIsDecorated(False)
        self.results_tree.setStyleSheet("QTreeView::branch { border-image: none; }")

        out = getattr(self, "last_outputs", None)
        inp = getattr(self, "last_inputs", None)
        if not out or not inp:
            self._show_warning_banner(None)
            return

        # Region normalization
        region = (getattr(inp, "region", "") or "Metro")
        level  = {"Metro": "Level 1", "North CO": "Level 2", "Mountains": "Level 3"}.get(region, "Level 1")

        # Prefer outputs; derive from SF if needed
        def _num(v) -> float:
            try:
                if isinstance(v, (int, float)): return float(v)
                s = str(v or "").replace("$", "").replace(",", "").strip()
                return float(s) if s else 0.0
            except Exception:
                return 0.0

        total_sq = _num(getattr(out, "total_sq", 0.0))
        if total_sq <= 0:
            total_sq = _num(getattr(out, "total_squares", 0.0))
        if total_sq <= 0:
            # derive from SF if available
            sf = float(getattr(inp, "facades_sf", 0.0) or 0.0)
            total_sq = round(sf / 100.0, 2) if sf > 0 else 0.0

        psq = _num(getattr(out, "labor_psq", 0.0))
        used_fallback = False

        if psq <= 0:
            # Compute deterministic fallback based on inputs
            try:
                from engine import EXTRA_LAYER_ADD_PER_SQ, BRICK_STUCCO_ADD_PER_SQ
            except Exception:
                EXTRA_LAYER_ADD_PER_SQ = 0.0
                BRICK_STUCCO_ADD_PER_SQ = 0.0

            stype = getattr(inp, "siding_type", "Lap")
            try:
                base_sf = float(LABOR_RATES.get(stype, LABOR_RATES.get("Lap", {})).get(region, 3.35))
            except Exception:
                base_sf = 3.35

            psq = 100.0 * base_sf  # convert $/SF to $/SQ

            demo_required = bool(getattr(inp, "demo_required", True))
            if not demo_required:
                psq += float(NO_DEMO_CREDIT_PER_SQ)

            layers = int(getattr(inp, "extra_layers", 0) or 0)
            if layers > 0:
                psq += float(EXTRA_LAYER_ADD_PER_SQ) * layers

            substrate = str(getattr(inp, "substrate", "") or "").lower()
            if substrate in ("brick", "stucco"):
                psq += float(BRICK_STUCCO_ADD_PER_SQ)

            used_fallback = True

        total_labor_dollars = _num(getattr(out, "labor_cost", 0.0))
        if total_labor_dollars <= 0 and total_sq > 0:
            total_labor_dollars = round(psq * total_sq, 2)

        header = QTreeWidgetItem(["Labor Payout Total", _fmt_money(total_labor_dollars)])
        self.results_tree.addTopLevelItem(header)

        mono = QFont("Menlo"); mono.setStyleHint(QFont.Monospace)

        row_base   = QTreeWidgetItem([f"├─ Base ({level} / {region}) ($/SQ)", _fmt_money(psq)])
        row_region = QTreeWidgetItem([ "├─ Region Upcharge ($/SQ)", _fmt_money(0.0)])
        demo_credit_psq = 0.0 if getattr(inp, "demo_required", True) else _num(NO_DEMO_CREDIT_PER_SQ)
        row_demo   = QTreeWidgetItem([ "├─ Demo Credit ($/SQ)", f"-{_fmt_money(demo_credit_psq)}" if demo_credit_psq else "$0.00"])
        row_total  = QTreeWidgetItem([ "└─ Total Labor ($/SQ)", _fmt_money(psq)])

        for it in (row_base, row_region, row_demo, row_total):
            it.setFont(0, mono)

        header.addChild(row_base)
        header.addChild(row_region)
        header.addChild(row_demo)
        header.addChild(row_total)
        self.results_tree.expandAll()

        # Only warn if we really had to synthesize psq
        self._show_warning_banner("Labor uses fallback constants. Parser or rates missing.") if used_fallback else self._show_warning_banner(None)



    # ---------- catalog + totals dialogs ----------

    @lore_guard("reload catalog failure", severity="low")
    def on_reload_catalog(self):
        # Lore: decision before reload
        try:
            set_context(file="app.py", func="on_reload_catalog")
            record_decision(
                title="catalog reload semantics",
                options=["lazy reload on open", "manual refresh only", "filesystem watcher with debounce"],
                decision="rebuild trade cost + reset unit baselines on manual refresh",
                rationale="determinism and clarity",
                status="accepted"
            )
        except Exception:
            pass

        # actual reload
        reload_catalog()

        # Lore: after reload
        try:
            current_catalog_version_string = "PZ90 v2 2025-10-01"  # TODO: thread real version
            set_context(catalog_version=current_catalog_version_string)
            log_event("catalog", "catalog_reloaded", [f"version={current_catalog_version_string}"])
        except Exception:
            pass

        # optional: kick a recompute with fresh catalog
        try:
            self.recompute_pricing(force_catalog_reload=False)
        except Exception:
            pass

        reload_catalog()
        try:
            current_catalog_version_string = "PZ90 v2 2025-10-01"
            set_context(catalog_version=current_catalog_version_string)
            log_event("catalog", "catalog_reloaded", [f"version={current_catalog_version_string}"])
        except Exception:
            pass
        try:
            self.recompute_pricing(force_catalog_reload=False)
        except Exception:
            pass

    # ---------- coverage helper ----------
    def _compute_planks_and_nails(self, siding_sf: float, plank_width_in: float) -> tuple[int, int]:
        try:
            exposure_in = max(1.0, float(plank_width_in) - 1.25)
            exposure_ft = exposure_in / 12.0
            coverage_sf_per_plank = 12.0 * exposure_ft
            if coverage_sf_per_plank <= 0:
                return 0, 0
            planks = int(max(0, round(siding_sf / coverage_sf_per_plank)))
            nails_per_plank = 108
            boxes = int(max(0, round((planks * nails_per_plank) / 3600.0)))
            return planks, (max(1, boxes) if planks > 0 else 0)
        except Exception:
            return 0, 0



    # --------------------- Results (compatibility) ---------------------
    def populate_results_table(self, outputs: dict):
        from types import SimpleNamespace
        # Store structured outputs (fixes the 'self.last_ outputs' typo)
        self.last_outputs = SimpleNamespace(**(outputs or {}))

        # Refresh panels using the existing pricing pipeline (safe if no inputs yet)
        try:
            if getattr(self, "last_inputs", None):
                self.recompute_pricing()
            self.populate_labor_payout()
        except Exception:
            # Non-fatal: still attempt to render labor panel
            self.populate_labor_payout()




# -------------------------- App bootstrap --------------------------
if __name__ == "__main__":
    import sys
    if sys.version_info >= (3, 14):
        raise SystemExit("Please run with Python 3.12.x (PySide6 is not available on 3.14 yet).")

    from PySide6.QtGui import QGuiApplication
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication.instance() or QApplication(sys.argv)

    w = Main()
    w.show()

    # enforce post-show sizing (prevents auto-maximize)
    try:
        w._normalize_window_sizing()
    except Exception:
        pass

    sys.exit(app.exec())
