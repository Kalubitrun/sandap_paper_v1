#!/bin/bash
# Container entrypoint: default $PORT (Render injects it), then supervise
# FastAPI (internal :8000) and Next.js (public :$PORT).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
export PORT="${PORT:-3000}"
export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
exec supervisord -c "$HERE/supervisord.conf"
