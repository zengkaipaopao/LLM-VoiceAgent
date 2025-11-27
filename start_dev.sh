#!/usr/bin/env bash
# 一键启动后端 (FastAPI) 与前端 (Vite)，并在退出时清理子进程。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

ensure_poetry() {
  POETRY_BIN="$(command -v poetry || true)"
  if [ -n "$POETRY_BIN" ]; then
    echo "检测到 poetry: $POETRY_BIN"
    return
  fi
  echo "poetry 未找到，尝试自动安装 (pip --user)..."
  if command -v pip3 >/dev/null 2>&1; then
    pip3 install --user poetry && POETRY_BIN="$(command -v poetry || true)"
  elif command -v pip >/dev/null 2>&1; then
    pip install --user poetry && POETRY_BIN="$(command -v poetry || true)"
  fi
  if [ -z "$POETRY_BIN" ]; then
    echo "poetry 安装失败，请手动安装后重试" >&2
    exit 1
  fi
}

ensure_node_modules() {
  if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
    echo "前端依赖未安装，执行 npm install..."
    (cd "$ROOT_DIR/frontend" && npm install)
  fi
  if [ ! -d "$ROOT_DIR/backend/.venv" ] && [ -n "$POETRY_BIN" ]; then
    echo "后端依赖未安装，执行 poetry install..."
    (cd "$ROOT_DIR/backend" && "$POETRY_BIN" install)
  fi
}

ensure_poetry
ensure_node_modules

BACKEND_CMD="cd \"$ROOT_DIR/backend\" && $POETRY_BIN run uvicorn app.main:app --reload --port 8000"
FRONTEND_CMD="cd \"$ROOT_DIR/frontend\" && npm run dev"

# 捕获退出信号，清理子进程
cleanup() {
  echo "\n停止前后端进程..."
  pkill -P $$ 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "启动后端: $BACKEND_CMD"
/bin/bash -c "$BACKEND_CMD" &
BACK_PID=$!

echo "启动前端: $FRONTEND_CMD"
/bin/bash -c "$FRONTEND_CMD" &
FRONT_PID=$!

# 轮询监控任一子进程退出（macOS 的 bash 无 wait -n）
while true; do
  if ! kill -0 $BACK_PID 2>/dev/null; then
    echo "后端进程已退出，停止前端..."
    kill $FRONT_PID 2>/dev/null || true
    break
  fi
  if ! kill -0 $FRONT_PID 2>/dev/null; then
    echo "前端进程已退出，停止后端..."
    kill $BACK_PID 2>/dev/null || true
    break
  fi
  sleep 1
done

# 等待清理
wait $BACK_PID 2>/dev/null || true
wait $FRONT_PID 2>/dev/null || true
