#!/bin/bash
set -e

# Default values if not provided by the environment
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
WORKERS="${WORKERS:-2}"

exec gunicorn app:app --bind "${HOST}:${PORT}" --workers "${WORKERS}" "$@"
