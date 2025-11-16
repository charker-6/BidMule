
# ============================================================================
#
#           “As the Elders fade, their logic remains.
#
#           "The Ascendant inherits the light unbroken.
#
#           "Where one Mule rests, another rises.”
#
# ============================================================================
#  BIDMULE — THE LINEAGE, THE LORE, AND THE LAW
#.
#├── .bak
#├── .bm_backups
#├── .bm_bak
#├── app.py
#├── bm_sizes.txt
#├── bm_summary.json
#├── bm_tree_L2.txt
#├── catalog.json
#├── config
#│   └── app.json
#├── core
#│   ├── __init__.py
#│   ├── catalog.py
#│   ├── labels.py
#│   ├── model.py
#│   ├── pricing.py
#│   ├── region.py
#│   └── rules.py
#├── engine.py
#├── future_assets
#│   ├── add_material.png
#│   ├── catalog_refreshg.png
#│   ├── cost_error.png
#│   ├── hover_reset.png
#│   ├── misc..png
#│   └── misc.2.png
#├── jobs
#│   ├── {yyyy-mm-dd} {time}.json
#│   └── last_pdf_text.txt
#├── lore
#│   ├── AdvisorCodex.txt
#│   ├── Chronicles.txt
#│   ├── Dialogues
#│   │   └── 2025-10-12 - Vizier-Advisor - On Dual Path.txt
#│   ├── LawsIndex.txt
#│   ├── LiveLore.md
#│   ├── Onboarding_BitMule6.txt
#│   ├── Prophecies.txt
#│   ├── Succession_Decree.txt
#│   ├── UI_Icon_Specs.txt
#│   ├── __init__.py
#│   ├── channeler_lore_bootstrap.py
#│   ├── lineage_truths.txt
#│   ├── lore_epoch_seed.py
#│   ├── lorekeeper.py
#│   └── weekly_lore_audit_template.txt
#├── project_tree.txt
#├── project_tree_pretty.txt
#├── scripts
#│   ├── archive
#│   │   ├── fix_bidmule9.py
#│   │   └── orphaned_material_total_fallback.1761453366.txt
#│   ├── catalog_migrate.py
#│   ├── install_shim_service.py
#│   ├── patch_engine.py
#│   ├── remove_yellow_banner.py
#│   ├── repair_engine_and_service.py
#│   ├── repair_engine_inline_service.py
#│   ├── restore_auto_region.py
#│   ├── restore_compute_estimate.py
#│   ├── restore_helpers.py
#│   ├── restore_parsers.py
#│   ├── smoke_catalog.py
#│   ├── smoke_materials.py
#│   └── validate_catalog.py
#├── tests
#│   ├── __init__.py
#│   ├── lore_epoch_seed.py
#│   ├── test_bnb_fasteners.py
#│   ├── test_compute_totals.py
#│   ├── test_pricing.py
#│   ├── test_pricing_schedule.py
#│   ├── test_regions_and_labor.py
#│   ├── test_rules.py
#│   ├── test_trim_selectors.py
#│   ├── test_ui_choices.py
#│   └── test_units.py
#├── tools
#│   ├── .bm_bak
#│   ├── app_patch.py
#│   ├── diag_drop.py
#│   ├── fix_drop_and_imports.py
#│   ├── fix_lap_block_indent.py
#│   ├── patch_drop_and_main.py
#│   ├── patch_drop_event.py
#│   ├── patch_lap_woodtone_corners.py
#│   └── repair_app.py
#└── trades
#    ├── __init__.py
#    ├── registry.py
#    └── siding
#        ├── materials.py
#        └── service.py
#
#17 directories


import os, sys, json, sqlite3, datetime, re
from pathlib import Path
from contextlib import contextmanager
import atexit
try:
    APP_DIR = str(Path(__file__).resolve().parent)
except NameError:
    APP_DIR = str(Path.cwd())
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from lore import lorekeeper



# ---- Writable app data root (early) -----------------------------------------
APP_FRIENDLY_NAME = "BidMule8"
APP_DATA = os.environ.get("BIDMULE_DATA_DIR") or os.path.join(
    os.path.expanduser("~"), f".{APP_FRIENDLY_NAME.lower()}"
)
os.makedirs(APP_DATA, exist_ok=True)

# Conventional subdirs for state (independent of module import location)
DATA_LORE = os.path.join(APP_DATA, "Lore")
DATA_JOBS = os.path.join(APP_DATA, "jobs")
os.makedirs(DATA_LORE, exist_ok=True)
os.makedirs(DATA_JOBS, exist_ok=True)

# ---- Minimal debug logger (opt-in via env) -----------------------------------
DEBUG_ON = os.environ.get("BIDMULE_DEBUG", "0") not in ("0", "", "false", "False", "FALSE")

def _dbg(exc: Exception, where: str = ""):
    """
    Lightweight logger for diagnostics. Enable with BIDMULE_DEBUG=1.
    Writes to ~/.bidmule8/debug.log (or BIDMULE_DATA_DIR/debug.log) and stderr.
    Safe to import anywhere; swallows its own errors.
    """
    if not DEBUG_ON:
        return
    try:
        import traceback, sys
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{stamp}] {where}: {exc}\n{traceback.format_exc()}"
        print(msg, file=sys.stderr)
        with open(os.path.join(APP_DATA, "debug.log"), "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

# ---- One-time migration from app folder to user data dir ---------------------
def _maybe_migrate_legacy_paths():
    """
    Best-effort copy of legacy state from the app directory to the per-user data dir.
    Runs once at startup; safe to rerun. Leaves originals in place.
    """
    try:
        import shutil

        # 1) Lore folder
        legacy_lore = os.path.join(APP_DIR, "Lore")
        if os.path.isdir(legacy_lore) and not os.listdir(DATA_LORE):
            try:
                shutil.copytree(legacy_lore, DATA_LORE, dirs_exist_ok=True)
            except Exception as e:
                _dbg(e, "migration:copy Lore")

        # 2) jobs folder (JSON snapshots + last_pdf_text.txt)
        legacy_jobs = os.path.join(APP_DIR, "jobs")
        if os.path.isdir(legacy_jobs) and not os.listdir(DATA_JOBS):
            try:
                shutil.copytree(legacy_jobs, DATA_JOBS, dirs_exist_ok=True)
            except Exception as e:
                _dbg(e, "migration:copy jobs/")

        # 3) jobs.db file (app root) → DATA_JOBS/jobs.db
        legacy_db = os.path.join(APP_DIR, "jobs.db")
        new_db    = os.path.join(DATA_JOBS, "jobs.db")
        if os.path.exists(legacy_db) and not os.path.exists(new_db):
            try:
                os.makedirs(DATA_JOBS, exist_ok=True)
                shutil.copy2(legacy_db, new_db)
            except Exception as e:
                _dbg(e, "migration:copy jobs.db")

    except Exception as e:
        _dbg(e, "migration")

_maybe_migrate_legacy_paths()


from PySide6.QtGui import QColor, QBrush, QFont, QFontMetrics, QShortcut, QKeySequence
from PySide6.QtCore import Qt, QTimer, QRect, QSize, Signal
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QTreeWidget,
    QTreeWidgetItem, QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox,
    QSizePolicy, QMessageBox)


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
    begin_session   = lorekeeper.begin_session
    end_session     = lorekeeper.end_session
    flush           = getattr(lorekeeper, "flush", lambda *a, **k: None)
    set_privacy     = getattr(lorekeeper, "set_privacy", lambda *a, **k: None)
    set_context     = getattr(lorekeeper, "set_context", lambda *a, **k: None)
    log_error       = getattr(lorekeeper, "log_error", lambda *a, **k: None)
    record_struggle = getattr(lorekeeper, "record_struggle", lambda *a, **k: None)
    record_decision = getattr(lorekeeper, "record_decision", lambda *a, **k: None)
    lore_guard      = getattr(lorekeeper, "lore_guard", lambda *a, **k: (lambda fn: fn))
    pdf_sha256      = getattr(lorekeeper, "pdf_sha256", lambda _p: "")

#--------------------------------------------------


# [BM-LEDGER|soft-fail|v1]
import traceback as _tb

def _soft_fail(title: str, *, severity: str = "low", owner: str = "bitmule6"):
    """
    Capture current exception to Struggles + Live Lore without raising.
    Use inside an `except Exception:` block.
    """
    try:
        info = _tb.format_exc(limit=8)
        record_struggle(title=title, severity=severity, owner=owner, notes=info)
        _live_lore_append("Soft Failure", title=title, severity=severity)
    except Exception:
        pass


# >>> BEGIN PATCH: app.py [BM-PDF-ENGINE|util+fallback|v1] <<<
def extract_pdf_text(pdf_path: str, *, max_pages: int = 4) -> str:
    """
    Best-effort text extraction with optional engines (in order):
      1) PyMuPDF (fitz)          — fastest & most robust if present
      2) pdfminer.six             — widely available, pure Python
      3) pypdf / PyPDF2 (>=3.x)   — simple, last-resort
    Override with BIDMULE_PDF_ENGINE={fitz|pdfminer|pypdf|none}.
    Returns concatenated text of first `max_pages` pages or "" on failure.
    """
    eng_env = (os.environ.get("BIDMULE_PDF_ENGINE") or "").strip().lower()
    engines = []
    if eng_env in ("", "auto"):
        engines = ["fitz", "pdfminer", "pypdf"]
    elif eng_env in ("fitz", "pdfminer", "pypdf"):
        engines = [eng_env]
    else:
        # 'none' or unknown → do not attempt any external engine
        engines = []

    # 1) PyMuPDF
    if "fitz" in engines:
        try:
            import fitz  # type: ignore
            text = []
            doc = fitz.open(pdf_path)
            try:
                for p in range(min(max_pages, doc.page_count)):
                    text.append(doc.load_page(p).get_text())
            finally:
                doc.close()
            return "\n".join(text)
        except Exception as e:
            _soft_fail("PyMuPDF text extraction failed", severity="low")
            _dbg(e, "extract_pdf_text:fitz")

    # 2) pdfminer.six
    if "pdfminer" in engines:
        try:
            from pdfminer.high_level import extract_text as _pdfminer_extract
            t = _pdfminer_extract(pdf_path, maxpages=max_pages)
            return t or ""
        except Exception as e:
            _soft_fail("pdfminer text extraction failed", severity="low")
            _dbg(e, "extract_pdf_text:pdfminer")

    # 3) pypdf / PyPDF2
    if "pypdf" in engines:
        try:
            try:
                from pypdf import PdfReader  # modern name
            except Exception:
                from PyPDF2 import PdfReader  # fallback import name
            rdr = PdfReader(pdf_path)
            text = []
            for i, page in enumerate(rdr.pages[:max_pages]):
                try:
                    text.append(page.extract_text() or "")
                except Exception:
                    continue
            return "\n".join(text)
        except Exception as e:
            _soft_fail("pypdf text extraction failed", severity="low")
            _dbg(e, "extract_pdf_text:pypdf")

    # Nothing worked; fail soft
    return ""
# >>> END PATCH: app.py [BM-PDF-ENGINE|util+fallback|v1] <<<



# ---------- Lore session start + mirrored ledgers (singleton guard) ----------
if not globals().get("_LORE_INIT_DONE", False):
    LORE_ROOT = DATA_LORE
    os.makedirs(LORE_ROOT, exist_ok=True)

    _EVENTS    = os.path.join(LORE_ROOT, "Events.jsonl")
    _STRUGGLES = os.path.join(LORE_ROOT, "Struggles.jsonl")
    _DECISIONS = os.path.join(LORE_ROOT, "Decisions.jsonl")
    _SESSIONS  = os.path.join(LORE_ROOT, "Sessions.jsonl")

    for _p in (_EVENTS, _STRUGGLES, _DECISIONS, _SESSIONS):
        try:
            if not os.path.exists(_p):
                with open(_p, "a", encoding="utf-8") as _f:
                    _f.write("")
        except Exception:
            pass

    def _append_jsonl(path, obj):
        try:
            # rotate at ~20 MB to keep tailing snappy
            max_bytes = 20 * 1024 * 1024
            if os.path.exists(path):
                try:
                    if os.path.getsize(path) >= max_bytes:
                        root, ext = os.path.splitext(os.path.basename(path))
                        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                        rotated = os.path.join(os.path.dirname(path), f"{root}.{ts}{ext}")
                        os.replace(path, rotated)  # atomic on same FS
                except Exception as e:
                    try: _dbg(e, f"_append_jsonl(rotate:{path})")
                    except Exception: pass

            obj = dict(obj)
            obj.setdefault("schema", "1.0")
            obj.setdefault("ts", datetime.datetime.now().isoformat(timespec="seconds"))
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        except Exception as e:
            try: _dbg(e, f"_append_jsonl(write:{path})")
            except Exception: pass


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


    _SESSION_CLOSED = False

    def end_session(*a, **k):
        global _SESSION_CLOSED
        if _SESSION_CLOSED:
            return
        try:
            _end_session_orig(*a, **k)
        except Exception:
            pass
        _append_jsonl(_SESSIONS, {"type": "session", "event": "end"})
        _SESSION_CLOSED = True


    def log_event(*args):
        """
        Supported:
          log_event("app_started", ["ui initialized"])
          log_event("compute", "estimate_begin")
          log_event("compute", "estimate_success", ["sq=123"])
        """
        try:
            if len(args) == 0:
                return
            # New-style: (event[, data])
            if len(args) == 1 or (len(args) == 2 and isinstance(args[1], (list, dict))):
                event = args[0]
                data = args[1] if len(args) == 2 else None
                return lorekeeper.log_event(event, data)

            # Legacy: (kind, event[, data])
            kind, event = args[0], args[1]
            data = args[2] if len(args) >= 3 else None

            # Keep an app-local mirror for backward tooling that tails DATA_LORE/Events.jsonl
            try:
                _events_path = os.path.join(DATA_LORE, "Events.jsonl")
                os.makedirs(DATA_LORE, exist_ok=True)
                with open(_events_path, "a", encoding="utf-8") as f:
                    payload = {
                        "type": kind,
                        "event": event,
                        "schema": "1.0",
                        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                    }
                    if data is not None:
                        payload["data"] = data
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            except Exception:
                pass

            # Forward to lorekeeper (central ledger) as a single event string
            return lorekeeper.log_event(f"{kind}:{event}", data)
        except Exception as e:
            _dbg(e, "log_event(shim)")
            
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

    #print(f"LORE: ledgers at {LORE_ROOT}", flush=True)
    if sid == "disabled":
        print("LORE: Guard appears DISABLED (stubbed). Ensure `Lore/` + `lorekeeper.py` are importable.", flush=True)
    else:
        print(f"LORE: session={sid}", flush=True)

    _LORE_INIT_DONE = True



# CALL IT IMMEDIATELY (create QApplication before any QWidget)


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
        # [BM-CATALOG|version-context|v1]
        try:
            from core.catalog import load_catalog
            cat_ver = getattr(load_catalog(), "version", "unknown")
        except Exception:
            cat_ver = "unknown"
        set_context(catalog_version=str(cat_ver), rules=["BM-W-001", "BM-F-012"])
        if getattr(job_inputs, "job_id", None):
            set_context(job_id=str(job_inputs.job_id))
        total_squares = getattr(result, "total_squares", None) or getattr(result, "squares", None) or "n/a"
        _live_lore_append("Compute Success", squares=str(total_squares))
        log_event("compute", "estimate_success", [f"sq={total_squares}"])
    except Exception:
        pass

    return result





# -------------------------- Tiny Apple-like toggle --------------------------
class ToggleSwitch(QCheckBox):
    """Minimal iOS-style toggle: 44x24, no inline text, no clipping."""
    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setCursor(Qt.PointingHandCursor)
        self._w, self._h = 44, 24
        self.setFixedSize(self._w, self._h)
        self.setStyleSheet("QCheckBox{spacing:0;padding:0;margin:0;}")

    def sizeHint(self):  # type: ignore[override]
        return QSize(self._w, self._h)

    def paintEvent(self, e):  # type: ignore[override]
        from PySide6.QtGui import QBrush, QFontMetrics, QPainter
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)

            # track
            r = self.rect().adjusted(1, 1, -1, -1)
            on = self.isChecked()
            bg = QColor("#34c759") if on else QColor("#d1d1d6")
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(bg))
            p.drawRoundedRect(r, r.height() / 2, r.height() / 2)

            # knob
            m = 2
            d = r.height() - 2 * m
            x = r.right() - m - d if on else r.left() + m
            knob = QRect(int(x), r.top() + m, int(d), int(d))
            p.setBrush(QBrush(QColor("transparent")))
            p.drawEllipse(knob)
        finally:
            p.end()

# >>> BEGIN PATCH: OSB linear policy (OSB Area = RATIO × Siding SF) <<<
OSB_LINEAR_RATIO = 1.0  # "same linear correlation" → 1:1 unless changed later

def _osb_area_from_siding_sf(siding_sf: float) -> float:
    try:
        sf = float(siding_sf or 0.0)
    except Exception:
        sf = 0.0
    area = OSB_LINEAR_RATIO * max(0.0, sf)
    # If siding is zero, force OSB to zero (explicit requirement)
    return 0.0 if sf <= 0.0 else float(area)
# >>> END PATCH: OSB linear policy <<<


