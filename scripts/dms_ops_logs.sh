#!/usr/bin/env bash
set -Eeuo pipefail

BENCH="${DMS_BENCH:-$HOME/frappe/dms-frappe-bench}"
BENCH_NAME="$(basename "$BENCH")"
LINES="${DMS_LOG_LINES:-200}"

sudo journalctl --no-pager -n "$LINES"   -u dms-dashboard-frontend.service   -u dms-dashboard-health.service   -u dms-dashboard-recover.service   -u "$BENCH_NAME-redis-cache.service"   -u "$BENCH_NAME-redis-queue.service"   -u "$BENCH_NAME-frappe-web.service"   -u "$BENCH_NAME-node-socketio.service"   -u "$BENCH_NAME-frappe-default-worker@1.service"   -u "$BENCH_NAME-frappe-short-worker@1.service"   -u "$BENCH_NAME-frappe-long-worker@1.service"   -u "$BENCH_NAME-frappe-schedule.service"

printf '\n===== Redis queue errors =====\n'
tail -n "$LINES" "$BENCH/logs/redis-queue.error.log" 2>/dev/null || true
printf '\n===== Redis cache errors =====\n'
tail -n "$LINES" "$BENCH/logs/redis-cache.error.log" 2>/dev/null || true
printf '\n===== Frappe web errors =====\n'
tail -n "$LINES" "$BENCH/logs/web.error.log" 2>/dev/null || true
printf '\n===== Frappe worker errors =====\n'
tail -n "$LINES" "$BENCH/logs/worker.error.log" 2>/dev/null || true
printf '\n===== Scheduler errors =====\n'
tail -n "$LINES" "$BENCH/logs/schedule.error.log" 2>/dev/null || true
printf '\n===== Socket.IO errors =====\n'
tail -n "$LINES" "$BENCH/logs/node-socketio.error.log" 2>/dev/null || true
printf '\n===== Socket.IO output =====\n'
tail -n "$LINES" "$BENCH/logs/node-socketio.log" 2>/dev/null || true
