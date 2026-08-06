#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${DMS_REPO:-$HOME/projects/dms-service}"
BENCH="${DMS_BENCH:-$HOME/frappe/dms-frappe-bench}"
SITE="${DMS_SITE:-dms.localhost}"
BENCH_NAME="$(basename "$BENCH")"
if [[ -n "${DMS_BENCH_COMMAND:-}" ]]; then
  BENCH_COMMAND="$DMS_BENCH_COMMAND"
elif [[ -x "$HOME/miniconda3/envs/dms-frappe/bin/bench" ]]; then
  BENCH_COMMAND="$HOME/miniconda3/envs/dms-frappe/bin/bench"
else
  BENCH_COMMAND="$(command -v bench)"
fi
[[ -n "$BENCH_COMMAND" && -x "$BENCH_COMMAND" ]]

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

systemctl --no-pager --full status "${units[@]}" || true

args=(
  --repo "$REPO"
  --bench "$BENCH"
  --site "$SITE"
  --bench-command "$BENCH_COMMAND"
)
for unit in "${units[@]}"; do
  args+=(--unit "$unit")
done

exec "$BENCH/env/bin/python" "$REPO/scripts/dms_ops_healthcheck.py" "${args[@]}"