# -------------------------- Questionnaire (selectors + toggles; indented subs) --------------------------
class Questionnaire(QDialog):
    """
    Main sheet shows selectors + toggles with subordinate controls:
      - Soffit & Fascia (master toggle)
        - Soffit Depth > 24"   (indented under Soffit & Fascia)
        - Fascia Width (in)    (indented under Soffit & Fascia)
      - Extra Layers?          (indented under Demo Required)
    Quantified details like eave/rake lengths live in Advanced.
    """
    def __init__(self, parent, defaults):
        super().__init__(parent)
        self.setWindowTitle("Job Questionnaire")

        # ---- advanced values store (used by AdvancedOptionsDialog) ----
        defaults = defaults or {}
        self._adv_vals = {
            "siding_sf":      str(defaults.get("siding_sf", "")),
            "openings":       str(defaults.get("openings_perim", "0")),
            "outside":        str(defaults.get("outside", "0")),
            "inside":         str(defaults.get("inside", "0")),
            "fascia_w":       int(defaults.get("fascia_w", 8)) if "fascia_w" in defaults else 8,
            "osb_area":       "",
            "eave":           str(defaults.get("eave_fascia", "0")),
            "rake":           str(defaults.get("rake_fascia", "0")),
            "depth_gt24":     bool(defaults.get("depth_gt24", False)),
            "layers":         int(defaults.get("layers", 0)),
            "lap_reveal_in":  float(defaults.get("lap_reveal_in", 7.0)) if "lap_reveal_in" in defaults else 7.0,
        }

        form = QFormLayout(self)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setContentsMargins(20, 16, 20, 12)

        # ---- selectors ----
        self.region = QComboBox(); self.region.addItems(["Metro","North CO","Mountains"])
        if defaults.get("region_guess") in [self.region.itemText(i) for i in range(self.region.count())]:
            self.region.setCurrentText(defaults["region_guess"])

        self.siding = QComboBox(); self.siding.addItems(["Lap","Board & Batten","Shake"])
        self.finish = QComboBox(); self.finish.addItems(["ColorPlus","Woodtone","Primed"])

        # Body/trim with label bound to finish
        self._lbl_body = QLabel("Body Color – ColorPlus:")
        self.body = QComboBox(); self.trim = QComboBox()
        self.body.addItems([
            "Arctic White","Cobble Stone","Navajo Beige","Khaki Brown","Monterey Taupe",
            "Timber Bark","Rich Espresso","Mountain Sage","Light Mist","Pearl Gray",
            "Gray Slate","Boothbay Blue","Evening Blue","Aged Pewter","Night Gray",
            "Iron Gray","Countrylane Red","Primed"
        ])
        self.trim.addItems(["Arctic White","Timber Bark","Cobblestone","Iron Gray","Primed"])
        if defaults.get("body_color"):
            self.body.setCurrentText(str(defaults["body_color"]))
        if defaults.get("trim_color"):
            self.trim.setCurrentText(str(defaults["trim_color"]))

        # lay out body+trim in one row
        body_row = QWidget(); bl = QHBoxLayout(body_row); bl.setContentsMargins(0,0,0,0)
        bl.addWidget(self.body, 1); bl.addWidget(QLabel("Trim:"), 0); bl.addWidget(self.trim, 1)

        self.complexity = QComboBox(); self.complexity.addItems(["Low","Med","High"])
        if defaults.get("complexity") in [self.complexity.itemText(i) for i in range(self.complexity.count())]:
            self.complexity.setCurrentText(defaults["complexity"])

        self.substrate = QComboBox(); self.substrate.addItems(["Wood","Brick","Stucco","Other"])
        if defaults.get("substrate") in [self.substrate.itemText(i) for i in range(self.substrate.count())]:
            self.substrate.setCurrentText(defaults["substrate"])

        # ---- toggles + indented sub-controls ----
        # Renamed to use "&" consistently.
        self.soffit_on = QCheckBox("Has Soffit & Fascia")
        self.soffit_on.setChecked(bool(defaults.get("soffit_on", True)))

        from PySide6.QtCore import Qt
        self.depth_gt24 = QCheckBox('Soffit Depth > 24"')
        self.depth_gt24.toggled.connect(self._on_depth_gt24_toggled, Qt.ConnectionType.UniqueConnection)
        self.depth_gt24.setChecked(bool(self._adv_vals.get("depth_gt24", False)))
        self.depth_gt24.setTristate(False)

        self.fascia_w = QComboBox(); self.fascia_w.addItems(["4","6","8","12"])
        self.fascia_w.setCurrentText(str(self._adv_vals.get("fascia_w", 8)))

        # Indented sub-row under "Soffit & Fascia"
        soffit_sub = QWidget()
        sl = QHBoxLayout(soffit_sub); sl.setContentsMargins(24,0,0,0)  # indent
        sl.addWidget(self.depth_gt24)
        sl.addStretch(1)
        sl.addWidget(QLabel("Fascia Width (in):"))
        sl.addWidget(self.fascia_w)

        # Demo toggle + sub-control (layers)
        self.demo = QCheckBox("Demo Required")
        self.demo.setChecked(bool(defaults.get("demo", True)))
        self.layers = QSpinBox(); self.layers.setRange(0, 5); self.layers.setValue(int(self._adv_vals.get("layers", 0)))
        demo_sub = QWidget(); dl = QHBoxLayout(demo_sub); dl.setContentsMargins(24,0,0,0)
        dl.addWidget(QLabel("Extra Layers?")); dl.addWidget(self.layers); dl.addStretch(1)

        # OSB toggle
        self.osb_on = QCheckBox("OSB Selected")
        self.osb_on.setChecked(bool(defaults.get("osb_on", False)))
        self.osb_on.toggled.connect(self._apply_osb_policy_now)

        # Advanced
        adv_btn = QPushButton("Advanced…")
        adv_btn.clicked.connect(self._open_advanced)

        # layout
        form.addRow("Region:", self.region)
        form.addRow("Siding Type:", self.siding)
        form.addRow("Finish:", self.finish)
        form.addRow(self._lbl_body, body_row)
        form.addRow("Complexity:", self.complexity)
        form.addRow("Substrate:", self.substrate)

        # Renamed the section label to "Soffit & Fascia:"
        form.addRow("Soffit & Fascia:", self.soffit_on)
        form.addRow("", soffit_sub)

        form.addRow("Demo:", self.demo)
        form.addRow("", demo_sub)
        form.addRow("OSB:", self.osb_on)
        form.addRow("", adv_btn)

        # wiring
        self.finish.currentTextChanged.connect(self._sync_finish_bindings)
        self.soffit_on.toggled.connect(self._sync_subordinates)
        self.demo.toggled.connect(self._sync_demo_subordinates)
        self.siding.currentTextChanged.connect(self._notify_adv_enablements)

        # seed
        self._sync_finish_bindings(self.finish.currentText())
        self._sync_subordinates()
        self._sync_demo_subordinates()

        # OK/Cancel
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        form.addRow("", btns)

    def _sync_subordinates(self):
        on = self.soffit_on.isChecked()
        self.depth_gt24.setEnabled(on)
        self.fascia_w.setEnabled(on)
        if not on and self.depth_gt24.isChecked():
            try:
                self.depth_gt24.blockSignals(True)
                self.depth_gt24.setChecked(False)
            finally:
                self.depth_gt24.blockSignals(False)
            self._adv_vals["depth_gt24"] = False
            try:
                if getattr(self, "_adv_dlg", None) and hasattr(self._adv_dlg, "depth_gt24"):
                    self._adv_dlg.depth_gt24.blockSignals(True)
                    self._adv_dlg.depth_gt24.setChecked(False)
                    self._adv_dlg.depth_gt24.blockSignals(False)
            except Exception:
                pass

    def _on_depth_gt24_toggled(self, on: bool):
        """Keep 'Soffit Depth > 24\"' unified across Questionnaire, Advanced, and store."""
        self._adv_vals["depth_gt24"] = bool(on)
        try:
            if getattr(self, "_adv_dlg", None) and hasattr(self._adv_dlg, "depth_gt24"):
                self._adv_dlg.depth_gt24.blockSignals(True)
                self._adv_dlg.depth_gt24.setChecked(bool(on))
                self._adv_dlg.depth_gt24.blockSignals(False)
        except Exception:
            pass

    def _sync_demo_subordinates(self):
        self.layers.setEnabled(self.demo.isChecked())

    def _open_advanced(self):
        if not hasattr(self, "_adv_dlg") or self._adv_dlg is None:
            self._adv_dlg = AdvancedOptionsDialog(self)
            # Persist edits live: every change in Advanced updates our store
            self._adv_dlg.applied.connect(lambda: self._adv_vals.update(self._adv_dlg.save_to_store()))

        if hasattr(self._adv_dlg, "load_from_store"):
            try: self._adv_dlg.load_from_store(self._adv_vals)
            except Exception: pass

        if hasattr(self._adv_dlg, "set_siding_type"):
            try: self._adv_dlg.set_siding_type(self.siding.currentText())
            except Exception: pass

        if hasattr(self._adv_dlg, "_sync_enablements"):
            try: self._adv_dlg._sync_enablements()
            except Exception: pass

        try:
            self._apply_osb_policy_now()
        except Exception:
            pass

        try:
            from PySide6.QtCore import Qt
            if hasattr(self._adv_dlg, "siding_sf"):
                self._adv_dlg.siding_sf.textChanged.connect(
                    self._apply_osb_policy_now, Qt.ConnectionType.UniqueConnection
                )
        except Exception:
            pass

        self._adv_dlg.show(); self._adv_dlg.raise_(); self._adv_dlg.activateWindow()

    def _notify_adv_enablements(self, *_):
        try:
            if getattr(self, "_adv_dlg", None) and self._adv_dlg.isVisible() and hasattr(self._adv_dlg, "_sync_enablements"):
                self._adv_dlg._sync_enablements()
        except Exception:
            pass

    def _sync_finish_bindings(self, text: str):
        finish = (text or "").strip().lower()
        colorplus = [
            "Arctic White","Cobble Stone","Navajo Beige","Khaki Brown","Monterey Taupe",
            "Timber Bark","Rich Espresso","Mountain Sage","Light Mist","Pearl Gray",
            "Gray Slate","Boothbay Blue","Evening Blue","Aged Pewter","Night Gray",
            "Iron Gray","Countrylane Red","Primed"
        ]
        woodtone = ["Coastal Gray","Black Canyon","River Rock","Summer Wheat","Mtn Cedar","Cascade Slate","Aspen Ridge","Old Cherry"]

        def _reset(combo, items, keep=None):
            cur = (keep or combo.currentText() or "").strip()
            combo.blockSignals(True)
            combo.clear(); combo.addItems(items)
            if cur in items:
                combo.setCurrentText(cur)
            combo.blockSignals(False)

        self.setUpdatesEnabled(False)
        try:
            if finish == "primed":
                _reset(self.body, ["Primed"])
                _reset(self.trim, ["Primed"])
                self.body.setEnabled(False); self.trim.setEnabled(False)
                self._lbl_body.setText("Body/Trim: Primed")
            elif finish == "woodtone":
                _reset(self.body, woodtone)
                if self.trim.count() == 0:
                    self.trim.addItems(["Arctic White","Timber Bark","Cobblestone","Iron Gray","Primed"])
                self.body.setEnabled(True); self.trim.setEnabled(True)
                self._lbl_body.setText("Body Stain – Woodtone:")
            else:
                _reset(self.body, colorplus)
                if self.body.findText("Arctic White") >= 0 and not self.body.currentText():
                    self.body.setCurrentText("Arctic White")
                if self.trim.count() == 0:
                    self.trim.addItems(["Arctic White","Timber Bark","Cobblestone","Iron Gray","Primed"])
                self.body.setEnabled(True); self.trim.setEnabled(True)
                self._lbl_body.setText("Body Color – ColorPlus:")
        finally:
            self.setUpdatesEnabled(True)

    def _on_accept(self):
        if hasattr(self, "_adv_dlg") and self._adv_dlg:
            if hasattr(self._adv_dlg, "save_to_store"):
                self._adv_vals.update(self._adv_dlg.save_to_store())

        self._adv_vals["depth_gt24"] = bool(self.depth_gt24.isChecked() and self.soffit_on.isChecked())
        self._adv_vals["layers"] = int(self.layers.value())
        try:
            self._adv_vals["fascia_w"] = int(self.fascia_w.currentText())
        except Exception:
            pass

        errors = []
        if not (self.region.currentText() or "").strip():
            errors.append("Region is required.")
        if not (self.siding.currentText() or "").strip():
            errors.append("Siding type is required.")
        if not (self.finish.currentText() or "").strip():
            errors.append("Finish is required.")
        if self.finish.currentText() != "Primed" and not (self.body.currentText() or "").strip():
            errors.append("Body color is required for non-Primed finishes.")

        if errors:
            QMessageBox.warning(self, "Missing info", "\n".join(errors))
            return

        # enforce OSB policy at commit
        try:
            if not self.osb_on.isChecked():
                self._set_adv_osb_area(0.0)
            else:
                self._set_adv_osb_area(_osb_area_from_siding_sf(self._current_siding_sf_float()))
        except Exception:
            pass

        self.accept()

    # --- OSB policy helpers ---
    def _current_siding_sf_float(self) -> float:
        try:
            return float(self._adv_vals.get("siding_sf", 0.0) or 0.0)
        except Exception:
            return 0.0

    def _set_adv_osb_area(self, val: float):
        v = max(0.0, float(val or 0.0))
        # keep the store as a pretty string for values()
        self._adv_vals["osb_area"] = f"{v:.0f}" if float(v).is_integer() else f"{v:.2f}"
        try:
            if getattr(self, "_adv_dlg", None) and hasattr(self._adv_dlg, "osb_area"):
                self._adv_dlg.osb_area.blockSignals(True)
                # QDoubleSpinBox needs setValue, not setText
                self._adv_dlg.osb_area.setValue(v)
                self._adv_dlg.osb_area.blockSignals(False)
        except Exception:
            pass

    def _apply_osb_policy_now(self):
        if not self.osb_on.isChecked():
            self._set_adv_osb_area(0.0)
            return
        siding_sf = self._current_siding_sf_float()
        self._set_adv_osb_area(_osb_area_from_siding_sf(siding_sf))

    # output
    def values(self):
        def _flt(s):
            try:
                return float(s) if str(s).strip() != "" else 0.0
            except Exception:
                return 0.0

        siding_sf_single = _flt(self._adv_vals.get("siding_sf", 0.0))

        return dict(
            region=self.region.currentText(),
            siding=self.siding.currentText(),
            finish=self.finish.currentText(),
            body_color=self.body.currentText(),
            trim_color=self.trim.currentText(),
            complexity=self.complexity.currentText(),
            demo=self.demo.isChecked(),
            layers=int(self.layers.value()),
            substrate=self.substrate.currentText(),
            facades_sf=siding_sf_single,
            trim_siding_sf=siding_sf_single,
            eave_fascia=ft_in_to_ft(self._adv_vals.get("eave","")) if self.soffit_on.isChecked() else 0.0,
            rake_fascia=ft_in_to_ft(self._adv_vals.get("rake","")) if self.soffit_on.isChecked() else 0.0,
            openings_perim=ft_in_to_ft(self._adv_vals.get("openings","")),
            outside=ft_in_to_ft(self._adv_vals.get("outside","")),
            inside=ft_in_to_ft(self._adv_vals.get("inside","")),
            fascia_w=int(self.fascia_w.currentText()),
            osb_on=self.osb_on.isChecked(),
            osb_area=_flt(self._adv_vals.get("osb_area","")) if str(self._adv_vals.get("osb_area","")).strip() else None,
            soffit_on=self.soffit_on.isChecked(),
            depth_gt24=bool(self.depth_gt24.isChecked() and self.soffit_on.isChecked()),
            lap_reveal_in=float(self._adv_vals.get("lap_reveal_in", 7.0)),
        )


# ---- helpers to parse corner lengths directly from HOVER text ----
_len_num = re.compile(r"(?<![\w.])([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)(?![\w.])")

def _parse_len_ft(s: str) -> float:
    """
    Accepts forms like:
      '96 LF', '96 ft', '96', "12' 6\"", '12 ft 6 in'
    Returns feet as float. Inches are converted to feet. Best-effort, safe fallback 0.0.
    """
    try:
        t = (s or "").strip().lower()
        # feet + inches pattern
        m = re.search(r"(\d+)\s*(?:ft|')\s*(\d+)\s*(?:in|\"?)", t)
        if m:
            ft = float(m.group(1)); inch = float(m.group(2)); return ft + (inch/12.0)
        # feet only
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:lf|ft|feet)\b", t)
        if m:
            return float(m.group(1).replace(",", ""))
        # bare number
        m = _len_num.search(t)
        if m:
            return float(m.group(1).replace(",", ""))
    except Exception:
        pass
    return 0.0

