#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

PYTHON_BIN="python3"
if [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$DIR/.venv/bin/python"
fi

exec "$PYTHON_BIN" server.py --open "$@"
