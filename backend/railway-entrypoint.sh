#!/usr/bin/env bash
set -Eeuo pipefail

readonly BENCH_DIR="/home/frappe/frappe-bench"
readonly SITE_NAME="${DMS_FRAPPE_SITE:-dms.localhost}"
readonly SITE_DIR="$BENCH_DIR/sites/$SITE_NAME"
readonly PORT="${PORT:-8000}"

if [[ ! "$SITE_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid DMS_FRAPPE_SITE: $SITE_NAME" >&2
  exit 20
fi

required=(
  DB_HOST
  DB_PORT
  DB_NAME
  DB_PASSWORD
  REDIS_CACHE
  REDIS_QUEUE
  FRAPPE_ENCRYPTION_KEY
)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: $name" >&2
    exit 20
  fi
done

mkdir -p \
  "$SITE_DIR/private/files" \
  "$SITE_DIR/public/files" \
  "$BENCH_DIR/logs"

export BENCH_DIR SITE_DIR SITE_NAME

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import json
import os
import socket
import subprocess
import time

bench = Path(os.environ["BENCH_DIR"])
site_dir = Path(os.environ["SITE_DIR"])
site_name = os.environ["SITE_NAME"]


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def wait_for_tcp(label: str, host: str, port: int, timeout: int = 90) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            with socket.create_connection((host, port), timeout=5):
                print(f"{label} is reachable at {host}:{port}")
                return
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"Timed out waiting for {label} at {host}:{port}: {exc}"
                ) from exc
            time.sleep(2)


wait_for_tcp("MariaDB", env("DB_HOST"), int(env("DB_PORT", "3306")))

seen_redis: set[tuple[str, int]] = set()
for variable in ("REDIS_CACHE", "REDIS_QUEUE", "REDIS_SOCKETIO"):
    value = env(variable)
    if not value:
        continue
    parsed = urlparse(value)
    target = (parsed.hostname or "", parsed.port or 6379)
    if not target[0] or target in seen_redis:
        continue
    wait_for_tcp(variable, target[0], target[1])
    seen_redis.add(target)

common = {
    "db_host": env("DB_HOST"),
    "db_port": int(env("DB_PORT", "3306")),
    "default_site": site_name,
    "serve_default_site": True,
    "redis_cache": env("REDIS_CACHE"),
    "redis_queue": env("REDIS_QUEUE"),
    "redis_socketio": env("REDIS_SOCKETIO", env("REDIS_QUEUE")),
    "socketio_port": 9000,
}

if env("BOOTSTRAP_EMPTY_SITE", "0") == "1":
    admin_password = env("FRAPPE_ADMIN_PASSWORD")
    if not admin_password:
        raise RuntimeError(
            "FRAPPE_ADMIN_PASSWORD is required when BOOTSTRAP_EMPTY_SITE=1"
        )

    # Site installation uses Frappe's cache while syncing DocTypes and fixtures.
    # Make the private Redis services available before invoking bench new-site.
    (bench / "sites" / "common_site_config.json").write_text(
        json.dumps(common, indent=2, sort_keys=True) + "\n"
    )

    print(f"Bootstrapping empty Frappe site {site_name}")
    try:
        subprocess.run(
            [
                "bench",
                "new-site",
                site_name,
                "--db-type",
                "mariadb",
                "--db-host",
                env("DB_HOST"),
                "--db-port",
                env("DB_PORT", "3306"),
                "--db-name",
                env("DB_NAME"),
                "--db-password",
                env("DB_PASSWORD"),
                "--admin-password",
                admin_password,
                "--no-setup-db",
                "--install-app",
                "dms",
                "--set-default",
                "--force",
            ],
            cwd=bench,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"bench new-site failed with exit code {exc.returncode}"
        ) from None
    subprocess.run(
        [
            "bench",
            "--site",
            site_name,
            "execute",
            "dms.railway_bootstrap.run",
        ],
        cwd=bench,
        check=True,
    )

site = {
    "db_name": env("DB_NAME"),
    "db_password": env("DB_PASSWORD"),
    "db_type": "mariadb",
    "db_host": env("DB_HOST"),
    "db_port": int(env("DB_PORT", "3306")),
    "ignore_csrf": int(env("DMS_IGNORE_CSRF", "1")),
    "dms_production_auth_required": 1,
    "dms_agentic_enabled": int(env("DMS_AGENTIC_ENABLED", "1")),
    "dms_agentic_fallback_enabled": int(
        env("DMS_AGENTIC_FALLBACK_ENABLED", "1")
    ),
    "dms_agentic_max_steps": int(env("DMS_AGENTIC_MAX_STEPS", "8")),
    "dms_agentic_max_tool_calls": int(
        env("DMS_AGENTIC_MAX_TOOL_CALLS", "16")
    ),
    "dms_agentic_reasoning_effort": env(
        "DMS_AGENTIC_REASONING_EFFORT", "high"
    ),
    "openai_timeout_seconds": int(env("OPENAI_TIMEOUT_SECONDS", "75")),
    "openai_max_retries": int(env("OPENAI_MAX_RETRIES", "2")),
    "openai_max_output_tokens": int(
        env("OPENAI_MAX_OUTPUT_TOKENS", "2400")
    ),
}

encryption_key = env("FRAPPE_ENCRYPTION_KEY")
if encryption_key:
    site["encryption_key"] = encryption_key

public_origin = env("DMS_PUBLIC_ORIGIN").rstrip("/")
if public_origin:
    if not public_origin.startswith(("https://", "http://")):
        raise ValueError("DMS_PUBLIC_ORIGIN must be an http(s) origin")
    site["allow_cors"] = [public_origin]
    site["host_name"] = public_origin


def write_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


write_json(bench / "sites" / "common_site_config.json", common)
write_json(site_dir / "site_config.json", site)
(bench / "sites" / "currentsite.txt").write_text(site_name + "\n")

apps_file = bench / "sites" / "apps.txt"
apps = [
    line.strip()
    for line in apps_file.read_text().splitlines()
    if line.strip()
]
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
  --chdir "$BENCH_DIR/sites" \
  --bind "0.0.0.0:$PORT" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --worker-class gthread \
  --worker-tmp-dir /dev/shm \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  frappe.app:application \
  --preload
