#!/usr/bin/env bash
# 本地一键启动（需要后端依赖已安装、PostgreSQL 可选）。
set -euo pipefail
cd "$(dirname "$0")"

export PYTHONPATH="$(pwd)/backend:${PYTHONPATH:-}"
export DATABASE_URL="${DATABASE_URL:-}"

echo "[1/2] 启动 FastAPI（:8000）..."
( cd backend && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 ) &
API_PID=$!

echo "[2/2] 启动 Vite（:5173）..."
( cd frontend && npm run dev ) &
WEB_PID=$!

trap 'kill $API_PID $WEB_PID 2>/dev/null || true' EXIT
wait