def _extract_corners_from_text(text: str) -> tuple[float, float, bool]:
    """
    Returns (outside_ft, inside_ft, any_corner_tokens_found)
    Looks for a few common HOVER label variants.
    """
    t = (text or "")
    tl = t.lower()
    any_tokens = ("corner" in tl) or ("oc" in tl) or ("ic" in tl)

    # Common label variants we’ve seen
    patt_out = re.compile(
        r"(?:outside\s+corners?|o\.?c\.?)\s*[:\-]?\s*(?:len(?:gth)?\s*[:\-]?\s*)?(.{0,24})",
        re.IGNORECASE
    )
    patt_in = re.compile(
        r"(?:inside\s+corners?|i\.?c\.?)\s*[:\-]?\s*(?:len(?:gth)?\s*[:\-]?\s*)?(.{0,24})",
        re.IGNORECASE
    )

    out_val = 0.0
    in_val  = 0.0

    mo = patt_out.search(t)
    if mo:
        out_val = _parse_len_ft(mo.group(1))
        any_tokens = True

    mi = patt_in.search(t)
    if mi:
        in_val = _parse_len_ft(mi.group(1))
        any_tokens = True

    # Also scan short “OC: 96 LF / IC: 72 LF” lines
    if out_val == 0.0:
        m = re.search(r"\boc\s*[:\-]\s*([^\n\r]+)", tl, re.IGNORECASE)
        if m: out_val = _parse_len_ft(m.group(1))
    if in_val == 0.0:
        m = re.search(r"\bic\s*[:\-]\s*([^\n\r]+)", tl, re.IGNORECASE)
        if m: in_val = _parse_len_ft(m.group(1))

    return out_val, in_val, any_tokens


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
    # Extract a few pages of text (robust to odd PDFs); fall back gently
    try:
        text = extract_pdf_text(pdf_path, max_pages=4)
        if not text:
            _soft_fail("No text extracted from PDF (parse_hover_pdf)", severity="low")
            try:
                with open(pdf_path, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception:
                text = ""
    except Exception:
        _soft_fail("PDF open failed (parse_hover_pdf)", severity="low")
        try:
            with open(pdf_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            _soft_fail("Fallback text read failed (parse_hover_pdf)", severity="low")
            text = ""

    # Identity from text (normalized 4-tuple)


    # Identity from text (normalized 4-tuple)
    try:
        name, street_line, city_state_zip, _zip_hint = extract_name_and_address(text)
    except Exception:
        name, street_line, city_state_zip, _zip_hint = "", "", "", ""

    job_address = f"{(street_line or '').strip()}, {(city_state_zip or '').strip()}".strip(", ").strip()

    # Totals from text (not the file path) for determinism
    try:
        totals = extract_hover_totals(text)
    except Exception:
        totals = {}

        # --- normalize HOVER totals keys (non-invasive; numbers only) ---
        try:
            def _num__bm(x):
                try:
                    if isinstance(x, (int, float)): return float(x)
                    if x is None: return 0.0
                    s = str(x).replace(",", "").strip()
                    return float(s) if s else 0.0
                except Exception:
                    return 0.0
        
            def _ensure__bm(key, *alts):
                cur = _num__bm(totals.get(key))
                if cur > 0:
                    totals[key] = cur
                    return
                for a in alts:
                    if a in totals:
                        v = _num__bm(totals.get(a))
                        if v > 0:
                            totals[key] = v
                            return
        
            _ensure__bm("outside",        "outside_corners_ft", "outside_corners", "oc", "outside_lf")
            _ensure__bm("inside",         "inside_corners_ft",  "inside_corners",  "ic", "inside_lf")
            _ensure__bm("openings_perim", "openings_perimeter_ft","openings_perimeter","openings_lf","openings")
            _ensure__bm("eave_fascia",    "eave","eaves","eave_lf","eave_length_lf","eaves_lf")
            _ensure__bm("rake_fascia",    "rake","rakes","rake_lf","rake_length_lf","rakes_lf")
            _ensure__bm("facades_sf",     "siding_area_sf","siding_sf","facades_total_sf","siding_total_sf")
            _ensure__bm("trim_siding_sf", "trim_sf","trim_siding_area_sf","siding_trim_sf")
        
            if "lap_reveal_in" in totals:
                totals["lap_reveal_in"] = _num__bm(totals.get("lap_reveal_in"))
        except Exception:
            pass

    # ---- backfill inside/outside corners if the engine missed them ----
    try:
        out_raw = totals.get("outside", "")
        in_raw  = totals.get("inside", "")
        out_ft = float(out_raw) if str(out_raw).strip() not in ("", None) else 0.0
        in_ft  = float(in_raw)  if str(in_raw).strip()  not in ("", None) else 0.0
    except Exception:
        out_ft, in_ft = 0.0, 0.0

    try:
        if out_ft == 0.0 or in_ft == 0.0:
            oc, ic, any_corner_tokens = _extract_corners_from_text(text)
            # Only overwrite missing/zero values; preserve engine-provided numbers
            if out_ft == 0.0 and oc > 0.0:
                out_ft = oc
            if in_ft == 0.0 and ic > 0.0:
                in_ft = ic

            totals["outside"] = out_ft
            totals["inside"]  = in_ft

            # Banner logic: show only if corners are clearly referenced but lengths are absent
            warn = bool(any_corner_tokens and (out_ft == 0.0 and in_ft == 0.0))
            totals["warn_corners"] = warn
        else:
            totals["warn_corners"] = False
    except Exception:
        # If anything goes wrong, keep a gentle warning rather than crashing
        totals.setdefault("warn_corners", True)

    # Optional template id (best-effort)
    try:
        template_id = str(totals.get("template_id", "")) if isinstance(totals, dict) else ""
    except Exception:
        template_id = ""

    # Lore: after parse success
    try:
        set_context(template_id=str(template_id), address=str(job_address))
        log_event("parse", "hover_parse_success", [f"template={template_id}"])
        _live_lore_append("Parse Success", template_id=str(template_id or "unknown"))
    except Exception:
        pass

    return template_id, job_address, totals



DB_PATH = os.path.join(DATA_JOBS, "jobs.db")
JOBS_DIR = DATA_JOBS
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

    # Board & Batten
    "bb_panel_4x10": "4'x10' JH B&B Panel",
    "bb_batten_12ft": "12' JH Batten Strip",

    # 4/4 Trim (surface-priced)
    "trim44_4_12ft":  '4/4" 4" JH Trim',
    "trim44_6_12ft":  '4/4" 6" JH Trim',
    "trim44_8_12ft":  '4/4" 8" JH Trim',
    "trim44_12_12ft": '4/4" 12" JH Trim',

}

# [BM-FRIENDLY|bb-entries|v1]
_FRIENDLY_NAMES.setdefault("bb_panel_4x10", "4'x10' JH B&B Panel")
_FRIENDLY_NAMES.setdefault("bb_batten_12ft", "12' JH Batten Strip")


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



# [BM-ZIP|fallback-alias|v1]
def _fallback_zip_from_text(text: str) -> str:
    """Deprecated shim — use _best_zip_from_text()."""
    return _best_zip_from_text(text, "")



# --- helper: normalize a trade_cost by applying the coil split once ---
def _apply_coil_split(trade_cost, finish: str, body_color: str, trim_color: str):
    """
    Returns a new trade_cost with coil rows split (Body/Trim) and material_cost recomputed.
    No-op if not ColorPlus/Woodtone or if nothing to split.
    """
    try:
        li2 = split_color_coils(
            getattr(trade_cost, "line_items", []),
            finish, body_color, trim_color
        )
        if not li2 or li2 == trade_cost.line_items:
            return trade_cost

        # recompute material cost deterministically from split lines
        mt = 0.0
        for _li in li2:
            try:
                q = float(getattr(_li, "qty", 0) or (_li.get("qty", 0) if isinstance(_li, dict) else 0))
                u = float(getattr(_li, "unit_cost", 0.0) or (_li.get("unit_cost", 0.0) if isinstance(_li, dict) else 0.0))
            except Exception:
                q, u = 0.0, 0.0
            mt += q * u

        return type(trade_cost)(
            trade=getattr(trade_cost, "trade", "Siding"),
            material_cost=round(mt, 2),
            labor_cost=getattr(trade_cost, "labor_cost", 0.0),
            line_items=li2,
        )
    except Exception as e:
        try: _dbg(e, "_apply_coil_split")
        except Exception: pass
        return trade_cost



# ------------------- Coil split helper (ColorPlus/Woodtone) -------------------
def split_color_coils(line_items, finish: str, body_color: str, trim_color: str):
    """
    Replace any coil line(s) with two color-labeled coil rows when finish is ColorPlus or Woodtone:
      - "{Body Color} Trim Coil" qty = ceil(total_coil_qty / 4)
      - "{Trim Color} Trim Coil" qty = ceil(total_coil_qty / 4)
    If body and trim colors are the same, suffix labels with "(Body)" and "(Trim)" to keep keys unique.
    Keep Primed behavior unchanged (return items as-is).
    Works with dict-like or object-like line items that at least expose: name/label/title, qty, uom, unit_cost.
    """
    import copy, math

    def _txt_of(li):
        parts = []
        for k in ("item","sku","key","code","name","title","label","description","desc"):
            v = None
            if isinstance(li, dict):
                v = li.get(k)
            else:
                v = getattr(li, k, None)
            if isinstance(v, str):
                parts.append(v.lower())
        return " ".join(parts)

    def _is_coil(li) -> bool:
        t = _txt_of(li)
        return ("coil" in t) or ("coil_roll" in t)

    def _get(li, k, default=None):
        if isinstance(li, dict): return li.get(k, default)
        return getattr(li, k, default)

    def _set(li, k, v):
        if isinstance(li, dict):
            li[k] = v
        else:
            try: setattr(li, k, v)
            except Exception: pass

    def _qty(li) -> float:
        for k in ("qty","quantity","count","units"):
            try:
                v = _get(li, k, None)
                if v is None: continue
                return float(v)
            except Exception:
                continue
        return 0.0

    def _set_qty(li, q: int):
        _set(li, "qty", int(q))

    def _set_uom(li, u: str = "RL"):
        u = (u or "RL")
        if isinstance(li, dict):
            if li.get("uom"): return
        else:
            if getattr(li, "uom", None): return
        _set(li, "uom", u)

    def _set_label(li, text: str):
        # overwrite the first present text-y field; else add .label for dicts
        for k in ("name","title","label","description","desc"):
            val = _get(li, k, None)
            if isinstance(val, str):
                _set(li, k, text); return
        if isinstance(li, dict):
            li["label"] = text
        else:
            try: setattr(li, "name", text)
            except Exception: pass

    fin = (finish or "").strip().lower()
    if fin not in ("colorplus", "woodtone"):
        return line_items

    items = list(line_items or [])
    if not items:
        return items

    # Aggregate coil rows
    coil_rows, coil_total = [], 0.0
    base_template = None
    for li in items:
        if _is_coil(li):
            coil_rows.append(li)
            q = max(0.0, _qty(li))
            coil_total += q
            if base_template is None:
                base_template = li

    if (coil_total <= 0.0) or (not coil_rows) or (base_template is None):
        return items  # nothing to do

    # Prune original coil rows
    pruned = [li for li in items if li not in coil_rows]

    # New per-color quantity
    per_color = int(math.ceil(float(coil_total) / 4.0))
    per_color = max(1, per_color)

    # Base attributes to carry through
    unit_cost = _get(base_template, "unit_cost", _get(base_template, "unit_price", 0.0))
    uom = _get(base_template, "uom", "RL")

    # Build Body & Trim rows with guaranteed-unique labels
    bc = (body_color or "Body").strip()
    tc = (trim_color or "Trim").strip()

    label_body = f"{bc} Trim Coil"
    label_trim = f"{tc} Trim Coil"

    # If colors match, keep both rows but suffix to keep keys unique in maps/tables
    if label_body.strip().lower() == label_trim.strip().lower():
        label_body = f"{label_body} (Body)"
        label_trim = f"{label_trim} (Trim)"

    body_li = copy.deepcopy(base_template)
    _set_qty(body_li, per_color)
    _set_uom(body_li, uom or "RL")
    _set(body_li, "unit_cost", float(unit_cost or 0.0))
    _set_label(body_li, label_body)

    trim_li = copy.deepcopy(base_template)
    _set_qty(trim_li, per_color)
    _set_uom(trim_li, uom or "RL")
    _set(trim_li, "unit_cost", float(unit_cost or 0.0))
    _set_label(trim_li, label_trim)

    pruned.extend([body_li, trim_li])
    return pruned


def _fmt_money(x: float) -> str:
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "$0.00"



# [BM-COMMISSION|helpers|v1]
def commission_rate_from_gross_gm(gross_gm: float) -> float:
    """
    Commission schedule f(g):
      g <= 0.20  → 0
      0.20 < g < 0.30 → g - 0.20   (1:1 reduction from 10% at 30%)
      g >= 0.30 → g / 3
    """
    g = float(gross_gm)
    if g <= 0.20:
        return 0.0
    if g < 0.30:
        return g - 0.20
    return g / 3.0

def commission_default_dollars(revenue: float, cogs: float) -> float:
    """Default commission dollars from revenue & COGS via f(gross GM)."""
    if revenue <= 0.0:
        return 0.0
    g = 1.0 - (float(cogs) / float(revenue))
    rate = commission_rate_from_gross_gm(g)
    return float(revenue) * rate

def solve_revenue_from_commission(comm_dollars: float, cogs: float) -> float:
    """
    Invert the schedule to find revenue given a target commission dollars.
    Piecewise, exact:
      Region 3 (g >= .30): Comm = (Rev - COGS)/3  → Rev = 3*Comm + COGS, valid if g>=.30
      Region 2 (0.20<g<.30): Comm = 0.80*Rev - COGS → Rev = (Comm + COGS)/0.80, valid if .20<g<.30
      Else clamp to 20% GM boundary (Comm==0 there).
    """
    C = float(cogs)
    Comm = max(0.0, float(comm_dollars))
    eps = 1e-9

    # Region 3 candidate
    rev3 = 3.0 * Comm + C
    g3 = 0.0 if rev3 <= 0 else 1.0 - (C / rev3)
    if g3 >= 0.30 - 1e-9:
        return rev3

    # Region 2 candidate
    denom2 = 0.80
    if denom2 > eps:
        rev2 = (Comm + C) / denom2
        g2 = 0.0 if rev2 <= 0 else 1.0 - (C / rev2)
        if 0.20 + 1e-9 < g2 < 0.30 - 1e-9:
            return rev2

    # Clamp to 20% GM boundary (Comm = 0 there)
    return C / max(eps, (1.0 - 0.20))

def solve_revenue_from_profit(profit_dollars: float, cogs: float, overhead_rate: float) -> float:
    """
    Invert profit to revenue across bands, exact and continuous at 30%:
      Region 3 (g >= .30): p = Rev*(2/3 - r) - (2/3)COGS  → Rev = (p + (2/3)C) / ((2/3) - r)
      Region 2 (.20<g<.30): p = Rev*(0.20 - r)            → Rev = p / (0.20 - r)  (independent of C)
      Region 1 (<=.20):     p = Rev*(1 - r) - C           → Rev = (p + C) / (1 - r)
    Tries region 3, then 2, else falls back to region 1.
    """
    p = float(profit_dollars); C = float(cogs); r = float(overhead_rate); eps = 1e-9

    # Region 3
    denom3 = (2.0/3.0) - r
    if abs(denom3) > eps:
        rev3 = (p + (2.0/3.0)*C) / denom3
        g3 = 0.0 if rev3 <= 0 else 1.0 - (C / rev3)
        if g3 >= 0.30 - 1e-9:
            return rev3

    # Region 2
    denom2 = 0.20 - r
    if abs(denom2) > eps:
        rev2 = p / denom2
        g2 = 0.0 if rev2 <= 0 else 1.0 - (C / rev2)
        if 0.20 + 1e-9 < g2 < 0.30 - 1e-9:
            return rev2

    # Region 1
    denom1 = 1.0 - r
    return (p + C) / max(eps, denom1)

    

# -------------------------- Meta Table  --------------------------
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")  
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


# [BM-ID-PARSE|compat-text-first|v2]
def _extract_identity_text_first(pdf_path: str) -> dict:
    """
    Old-behavior identity extraction, but without requiring PyMuPDF:
      1) Read first pages' text via extract_pdf_text()
      2) Call extract_name_and_address(TEXT)
      3) Fallback to extract_name_and_address(PATH) if text parse fails
      4) Normalize fields + build display_title (NAME — Street, City ST ZIP)
    Returns a dict with: name_upper, street_line, city_state_zip, zip_code_safe,
    addr_full, street_only, display_title, raw_text
    """
    # 1) text-first
    text = ""
    try:
        text = extract_pdf_text(pdf_path, max_pages=4) or ""
    except Exception:
        text = ""

    # 2) parse identity from text
    name = street_line = city_state_zip = _zip_hint = ""
    try:
        name, street_line, city_state_zip, _zip_hint = extract_name_and_address(text)
    except Exception:
        name = street_line = city_state_zip = _zip_hint = ""

    # 3) fallback: path-based parse if text parse yielded nothing
    if not (name or street_line or city_state_zip):
        try:
            name, street_line, city_state_zip, _zip_hint = extract_name_and_address(pdf_path)
        except Exception:
            name = street_line = city_state_zip = _zip_hint = ""

    name_upper = (name or "").strip().upper()
    street_line_safe = (street_line or "").strip()
    city_state_zip_safe = (city_state_zip or "").strip()

    # Prefer a ZIP found near a state token in the text; fallback to hint
    zip_code_safe = _best_zip_from_text(text, city_state_zip_safe)

    addr_full = f"{street_line_safe}, {city_state_zip_safe}".strip(", ").strip()
    try:
        street_only = street_line_safe.split(",")[0].strip().title()
    except Exception:
        street_only = street_line_safe.strip().title()

    display_title = _mk_display_title(name_upper, addr_full, zip_code_safe)

    return dict(
        name_upper=name_upper,
        street_line=street_line_safe,
        city_state_zip=city_state_zip_safe,
        zip_code_safe=zip_code_safe,
        addr_full=addr_full,
        street_only=street_only,
        display_title=display_title,
        raw_text=text,
    )



# ------------------- Region canonicalization (ZIP aware) -------------------
def _canonical_region(region_guess: str | None, zip_code: str | None) -> str:
    """
    Normalize into one of: "Metro", "North CO", "Mountains".
    """
    s = (region_guess or "").strip().lower()
    synonyms = {
        "metro": "Metro", "main": "Metro", "denver": "Metro", "front range": "Metro",
        "north": "North CO", "north co": "North CO", "north colorado": "North CO", "noco": "North CO",
        "mountain": "Mountains", "mountains": "Mountains", "mt": "Mountains",
    }
    if s in synonyms:
        return synonyms[s]

    z = (zip_code or "").strip()
    if len(z) >= 3 and z[:3].isdigit():
        p = z[:3]
        if p in ("804", "816"):   # High country & West Slope
            return "Mountains"
        if p in ("805", "806"):   # Fort Collins / Greeley corridor
            return "North CO"
        return "Metro"

    return "Metro"


def _mk_display_title(name_upper: str, address_full: str, zip_code: str) -> str:
    """
    Compose the Jobs-list title as:
      NAME — <street, city ST ZIP>
    - If zip_code is present but not already in address_full, append it.
    - Avoid trailing commas/spaces.
    """
    name = (name_upper or "").strip()
    addr = (address_full or "").strip().strip(",")
    z = (zip_code or "").strip()

    if z and z not in addr:
        # add a space before ZIP if we already have "City, ST"
        addr = (addr + " " + z).strip()

    if addr:
        return f"{name} — {addr}"
    return name



# -------------------------- Drag/drop widget --------------------------
# [BM-DROPAREA|fix-missing-label+white-text|v2]
class DropArea(QWidget):
    """Drag-and-drop target for HOVER PDFs (macOS-safe)."""
    # [HF-DA|__init__|v2] — replaces DropArea.__init__
    def __init__(self, on_pdf_dropped, parent=None):
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
        from PySide6.QtCore import Qt
        super().__init__(parent)
        self.on_pdf_dropped = on_pdf_dropped
        self.setAcceptDrops(True)

        self.label = QLabel("Drop PDF here")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(self.label)

        # Style AFTER label exists
        self.label.setStyleSheet("""
            QLabel {
                border: 1px dashed #888;
                padding: 12px;
                border-radius: 6px;
                font-size: 13px;
            }
        """)


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
        # Prefer PySide6; fall back to PyQt5; else None
        try:
            from PySide6.QtWidgets import QMessageBox
        except Exception:
            try:
                from PyQt5.QtWidgets import QMessageBox  # type: ignore
            except Exception:
                QMessageBox = None  # type: ignore

        try:
            path = ""
            md = e.mimeData() if e else None
            urls = md.urls() if (md and md.hasUrls()) else []

            # Find the first valid local .pdf among all dropped URLs
            for u in urls:
                candidate = ""

                # 1) Normal local file
                if getattr(u, "isLocalFile", lambda: False)():
                    candidate = u.toLocalFile()

                # 2) Try alternate representations (covers odd Desktop names like 'https:hover.to:...pdf')
                if not candidate:
                    reps = []
                    for attr in ("toLocalFile", "toString", "path"):
                        try:
                            v = getattr(u, attr)()
                            if v:
                                reps.append(str(v))
                        except Exception:
                            pass
                    for c in reps:
                        if os.path.exists(c):
                            candidate = c
                            break

                # 3) file:// URL → POSIX path
                if not candidate:
                    try:
                        s = u.toString()
                        if isinstance(s, str) and s.startswith("file://"):
                            from urllib.parse import urlparse, unquote
                            candidate = unquote(urlparse(s).path)
                    except Exception:
                        pass

                if candidate and candidate.lower().endswith(".pdf") and os.path.isfile(candidate):
                    path = candidate
                    break

            # Final validation
            if not (path and os.path.isfile(path) and path.lower().endswith(".pdf")):
                msg = f"Drop ignored; not a local .pdf:\n{path}"
                if QMessageBox:
                    try: QMessageBox.warning(self, "Drop ignored", msg)
                    except Exception: pass
                else:
                    print("WARN:", msg)
                return

            print(f"DEBUG: normalized drop path = {path}")

            # Prefer the injected callback from DropArea(on_pdf_dropped=...)
            cb = getattr(self, "on_pdf_dropped", None)
            if callable(cb):
                cb(path)
                try: e.acceptProposedAction()
                except Exception: pass
                return

            # Fallback: look for common handlers on the parent/window
            parent = self.parent() or self.window()
            for name in ("handle_pdf_drop", "handle_pdf", "open_pdf", "on_drop_pdf", "on_drop", "process_pdf"):
                if hasattr(parent, name):
                    getattr(parent, name)(path)
                    try: e.acceptProposedAction()
                    except Exception: pass
                    return

            raise RuntimeError("No PDF handler found on parent (expected handle_pdf_drop/handle_pdf/open_pdf/…)")

        except Exception as ex:
            import traceback; traceback.print_exc()
            if QMessageBox:
                try: QMessageBox.critical(self, "Drop failed", f"{type(ex).__name__}: {ex}")
                except Exception: pass


# >>> BEGIN PATCH: app.py [BM-LAP-REVEAL|catalog-helper|v1] <<<
def _lap_reveals_from_catalog() -> list[float]:
    """
    Returns a sorted, unique list of lap REVEALS (inches) available in the catalog.
    We infer from plank item keys, e.g. 'plank_8_25_*' (8.25\" width -> ~7.0\" reveal).
    Fallback: common reveals if catalog unavailable.
    """
    reveals: set[float] = set()
    try:
        from core.catalog import load_catalog
        cat = load_catalog()
        items = (cat.raw or {}).get("items", {}) if hasattr(cat, "raw") else {}
        if isinstance(items, dict):
            for key in items.keys():
                # Expect keys like: plank_5_25_* , plank_6_25_* , plank_7_25_* , plank_8_25_* , plank_9_25_* , plank_12_*
                # Map token -> nominal width inches
                # NOTE: Hardie "12" token maps to 11.25" nominal width; others "_X_25" -> X.25 inches.
                if key.startswith("plank_"):
                    after = key[len("plank_"):]
                    parts = after.split("_")
                    if not parts:
                        continue
                    token = parts[0]  # e.g., "8" or "12" or "5"
                    width_in = None
                    try:
                        if len(parts) >= 2 and parts[1] == "25":
                            width_in = float(f"{int(token)}.25")
                        else:
                            # special-case "12" → 11.25" nominal
                            width_in = 11.25 if token == "12" else float(token)
                    except Exception:
                        continue
                    # Convert nominal width to reveal (exposure) ≈ width - 1.25"
                    if width_in is not None:
                        reveal = max(1.0, round(width_in - 1.25, 2))
                        if 1.0 <= reveal <= 12.0:
                            reveals.add(reveal)
    except Exception:
        pass

    if not reveals:
        # Fallback set: 5, 6, 7, 8, 10 inch reveals (typical)
        return [5.0, 6.0, 7.0, 8.0, 10.0]
    return sorted({round(x, 2) for x in reveals})
# >>> END PATCH: app.py [BM-LAP-REVEAL|catalog-helper|v1] <<<


def _build_lap_reveal_selector(parent):
    """
    Returns (widget, get_value, set_value) for a compact 'Lap Reveal' control:
      - A QComboBox pre-populated from _lap_reveals_from_catalog()
      - A 'Custom…' option that shows a QDoubleSpinBox for any value
    """
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QDoubleSpinBox
    from PySide6.QtCore import Qt

    reveals = _lap_reveals_from_catalog()
    reveals_str = [f"{r:.2f}".rstrip("0").rstrip(".") for r in reveals]  # clean like "7" or "7.25"

    row = QWidget(parent)
    hl = QHBoxLayout(row)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(6)

    combo = QComboBox(row)
    for s in reveals_str:
        combo.addItem(s)
    combo.addItem("Custom…")

    spin = QDoubleSpinBox(row)
    spin.setDecimals(2)
    spin.setRange(3.00, 10.00)
    spin.setSingleStep(0.25)
    spin.setSuffix(" in")
    spin.setAlignment(Qt.AlignRight)
    spin.setFixedWidth(120)
    spin.setVisible(False)

    def _sync_visibility():
        is_custom = combo.currentText().strip().lower().startswith("custom")
        spin.setVisible(is_custom)

    combo.currentIndexChanged.connect(_sync_visibility)

    def get_value() -> float:
        txt = combo.currentText().strip().lower()
        if txt.startswith("custom"):
            return float(spin.value())
        try:
            return float(combo.currentText())
        except Exception:
            return float(spin.value())

    def set_value(v: float):
        # try to match an existing option; else drop to custom
        try:
            fmt = f"{float(v):.2f}".rstrip("0").rstrip(".")
        except Exception:
            fmt = "7"
        idx = combo.findText(fmt)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            _sync_visibility()
        else:
            # set custom
            combo.setCurrentIndex(combo.count() - 1)
            spin.setValue(float(v) if v else 7.0)
            _sync_visibility()

    hl.addWidget(combo, 1)
    hl.addWidget(spin, 0)

    return row, get_value, set_value



   

# -------------------------- AdvancedOptionsDialog (clean UI) --------------------------
class AdvancedOptionsDialog(QDialog):
    """
    Quantities & Details — cleaner visual grouping and aligned controls.
    Wires to Questionnaire via load_from_store()/save_to_store().
    """
    applied = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced — Quantities & Details")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._defaults_snapshot = {}   # filled by load_from_store()

        # ---------- main form ----------
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        form.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        form.setContentsMargins(16, 10, 16, 10)

        def _num_le(placeholder=""):
            le = QLineEdit()
            le.setAlignment(Qt.AlignRight)
            if placeholder:
                le.setPlaceholderText(placeholder)
            # REMOVE any fixed width
            sp = le.sizePolicy()
            sp.setHorizontalPolicy(QSizePolicy.Expanding)  # let the field stretch
            le.setSizePolicy(sp)
            le.setMinimumWidth(120)                        # keeps it from getting too tiny
            return le

        def header(txt: str) -> QLabel:
            lbl = QLabel(txt)
            lbl.setStyleSheet("font-weight:600; margin-top:8px;")
            return lbl

        # --- fields ---
        # Siding SF
        self.siding_sf = _num_le("e.g. 1552")
        self.siding_sf.setToolTip("Total wall siding surface area (square feet).")

        # Openings / corners
        self.openings = _num_le("ft or 000'00\"")
        self.openings.setToolTip("Total perimeter of windows/doors in feet (accepts 000'00\" format).")
        self.outside  = _num_le("ft or 000'00\"")
        self.inside   = _num_le("ft or 000'00\"")
        self.outside.setToolTip("Linear feet of outside corners.")
        self.inside.setToolTip("Linear feet of inside corners.")

        # Fascia width (inches)
        self.fascia_w = QSpinBox()
        self.fascia_w.setRange(3, 16)
        self.fascia_w.setSingleStep(1)       # expected increment
        self.fascia_w.setSuffix(" in")
        self.fascia_w.setAlignment(Qt.AlignRight)
        self.fascia_w.setFixedWidth(120)
        self.fascia_w.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # OSB override (sf)
        self.osb_area = QDoubleSpinBox()
        self.osb_area.setDecimals(2)
        self.osb_area.setRange(0.0, 100000.0)
        self.osb_area.setSingleStep(10.0)
        self.osb_area.setSuffix(" sf")
        self.osb_area.setAlignment(Qt.AlignRight)
        self.osb_area.setToolTip("Optional manual override. Leave 0 to auto-calculate.")
        self.osb_area.setFixedWidth(140)
        self.osb_area.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Lap reveal (selector with common reveals + custom)
        self._lap_reveal_row, self._lap_get_reveal, self._lap_set_reveal = _build_lap_reveal_selector(self)

        # Eave/Rake fascia (ft or 000'00")
        self.eave  = _num_le("ft or 000'00\"")
        self.rake  = _num_le("ft or 000'00\"")
        self.eave.setToolTip("Eave fascia length.")
        self.rake.setToolTip("Rake fascia length.")

        # Demo: extra layers
        self.layers = QSpinBox()
        self.layers.setRange(0, 5)
        self.layers.setAlignment(Qt.AlignRight)
        self.layers.setFixedWidth(120)
        self.layers.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Depth toggle — label on left column, bare checkbox on right column
        self.depth_gt24 = QCheckBox()
        self.depth_gt24.setToolTip('Check if soffit depth exceeds 24".')

        # ----- sections / layout -----
        form.addRow(header("Siding"))
        form.addRow("Siding (SF):", self.siding_sf)

        form.addRow(header("Openings & Corners"))
        form.addRow("Openings Perimeter:", self.openings)
        form.addRow("Outside Corners:",   self.outside)
        form.addRow("Inside Corners:",    self.inside)

        form.addRow(header("Soffit & Fascia"))
        form.addRow('Soffit Depth > 24"?', self.depth_gt24)   # aligned like other rows
        form.addRow("Fascia Width:", self.fascia_w)
        form.addRow("Eave Fascia:",  self.eave)
        form.addRow("Rake Fascia:",  self.rake)

        form.addRow(header("Lap Siding"))
        form.addRow("Lap Reveal:", self._lap_reveal_row)

        form.addRow(header("OSB"))
        form.addRow("OSB Area Override:", self.osb_area)

        form.addRow(header("Demo"))
        form.addRow("Extra Layers?", self.layers)

        # ---------- buttons ----------
        btns = QDialogButtonBox(Qt.Horizontal)
        self._btn_reset  = btns.addButton("Reset",  QDialogButtonBox.ActionRole)
        self._btn_return = btns.addButton("Return", QDialogButtonBox.RejectRole)
        self._btn_return.setEnabled(True)
        self._btn_return.setAutoDefault(False)
        self._btn_return.setDefault(False)

        # layout root
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.addLayout(form, 1)
        root.addStretch(1)
        root.addWidget(btns, 0, Qt.AlignBottom)

        # 'Return' closes the dialog
        btns.rejected.connect(self.close)
        # 'Reset' snaps all fields back to the snapshot taken by load_from_store()
        self._btn_reset.clicked.connect(self._reset_to_defaults)
        self.depth_gt24.toggled.connect(self._sync_enablements)

        # Auto-apply: emit on every change so the parent can persist immediately
        self._wire_auto_apply()
        self._sync_enablements()


    # -------- API used by Questionnaire --------
    def set_siding_type(self, siding_text: str):
        pass  # reserved for future dynamic behavior

    def _wire_auto_apply(self):
        from PySide6.QtWidgets import QComboBox, QDoubleSpinBox  # local import for selector wiring

        # QLineEdit fields
        for le in (self.siding_sf, self.openings, self.outside, self.inside, self.eave, self.rake):
            le.textChanged.connect(self._emit_applied)
        # Spinboxes / checkboxes
        self.fascia_w.valueChanged.connect(self._emit_applied)
        self.osb_area.valueChanged.connect(self._emit_applied)
        self.layers.valueChanged.connect(self._emit_applied)
        self.depth_gt24.toggled.connect(self._emit_applied)

        # Lap reveal selector emits via combo/spin changes
        try:
            # the row contains a QComboBox and (conditionally) a QDoubleSpinBox
            for child in self._lap_reveal_row.findChildren((QComboBox, QDoubleSpinBox)):
                try:
                    child.currentIndexChanged.connect(self._emit_applied)  # QComboBox
                except Exception:
                    pass
                try:
                    child.valueChanged.connect(self._emit_applied)          # QDoubleSpinBox
                except Exception:
                    pass
        except Exception:
            pass


    def _emit_applied(self, *_):
        try:
            self.applied.emit()
        except Exception:
            pass

    # -------- persistence --------
    def load_from_store(self, s: dict):
        self.siding_sf.setText(str(s.get("siding_sf", "") or ""))
        self.openings.setText(str(s.get("openings", "") or ""))
        self.outside.setText(str(s.get("outside", "") or ""))
        self.inside.setText(str(s.get("inside", "") or ""))
        self.fascia_w.setValue(int(s.get("fascia_w", 8) or 8))
        self.osb_area.setValue(float(s.get("osb_area", 0) or 0))
        self.eave.setText(str(s.get("eave", "") or ""))
        self.rake.setText(str(s.get("rake", "") or ""))
        self.layers.setValue(int(s.get("layers", 0) or 0))
        self.depth_gt24.setChecked(bool(s.get("depth_gt24", False)))
        try:
            self._lap_set_reveal(float(s.get("lap_reveal_in", 7.0)))
        except Exception:
            self._lap_set_reveal(7.0)

        self._sync_enablements()

        # capture a snapshot used by Reset
        try:
            self._defaults_snapshot = dict(s)
        except Exception:
            self._defaults_snapshot = {}


    def save_to_store(self) -> dict:
        return {
            "siding_sf": self.siding_sf.text().strip(),
            "openings": self.openings.text().strip(),
            "outside": self.outside.text().strip(),
            "inside": self.inside.text().strip(),
            "fascia_w": int(self.fascia_w.value()),
            "osb_area": f"{self.osb_area.value():.2f}",
            "eave": self.eave.text().strip(),
            "rake": self.rake.text().strip(),
            "layers": int(self.layers.value()),
            "depth_gt24": bool(self.depth_gt24.isChecked()),
            "lap_reveal_in": float(self._lap_get_reveal()),
        }


    # -------- internals --------
    def _sync_enablements(self):
        """
        Keep everything enabled; depth toggle is semantic only.
        Force-enable in case any outside code had disabled these.
        """
        for w in (self.openings, self.outside, self.inside,
                  self.eave, self.rake, self.siding_sf,
                  self.fascia_w, self._lap_reveal_row, self.osb_area, self.layers):
            w.setEnabled(True)


    def _reset_to_defaults(self):
        """Restore widgets to the values captured when the dialog was opened."""
        s = self._defaults_snapshot or {}
        self.load_from_store(s)
        self._emit_applied()




# -------------------------- Living Lore (About) --------------------------
LIVE_LORE_PATH = os.path.join(DATA_LORE, "LiveLore.md")
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

# [BM-MATS-ROWHEIGHT|delegate|v1]
from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtCore import QSize

class _FixedRowHeightDelegate(QStyledItemDelegate):
    """Forces a uniform row height in QTableWidget despite sizeHint variance."""
    def __init__(self, row_height: int = 32, parent=None):
        super().__init__(parent)
        self._h = int(row_height)

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(max(1, s.width()), self._h)


    

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


        from PySide6.QtCore import Qt
        self.list = QListWidget()
        self.list.setUniformItemSizes(True)
        self.list.itemClicked.connect(self.open_job)


        # Build right panel (creates self.rightw, self.materials, self.costs, self.results_tree)
        self._setup_right_panel()
        # [BM-COSTS-LOCK|init|v1]
        self._costs_lock = "gm"   # "gm" or "revenue"; switches based on last edit
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

        # [BM-UX|geometry-load|v1]
        from PySide6.QtCore import QSettings
        try:
            s = QSettings("BidMule", "BidMule8")
            if (geo := s.value("main/geometry", None)) is not None:
                self.restoreGeometry(geo)
            if (state := s.value("main/state", None)) is not None:
                self.restoreState(state)
        except Exception:
            pass
            


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


#

    def closeEvent(self, ev):
        # [BM-UX|geometry-save|v1]
        try:
            from PySide6.QtCore import QSettings
            s = QSettings("BidMule", "BidMule8")
            s.setValue("main/geometry", self.saveGeometry())
            s.setValue("main/state", self.saveState())
        except Exception:
            pass

        try:
            try:
                log_event("app", "app_closing", [])
            except Exception:
                pass
            end_session()
            flush(1200)
        finally:
            super().closeEvent(ev)


    # [BM-MATS|rowheight|enforce|v2]
    def _enforce_uniform_material_row_heights(self):
        """
        Force a uniform, fixed row height for Materials so the last row
        never stretches to fill the viewport (e.g., the 12th row).
        """
        try:
            view = getattr(self, "materials", None)
            if not view:
                return

            vh = view.verticalHeader()

            # 1) Never stretch the last row to fill leftover space
            try:
                vh.setStretchLastSection(False)
            except Exception:
                pass

            # 2) Lock row sizing to Fixed and pick a consistent H
            try:
                from PySide6.QtWidgets import QHeaderView  # local import avoids top-level churn
                vh.setSectionResizeMode(QHeaderView.Fixed)
            except Exception:
                pass

            H = int(max(30, vh.defaultSectionSize() or 32))
            vh.setDefaultSectionSize(H)
            vh.setMinimumSectionSize(H)

            # 3) Install a fixed-height delegate once (prevents sizeHint growth)
            if not getattr(self, "_mats_fixed_height_delegate_installed", False):
                try:
                    view.setItemDelegate(_FixedRowHeightDelegate(H, view))
                    self._mats_fixed_height_delegate_installed = True
                except Exception:
                    pass

            # 4) Apply to all current rows
            try:
                view.setWordWrap(False)  # ensure text can’t force row growth
            except Exception:
                pass

            for r in range(view.rowCount()):
                try:
                    view.setRowHeight(r, H)
                except Exception:
                    continue

        except Exception:
            pass




    # [BM-UX-QUESTIONNAIRE|flow|v1]
    def _run_questionnaire_after_parse(self, base_inp: JobInputs, totals: dict, region_guess: str | None):
        try:
            defaults = {
                "region_guess": region_guess or getattr(base_inp, "region", "Metro"),
                "siding_sf": max(float(totals.get("facades_sf") or 0.0), float(totals.get("trim_siding_sf") or 0.0)),
                "eave_fascia": str(totals.get("eave_fascia", 0.0)),
                "rake_fascia": str(totals.get("rake_fascia", 0.0)),
                "openings_perim": str(totals.get("openings_perim", 0.0)),
                "outside": str(totals.get("outside", 0.0)),
                "inside": str(totals.get("inside", 0.0)),
                "body_color": getattr(base_inp, "body_color", "Iron Gray"),
                # Keep warn_corners logic in sync with handle_pdf_drop
                "warn_corners": (float(totals.get("outside", 0.0) or 0.0) > 0.0) and (float(totals.get("inside", 0.0) or 0.0) == 0.0),
            }
            dlg = Questionnaire(self, defaults)
            if not dlg.exec():
                return None
            v = dlg.values()
            return JobInputs(
                customer_name=base_inp.customer_name,
                address=base_inp.address,
                region=v["region"],
                siding_type=v["siding"],
                finish=v["finish"],
                body_color=v["body_color"],
                trim_color=v["trim_color"],
                complexity=v["complexity"],
                demo_required=v["demo"],
                extra_layers=v["layers"],
                substrate=v["substrate"],
                facades_sf=float(v["facades_sf"]),
                trim_siding_sf=float(v["trim_siding_sf"]),
                eave_fascia_ft=float(v["eave_fascia"]),
                rake_fascia_ft=float(v["rake_fascia"]),
                soffit_depth_gt_24=bool(v["depth_gt24"]),
                openings_perimeter_ft=float(v["openings_perim"]),
                outside_corners_ft=float(v["outside"]),
                inside_corners_ft=float(v["inside"]),
                fascia_width_in=int(v["fascia_w"]),
                osb_selected=bool(v["osb_on"]),
                osb_area_override_sf=(float(v["osb_area"]) if v["osb_area"] is not None else 0.0),
                lap_reveal_in=float(v.get("lap_reveal_in", 7.0)),
            )
        except Exception:
            return None


    # [BM-MATS|recompute_scheduled|v2]
    def _recompute_after_material_edit(self):
        self._mats_recompute_scheduled = False
        try:
            view = self.materials
            # Preserve scroll & selection
            vbar = view.verticalScrollBar()
            hbar = view.horizontalScrollBar()
            v_val = vbar.value(); h_val = hbar.value()
            sel   = view.selectedItems()

            # Recompute (may rebuild trade cost; our populate keeps height uniform)
            # IMPORTANT: do not rewrite the Costs baseline when this recompute is due to Materials changes
            self._suppress_next_costs_baseline_reset = True
            self.recompute_pricing()

            # Restore scroll & selection
            vbar.setValue(v_val); hbar.setValue(h_val)
            if sel:
                try:
                    view.setCurrentItem(sel[0])
                except Exception:
                    pass

            self._enforce_uniform_material_row_heights()
        except Exception:
            pass




    def _build_about_dropdown(self):
        """Return a QToolButton with a menu: Siding, Roofing, Gutters (inert for now)."""
        from PySide6.QtWidgets import QToolButton, QMenu
        from PySide6.QtCore import Qt

        btn = QToolButton(self)
        btn.setText("About")  # looks like a normal button 
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn.setPopupMode(QToolButton.InstantPopup)  # click anywhere to open

        m = QMenu(btn)
        m.addAction("Siding")
        m.addAction("Roofing")
        m.addAction("Gutters")
        m.triggered.connect(lambda act: self._on_about_choice(act.text()))
        btn.setMenu(m)
        btn.setFixedHeight(32)  # keep consistent with your other buttons

        return btn

    def _on_about_choice(self, which: str):
        """
        Placeholder — inert by design for now.
        We just show a subtle status message so you can verify the click path.
        """
        try:
            self.statusBar().showMessage(f"About • {which} (coming soon)", 2500)
        except Exception:
            pass



    # ---------- sizing, signal helpers, styles ----------
    def _normalize_window_sizing(self):
        """Classic BitMule layout: 1200x800 window, centered, resizable; crisp tables."""
        try:
            from PySide6.QtGui import QFontMetrics, QGuiApplication
            from PySide6.QtWidgets import QSplitter 

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

        
    def _enforce_band_ratio(self):
        try:
            if not hasattr(self, "_band_row_wrap") or self._band_row_wrap is None:
                return

            total = int(self._band_row_wrap.width())
            if total <= 0:
                return

            # Target 2:1 split
            right_target = max(260, total // 3)

            # Let Materials grow naturally; just cap the right column
            self._right_stack_wrap.setMaximumWidth(right_target)

        except Exception:
            pass

        



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


###
    def _autowire_existing_about(self):
        """
        Connect any existing 'About' action/button to open_about_dialog(), without adding new UI.
        """
        # Probe by existing action type only if it actually exists
        try:
            about_proto = getattr(self, "aboutAction", None)
            if about_proto is not None:
                for act in self.findChildren(type(about_proto)):
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

        # ... keep the generic QAction and QPushButton scans exactly as you have them



#####


#####
 

    # [BM-UI|resizeEvent|v2]
    def resizeEvent(self, ev):
        try:
            super().resizeEvent(ev)
        except Exception:
            pass
        try:
            self._sync_top_band_sizes()   # keeps drop + button widths happy
        except Exception:
            pass
        try:
            self._sync_left_jobs_panel()  # left list hygiene
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

    # [BM-UI-SYNC|top_band_sizes|full-width-rightcol|v10]
    def _sync_top_band_sizes(self):
        """
        Keep the band at a strict 2:1 ratio (Materials : Right stack) and let the
        Right stack widgets (Drop + 2×2 buttons) naturally match the Costs width.
        No hard min/max clamps (prevents the right column from overpowering the left).
        Buttons are equal width via layout stretches.
        """
        try:
            # 1) Reassert 2:1 at the shared grid
            grid_host = getattr(self, "_band_row_wrap", None)
            if grid_host and grid_host.layout():
                grid = grid_host.layout()
                grid.setColumnStretch(0, 2)  # Materials
                grid.setColumnStretch(1, 1)  # Right stack (Drop+Buttons+Costs)

            # 2) Drop box: fill the right column; remove any stale clamps
            if hasattr(self, "drop_w") and self.drop_w:
                sp = self.drop_w.sizePolicy()
                sp.setHorizontalPolicy(QSizePolicy.Expanding)     # <-- fixed
                self.drop_w.setSizePolicy(sp)
                self.drop_w.setMinimumWidth(0)
                self.drop_w.setMaximumWidth(16777215)

            # 3) Button cluster: fill the right column; equalize internal buttons
            if hasattr(self, "btns_cluster") and self.btns_cluster:
                sp = self.btns_cluster.sizePolicy()
                sp.setHorizontalPolicy(QSizePolicy.Expanding)     # <-- fixed
                self.btns_cluster.setSizePolicy(sp)
                self.btns_cluster.setMinimumWidth(0)
                self.btns_cluster.setMaximumWidth(16777215)

                lay = self.btns_cluster.layout()
                if lay:
                    lay.setColumnStretch(0, 1)
                    lay.setColumnStretch(1, 1)

                for b in getattr(self, "_btns_all", ()):
                    try:
                        spb = b.sizePolicy()
                        spb.setHorizontalPolicy(QSizePolicy.Expanding)  # <-- fixed
                        b.setSizePolicy(spb)
                        b.setMinimumWidth(0)
                        b.setMaximumWidth(16777215)
                    except Exception:
                        pass

            # (Costs table remains Stretch in its Value column; it dictates the right column width.)
        except Exception as e:
            try:
                _dbg(e, "Main._sync_top_band_sizes")
            except Exception:
                pass



#####
    # ---------- Styling: match Labor header look + compact header height ----------

    # [BM-STYLE-UNIFY|native|v2]
    def _restyle_tables_once(self):
        """
        Unify visual style: use native palette across Materials, Costs, and Labor.
        - Clear any hard-coded QSS on tables
        - Compact, consistent headers
        - Keep Δ column widths as configured in each populate
        """
        try:
            headers = []
            if hasattr(self, "costs") and self.costs:
                # Clear custom styles for native look
                self.costs.setStyleSheet("")
                headers.append(self.costs.horizontalHeader())
                self.costs.verticalHeader().setVisible(False)
                self.costs.setShowGrid(True)

            if hasattr(self, "materials") and self.materials:
                self.materials.setStyleSheet("")
                headers.append(self.materials.horizontalHeader())
                self.materials.verticalHeader().setVisible(False)
                self.materials.setShowGrid(True)

            if hasattr(self, "results_tree") and self.results_tree:
                # Keep labor native; minimal branch styling
                self.results_tree.setRootIsDecorated(False)
                self.results_tree.setStyleSheet("")  # native
                headers.append(self.results_tree.header())

            for h in headers:
                h.setStyleSheet("")  # native header
                h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                try:
                    h.setFixedHeight(24)
                except Exception:
                    pass

        except Exception:
            pass

 

    # [HF-CORE|status+drop|v1] — add inside Main after _wire_signals, before _setup_drop_and_banner
    def _status(self, msg: str):
        """Non-fatal UI+console status helper."""
        try:
            sb = self.statusBar()  # QMainWindow API
            if sb:
                sb.showMessage(msg, 3000)
        except Exception:
            pass
        try:
            print(f"DEBUG: {msg}")
        except Exception:
            pass



    # [HF-SIG|helpers+stubs|v1]
    def _safe_disconnect(self, signal, slot):
        """Disconnect if connected; ignore if not."""
        try:
            signal.disconnect(slot)
        except Exception:
            try:
                signal.disconnect()
            except Exception:
                pass

    def _wire_signals(self):
        """Connect signals once using UniqueConnection; no pre-disconnect (avoids warnings)."""
        from PySide6.QtCore import Qt

        # Costs table signals
        if hasattr(self, "costs") and self.costs:
            if hasattr(self, "on_costs_cell_changed"):
                try:
                    self.costs.cellChanged.connect(self.on_costs_cell_changed, Qt.ConnectionType.UniqueConnection)
                except Exception:
                    pass
            if hasattr(self, "_on_costs_delta_clicked"):
                try:
                    self.costs.cellClicked.connect(self._on_costs_delta_clicked, Qt.ConnectionType.UniqueConnection)
                except Exception:
                    pass

        # Materials table signals
        view = getattr(self, "materials", None)
        if view:
            if hasattr(self, "_on_materials_item_changed"):
                try:
                    view.itemChanged.connect(self._on_materials_item_changed, Qt.ConnectionType.UniqueConnection)
                except Exception:
                    pass
            if hasattr(self, "_on_materials_delta_clicked"):
                try:
                    view.cellClicked.connect(self._on_materials_delta_clicked, Qt.ConnectionType.UniqueConnection)
                except Exception:
                    pass





    def reset_costs_to_baseline(self):
        """Reload all costs from baseline dict if available."""
        from PySide6.QtWidgets import QTableWidgetItem
        try:
            baseline = getattr(self, "_costs_baseline", {})
            if not baseline or not hasattr(self, "costs") or not self.costs:
                return
            self.costs.blockSignals(True)
            name_col = 0
            value_col = 1
            for r in range(self.costs.rowCount()):
                key_item = self.costs.item(r, name_col)
                key = key_item.text().strip() if key_item else ""
                if not key:
                    continue
                if key in baseline:
                    self.costs.setItem(r, value_col, QTableWidgetItem(f"{baseline[key]:,.2f}"))
        except Exception:
            pass
        finally:
            try:
                self.costs.blockSignals(False)
            except Exception:
                pass
        try:
            self._refresh_material_total_pill(None)
        except Exception:
            pass



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
        Controls the transparent warning banner at the top of the right pane.
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

    ###
    # [UI|helpers|total-pill & parsed-btn|v4]
    def _total_pill_widget(self):
        """
        Return the canonical 'materials total' pill QLabel regardless of which
        attribute earlier code uses.
        """
        w = getattr(self, "_mat_total_pill", None)
        if w is None:
            w = getattr(self, "_materials_total_pill", None)
            if w is not None:
                self._mat_total_pill = w
        else:
            self._materials_total_pill = w
        return w


    # [BM-DELTA-RESET|helpers]
    def _reset_materials_to_defaults(self):
        """
        Rebuild materials from engine output (idempotent), apply coil split,
        refresh baselines, and repaint the materials table.
        """
        if not getattr(self, "last_inputs", None) or not getattr(self, "last_outputs", None):
            return

        trade = price_trade("Siding", self.last_inputs, self.last_outputs)
        trade = _apply_coil_split(
            trade,
            getattr(self.last_inputs, "finish", ""),
            getattr(self.last_inputs, "body_color", ""),
            getattr(self.last_inputs, "trim_color", "")
        )

        # Refresh baselines from the computed lines
        self.baseline_unit_costs = {li.name: li.unit_cost for li in trade.line_items}
        self._materials_baseline = {li.name: int(round(li.qty)) for li in trade.line_items}
        self._materials_unit_cost = dict(self.baseline_unit_costs)

        # Repaint materials and total pill
        self.populate_materials_table(trade)
        try:
            self._refresh_material_total_pill(trade)
        except Exception:
            pass

        # Keep the last trade around for downstream UI
        self._last_trade_cost = trade

    

    def _set_parsed_totals_visible(self, visible: bool):
        """Keep for compatibility; button is now always present, but this won't hurt."""
        try:
            btn = getattr(self, "_parsed_btn", None)
            if btn is not None:
                btn.setVisible(bool(visible))
        except Exception:
            pass


    # --- Board & Batten hygiene: keep generic 'siding sf' out of baselines ---
    def _is_board_and_batten(self) -> bool:
        try:
            st = (getattr(self, "last_inputs", None) and getattr(self.last_inputs, "siding_type", "")) or ""
            return st.strip().lower() in ("board & batten", "board and batten", "board &amp; batten")
        except Exception:
            return False

    # [BM-BB-PURGE|guard|v2]
    def _purge_generic_siding_from_baselines(self) -> None:
        """
        Remove the generic 'siding sf' style keys ONLY if a true replacement exists
        (e.g., Lap planks or B&B panel/batten items). Otherwise, keep the generic
        row so Materials never goes blank for Board & Batten.
        """
        try:
            bad = {"siding sf", "siding_sf", "siding sqft", "siding_sqft"}

            # Collect known item keys across our caches/baselines
            baseline_keys = set((getattr(self, "_materials_baseline", {}) or {}).keys())
            unit_cost_keys = set((getattr(self, "baseline_unit_costs", {}) or {}).keys())
            live_unit_keys = set((getattr(self, "_materials_unit_cost", {}) or {}).keys())
            all_keys = {str(k or "") for k in (baseline_keys | unit_cost_keys | live_unit_keys)}

            # Do we have a concrete replacement for generic siding?
            has_plank_substitution = any(k.startswith("plank_") for k in all_keys)
            has_bb_substitution = any(k in ("bb_panel_4x10", "bb_batten_12ft") for k in all_keys)
            has_replacement = has_plank_substitution or has_bb_substitution

            if not has_replacement:
                # Keep generic rows; nothing to purge yet.
                return

            # Purge generic keys now that we have real parts
            for k in list(getattr(self, "_materials_baseline", {}).keys()):
                if (k or "").strip().lower() in bad:
                    self._materials_baseline.pop(k, None)

            try:
                for k in list((getattr(self, "baseline_unit_costs", {}) or {}).keys()):
                    if (k or "").strip().lower() in bad:
                        self.baseline_unit_costs.pop(k, None)
            except Exception:
                pass

            try:
                muc = getattr(self, "_materials_unit_cost", {})
                for k in list(muc.keys()):
                    if (k or "").strip().lower() in bad:
                        muc.pop(k, None)
            except Exception:
                pass
        except Exception:
            pass



    def _refresh_material_total_pill(self, payload=None):
        """
        Update the 'Total' pill, preferring the Costs grid:
          1) 'Revenue Target' (primary)
          2) 'Material Cost' (fallback)
          3) Sum Ext. Cost from Materials table (fallback)
          4) Fallback to payload (trade_cost-like object or dict)

        This makes the pill auto-reflect edits to GM/Profit/Commission/Revenue and also
        “snap back” when Δ resets the Costs grid to baseline.
        """
        try:
            # Resolve the canonical pill label
            lbl = self._total_pill_widget() if hasattr(self, "_total_pill_widget") else getattr(self, "_mat_total_pill", None)
            if not lbl:
                return

            def _money_to_float(s: str) -> float:
                try:
                    return float((s or "").replace("$", "").replace(",", "").strip())
                except Exception:
                    return 0.0

            total = None

            # 1) Prefer 'Revenue Target' from the Costs grid
            ctbl = getattr(self, "costs", None)
            if ctbl and ctbl.rowCount() > 0:
                for r in range(ctbl.rowCount()):
                    ki = ctbl.item(r, 0)
                    vi = ctbl.item(r, 1)
                    if ki and vi and (ki.text() or "").strip() == "Revenue Target":
                        total = _money_to_float(vi.text())
                        break

            # 2) Fallback: 'Material Cost' from the grid
            if total is None and ctbl and ctbl.rowCount() > 0:
                for r in range(ctbl.rowCount()):
                    ki = ctbl.item(r, 0)
                    vi = ctbl.item(r, 1)
                    if ki and vi and (ki.text() or "").strip() == "Material Cost":
                        total = _money_to_float(vi.text())
                        break

            # 3) Fallback: sum Ext. Cost from the Materials table
            if total is None:
                total = 0.0
                mt = getattr(self, "materials", None)
                if mt and mt.rowCount() > 0:
                    ext_col = 4
                    try:
                        for i in range(mt.columnCount()):
                            hh = mt.horizontalHeaderItem(i)
                            if hh and (hh.text() or "").strip().lower().startswith("ext"):
                                ext_col = i
                                break
                    except Exception:
                        pass
                    for r in range(mt.rowCount()):
                        it = mt.item(r, ext_col)
                        if it:
                            total += _money_to_float(it.text())

            # 4) Fallback: payload (trade_cost-like or dict)
            if (total is None or total <= 0.0) and payload is not None:
                try:
                    # trade_cost-like with .line_items
                    if hasattr(payload, "line_items"):
                        total = 0.0
                        for li in getattr(payload, "line_items", []):
                            qty  = float(getattr(li, "qty", 0.0) or 0.0)
                            unit = float(getattr(li, "unit_cost", 0.0) or 0.0)
                            ext  = getattr(li, "ext_cost", qty * unit)
                            total += float(ext or 0.0)
                    # dict: prefer 'material_cost'; else sum its line_items
                    elif isinstance(payload, dict):
                        total = float(payload.get("material_cost", 0.0) or 0.0)
                        if total <= 0.0:
                            for li in payload.get("line_items", []):
                                qty  = float(li.get("qty", 0.0) or 0.0)
                                unit = float(li.get("unit_cost", 0.0) or 0.0)
                                ext  = li.get("ext_cost", qty * unit)
                                total += float(ext or 0.0)
                except Exception:
                    pass

            # Paint
            lbl.setText(f"Revenue: ${max(0.0, float(total or 0.0)):,.2f}")
            lbl.setVisible(True)
            try:
                lbl.setMinimumHeight(36)
                lbl.setMaximumHeight(36)
            except Exception:
                pass

        except Exception:
            # Fail-safe
            try:
                lbl = self._total_pill_widget() if hasattr(self, "_total_pill_widget") else getattr(self, "_mat_total_pill", None)
                if lbl:
                    lbl.setText("Revenue: $0.00")
                    lbl.setVisible(True)
            except Exception:
                pass







    # [200|ui|_setup_right_panel|v7] — mirrored top rows so Materials & Costs bottoms align; totals pill wired
    def _setup_right_panel(self):
        from PySide6.QtWidgets import (
            QWidget, QLabel, QPushButton, QGridLayout, QVBoxLayout, QHBoxLayout,
            QTableWidget, QHeaderView, QTreeWidget, QSizePolicy
        )
        from PySide6.QtCore import Qt, QTimer

        # ── Drop zone + warning banner ─────────────────────────────────────────────
        drop_w, warn_lbl = self._setup_drop_and_banner()
        self.drop_w = drop_w

        # ── Buttons (order + style) ───────────────────────────────────────────────
        parsed_btn  = QPushButton("Parsed Totals")
        catalog_btn = QPushButton("Catalog")
        open_btn    = QPushButton("Open PDF")

        # NEW: About dropdown styled like the other buttons
        about_dd = self._build_about_dropdown()

        # Style both QPushButton and QToolButton the same
        btn_css = (
            "QPushButton, QToolButton {"
            "  border: 1px solid #b9c0c7;"
            "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f4f6f8, stop:1 #e9edf2);"
            "  border-radius: 6px; padding: 6px 12px; font-weight: 600; color: #111;"
            "}"
            "QPushButton:pressed, QToolButton:pressed {"
            "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #e6ebf1, stop:1 #dbe2ea);"
            "}"
        )

        for b in (parsed_btn, catalog_btn, open_btn, about_dd):
            b.setStyleSheet(btn_css)
            sp = b.sizePolicy()
            sp.setHorizontalPolicy(QSizePolicy.Expanding)
            sp.setHorizontalStretch(1)
            b.setSizePolicy(sp)

        parsed_btn.clicked.connect(self.open_totals_dialog)
        catalog_btn.clicked.connect(self.open_catalog_dialog)
        open_btn.clicked.connect(self.open_pdf_dialog)

        S = 8  # uniform spacing
        btn_grid = QGridLayout()
        btn_grid.setContentsMargins(0, 0, 0, 0)
        btn_grid.setHorizontalSpacing(S)
        btn_grid.setVerticalSpacing(S)
        # Order: top row (Parsed, Catalog) / bottom row (Open PDF, About ▼)
        btn_grid.addWidget(parsed_btn,  0, 0)
        btn_grid.addWidget(catalog_btn, 0, 1)
        btn_grid.addWidget(open_btn,    1, 0)
        btn_grid.addWidget(about_dd,    1, 1)
        btn_grid.setColumnStretch(0, 1)
        btn_grid.setColumnStretch(1, 1)

        btns_cluster = QWidget()
        btns_cluster.setLayout(btn_grid)
        sp = btns_cluster.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Expanding)
        btns_cluster.setSizePolicy(sp)

        self.btns_cluster = btns_cluster
        # keep reference list for sizing; add about_dd in place of old about_btn
        self._btns_all = (parsed_btn, catalog_btn, open_btn, about_dd)
        self._btn_spacing = S


        # ── Materials table ───────────────────────────────────────────────────────
        self.materials = QTableWidget(0, 6)
        self.materials.setHorizontalHeaderLabels(["Material", "Qty", "UOM", "Unit Cost", "Ext. Cost", "Δ"])
        mh = self.materials.horizontalHeader()
        mh.setMinimumSectionSize(28)
        mh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        mh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        mh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        mh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        mh.setSectionResizeMode(4, QHeaderView.Stretch)
        mh.setSectionResizeMode(5, QHeaderView.Fixed);   mh.resizeSection(5, 28)
        self.materials.verticalHeader().setDefaultSectionSize(32)
        self.materials.verticalHeader().setMinimumSectionSize(30)
        self.materials.verticalHeader().setVisible(False)
        self.materials.setShowGrid(True)

        # ── Costs table ───────────────────────────────────────────────────────────
        self.costs = QTableWidget(0, 3)
        self.costs.setHorizontalHeaderLabels(["Cost Metric", "Value", "Δ"])
        ch = self.costs.horizontalHeader()
        ch.setMinimumSectionSize(28)
        ch.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        ch.setSectionResizeMode(1, QHeaderView.Stretch)   # Value expands
        ch.setSectionResizeMode(2, QHeaderView.Fixed); ch.resizeSection(2, 28)
        self.costs.verticalHeader().setDefaultSectionSize(32)
        self.costs.verticalHeader().setMinimumSectionSize(30)
        self.costs.verticalHeader().setVisible(False)
        self.costs.setShowGrid(True)

        # ── Pills row: Reset (fills Materials width) | Total (always visible) ────
        pill_btn_css = (
            "QPushButton { border: 1px solid #b9c0c7; "
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f4f6f8, stop:1 #e9edf2); "
            "border-radius: 6px; padding: 6px 14px; font-weight: 600; color:#111; }"
        )

        pill_lbl_css = (
            "QLabel {"
            "  border: 1px solid #b9c0c7;"
            "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f4f6f8, stop:1 #e9edf2);"
            "  border-radius: 6px;"
            "  padding: 6px 14px;"
            "  font-weight: 700;"
            "  color: #111;"
            "}"
        )

        

        if not hasattr(self, "reset_hover_rb"):
            self.reset_hover_rb = QPushButton("Reset to Default")
            self.reset_hover_rb.clicked.connect(self._reset_materials_to_hover)
        self.reset_hover_rb.setStyleSheet(pill_btn_css)
        self.reset_hover_rb.setFixedHeight(36)
        sp = self.reset_hover_rb.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Expanding)
        self.reset_hover_rb.setSizePolicy(sp)

        if not hasattr(self, "_mat_total_pill"):
            self._mat_total_pill = QLabel("Total: $0.00")
        else:
            self._mat_total_pill.setText("Total: $0.00")
        self._mat_total_pill.setStyleSheet(pill_lbl_css)
        self._mat_total_pill.setFixedHeight(36)
        self._mat_total_pill.setAlignment(Qt.AlignCenter)  # reliable centering
        self._mat_total_pill.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._mat_total_pill.setVisible(True)

        # Back-compat: keep the alias so older code paths hit the same widget
        self._materials_total_pill = self._mat_total_pill


        left_pill_wrap  = QWidget()
        lp = QHBoxLayout(left_pill_wrap)
        lp.setContentsMargins(0,0,0,0)
        lp.addWidget(self.reset_hover_rb, 1)

        right_pill_wrap = QWidget()
        rp = QHBoxLayout(right_pill_wrap)
        rp.setContentsMargins(0,0,0,0)
        rp.addWidget(self._mat_total_pill, 1)


        # ── Right stack: Costs label → hint → Costs table ────────────────────────
        right_col_layout = QVBoxLayout()
        right_col_layout.setContentsMargins(0, 0, 0, 0)
        right_col_layout.setSpacing(S)

        costs_lbl = QLabel("Costs")
        costs_lbl.setStyleSheet("font-weight:600;")
        right_col_layout.addWidget(costs_lbl, 0)
        right_col_layout.addWidget(self.costs, 1)

        right_stack_wrap = QWidget()
        right_stack_wrap.setLayout(right_col_layout)
        sp = right_stack_wrap.sizePolicy()
        sp.setHorizontalStretch(1)
        right_stack_wrap.setSizePolicy(sp)

        # ── Materials wrapper ─────────────────────────────────────────────────────
        mats_col = QVBoxLayout()
        mats_col.setContentsMargins(0, 0, 0, 0)
        mats_col.setSpacing(6)
        mats_lbl = QLabel("Materials")
        mats_lbl.setStyleSheet("font-weight:600;")
        mats_col.addWidget(mats_lbl, 0)
        mats_col.addWidget(self.materials, 1)
        mats_wrap = QWidget()
        mats_wrap.setLayout(mats_col)
        sp = mats_wrap.sizePolicy()
        sp.setHorizontalStretch(2)
        mats_wrap.setSizePolicy(sp)

        # ── Shared grid using row-span: Materials spans Drop+Buttons+Costs ─────
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        # Fix drop height (compact) and buttons height
        DROP_H = max(110, self.drop_w.sizeHint().height() // 2)
        self.drop_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.drop_w.setFixedHeight(DROP_H)

        btn_row_h = max(44, btns_cluster.sizeHint().height())
        btns_cluster.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btns_cluster.setFixedHeight(btn_row_h)

        # Right column: Drop (row 0), Buttons (row 1), Costs stack (row 2)
        grid.addWidget(self.drop_w,         0, 1)
        grid.addWidget(btns_cluster,        1, 1)
        grid.addWidget(right_stack_wrap,    2, 1)

        # LEFT: Materials spans rows 0..2 so it gets the full height of those rows
        grid.addWidget(mats_wrap,           0, 0, 3, 1)

        # Pill row (row 3) shared across both columns
        grid.addWidget(left_pill_wrap,      3, 0)
        grid.addWidget(right_pill_wrap,     3, 1)

        grid.setColumnStretch(0, 2)   # Materials wider
        grid.setColumnStretch(1, 1)   # Right stack narrower
        grid.setRowStretch(0, 0)      # drop fixed
        grid.setRowStretch(1, 0)      # buttons fixed
        grid.setRowStretch(2, 1)      # tables eat remaining height
        grid.setRowStretch(3, 0)      # pills fixed

        grid_wrap = QWidget()
        grid_wrap.setLayout(grid)


        # keep refs for sizing sync (if you use them elsewhere)
        self._band_row_wrap = grid_wrap
        self._mats_wrap = mats_wrap
        self._right_stack_wrap = right_stack_wrap


        # First paint of Total pill (safe even before a job is loaded)
        try:
            self._refresh_material_total_pill(None)
        except Exception:
            pass


        # ── Labor Payout ─────────────────────────────────────────────────────────
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Component / Rate", "Amount"])
        rvh = self.results_tree.header()
        rvh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        rvh.setSectionResizeMode(1, QHeaderView.Stretch)
        self.results_tree.setRootIsDecorated(True)

        # ── Compose right pane ───────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setContentsMargins(6, 6, 6, 6)
        right.setSpacing(10)
        right.addWidget(warn_lbl, 0)
        right.addWidget(grid_wrap, 3)
        right.addWidget(QLabel("Labor Payout"), 0)
        right.addWidget(self.results_tree, 2)

        self.rightw = QWidget()
        self.rightw.setLayout(right)



    # [BM-UI-SYNC|normalize_top_band|v1]
    def _normalize_top_band_alignment(self):
        """
        One-shot post-build normalization so the drop box and 2×2 button cluster
        anchor to the left boundary of the right column container.
        """
        try:
            right_col = getattr(self, "drop_w", None)
            if right_col is None:
                return
            right_col = right_col.parentWidget()
            if right_col is None or right_col.layout() is None:
                return
            rlay = right_col.layout()
            rlay.setAlignment(self.drop_w, Qt.AlignTop | Qt.AlignLeft)
            rlay.setAlignment(self.btns_cluster, Qt.AlignTop | Qt.AlignLeft)

            sp = right_col.sizePolicy()
            sp.setHorizontalPolicy(QSizePolicy.Expanding)
            right_col.setSizePolicy(sp)

            # Re-run sizing once with the corrected alignment.
            QTimer.singleShot(0, self._sync_top_band_sizes)
        except Exception:
            pass


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
        self.drop.setFixedHeight(110)  # was 220 → 50% height

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
    
    # [220|ui|_apply_layout_proportions] Correct stretch using actual widgets
    def _apply_layout_proportions(self):
        try:
            # Horizontal: already enforced in _setup_right_panel via band_row with stretch 2:1
            # Vertical: band row (tables) : labor = 2 : 1
            right = self.rightw.layout() if hasattr(self, "rightw") else None
            if right and hasattr(self, "_band_row_wrap"):
                i_band = right.indexOf(self._band_row_wrap)
                i_labor = right.indexOf(self.results_tree)
                if i_band >= 0:
                    right.setStretch(i_band, 2)
                if i_labor >= 0:
                    right.setStretch(i_labor, 1)

            # Main splitter: left jobs : right content ≈ 1 : 3
            if hasattr(self, "main_split"):
                self.main_split.setStretchFactor(0, 1)
                self.main_split.setStretchFactor(1, 3)
                if not getattr(self, "_main_split_sized_once", False):
                    self.main_split.setSizes([360, max(900, self.width() - 360)])
                    self._main_split_sized_once = True

            # Sensible first-paint sizing
            if hasattr(self, "costs"): self.costs.resizeColumnsToContents()
            if hasattr(self, "materials"): self.materials.resizeColumnsToContents()
        except Exception:
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

        try:
            if self._is_board_and_batten():
                self._purge_generic_siding_from_baselines()
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


    # [BM-PILLS|ensure|v3]
    def _ensure_total_pill(self):
        """Create one canonical Total pill, keep a compat alias, and ensure it's visible."""
        from PySide6.QtWidgets import QLabel, QSizePolicy

        if getattr(self, "_mat_total_pill", None) is None:
            self._mat_total_pill = QLabel("Total: $0.00")
            self._mat_total_pill.setVisible(True)
            # same style you already use for the pill
            self._mat_total_pill.setStyleSheet(
                "QLabel {"
                "  border: 1px solid #b9c0c7;"
                "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 transparent, stop:1 #f6f8fa);"
                "  border-radius: 6px;"
                "  padding: 6px 14px;"
                "  font-weight: 700;"
                "  qproperty-alignment: 'AlignCenter';"
                "}"
            )
            self._mat_total_pill.setFixedHeight(36)
            self._mat_total_pill.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Back-compat alias so old code that references _materials_total_pill still updates the same widget
        self._materials_total_pill = self._mat_total_pill


        

    # [BM-PDF-LATENCY|open_dialog|v1]
    @lore_guard("open pdf dialog failure", severity="low")
    def open_pdf_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select HOVER PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        # Yield back to event loop, then start heavy work
        QTimer.singleShot(0, lambda p=path: self.handle_pdf_drop(p))
        

    # [BM-PARSED-QUESTIONNAIRE|open_totals_dialog|v5]
    @lore_guard("open totals dialog failure", severity="low")
    def open_totals_dialog(self):
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
            QPushButton, QHeaderView, QLabel, QMessageBox
        )

        dlg = QDialog(self)
        dlg.setWindowTitle("Parsed Totals (from HOVER)")
        lay = QVBoxLayout(dlg)

        # --- table ---------------------------------------------------------
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

        def _populate_table(t: dict | None):
            tbl.setRowCount(0)
            keys = ["siding_sf_single","eave_fascia","rake_fascia","openings_perim","outside","inside"]
            labels = {
                "siding_sf_single": "Siding (Facades + Trim)",
                "eave_fascia": "Eave Fascia Length",
                "rake_fascia": "Rake Fascia Length",
                "openings_perim": "Openings Perimeter",
                "outside": "Outside Corners",
                "inside": "Inside Corners",
            }
            siding_sf_single = 0.0
            if t:
                try:
                    siding_sf_single = max(float(t.get("facades_sf", 0.0)),
                                           float(t.get("trim_siding_sf", 0.0)))
                except Exception:
                    siding_sf_single = 0.0

            values = {
                "siding_sf_single": siding_sf_single,
                "eave_fascia": float((t or {}).get("eave_fascia", 0.0)),
                "rake_fascia": float((t or {}).get("rake_fascia", 0.0)),
                "openings_perim": float((t or {}).get("openings_perim", 0.0)),
                "outside": float((t or {}).get("outside", 0.0)),
                "inside": float((t or {}).get("inside", 0.0)),
            }

            for k in keys:
                r = tbl.rowCount()
                tbl.insertRow(r)
                tbl.setItem(r, 0, QTableWidgetItem(labels[k]))
                tbl.setItem(r, 1, QTableWidgetItem(str(values[k])))
                tbl.setItem(r, 2, QTableWidgetItem("SF" if k == "siding_sf_single" else UOMS.get(k, "")))

            tbl.resizeColumnsToContents()

        totals = getattr(self, "last_totals", {}) or {}
        _populate_table(totals)

        # --- helpers (scoped) --------------------------------
        def _val_for(label_text: str) -> float:
            for r in range(tbl.rowCount()):
                key_item = tbl.item(r, 0)
                val_item = tbl.item(r, 1)
                if key_item and val_item and (key_item.text() or "") == label_text:
                    try:
                        return float(val_item.text())
                    except Exception:
                        return 0.0
            return 0.0

        def do_reparse():
            """Re-parse from the last saved raw PDF text (no extra popups beyond errors)."""
            try:
                text_path = os.path.join(JOBS_DIR, "last_pdf_text.txt")
                if not os.path.exists(text_path):
                    QMessageBox.warning(dlg, "Not Found", "No last_pdf_text.txt available to re-parse.")
                    return
                with open(text_path, "r", encoding="utf-8") as f:
                    text = f.read()
                totals2 = extract_hover_totals(text)
                self.last_totals = totals2
                _populate_table(totals2)
            except Exception as e:
                QMessageBox.critical(dlg, "Re-parse Failed", str(e))

        def do_questionnaire():
            """Close this dialog, open Questionnaire with these values, and recompute — no status popup."""
            if not getattr(self, "last_inputs", None):
                QMessageBox.warning(dlg, "No Job", "Open a job first (drop a HOVER PDF).")
                return

            # Gather defaults from the table + current job context (labels now match the table)
            defaults = {
                "region_guess": getattr(self.last_inputs, "region", "Metro"),
                "siding_sf": _val_for("Siding (Facades + Trim)"),
                "eave_fascia": str(_val_for("Eave Fascia Length")),
                "rake_fascia": str(_val_for("Rake Fascia Length")),
                "openings_perim": str(_val_for("Openings Perimeter")),
                "outside": str(_val_for("Outside Corners")),
                "inside": str(_val_for("Inside Corners")),
                "body_color": getattr(self.last_inputs, "body_color", "Iron Gray"),
                # Keep warn_corners logic in sync with handle_pdf_drop
                "warn_corners": (_val_for("Outside Corners") > 0.0) and (_val_for("Inside Corners") == 0.0),
            }

            # IMPORTANT: close the Parsed Totals dialog *before* opening Questionnaire
            dlg.accept()

            q = Questionnaire(self, defaults)
            if q.exec() != QDialog.Accepted:
                return
            v = q.values()
            # after v = q.values()
            li = self.last_inputs
            new_inp = JobInputs(
                customer_name=li.customer_name,
                address=li.address,
                region=v.get("region", getattr(li, "region", "Metro")),
                siding_type=v.get("siding", getattr(li, "siding_type", "Lap")),
                finish=v.get("finish", getattr(li, "finish", "ColorPlus")),
                body_color=v.get("body_color", getattr(li, "body_color", "Iron Gray")),
                trim_color=v.get("trim_color", getattr(li, "trim_color", "Arctic White")),
                complexity=v.get("complexity", getattr(li, "complexity", "Low")),
                demo_required=bool(v.get("demo", getattr(li, "demo_required", True))),
                extra_layers=int(v.get("layers", getattr(li, "extra_layers", 0))),
                substrate=v.get("substrate", getattr(li, "substrate", "Wood")),
                facades_sf=float(v.get("facades_sf", v.get("siding_sf", 0.0) or 0.0)),
                trim_siding_sf=float(v.get("trim_siding_sf", 0.0)),
                eave_fascia_ft=float(v.get("eave_fascia", v.get("eave", 0.0) or 0.0)),
                rake_fascia_ft=float(v.get("rake_fascia", v.get("rake", 0.0) or 0.0)),
                soffit_depth_gt_24=bool(v.get("depth_gt24", False)),
                openings_perimeter_ft=float(v.get("openings_perim", v.get("openings", 0.0) or 0.0)),
                outside_corners_ft=float(v.get("outside", 0.0)),
                inside_corners_ft=float(v.get("inside", 0.0)),
                fascia_width_in=int(v.get("fascia_w", getattr(li, "fascia_width_in", 8))),
                osb_selected=bool(v.get("osb_on", getattr(li, "osb_selected", False))),
                osb_area_override_sf=(float(v["osb_area"]) if v.get("osb_area") not in (None, "") else 0.0),
                lap_reveal_in=float(v.get("lap_reveal_in", getattr(li, "lap_reveal_in", 7.0))),
            )



            # Compute via wrapper, set baselines, refresh UI — no messagebox
            new_out = compute_estimate_wrapper(new_inp)
            self.last_inputs  = new_inp
            self.last_outputs = new_out

            try:
                tc = price_trade("Siding", self.last_inputs, self.last_outputs)
                self.baseline_unit_costs = {li.name: li.unit_cost for li in tc.line_items}
                self._materials_baseline  = {li.name: int(round(li.qty)) for li in tc.line_items}
                self._materials_unit_cost = dict(self.baseline_unit_costs)
            except Exception:
                pass

            # Clear manual cost overrides on shape change
            self._user_cost_overrides = {}

            # Single authoritative recompute (no extra popups)
            self.recompute_pricing()

        # --- buttons -------------------------------------------------------
        reparse_btn = QPushButton("Re-parse from Last PDF Text")
        reparse_btn.clicked.connect(do_reparse)
        lay.addWidget(reparse_btn)

        q_btn = QPushButton("Questionnaire (Review & Apply)")
        q_btn.clicked.connect(do_questionnaire)
        lay.addWidget(q_btn)

        dlg.resize(640, 420)
        dlg.exec()

    # [BM-A-001|dialog|catalog|v1] uses Catalog object (not dict)
    @lore_guard("open catalog dialog failure", severity="low")
    def open_catalog_dialog(self):
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
            QPushButton, QHeaderView, QMessageBox, QLabel
        )
        try:
            from core.catalog import load_catalog
            cat = load_catalog()                     # <-- Catalog object
            items = cat.raw.get("items", {})         # <-- drill into .raw
            ver = cat.version
        except Exception as e:
            QMessageBox.critical(self, "Catalog Load Error", str(e))
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Catalog Viewer — v{ver}")
        lay = QVBoxLayout(dlg)

        meta = QLabel(f"Version: {ver}   •   Path: config/catalog.json")
        meta.setStyleSheet("color:#555;")
        lay.addWidget(meta)

        tbl = QTableWidget(0, 4)
        tbl.setHorizontalHeaderLabels(["Item", "Description", "Unit", "Cost (example)"])
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        lay.addWidget(tbl)
        try:
            if not isinstance(items, dict):
                raise TypeError(f"Catalog 'items' is not a dict (got {type(items).__name__}).")

            rows = sorted(items.items())
            tbl.setRowCount(len(rows))
            # [BM-CATALOG-FRIENDLY|names|v1]

            def _first_num(d):
                if isinstance(d, (int, float)):
                    return float(d)
                if isinstance(d, dict):
                    for _vv in d.values():
                        x = _first_num(_vv)
                        if x is not None:
                            return x
                return None

            for r, (k, v) in enumerate(rows):
                v = v or {}
                desc = str(v.get("desc", ""))
                uom  = str(v.get("uom", ""))

                num = _first_num(v.get("cost", {}))
                cost_str = f"${num:,.2f}" if isinstance(num, (int, float)) else ""

                # Friendly item name (same mapping used by Materials)
                friendly_name = _friendly(k)

                tbl.setItem(r, 0, QTableWidgetItem(friendly_name))
                tbl.setItem(r, 1, QTableWidgetItem(desc))
                tbl.setItem(r, 2, QTableWidgetItem(uom))
                tbl.setItem(r, 3, QTableWidgetItem(cost_str))

        except Exception as e:
            QMessageBox.warning(dlg, "Catalog Error", f"Unable to populate table: {e}")

        from core.catalog import reload_catalog
        reload_btn = QPushButton("Reload Catalog")
        reload_btn.clicked.connect(self.on_reload_catalog)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(reload_btn)
        lay.addWidget(close_btn)

        dlg.resize(900, 600)
        dlg.exec()


    # --- handle_pdf_drop (fixed: totals/region defined before use) ---
    @lore_guard("pdf drop failure", severity="critical")
    def handle_pdf_drop(self, pdf_path: str):
        # Reject non-local or missing files
        if not (pdf_path and os.path.exists(pdf_path) and pdf_path.lower().endswith(".pdf")):
            self._show_warning_banner("That item isn’t a local PDF file. Please download the PDF to disk, then drop it here.")
            return

        """
        Deterministic drop handler:
          1) Extract text (for parsing + diagnostics).
          2) Parse identity + HOVER totals from TEXT.
          3) Canonicalize region → open Questionnaire prefilled.
          4) Build JobInputs; compute + price; split coils.
          5) Persist; refresh UI; show totals.
        """

        # 1) Identity + raw text
        ident = _extract_identity_text_first(pdf_path)
        text = ident.get("raw_text", "") or ""

        # Keep last text for dev aid
        try:
            os.makedirs(JOBS_DIR, exist_ok=True)
            with open(os.path.join(JOBS_DIR, "last_pdf_text.txt"), "w", encoding="utf-8") as _f:
                _f.write(text)
        except Exception:
            pass

        name_upper          = ident.get("name_upper", "")
        street_line_safe    = ident.get("street_line", "")
        city_state_zip_safe = ident.get("city_state_zip", "")
        zip_code_safe       = ident.get("zip_code_safe", "")
        addr_full           = ident.get("addr_full", "")
        street_only         = ident.get("street_only", "")
        display_title       = ident.get("display_title", "")

        # 2) Totals from TEXT (deterministic) + warn_corners backfill
        try:
            totals = extract_hover_totals(text) or {}
        except Exception:
            totals = {}

        # Backfill corners if missing (same logic your parse_hover_pdf uses)
        try:
            out_ft = float(totals.get("outside", 0.0) or 0.0)
            in_ft  = float(totals.get("inside", 0.0) or 0.0)
        except Exception:
            out_ft, in_ft = 0.0, 0.0

        if out_ft == 0.0 or in_ft == 0.0:
            oc, ic, any_corner_tokens = _extract_corners_from_text(text)
            if out_ft == 0.0 and oc > 0.0:
                out_ft = oc
            if in_ft == 0.0 and ic > 0.0:
                in_ft = ic
            totals["outside"] = out_ft
            totals["inside"]  = in_ft
            totals["warn_corners"] = bool(any_corner_tokens and out_ft == 0.0 and in_ft == 0.0)
        else:
            totals["warn_corners"] = False

        # Make these available to "Parsed Totals"
        self.last_totals = dict(totals)

        # 3) Region guess (ZIP-aware)
        region_guess = _canonical_region(None, zip_code_safe)

        # 4) Questionnaire defaults (safe siding_sf)
        sid_sf = max(float(totals.get("facades_sf", 0.0) or 0.0),
                     float(totals.get("trim_siding_sf", 0.0) or 0.0))

        q_defaults = dict(self._questionnaire_defaults_from(totals=totals, region_guess=region_guess))
        q_defaults["region_guess"] = region_guess

        vals = self._open_questionnaire(q_defaults)

        if vals:
            inp = JobInputs(
                customer_name=name_upper or "UNKNOWN",
                address=addr_full,
                region=vals["region"],
                siding_type=vals["siding"],
                finish=vals["finish"],
                body_color=vals["body_color"],
                trim_color=vals["trim_color"],
                complexity=vals["complexity"],
                demo_required=vals["demo"],
                extra_layers=vals["layers"],
                substrate=vals["substrate"],
                facades_sf=float(vals["facades_sf"]),
                trim_siding_sf=float(vals["trim_siding_sf"]),
                eave_fascia_ft=float(vals["eave_fascia"]),
                rake_fascia_ft=float(vals["rake_fascia"]),
                soffit_depth_gt_24=bool(vals.get("depth_gt24", False)),
                openings_perimeter_ft=float(vals["openings_perim"]),
                outside_corners_ft=float(vals["outside"]),
                inside_corners_ft=float(vals["inside"]),
                fascia_width_in=int(vals["fascia_w"]),
                osb_selected=bool(vals["osb_on"]),
                osb_area_override_sf=(float(vals["osb_area"]) if vals["osb_area"] is not None else 0.0),
                lap_reveal_in=float(vals.get("lap_reveal_in", 7.0)),
            )
        else:
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
                osb_area_override_sf=0.0,
                lap_reveal_in=7.0,
            )

        # Clear prior overrides for a new job
        self._user_cost_overrides = {}

        # 5) Compute + price + split coils
        out = compute_estimate_wrapper(inp)
        self.last_inputs  = inp
        self.last_outputs = out

        # Price trade then split coils (idempotent)
        try:
            trade_cost = price_trade("Siding", inp, out)
            trade_cost = _apply_coil_split(trade_cost, inp.finish, inp.body_color, inp.trim_color)
        except Exception as _e:
            _dbg(_e, "price_trade:handle_pdf_drop")
            self._show_warning_banner("Couldn’t compute pricing for this job. Check logs.")
            return

        # Baselines for Δ
        self.baseline_unit_costs = {li.name: li.unit_cost for li in trade_cost.line_items}
        self._materials_baseline = {li.name: int(round(li.qty)) for li in trade_cost.line_items}
        self._materials_unit_cost = dict(self.baseline_unit_costs)

        try:
            if self._is_board_and_batten():
                self._purge_generic_siding_from_baselines()
        except Exception:
            pass

        def _gm_band(gv: float) -> str:
            if gv < 0.30: return "LOW!"
            if gv <= 0.40: return "MID"
            return "HIGH"

        material_cost = float(trade_cost.material_cost)
        labor_cost    = float(trade_cost.labor_cost)
        cogs_total    = material_cost + labor_cost
        overhead_rate = 0.20
        target_gm     = 0.35

        rev = round(cogs_total / max(1e-9, (1.0 - target_gm)), 2)
        comm_rate          = commission_rate_from_gross_gm(target_gm)
        commission_dollars = round(rev * comm_rate, 2)
        overhead_dollars   = round(overhead_rate * rev, 2)
        projected_profit   = round(rev - cogs_total - overhead_dollars - commission_dollars, 2)
        gm_band            = _gm_band(target_gm)

        costs_dict = {
            "material_cost": material_cost,
            "labor_cost": labor_cost,
            "cogs": cogs_total,
            "overhead_rate": overhead_rate,
            "target_gm": target_gm,
            "overhead_dollars": overhead_dollars,
            "revenue_target": rev,
            "projected_profit": projected_profit,
            "gm_band": gm_band,
            "commission_total": commission_dollars,
            "line_items": [vars(li) for li in trade_cost.line_items],
        }

        self._costs_baseline = {
            "Material Cost":     material_cost,
            "Labor Cost":        labor_cost,
            "COGS":              cogs_total,
            "Overhead Rate":     overhead_rate,
            "Target GM":         target_gm,
            "Overhead $":        overhead_dollars,
            "Revenue Target":    rev,
            "Projected Profit":  projected_profit,
            "GM Band":           gm_band,
            "Commission Total":  commission_dollars,
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
            try: con.close()
            except Exception: pass

        # 7) Refresh UI panes
        mats = getattr(self, "materials", None)
        csts = getattr(self, "costs", None)
        try:
            if mats: mats.setUpdatesEnabled(False)
            if csts: csts.setUpdatesEnabled(False)

            self.load_jobs_into_list()
            self.populate_costs_table(costs_dict)
            self.populate_materials_table(trade_cost)
            self.populate_labor_payout()
        finally:
            if mats: mats.setUpdatesEnabled(True)
            if csts: csts.setUpdatesEnabled(True)

        # Ensure Parsed Totals is always visible
        try:
            self._set_parsed_totals_visible(True)
        except Exception:
            pass

        # Stabilize Total pill
        try:
            self._refresh_material_total_pill(trade_cost)
        except Exception:
            try: self._refresh_material_total_pill(costs_dict)
            except Exception: pass

        try:
            self._update_materials_reset_visibility()
        except Exception:
            pass





    def _questionnaire_defaults_from(self, *, totals: dict, region_guess: str) -> dict:
        return {
            "region_guess": region_guess or "Metro",
            "siding_sf": float(max(totals.get("facades_sf", 0.0), totals.get("trim_siding_sf", 0.0))),
            "eave_fascia": str(totals.get("eave_fascia", 0.0)),
            "rake_fascia": str(totals.get("rake_fascia", 0.0)),
            "openings_perim": str(totals.get("openings_perim", 0.0)),
            "outside": str(totals.get("outside", 0.0)),
            "inside": str(totals.get("inside", 0.0)),
            # Parity with other paths:
            "warn_corners": (float(totals.get("outside") or 0.0) > 0.0) and (float(totals.get("inside") or 0.0) == 0.0),
            "body_color": "Arctic White",
            "lap_reveal_in": 7.0,
        }


    def _open_questionnaire(self, defaults: dict) -> dict | None:
        dlg = Questionnaire(self, defaults)
        return dlg.values() if dlg.exec() == QDialog.Accepted else None

    # [BM-COSTS-COMMISSION|recompute|apply-override|v1]
    @lore_guard("estimate compute failure", severity="high")
    def recompute_pricing(self, override_target_gm: float | None = None, force_catalog_reload: bool = False):
        """
        Rebuilds pricing and repaints Materials/Costs/Labor.

        Lock policy:
          - If self._costs_lock == "gm": GM is the control; Revenue is derived.
          - If self._costs_lock == "revenue": Revenue (from the grid) is control; GM is derived.
          - Editing Target GM sets lock="gm"; editing any other cost cell sets lock="revenue".

        Commission override:
          - If self._user_cost_overrides['commission_total'] exists, use it instead of catalog/band-computed commission.
        """
        def _num_money(s: str) -> float:
            try: return float((s or "").replace("$", "").replace(",", "").strip())
            except Exception: return 0.0

        def _num_pct(s: str) -> float:
            s = (s or "").strip()
            try:
                if s.endswith("%"): return float(s[:-1]) / 100.0
                v = float(s)
                return v/100.0 if v > 1 else v
            except Exception:
                return 0.0

        def _norm_uom(u: str) -> str:
            u = (u or "").strip().upper()
            if u in ("ROLLS","ROLL"): return "ROLL"
            if u in ("BOXES","BOX"):  return "BOX"
            return u or "EA"

        def _read_cost_controls_from_grid():
            oh, gm, rev = 0.20, 0.35, 0.0
            try:
                for r in range(self.costs.rowCount()):
                    k = (self.costs.item(r, 0).text() or "").strip()
                    v = (self.costs.item(r, 1).text() or "").strip()
                    if k == "Overhead Rate": oh = _num_pct(v)
                    elif k == "Target GM":   gm = _num_pct(v)
                    elif k == "Revenue Target": rev = _num_money(v)
            except Exception:
                pass
            return oh, gm, rev

        def _user_qty_and_units():
            user_qty, live_units = {}, dict(getattr(self, "_materials_unit_cost", {}))
            try:
                for r in range(self.materials.rowCount()):
                    name_key = (self.materials.item(r, 0).data(Qt.UserRole) if self.materials.item(r, 0) else None)
                    if not name_key: continue
                    try:
                        qv = int(float((self.materials.item(r, 1).text() or "0").strip()))
                        user_qty[name_key] = max(0, qv)
                    except Exception:
                        pass
                    try:
                        uv = _num_money(self.materials.item(r, 3).text())
                        live_units[name_key] = float(max(0.0, uv))
                    except Exception:
                        pass
            except Exception:
                pass
            return user_qty, live_units

        def _live_uom_map():
            m = {}
            try:
                for r in range(self.materials.rowCount()):
                    name_item = self.materials.item(r, 0)
                    uom_item  = self.materials.item(r, 2)
                    if not (name_item and uom_item): continue
                    key = name_item.data(Qt.UserRole)
                    if not key: continue
                    m[key] = (uom_item.text() or "").strip().upper()
            except Exception:
                pass
            return m

        def _do():
            if not getattr(self, "last_inputs", None) or not getattr(self, "last_outputs", None):
                return
            if not hasattr(self, "_materials_uom") or self._materials_uom is None:
                self._materials_uom = {}

            # 1) Base trade from engine
            trade_cost = price_trade("Siding", self.last_inputs, self.last_outputs)

            # Apply the same coil split (idempotent)
            trade_cost = _apply_coil_split(
                trade_cost,
                getattr(self.last_inputs, "finish", ""),
                getattr(self.last_inputs, "body_color", ""),
                getattr(self.last_inputs, "trim_color", "")
            )

            # 2) Apply live Materials overrides (qty & unit); preserve UOM
            user_qty, live_units = _user_qty_and_units()
            live_uoms = _live_uom_map()

            cat_units = {li.name: float(getattr(li, "unit_cost", 0.0)) for li in (trade_cost.line_items or [])}
            cat_uoms  = {li.name: _norm_uom(getattr(li, "uom", "EA")) for li in (trade_cost.line_items or [])}
            base_qty  = dict(getattr(self, "_materials_baseline", {}))
            all_names = set(cat_units) | set(base_qty) | set(user_qty) | set(live_units) | set(live_uoms) | set(self._materials_uom.keys())

            new_lines, mat_total = [], 0.0
            any_type = type(trade_cost.line_items[0]) if trade_cost.line_items else None
            for name in sorted(all_names):
                cat_qty = next((int(round(float(li.qty or 0))) for li in trade_cost.line_items if li.name == name), 0)
                qty = user_qty.get(name, cat_qty if name in cat_units else int(base_qty.get(name, 0)))
                baseline_units = getattr(self, "baseline_unit_costs", {}) or {}
                unit_now = float(live_units.get(name, cat_units.get(name, float(baseline_units.get(name, 0.0)))))
                uom_now = (live_uoms.get(name, self._materials_uom.get(name, cat_uoms.get(name, "EA"))) or "EA")
                ext = float(qty) * float(unit_now)
                mat_total += ext
                self._materials_uom[name] = uom_now
                try:
                    new_lines.append(any_type(name, qty, uom_now, unit_now, ext))
                except Exception:
                    from types import SimpleNamespace
                    new_lines.append(SimpleNamespace(name=name, qty=qty, uom=uom_now, unit_cost=unit_now, ext_cost=ext))

            labor_cost_now = trade_cost.labor_cost
            if getattr(self, "_user_cost_overrides", None) and "labor_cost" in self._user_cost_overrides:
                try: labor_cost_now = float(self._user_cost_overrides["labor_cost"])
                except Exception: pass

            trade_cost = type(trade_cost)(
                trade=trade_cost.trade,
                material_cost=round(mat_total, 2),
                labor_cost=labor_cost_now,
                line_items=new_lines
            )
            self._last_trade_cost = trade_cost

            # 3) Read controls from grid
            oh_rate, gm_from_grid, rev_from_grid = _read_cost_controls_from_grid()

            # 4) Choose GM vs Revenue lock
            gm_target = gm_from_grid
            if override_target_gm is not None:
                gm_target = float(override_target_gm)
                self._costs_lock = "gm"
            else:
                lock = getattr(self, "_costs_lock", "gm")
                if lock == "revenue" and rev_from_grid > 0.0:
                    cogs_preview = float(trade_cost.material_cost) + float(trade_cost.labor_cost)
                    gm_target = max(0.0, min(0.95, 1.0 - (cogs_preview / max(1e-9, rev_from_grid))))

            # 5) Summarize Costs with chosen control — CANONICAL (GM ↔ Revenue identity)
            C = float(trade_cost.material_cost) + float(trade_cost.labor_cost)

            # clamp GM for numerical sanity
            g = float(gm_target if gm_target is not None else 0.35)
            g = max(0.0, min(0.95, g))

            denom = max(1e-9, (1.0 - g))
            revenue_now = round(C / denom, 2)

            # Overhead from revenue
            overhead_dollars = round(oh_rate * revenue_now, 2)
            
            # [BM-COMMISSION|single-source|apply|recompute_pricing]
            comm_rate = commission_rate_from_gross_gm(g)

            commission_default = round(revenue_now * comm_rate, 2)

            # Honor a manual override if the user explicitly set commission earlier
            commission_now = commission_default
            try:
                if getattr(self, "_user_cost_overrides", None) and "commission_total" in self._user_cost_overrides:
                    commission_now = float(self._user_cost_overrides["commission_total"])
            except Exception:
                pass

            projected_profit_now = round(revenue_now - C - overhead_dollars - commission_now, 2)

            # Keep GM band visible and correct under GM lock
            try:
                gm_band_label = self._gm_band_label(g)
            except Exception:
                gm_band_label = "MID" if 0.30 <= g <= 0.40 else ("LOW!" if g < 0.30 else "HIGH")


            # (Optional) Update the inline commission schedule preview

            costs_dict = {
                "material_cost": float(trade_cost.material_cost),
                "labor_cost": float(trade_cost.labor_cost),
                "cogs": float(C),
                "overhead_rate": float(oh_rate),
                "target_gm": float(g),
                "overhead_dollars": float(overhead_dollars),
                "revenue_target": float(revenue_now),
                "projected_profit": float(projected_profit_now),
                "gm_band": gm_band_label,
                "commission_total": float(round(commission_now, 2)),
            }

            # 6) Baseline reset guard
            if getattr(self, "_suppress_next_costs_baseline_reset", False):
                should_reset_baseline = False
            else:
                should_reset_baseline = True
                try:
                    if hasattr(self, "costs") and self.costs:
                        if self.costs.hasFocus() and self.costs.currentColumn() == 1 and self.costs.currentItem() is not None:
                            should_reset_baseline = False
                except Exception:
                    pass

            if should_reset_baseline:
                self._costs_baseline = {
                    "Material Cost":     float(costs_dict.get("material_cost", 0.0)),
                    "Labor Cost":        float(costs_dict.get("labor_cost", 0.0)),
                    "COGS":              float(costs_dict.get("cogs", 0.0)),
                    "Overhead Rate":     float(costs_dict.get("overhead_rate", 0.0)),
                    "Target GM":         float(costs_dict.get("target_gm", 0.0)),
                    "Overhead $":        float(costs_dict.get("overhead_dollars", 0.0)),
                    "Revenue Target":    float(costs_dict.get("revenue_target", 0.0)),
                    "Projected Profit":  float(costs_dict.get("projected_profit", 0.0)),
                    "GM Band":           str(costs_dict.get("gm_band", "")),
                    "Commission Total":  float(costs_dict.get("commission_total", 0.0)),
                }

            # 7) Paint UI
            self.populate_materials_table(trade_cost)
            self.populate_costs_table(costs_dict)
            self.populate_labor_payout()
            self._refresh_material_total_pill(costs_dict)

            self._suppress_next_costs_baseline_reset = False

        return self._with_recompute_guard(_do)



    # [BM-COMMISSION|delegate-only|v2]
    def _commission_rate_from_gm(self, gm: float) -> float:
        return commission_rate_from_gross_gm(gm)

    # [BM-COMMISSION|dollars_from_gm+revenue|v1]
    def _commission_dollars(self, gm: float, revenue: float) -> float:
        """
        Convenience helper: commission dollars from GM (decimal) and Revenue ($).
        """
        rate = self._commission_rate_from_gm(gm)
        try:
            R = float(revenue)
        except Exception:
            R = 0.0
        return max(0.0, rate * R)

    # [BM-GM-BAND|helper|v2]
    def _gm_band_label(self, g: float) -> str:
        """
        Gross GM band:
          LOW! = under 30%
          MID  = 30%–40% (inclusive)
          HIGH = over 40%

        Robust to float jitter, NaN/inf, and keeps your 0..0.95 clamp.
        """
        import math
        GM_LOW  = 0.30
        GM_HIGH = 0.40
        EPS     = 1e-9  # treat values within 1e-9 of a boundary as on it

        try:
            gg = float(g)
            if math.isnan(gg) or math.isinf(gg):
                gg = 0.0
        except Exception:
            gg = 0.0

        # clamp for safety
        gg = max(0.0, min(0.95, gg))

        if gg < GM_LOW - EPS:
            return "LOW!"
        if gg <= GM_HIGH + EPS:
            return "MID"
        return "HIGH"


 




    # [BM-COMMISSION|selftest|v1]
    def _selftest_commission_rule(self):
        """
        Quick sanity checks (raises AssertionError on failure).
        """
        eps = 1e-6
        def near(a, b): return abs(a - b) < eps

        # [BM-COMMISSION|selftest-use-global|v1]
        assert near(commission_rate_from_gross_gm(0.25), 0.05)
        assert near(commission_rate_from_gross_gm(0.21), 0.01)
        assert near(commission_rate_from_gross_gm(0.20), 0.00)
        assert near(commission_rate_from_gross_gm(0.30), 0.10)
        assert near(commission_rate_from_gross_gm(0.33), 0.11)
        assert near(commission_rate_from_gross_gm(0.40), 0.1333333333333)

        # Dollars helper (e.g., R=$100, GM=33% → 11% of 100)
        assert near(self._commission_dollars(0.33, 100.0), 11.0)

    # [BM-COSTS|on_change|labor-delta-moves-revenue|v20]
    def on_costs_cell_changed(self, row: int, col: int):
        """
        Editing 'Labor Cost' keeps GM as the control:
          - ΔLabor is applied and Revenue is recomputed from the fixed Target GM:
            ΔR = ΔL / (1 - g). Overhead and Commission update from the new Revenue.
        Other cells:
          - Editing Target GM -> lock='gm' and recompute.
          - Editing Revenue/Profit/Commission -> lock='revenue' with the appropriate inversion.
        """
        # Only react to edits in the Value column and avoid recursion
        if col != 1 or getattr(self, "_in_costs_edit", False):
            return

        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtCore import Qt

        key_item = self.costs.item(row, 0)
        val_item = self.costs.item(row, 1)
        if not key_item or not val_item:
            return

        key = (key_item.text() or "").strip()
        raw_txt = (val_item.text() or "").strip()

        # ----- helpers -----------------------------------------------------
        def _money_to_float(s: str) -> float:
            try:
                return float((s or "").replace("$", "").replace(",", "").strip())
            except Exception:
                return 0.0

        def _pct_to_float(s: str) -> float:
            s = (s or "").strip()
            try:
                if s.endswith("%"):
                    return float(s[:-1].strip()) / 100.0
                v = float(s)
                return v/100.0 if v > 1.0 else v
            except Exception:
                return 0.0

        def _fmt_money(v: float) -> str:
            try:
                return f"${float(v):,.2f}"
            except Exception:
                return "$0.00"

        def _fmt_pct(v: float) -> str:
            try:
                return f"{float(v):.2%}"
            except Exception:
                return "0.00%"

        def _row_of(label: str) -> int:
            for r in range(self.costs.rowCount()):
                it_k = self.costs.item(r, 0)
                if it_k and (it_k.text() or "").strip() == label:
                    return r
            return -1

        def _get_cost_value(label: str, default: float = 0.0) -> float:
            r = _row_of(label)
            if r < 0:
                return default
            it_v = self.costs.item(r, 1)
            if not it_v:
                return default
            s = (it_v.text() or "")
            if label.endswith("Rate") or label in ("Target GM", "Gross Margin"):
                return _pct_to_float(s)
            return _money_to_float(s)

        def _set_cost_value(label: str, value_str: str):
            r = _row_of(label)
            if r < 0:
                return
            it_v = self.costs.item(r, 1)
            if it_v is None:
                it_v = QTableWidgetItem(value_str)
                self.costs.setItem(r, 1, it_v)
            else:
                it_v.setText(value_str)
            it_v.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)

        # Ensure overrides dict exists
        if not hasattr(self, "_user_cost_overrides") or self._user_cost_overrides is None:
            self._user_cost_overrides = {}

        # Snapshot current core values for inversions
        mat_now = _get_cost_value("Material Cost", 0.0)
        labor_now_grid = _get_cost_value("Labor Cost", 0.0)
        rev_now_grid = _get_cost_value("Revenue Target", 0.0)
        oh_rate = _get_cost_value("Overhead Rate", 0.20)
        cogs_now = float(mat_now + labor_now_grid)

        # ----- route per edited key ---------------------------------------
        self._in_costs_edit = True
        try:
            if key == "Labor Cost":
                # Persist explicit labor override
                new_labor = _money_to_float(raw_txt)
                self._user_cost_overrides["labor_cost"] = float(max(0.0, new_labor))

                # CRITICAL: GM is the control. Revenue must be recomputed from COGS and the fixed Target GM.
                # This enforces ΔR = ΔL / (1 - g) and keeps g unchanged unless the user edits it.
                self._costs_lock = "gm"
                self._suppress_next_costs_baseline_reset = True

                # Recompute -> revenue = COGS / (1 - g), OH = r*revenue, Commission = f(g)*revenue
                self.recompute_pricing()
                return


            if key in ("Gross Margin", "Target GM"):
                g_target = _pct_to_float(raw_txt)
                self._costs_lock = "gm"
                self._suppress_next_costs_baseline_reset = True
                self.recompute_pricing(override_target_gm=g_target)
                return

            if key == "Revenue Target":
                self._costs_lock = "revenue"
                self._suppress_next_costs_baseline_reset = True
                self.recompute_pricing()
                return

            if key == "Projected Profit":
                # Profit→Revenue inversion (kept intact)
                p_user = _money_to_float(raw_txt)
                try:
                    rev_new = solve_revenue_from_profit(p_user, cogs_now, oh_rate)
                except Exception:
                    eps = 1e-9
                    denom1 = 1.0 - oh_rate
                    rev_new = (p_user + cogs_now) / max(eps, denom1)
                _set_cost_value("Revenue Target", _fmt_money(rev_new))
                self._costs_lock = "revenue"
                self._suppress_next_costs_baseline_reset = True
                self.recompute_pricing()
                return

            if key == "Commission Total":
                Comm = _money_to_float(raw_txt)
                try:
                    rev_new = solve_revenue_from_commission(Comm, cogs_now)
                except Exception:
                    eps = 1e-9
                    rev3 = 3.0 * Comm + cogs_now
                    g3 = 0.0 if rev3 <= 0 else 1.0 - (cogs_now / rev3)
                    if g3 >= 0.30 - 1e-9:
                        rev_new = rev3
                    else:
                        rev2 = (Comm + cogs_now) / 0.80 if 0.80 > eps else cogs_now
                        g2 = 0.0 if rev2 <= 0 else 1.0 - (cogs_now / rev2)
                        rev_new = rev2 if (0.20 + 1e-9 < g2 < 0.30 - 1e-9) else max(cogs_now / (1.0 - 0.20), cogs_now + Comm)
                self._user_cost_overrides["commission_total"] = float(max(0.0, Comm))
                _set_cost_value("Revenue Target", _fmt_money(rev_new))
                self._costs_lock = "revenue"
                self._suppress_next_costs_baseline_reset = True
                self.recompute_pricing()
                return

            # Fallback: any other label just triggers a recompute
            self._suppress_next_costs_baseline_reset = True
            self.recompute_pricing()

        finally:
            self._in_costs_edit = False




    def _on_costs_delta_clicked(self, row: int, col: int):
        """
        Clicking Δ on ANY Costs row now resets BOTH:
          1) Materials (qty back to baseline)
          2) Costs (grid back to baseline)
        Then triggers a single recompute.
        """
        if col != 2:
            return
        try:
            # One canonical reset path: this resets materials, then costs, and recomputes.
            self._reset_materials_to_hover()
        except Exception:
            # Fallback: at least restore costs and recompute
            try:
                self._reset_all_costs_to_baseline()
            except Exception:
                pass
            try:
                self.recompute_pricing()
            except Exception:
                pass


    # [BM-MATS-POPULATE|ducktype+uniform+delta|v8] — record UOM to self._materials_uom; prefer remembered UOM
    def populate_materials_table(self, data):
        """
        Materials table: 6 columns [Material, Qty, UOM, Unit Cost, Ext. Cost, Δ]
        - Duck-typed input
        - Δ is qty-only
        - Persist UOM in self._materials_uom so it survives recomputes.
        """
        if not hasattr(self, "_materials_uom") or self._materials_uom is None:
            self._materials_uom = {}
        view = self.materials
        if not hasattr(self, "_materials_unit_cost"):
            self._materials_unit_cost = {}
        if not hasattr(self, "_materials_baseline"):
            self._materials_baseline = {}
        if not hasattr(self, "baseline_unit_costs"):
            self.baseline_unit_costs = {}

        # normalize incoming data -> iterable of items with (name, qty, uom, unit_cost)
        iter_items = []
        try:
            if hasattr(data, "line_items"):
                iter_items = list(getattr(data, "line_items") or [])
            elif isinstance(data, list):
                iter_items = data
        except Exception:
            pass

        # --- TEMP UI FIX: hide generic 'siding_sf' for Board & Batten ONLY IF we truly have B&B parts ---
        def _name_of(li):
            try:
                return getattr(li, "name")
            except Exception:
                try:
                    return li.get("name", "")
                except Exception:
                    return ""

        try:
            siding_is_bb = (
                getattr(self, "last_inputs", None)
                and (getattr(self.last_inputs, "siding_type", "") or "")
                    .strip().lower() in ("board & batten", "board and batten", "board &amp; batten")
            )
        except Exception:
            siding_is_bb = False

        has_bb_specific = False
        if iter_items:
            names_lower = {(_name_of(li) or "").strip().lower() for li in iter_items}
            has_bb_specific = any(n in ("bb_panel_4x10", "bb_batten_12ft") for n in names_lower)

        if siding_is_bb and iter_items and has_bb_specific:
            iter_items = [
                li for li in iter_items
                if (_name_of(li) or "").strip().lower() not in ("siding sf", "siding_sf", "siding sqft", "siding_sqft")
            ]

        # Ensure baselines can't bring the generic row back ONLY when true replacement exists
        try:
            if siding_is_bb and has_bb_specific:
                self._purge_generic_siding_from_baselines()
        except Exception:
            pass

        # Build cur_items dict by name
        def _norm_uom(u: str) -> str:
            u = (u or "").strip().upper()
            if u in ("ROLLS", "ROLL"):
                return "ROLL"
            if u in ("BOXES", "BOX"):
                return "BOX"
            return u or "EA"

        cur_items: dict[str, dict] = {}
        for li in iter_items:
            try:
                name = _name_of(li)
                qty  = getattr(li, "qty",  None) if hasattr(li, "qty")  else li.get("qty", 0)
                uom_in  = getattr(li, "uom",  None) if hasattr(li, "uom")  else li.get("uom", "")
                unit = getattr(li, "unit_cost", None) if hasattr(li, "unit_cost") else li.get("unit_cost", 0.0)
                cur_items[str(name)] = dict(
                    qty=int(round(float(qty or 0))),
                    uom=_norm_uom(uom_in or self._materials_uom.get(str(name), "")),
                    unit_cost=float(unit or 0.0),
                )
            except Exception:
                continue

        # If nothing sane, clear and bail
        if not cur_items and not getattr(self, "_materials_baseline", {}):
            with self._block_signals(view):
                view.setRowCount(0)
            try:
                self._update_materials_reset_visibility()
                self._refresh_material_total_pill(None)
            except Exception:
                pass
            return

        # Union of all known names so zero-qty baseline rows remain visible
        all_names = set(cur_items.keys()) | set(self._materials_baseline.keys())

        from PySide6.QtWidgets import QHeaderView, QTableWidgetItem

        # -------- prep the table schema (6 columns)
        with self._block_signals(view):
            if view.columnCount() != 6:
                view.setColumnCount(6)
                view.setHorizontalHeaderLabels(["Material", "Qty", "UOM", "Unit Cost", "Ext. Cost", "Δ"])
                mh = view.horizontalHeader()
                mh.setStretchLastSection(False)
                mh.setMinimumSectionSize(24)
                mh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                mh.setSectionResizeMode(1, QHeaderView.Fixed);   mh.resizeSection(1, 70)
                mh.setSectionResizeMode(2, QHeaderView.Fixed);   mh.resizeSection(2, 70)
                mh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
                mh.setSectionResizeMode(4, QHeaderView.Stretch)
                mh.setSectionResizeMode(5, QHeaderView.Fixed);   mh.resizeSection(5, 28)
                view.setStyleSheet(""); view.setAlternatingRowColors(False); view.setShowGrid(True); view.setWordWrap(False)
                vh = view.verticalHeader()
                try: vh.setSectionResizeMode(QHeaderView.Fixed)
                except Exception: pass
                vh.setDefaultSectionSize(32); vh.setMinimumSectionSize(32); vh.setVisible(False)

            # Freeze painting and remember scroll
            try:
                view.setUpdatesEnabled(False)
                vbar = view.verticalScrollBar(); hbar = view.horizontalScrollBar()
                v_pos, h_pos = vbar.value(), hbar.value()
            except Exception:
                v_pos = h_pos = None

            view.setRowCount(0)
            running_total = 0.0
            H = view.verticalHeader().defaultSectionSize() or 32

            # Stable sorted order by name
            for idx, name in enumerate(sorted(all_names), start=1):
                info = cur_items.get(name, {})
                qty = int(round(float(info.get("qty", self._materials_baseline.get(name, 0)))))
                uom_now = _norm_uom(info.get("uom", self._materials_uom.get(name, "")))
                unit_now = float(info.get("unit_cost", self.baseline_unit_costs.get(name, 0.0)))

                # Track live unit cost + remember UOM
                self._materials_unit_cost[name] = unit_now
                self._materials_uom[name] = uom_now

                qty_base  = int(self._materials_baseline.get(name, qty))

                r = view.rowCount(); view.insertRow(r); view.setRowHeight(r, H)

                # Friendly label (numbered)
                fascia_w = None
                if name == "fascia_12ft" and getattr(self, "last_inputs", None):
                    try: fascia_w = int(self.last_inputs.fascia_width_in)
                    except Exception: fascia_w = None
                friendly = _friendly(name, fascia_width_in=fascia_w).replace("\n", " ")
                numbered = f"{idx}. {friendly}"

                it_name = QTableWidgetItem(numbered)
                it_name.setData(Qt.UserRole, name)
                it_name.setFlags(it_name.flags() & ~Qt.ItemIsEditable)
                view.setItem(r, 0, it_name)

                it_qty = QTableWidgetItem(str(qty))
                it_qty.setData(Qt.UserRole, name)
                view.setItem(r, 1, it_qty)

                it_uom = QTableWidgetItem(uom_now)
                it_uom.setFlags(it_uom.flags() & ~Qt.ItemIsEditable)
                view.setItem(r, 2, it_uom)

                it_unit = QTableWidgetItem(f"${unit_now:,.2f}")
                view.setItem(r, 3, it_unit)

                ext_now = float(qty) * float(unit_now)
                it_ext = QTableWidgetItem(_fmt_money(ext_now))
                it_ext.setFlags(it_ext.flags() & ~Qt.ItemIsEditable)
                view.setItem(r, 4, it_ext)
                running_total += ext_now

                it_delta = QTableWidgetItem("")
                it_delta.setFlags(it_delta.flags() & ~Qt.ItemIsEditable)
                if qty != qty_base:
                    up = qty > qty_base
                    it_delta.setText("▲" if up else "▼")
                    from PySide6.QtGui import QColor, QBrush, QFontMetrics
                    it_delta.setForeground(QBrush(QColor("#1a7f37" if up else "#cc0000")))
                view.setItem(r, 5, it_delta)

            # Restore scroll; unfreeze paint
            try:
                if v_pos is not None: vbar.setValue(v_pos)
                if h_pos is not None: hbar.setValue(h_pos)
                view.setUpdatesEnabled(True)
            except Exception:
                try: view.setUpdatesEnabled(True)
                except Exception: pass

        # Wire signals (idempotent)
        view.itemChanged.connect(self._on_materials_item_changed, Qt.ConnectionType.UniqueConnection)
        view.cellClicked.connect(self._on_materials_delta_clicked, Qt.ConnectionType.UniqueConnection)

        # Totals + uniform height sweep
        self._update_materials_reset_visibility()
        self._update_materials_total_label(running_total)
        self._refresh_material_total_pill(None)
        self._enforce_uniform_material_row_heights()



    # [BM-MATS-DELTA|click|reset-to-baseline|v2]
    def _on_materials_delta_clicked(self, row: int, col: int):
        """
        Clicking Δ (col=5) resets that row's Qty to its baseline (Hover/catalog) value.
        This gives users a fast 'revert' action and proves Δ is actionable.
        """
        if col != 5:
            return
        try:
            name_item = self.materials.item(row, 0)
            qty_item  = self.materials.item(row, 1)
            if not (name_item and qty_item):
                return
            key = name_item.data(Qt.UserRole) or ""
            base_q = int(self._materials_baseline.get(key, 0))
            if str(qty_item.text()).strip() != str(base_q):
                self.materials.blockSignals(True)
                qty_item.setText(str(base_q))
            self.materials.blockSignals(False)
            # Keep the view steady; recompute on the next event loop tick
            if not getattr(self, "_mats_recompute_scheduled", False):
                self._mats_recompute_scheduled = True
                QTimer.singleShot(0, self._recompute_after_material_edit)
        except Exception:
            pass

    # [BM-MATS|item_changed|smooth|v4]
    def _on_materials_item_changed(self, item: QTableWidgetItem):
        """
        Enforce integer in Qty, update Ext and Δ immediately (no full repaint),
        then schedule a recompute on the next tick (prevents visual jump).
        """
        try:
            if getattr(self, "_materials_rebuilding", False) or item.column() != 1:
                return

            view = self.materials
            row  = item.row()

            # Normalize Qty to non-negative int
            vtxt = (item.text() or "0").strip()
            try:
                v = int(float(vtxt)) if vtxt not in ("", "-", "+") else 0
            except Exception:
                v = 0
            if v < 0:
                v = 0
            if item.text() != str(v):
                view.blockSignals(True)
                item.setText(str(v))
                view.blockSignals(False)

            # Read Unit → update Ext
            unit_item = view.item(row, 3)
            ext_item  = view.item(row, 4)
            name_item = view.item(row, 0)

            try:
                unit_now = float((unit_item.text() or "").replace("$","").replace(",",""))
            except Exception:
                unit_now = 0.0

            ext_now = float(v) * unit_now
            if ext_item is None:
                ext_item = QTableWidgetItem("")
                view.setItem(row, 4, ext_item)
            ext_item.setText(_fmt_money(ext_now))

            # Δ vs baseline (qty-only)
            key = name_item.data(Qt.UserRole) if name_item else None
            qty_base  = int(self._materials_baseline.get(key, 0)) if key else 0
            it_delta  = view.item(row, 5) or QTableWidgetItem("")
            it_delta.setFlags(it_delta.flags() & ~Qt.ItemIsEditable)
            if v != qty_base:
                up = v > qty_base
                it_delta.setText("▲" if up else "▼")
                it_delta.setForeground(QBrush(QColor("#1a7f37" if up else "#cc0000")))
            else:
                it_delta.setText("")
            view.setItem(row, 5, it_delta)

            # Running total pill (quick) + keep row heights uniform
            self._refresh_material_total_pill(None)
            self._enforce_uniform_material_row_heights()

            # schedule recompute (prevents jump due to full table rebuild mid-edit)
            if not getattr(self, "_mats_recompute_scheduled", False):
                self._mats_recompute_scheduled = True
                QTimer.singleShot(0, self._recompute_after_material_edit)

        except Exception:
            return

            



    # [BM-PILLS-TOTAL|update_proxy|v1]
    def _update_materials_total_label(self, _value: float):
        """
        Backward-compatible name, now proxies to revenue pill refresh based on grid.
        """
        try:
            self._refresh_material_total_pill(None)
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

        # NEW: also reset the entire Costs grid back to its baseline
        try:
            self._reset_all_costs_to_baseline()
        except Exception:
            pass

        # Recompute with baselines in place
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

    # [BM-COSTS|populate|fit-values+delta-readonly|v5]
    def populate_costs_table(self, costs_dict):
        from PySide6.QtWidgets import QHeaderView, QTableWidgetItem
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QBrush, QFontMetrics
        _wire_costs_signals(self)


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

        view = self.costs
        with self._block_signals(view):
            # Schema (3 cols) and native look
            if view.columnCount() != 3:
                view.setColumnCount(3)
                view.setHorizontalHeaderLabels(["Cost Metric", "Value", "Δ"])
                view.setStyleSheet("")
                vh = view.verticalHeader()
                try:
                    vh.setSectionResizeMode(QHeaderView.Fixed)
                except Exception:
                    pass
                vh.setDefaultSectionSize(32)
                vh.setMinimumSectionSize(32)
                vh.setVisible(False)
                view.setShowGrid(True)

            # Header sizing — STOP jitter in Value column by using Stretch
            ch = view.horizontalHeader()
            ch.setStretchLastSection(False)
            ch.setMinimumSectionSize(24)
            ch.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Metric
            ch.setSectionResizeMode(1, QHeaderView.Stretch)           # Value = stable width (no jitter)
            ch.setSectionResizeMode(2, QHeaderView.Fixed)             # Δ fixed @28px
            ch.resizeSection(2, 28)

            view.clearContents()
            view.setRowCount(len(rows))

            editable_keys = {"Labor Cost", "Target GM", "Revenue Target", "Projected Profit", "Commission Total"}

            for r, (label, value, delta) in enumerate(rows):
                it_label = QTableWidgetItem(str(label))
                it_label.setFlags(it_label.flags() & ~Qt.ItemIsEditable)
                it_label.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                view.setItem(r, 0, it_label)

                it_value = QTableWidgetItem(str(value))
                if label not in editable_keys:
                    it_value.setFlags(it_value.flags() & ~Qt.ItemIsEditable)
                it_value.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                view.setItem(r, 1, it_value)

                it_delta = QTableWidgetItem(str(delta))
                it_delta.setFlags(it_delta.flags() & ~Qt.ItemIsEditable)
                it_delta.setTextAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
                view.setItem(r, 2, it_delta)

                # Paint the delta marker once at populate
                self._set_costs_delta_marker(r)

        # Ensure signals are connected (idempotent via UniqueConnection)
        self._wire_signals()

        # Sync the pill to freshly-painted grid (reads 'Revenue Target')
        try:
            self._refresh_material_total_pill(None)
        except Exception:
            pass

        



    # [BM-COSTS-DELTA|fix|v2]
    def _set_costs_delta_marker(self, row: int):
        key_item = self.costs.item(row, 0)
        val_item = self.costs.item(row, 1)
        delta_item = self.costs.item(row, 2)
        if not key_item or not val_item:
            return
        if delta_item is None:
            delta_item = QTableWidgetItem("")
            delta_item.setFlags(delta_item.flags() & ~Qt.ItemIsEditable)
            self.costs.setItem(row, 2, delta_item)

        # default (no delta)
        delta_item.setText("")
        delta_item.setForeground(QBrush(QColor("#000000")))  # black

        key = key_item.text()
        val = val_item.text()
        base = getattr(self, "_costs_baseline", {}).get(key, None)
        if base is None:
            return

        # parse current vs baseline by type
        if key in ("Target GM", "Overhead Rate"):
            try:
                cur = float(val.replace("%", "")) / 100.0 if "%" in val else float(val)
            except Exception:
                cur = float(base)
            base_v = float(base)
            diff = cur - base_v
        elif key == "GM Band":
            cur = str(val)
            base_v = str(base)
            diff = 0.0  # handled symbolically below
        else:
            try:
                cur = float(val.replace("$", "").replace(",", ""))
            except Exception:
                cur = float(base)
            base_v = float(base)
            diff = cur - base_v

        # GM Band: show ▲ if text changed
        if key == "GM Band":
            if cur != base_v:
                delta_item.setText("▲")
                delta_item.setForeground(QBrush(QColor("#1a7f37")))  # green
            else:
                delta_item.setText("")
            return

        # numeric deltas
        if abs(diff) < 1e-9:
            delta_item.setText("")
            delta_item.setForeground(QBrush(QColor("#000000")))
        elif diff > 0:
            delta_item.setText("▲")
            delta_item.setForeground(QBrush(QColor("#1a7f37")))     # green
        else:
            delta_item.setText("▼")
            delta_item.setForeground(QBrush(QColor("#cc0000")))     # red

    # [BM-COSTS-DELTA|reset_all_to_baseline|v1]
    def _reset_all_costs_to_baseline(self):
        """
        Reset the entire Costs table to the saved baseline (self._costs_baseline).
        - Preserves right alignment on Value column
        - Clears Δ markers for all rows
        - Does NOT rewrite the baseline
        """
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtCore import Qt

        baseline_map = getattr(self, "_costs_baseline", {}) or {}
        if not baseline_map or not hasattr(self, "costs") or not self.costs:
            return

        def _fmt_money(v: float) -> str:
            try: return f"${float(v):,.2f}"
            except Exception: return "$0.00"

        def _fmt_pct(v: float) -> str:
            try: return f"{float(v):.2%}"
            except Exception: return "0.00%"

        self.costs.blockSignals(True)
        try:
            # Set each value from baseline with correct formatting + alignment
            for r in range(self.costs.rowCount()):
                key_item = self.costs.item(r, 0)
                val_item = self.costs.item(r, 1)
                if not key_item:
                    continue
                key = (key_item.text() or "").strip()
                if key not in baseline_map:
                    continue
                base = baseline_map[key]

                if key in ("Target GM", "Overhead Rate"):
                    txt = _fmt_pct(float(base))
                elif key == "GM Band":
                    txt = str(base)
                else:
                    txt = _fmt_money(float(base))

                if val_item is None:
                    val_item = QTableWidgetItem(txt)
                    self.costs.setItem(r, 1, val_item)
                else:
                    val_item.setText(txt)
                val_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)

            # Recompute Δ markers (they should all clear)
            for rr in range(self.costs.rowCount()):
                self._set_costs_delta_marker(rr)
        finally:
            self.costs.blockSignals(False)

        # Keep the Total pill in sync with the baseline Revenue Target
        try:
            self._refresh_material_total_pill(None)  # reads 'Revenue Target' from the grid
        except Exception:
            pass

        # [BM-COSTS-COMMISSION|reset-baseline|clear-overrides|v1]
        try:
            if getattr(self, "_user_cost_overrides", None):
                self._user_cost_overrides.pop("commission_total", None)
                self._user_cost_overrides.pop("labor_cost", None)
        except Exception:
            pass

  
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
        from PySide6.QtGui import QFont, QFontMetrics

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
    # [BM-FIX-E|catalog|v2]
    @lore_guard("reload catalog failure", severity="low")
    def on_reload_catalog(self):
        try:
            set_context(file="app.py", func="on_reload_catalog")
            record_decision(
                title="catalog reload semantics",
                options=["lazy reload on open", "manual refresh only", "filesystem watcher with debounce"],
                decision="manual refresh; recompute with fresh prices",
                rationale="determinism and clarity",
                status="accepted"
            )
        except Exception:
            pass

        reload_catalog()

        try:


            # [BM-CATALOG|version-log|v1]
            try:
                from core.catalog import load_catalog
                current_catalog_version_string = str(getattr(load_catalog(), "version", "unknown"))
            except Exception:
                current_catalog_version_string = "unknown"
            set_context(catalog_version=current_catalog_version_string)
            log_event("catalog", "catalog_reloaded", [f"version={current_catalog_version_string}"])


        except Exception:
            pass

        try:
            self.recompute_pricing(force_catalog_reload=True)
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

