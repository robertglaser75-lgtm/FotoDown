#!/usr/bin/env bash
# FotoDown Linux Launcher

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python fotodown.py "$@"
elif command -v python3 &>/dev/null; then
    python3 fotodown.py "$@"
elif command -v python &>/dev/null; then
    python fotodown.py "$@"
else
    echo "[Fehler] Python 3 wurde nicht gefunden. Bitte installieren Sie Python 3."
    exit 1
fi
