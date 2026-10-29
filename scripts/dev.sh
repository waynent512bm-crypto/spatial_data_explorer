#!/usr/bin/env bash
# Starts backend + frontend for local development (macOS / Linux).
#   ./scripts/dev.sh                                    # synthetic demo data
#   ./scripts/dev.sh /path/to/annotated.h5ad xenium [layer]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/backend/.venv/bin/python"
H5AD="${1:-}"
PLATFORM="${2:-xenium}"
LAYER="${3:-}"
PORT="${SDE_PORT:-8000}"

if [ ! -x "$PY" ]; then
  echo "Creating backend virtualenv..."
  python3 -m venv "$ROOT/backend/.venv"
  "$PY" -m pip install -e "$ROOT/backend[dev]"
fi
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "Installing frontend packages..."
  (cd "$ROOT/frontend" && npm install)
fi
if [ -z "$H5AD" ]; then
  H5AD="$ROOT/data/demo/demo_annotated.h5ad"
  [ -f "$H5AD" ] || "$PY" -m sde demo --out "$ROOT/data/demo"
fi

ARGS=(-m sde serve --h5ad "$H5AD" --platform "$PLATFORM" --port "$PORT")
[ -n "$LAYER" ] && ARGS+=(--layer "$LAYER")
"$PY" "${ARGS[@]}" &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT

cd "$ROOT/frontend"
SDE_BACKEND="http://127.0.0.1:$PORT" npm run dev
