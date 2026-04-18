#!/usr/bin/env bash
# Free backend/frontend ports and start uvicorn + Vite (pixel-love-studio).
# Usage: from repo root —  chmod +x scripts/dev.sh && ./scripts/dev.sh
# Ctrl+C stops both servers.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
VENV_PY="${ROOT}/.venv/bin/python"
UVICORN="${ROOT}/.venv/bin/uvicorn"

kill_listeners() {
  local port="$1"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    echo "[dev] :$port is free"
    return 0
  fi
  echo "[dev] stopping listener(s) on :$port — $pids"
  kill $pids 2>/dev/null || true
  sleep 0.7
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "[dev] force kill :$port — $pids"
    kill -9 $pids 2>/dev/null || true
    sleep 0.3
  fi
}

if [[ ! -x "$UVICORN" ]]; then
  echo "error: missing $UVICORN — run: python3.11 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

if [[ ! -d "${ROOT}/pixel-love-studio/node_modules" ]]; then
  echo "error: run once: cd pixel-love-studio && npm install" >&2
  exit 1
fi

kill_listeners "$BACKEND_PORT"
kill_listeners "$FRONTEND_PORT"

UV_PID=""
FE_PID=""
cleanup() {
  echo ""
  echo "[dev] shutting down…"
  [[ -n "${UV_PID:-}" ]] && kill "$UV_PID" 2>/dev/null || true
  [[ -n "${FE_PID:-}" ]] && kill "$FE_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[dev] backend  http://127.0.0.1:${BACKEND_PORT}  (docs: /docs)"
"$UVICORN" backend.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT" &
UV_PID=$!

echo "[dev] frontend http://127.0.0.1:${FRONTEND_PORT}"
(
  cd "${ROOT}/pixel-love-studio"
  exec npm run dev -- --port "$FRONTEND_PORT" --strictPort
) &
FE_PID=$!

echo "[dev] ready — Ctrl+C to stop both"
wait $UV_PID $FE_PID