def _wire_costs_signals(self):
    """
    Idempotently wire the Costs table signals:
      - itemChanged -> on_costs_cell_changed (handles edits like Labor/GM/Revenue)
      - cellClicked -> _on_costs_delta_clicked (click Δ to reset entire Costs)
    Uses UniqueConnection to avoid duplicate connections across repaints.
    """
    try:
        from PySide6.QtCore import Qt
        if getattr(self, "costs", None):
            try:
                self.costs.itemChanged.connect(self.on_costs_cell_changed, Qt.ConnectionType.UniqueConnection)
            except TypeError:
                # Fallback for older PySide6 without UniqueConnection overload
                try: self.costs.itemChanged.disconnect(self.on_costs_cell_changed)
                except Exception: pass
                self.costs.itemChanged.connect(self.on_costs_cell_changed)

            try:
                self.costs.cellClicked.connect(self._on_costs_delta_clicked, Qt.ConnectionType.UniqueConnection)
            except TypeError:
                try: self.costs.cellClicked.disconnect(self._on_costs_delta_clicked)
                except Exception: pass
                self.costs.cellClicked.connect(self._on_costs_delta_clicked)
    except Exception:
        # Never hard-fail on wiring (UI is still usable)
        pass

if __name__ == "__main__":
    import sys
    if not ((3, 10) <= sys.version_info < (3, 14)):
        raise SystemExit("Please run with Python 3.10–3.13 (tested on 3.12.x).")

    from PySide6.QtGui import QFontMetrics, QGuiApplication
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

