#!/usr/bin/env bash
set -e

# Chuyển về thư mục chứa script
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=================================================="
echo "    AI TRADING - Multi-Agent System (macOS / Linux)"
echo "=================================================="
echo "Chỉ phục vụ học tập và nghiên cứu, KHÔNG phải lời khuyên đầu tư."
echo ""

# 1. Tìm hoặc thiết lập Python phù hợp (>= 3.11)
VENV_DIR="$DIR/.venv"
PYTHON_BIN=""

if command -v uv >/dev/null 2>&1; then
    if [ ! -d "$VENV_DIR" ]; then
        echo "[1/3] Khởi tạo môi trường ảo Python 3.12 qua 'uv'..."
        uv venv "$VENV_DIR" --python 3.12
    fi
    PYTHON_BIN="$VENV_DIR/bin/python"
    
    if [ ! -f "$VENV_DIR/.installed" ]; then
        echo "[2/3] Cài đặt các thư viện cần thiết (TradingAgents v0.5.2)..."
        uv pip install -r requirements.txt
        touch "$VENV_DIR/.installed"
    fi
else
    # Tìm python khả dụng
    for py in python3.12 python3.13 python3.11 python3; do
        if command -v "$py" >/dev/null 2>&1; then
            VER=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            MAJOR=$(echo "$VER" | cut -d. -f1)
            MINOR=$(echo "$VER" | cut -d. -f2)
            if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 11 ]; then
                FOUND_PY="$py"
                break
            fi
        fi
    done

    if [ -z "$FOUND_PY" ]; then
        echo "LỖI: Không tìm thấy Python 3.11 trở lên trên hệ thống."
        echo "Hãy cài đặt Python 3.12 qua Homebrew:"
        echo "    brew install python@3.12"
        exit 1
    fi

    if [ ! -d "$VENV_DIR" ]; then
        echo "[1/3] Tạo môi trường ảo với $FOUND_PY..."
        "$FOUND_PY" -m venv "$VENV_DIR"
    fi
    PYTHON_BIN="$VENV_DIR/bin/python"

    if [ ! -f "$VENV_DIR/.installed" ]; then
        echo "[2/3] Cài đặt thư viện (TradingAgents v0.5.2)..."
        "$PYTHON_BIN" -m pip install --upgrade pip -q
        "$PYTHON_BIN" -m pip install -r requirements.txt
        touch "$VENV_DIR/.installed"
    fi
fi

echo "[3/3] Môi trường đã sẵn sàng!"
echo ""

# Chạy main.py
exec "$PYTHON_BIN" main.py "$@"
