#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Đảm bảo luồng stdin hợp lệ nếu chạy ngầm/daemon
if ! 0<&0 2>/dev/null; then
    exec 0</dev/null
fi

echo "=========================================================="
echo "   AI TRADING MULTI-AGENT (ANTIGRAVITY NATIVE SESSION)"
echo "   Chạy qua tài khoản Antigravity - KHÔNG CẦN API KEY"
echo "=========================================================="

if [ ! -d "$DIR/.venv" ]; then
    echo "Đang khởi tạo môi trường ảo..."
    uv venv "$DIR/.venv" --python 3.12
    uv pip install -r requirements.txt
fi

# Chạy với Python trong môi trường ảo
exec "$DIR/.venv/bin/python" main_antigravity.py "$@"
