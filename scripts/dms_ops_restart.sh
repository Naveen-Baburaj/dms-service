#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${DMS_REPO:-$HOME/projects/dms-service}"
BENCH="${DMS_BENCH:-$HOME/frappe/dms-frappe-bench}"
SITE="${DMS_SITE:-dms.localhost}"
BENCH_NAME="$(basename "$BENCH")"

units=(
  dms-dashboard.target
  "$BENCH_NAME.target"
  "$BENCH_NAME-redis-cache.service"
  "$BENCH_NAME-redis-queue.service"
  "$BENCH_NAME-frappe-web.service"
  "$BENCH_NAME-node-socketio.service"
  "$BENCH_NAME-frappe-default-worker@1.service"
  "$BENCH_NAME-frappe-short-worker@1.service"
  "$BENCH_NAME-frappe-long-worker@1.service"
  "$BENCH_NAME-frappe-schedule.service"
  dms-dashboard-frontend.service
  dms-dashboard-health.timer
)

echo "Restarting the supervised DMS target..."
sudo systemctl restart dms-dashboard.target

ready=0
for attempt in $(seq 1 180); do
  all_active=1
  for unit in "${units[@]}"; do
    if ! systemctl is-active --quiet "$unit"; then
      all_active=0
      break
    fi
  done

  if [[ "$all_active" -eq 1 ]]       && curl --noproxy '*' -fsS --max-time 3         -H "Host: $SITE"         "http://127.0.0.1:8000/api/method/ping" >/dev/null 2>&1       && curl --noproxy '*' -fsS --max-time 3         -H "Host: $SITE"         "http://127.0.0.1:3000/login" >/dev/null 2>&1; then
    socket_body="$(curl --noproxy '*' -fsS --max-time 3       -H "Host: $SITE"       'http://127.0.0.1:9000/socket.io/?EIO=4&transport=polling'       2>/dev/null || true)"
    if [[ "$socket_body" == 0* ]]; then
      ready=1
      break
    fi
  fi
  sleep 1
done

if [[ "$ready" -ne 1 ]]; then
  echo "The DMS target did not become ready within 180 seconds." >&2
  systemctl --no-pager --full status "${units[@]}" || true
  exit 1
fi

exec "$REPO/scripts/dms_ops_status.sh"
