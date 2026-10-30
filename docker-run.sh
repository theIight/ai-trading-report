#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

mkdir -p "$DIR/Kết quả" "$DIR/cache"

# Build image nếu chưa có
if ! docker image inspect ai-trading:latest >/dev/null 2>&1; then
    echo "Đang build Docker image 'ai-trading:latest'..."
    docker build -t ai-trading:latest .
fi

# Chạy container interactive
echo "Khởi chạy AI Trading trong Docker..."
docker run -it --rm \
    --name ai-trading-run \
    -v "$DIR/Kết quả:/app/Kết quả" \
    -v "$DIR/cache:/app/cache" \
    $( [ -f "$DIR/.env" ] && echo "--env-file $DIR/.env" ) \
    $( [ -f "$DIR/khoa-gemini.txt" ] && echo "-v $DIR/khoa-gemini.txt:/app/khoa-gemini.txt:ro" ) \
    -e GOOGLE_API_KEY="${GOOGLE_API_KEY:-}" \
    ai-trading:latest "$@"
