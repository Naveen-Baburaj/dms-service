#!/usr/bin/env bash
set -Eeuo pipefail

BENCH_DIR="/home/frappe/frappe-bench"
SITE_NAME="${DMS_FRAPPE_SITE:-dms.localhost}"
SITE_DIR="$BENCH_DIR/sites/$SITE_NAME"
PORT="${PORT:-8000}"

required=(DB_HOST DB_PORT DB_NAME DB_PASSWORD REDIS_CACHE REDIS_QUEUE)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: $name" >&2
    exit 20
  fi
done

mkdir -p "$SITE_DIR/private/files" "$SITE_DIR/public/files" "$BENCH_DIR/logs"

export SITE_NAME SITE_DIR BENCH_DIR
python3 - <<'PY'
from pathlib import Path
import json
import os

bench = Path(os.environ["BENCH_DIR"])
site_name = os.environ["SITE_NAME"]
site_dir = Path(os.environ["SITE_DIR"])

def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)

common = {
    "db_host": env("DB_HOST"),
    "db_port": int(env("DB_PORT", "3306")),
    "redis_cache": env("REDIS_CACHE"),
    "redis_queue": env("REDIS_QUEUE"),
    "redis_socketio": env("REDIS_SOCKETIO", env("REDIS_QUEUE")),
    "socketio_port": 9000,
}

site = {
    "db_name": env("DB_NAME"),
    "db_password": env("DB_PASSWORD"),
    "db_type": "mariadb",
    "db_host": env("DB_HOST"),
    "db_port": int(env("DB_PORT", "3306")),
    "ignore_csrf": int(env("DMS_IGNORE_CSRF", "1")),
    "dms_production_auth_required": 1,
    "dms_agentic_enabled": int(env("DMS_AGENTIC_ENABLED", "1")),
    "dms_agentic_fallback_enabled": int(env("DMS_AGENTIC_FALLBACK_ENABLED", "1")),
    "dms_agentic_max_steps": int(env("DMS_AGENTIC_MAX_STEPS", "8")),
    "dms_agentic_max_tool_calls": int(env("DMS_AGENTIC_MAX_TOOL_CALLS", "16")),
    "dms_agentic_reasoning_effort": env("DMS_AGENTIC_REASONING_EFFORT", "high"),
    "openai_timeout_seconds": int(env("OPENAI_TIMEOUT_SECONDS", "75")),
    "openai_max_retries": int(env("OPENAI_MAX_RETRIES", "2")),
    "openai_max_output_tokens": int(env("OPENAI_MAX_OUTPUT_TOKENS", "2400")),
}

public_origin = env("DMS_PUBLIC_ORIGIN")
if public_origin:
    site["allow_cors"] = [public_origin]

(bench / "sites" / "common_site_config.json").write_text(
    json.dumps(common, indent=2, sort_keys=True) + "\n"
)
(site_dir / "site_config.json").write_text(
    json.dumps(site, indent=2, sort_keys=True) + "\n"
)
(bench / "sites" / "currentsite.txt").write_text(site_name + "\n")

apps_file = bench / "sites" / "apps.txt"
apps = [line.strip() for line in apps_file.read_text().splitlines() if line.strip()]
for app in ("frappe", "dms"):
    if app not in apps:
        apps.append(app)
apps_file.write_text("\n".join(apps) + "\n")
PY

cd "$BENCH_DIR"

if [[ "${RUN_MIGRATE:-0}" == "1" ]]; then
  echo "Running Frappe migrations for $SITE_NAME"
  bench --site "$SITE_NAME" migrate
fi

if [[ "${RUN_CLEAR_CACHE:-0}" == "1" ]]; then
  bench --site "$SITE_NAME" clear-cache || true
fi

echo "Starting Frappe $SITE_NAME on 0.0.0.0:$PORT"
exec gunicorn \
  --bind "0.0.0.0:$PORT" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --worker-class gthread \
  --worker-tmp-dir /dev/shm \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  frappe.app:application \
  --preload
