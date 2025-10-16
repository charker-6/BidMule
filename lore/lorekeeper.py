# lorekeeper.py — lowercase lore utilities (ASCII, append-only)
import os
import traceback
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # .../projectfolder/lore
CHRONICLES = os.path.join(BASE_DIR, "chronicles.txt")
ADVISOR = os.path.join(BASE_DIR, "advisorcodex.txt")
LAWS = os.path.join(BASE_DIR, "lawsindex.txt")
PROPHECIES = os.path.join(BASE_DIR, "prophecies.txt")
DIALOGUES_DIR = os.path.join(BASE_DIR, "dialogues")

DIV = "=" * 79

HEADERS = {
    CHRONICLES: f"""{DIV}
BIDMULE CHRONICLES - the living lineage
{DIV}
maintained by: grand vizier
note: append chronologically; never rewrite history
{DIV}
""",
    ADVISOR: f"""{DIV}
THE ADVISOR CODEX - path of lore
{DIV}
maintained by: the great advisor
purpose: iconography, color systems, interface metaphors, narrative style
{DIV}
""",
    LAWS: f"""{DIV}
BIDMULE LAWS INDEX - path of law
{DIV}
maintained by: grand vizier
rule changes logged chronologically; no deletions, only addenda
{DIV}
""",
    PROPHECIES: f"""{DIV}
PROPHECIES OF BIDMULE - the forward path
{DIV}
authored by: visionary
curated by: grand vizier
{DIV}
""",
}

def _ensure_dirs_and_headers():
    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(DIALOGUES_DIR, exist_ok=True)
    for path, header in HEADERS.items():
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(header)

def _append_block(path: str, title: str, lines: list[str]) -> None:
    _ensure_dirs_and_headers()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = [DIV, f"{title} - {ts}", DIV]
    block.extend(lines)
    block.append(DIV)
    block.append("end of entry")
    block.append(DIV)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(block) + "\n")

def append_to_chronicles(title: str, lines: list[str]) -> None:
    _append_block(CHRONICLES, title, lines)

def append_to_prophecies(title: str, lines: list[str]) -> None:
    _append_block(PROPHECIES, title, lines)

def append_to_advisorcodex(title: str, lines: list[str]) -> None:
    _append_block(ADVISOR, title, lines)

def append_law_once(code: str, text: str) -> bool:
    """Add a law line if not already present. Returns True if added."""
    _ensure_dirs_and_headers()
    needle = f"{code} "
    if os.path.exists(LAWS):
        with open(LAWS, "r", encoding="utf-8") as f:
            if needle in f.read():
                return False
    with open(LAWS, "a", encoding="utf-8", newline="\n") as f:
        if os.path.getsize(LAWS) > 0 and not open(LAWS, "r", encoding="utf-8").read().endswith("\n"):
            f.write("\n")
        f.write(f"{code} {text}\n")
    return True

def log_app_event(event: str, details: list[str] | None = None) -> None:
    details = details or []
    lines = [f"event: {event}"]
    lines.extend([f"- {d}" for d in details])
    append_to_chronicles("channeler log", lines)

def log_error(event: str, err: Exception) -> None:
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    lines = [f"error: {event}", "traceback:", tb.strip()]
    append_to_chronicles("channeler error", lines)

def record_dialogue(date_str: str, participants: str, topic: str, transcript: str, outcome: str) -> str:
    _ensure_dirs_and_headers()
    safe_name = f"{date_str} - {participants} - {topic}.txt"
    path = os.path.join(DIALOGUES_DIR, safe_name)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"""{DIV}
DIALOGUE RECORD
date: {date_str}
participants: {participants}
topic: {topic}
{DIV}
transcript:
{transcript.strip()}
{DIV}
outcome / directives:
{outcome.strip()}
{DIV}
""")
    return path
