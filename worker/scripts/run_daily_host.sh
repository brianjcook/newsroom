#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
PYUSERBASE_DIR="$ROOT_DIR/.pyuser"
LOG_DIR="$ROOT_DIR/storage/logs"
LOG_FILE="$LOG_DIR/run_daily.log"

mkdir -p "$LOG_DIR"

export PYTHONPATH="$ROOT_DIR/worker"
export PYTHONUSERBASE="$PYUSERBASE_DIR"
export NEWSROOM_DB_HOST="${NEWSROOM_DB_HOST:-localhost}"
export NEWSROOM_DB_PORT="${NEWSROOM_DB_PORT:-3306}"
export NEWSROOM_DB_NAME="${NEWSROOM_DB_NAME:-bricoo10_newsroom}"
export NEWSROOM_DB_USER="${NEWSROOM_DB_USER:-}"
export NEWSROOM_DB_PASSWORD="${NEWSROOM_DB_PASSWORD:-}"
export NEWSROOM_DB_UNIX_SOCKET="${NEWSROOM_DB_UNIX_SOCKET:-/run/mysqld/mysqld.sock}"
export NEWSROOM_SOURCE_DISCOVERY_ENABLED="${NEWSROOM_SOURCE_DISCOVERY_ENABLED:-1}"

cd "$ROOT_DIR"
python3 worker/scripts/run_daily.py >> "$LOG_FILE" 2>&1
