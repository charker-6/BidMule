#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$PROJECT_ROOT/.venv"
PYTHON_BIN="python3"
VENV_PY="$VENV_PATH/bin/python"

if [ ! -x "$PROJECT_ROOT/run_app.sh" ]; then
  echo "[BidMule] TIP: If './run_app.sh' reports permission denied, run 'chmod +x run_app.sh' once or invoke it via 'bash run_app.sh'."
fi

if [ ! -d "$VENV_PATH" ]; then
  echo "[BidMule] Creating virtual environment at $VENV_PATH"
  "$PYTHON_BIN" -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"
"$VENV_PY" -m pip install --upgrade pip >/dev/null
REQ_FILE="$PROJECT_ROOT/requirements.txt"
if [ ! -f "$REQ_FILE" ]; then
  cat >"$REQ_FILE" <<'EOF'
PySide6>=6.5,<7.0
PyMuPDF>=1.21
pytest>=7
EOF
  echo "[BidMule] Created missing requirements.txt with default dependencies."
fi
echo "[BidMule] Installing Python dependencies"
"$VENV_PY" -m pip install -r "$REQ_FILE"
cd "$PROJECT_ROOT"
echo "[BidMule] Launching BidMule"
exec "$VENV_PY" app.py