# --- bidmule: auto-hide yellow banner ---
def _bm_hide_yellow_banner_if_any(_root=None):
    try:
        from PyQt5 import QtWidgets, QtGui
    except Exception:
        try:
            from PySide2 import QtWidgets, QtGui
        except Exception:
            return
    app = QtWidgets.QApplication.instance()
    if not app:
        return
    for w in app.allWidgets():
        try:
            name = (w.objectName() or "").lower()
            if any(k in name for k in ('banner', 'alert', 'warning', 'notice')):
                try:
                    w.hide()
                    w.setFixedHeight(0)
                except Exception:
                    pass
            # Style-based hide (yellow background)
            try:
                ss = (w.styleSheet() or "").lower()
                if "yellow" in ss or "#ff0" in ss or "#ffff" in ss:
                    w.hide()
                    w.setFixedHeight(0)
            except Exception:
                pass
        except Exception:
            pass

# best-effort: run after startup via single shot timer if Qt is present
try:
    from PyQt5 import QtCore
    QtCore.QTimer.singleShot(0, _bm_hide_yellow_banner_if_any)
except Exception:
    try:
        from PySide2 import QtCore
        QtCore.QTimer.singleShot(0, _bm_hide_yellow_banner_if_any)
    except Exception:
        pass
# --- /bidmule: auto-hide yellow banner ---

