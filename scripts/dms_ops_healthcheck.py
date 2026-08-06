#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from redis import Redis


def parse_args() -> argparse.Namespace:
    home = Path.home()
    parser = argparse.ArgumentParser(
        description="Validate the supervised DMS runtime without exposing secrets."
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("DMS_REPO", str(home / "projects/dms-service")),
    )
    parser.add_argument(
        "--bench",
        default=os.environ.get(
            "DMS_BENCH", str(home / "frappe/dms-frappe-bench")
        ),
    )
    parser.add_argument(
        "--site",
        default=os.environ.get("DMS_SITE", "dms.localhost"),
    )
    parser.add_argument(
        "--bench-command",
        default=os.environ.get("DMS_BENCH_COMMAND", "bench"),
    )
    parser.add_argument(
        "--backend-url",
        default=os.environ.get(
            "DMS_BACKEND_HEALTH_URL",
            "http://127.0.0.1:8000/api/method/ping",
        ),
    )
    parser.add_argument(
        "--frontend-url",
        default=os.environ.get(
            "DMS_FRONTEND_HEALTH_URL", "http://127.0.0.1:3000/login"
        ),
    )
    parser.add_argument(
        "--socketio-url",
        default=os.environ.get(
            "DMS_SOCKETIO_HEALTH_URL",
            "http://127.0.0.1:9000/socket.io/?EIO=4&transport=polling",
        ),
    )
    parser.add_argument("--unit", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def request_json_or_text(url: str, host: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Host": host,
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            "User-Agent": "dms-ops-healthcheck/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(1024 * 1024)
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        body = exc.read(1024 * 1024)
        status = int(exc.code)
    return {
        "status": status,
        "body": body.decode("utf-8", errors="replace"),
    }


def extract_json(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"No JSON object found in command output: {text!r}")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise TypeError("Expected a JSON object from the Frappe preflight probe.")
    return parsed


def main() -> int:
    args = parse_args()
    bench = Path(args.bench).resolve()
    repo = Path(args.repo).resolve()
    common_config = bench / "sites/common_site_config.json"
    result: dict[str, Any] = {
        "status": "pass",
        "repo": str(repo),
        "bench": str(bench),
        "site": args.site,
        "checks": {},
        "errors": [],
    }

    try:
        backend = request_json_or_text(args.backend_url, args.site, args.timeout)
        if backend["status"] != 200 or "pong" not in backend["body"].lower():
            raise RuntimeError(
                f"Backend ping failed: HTTP {backend['status']} {backend['body'][:300]!r}"
            )
        result["checks"]["backend"] = {"http_status": backend["status"]}
    except Exception as exc:
        result["errors"].append(f"backend: {type(exc).__name__}: {exc}")

    try:
        frontend = request_json_or_text(args.frontend_url, args.site, args.timeout)
        if frontend["status"] != 200:
            raise RuntimeError(f"Frontend login failed: HTTP {frontend['status']}")
        result["checks"]["frontend"] = {"http_status": frontend["status"]}
    except Exception as exc:
        result["errors"].append(f"frontend: {type(exc).__name__}: {exc}")

    try:
        socketio = request_json_or_text(args.socketio_url, args.site, args.timeout)
        body = socketio["body"].lstrip()
        if socketio["status"] != 200 or not body.startswith("0"):
            raise RuntimeError(
                "Socket.IO handshake failed: "
                f"HTTP {socketio['status']} {body[:300]!r}"
            )
        result["checks"]["socketio"] = {
            "http_status": socketio["status"],
            "engine_open_packet": True,
        }
    except Exception as exc:
        result["errors"].append(f"socketio: {type(exc).__name__}: {exc}")

    try:
        config = json.loads(common_config.read_text())
        redis_checks = {}
        for key in ("redis_cache", "redis_queue"):
            url = str(config.get(key) or "")
            if not url:
                raise RuntimeError(f"Missing {key} in {common_config}")
            client = Redis.from_url(
                url,
                socket_connect_timeout=args.timeout,
                socket_timeout=args.timeout,
            )
            if client.ping() is not True:
                raise RuntimeError(f"{key} did not return PONG")
            redis_checks[key] = True
        result["checks"]["redis"] = redis_checks
    except Exception as exc:
        result["errors"].append(f"redis: {type(exc).__name__}: {exc}")

    try:
        completed = subprocess.run(
            [
                args.bench_command,
                "--site",
                args.site,
                "execute",
                "dms.auth_setup.preflight_probe",
            ],
            cwd=bench,
            text=True,
            capture_output=True,
            timeout=max(30.0, args.timeout * 4),
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"preflight exit={completed.returncode}; stderr={completed.stderr[-1000:]!r}"
            )
        preflight = extract_json(completed.stdout)
        if preflight.get("status") != "pass":
            raise RuntimeError(f"Frappe preflight did not pass: {preflight!r}")
        if not (
            preflight.get("database")
            and preflight.get("redis_cache")
            and preflight.get("redis_queue")
        ):
            raise RuntimeError(f"Frappe dependencies failed: {preflight!r}")
        users = preflight.get("users") or []
        if len(users) != 4 or not all(
            row.get("exists")
            and row.get("enabled")
            and row.get("exact_dms_role")
            for row in users
        ):
            raise RuntimeError(f"Frappe user contract failed: {users!r}")
        result["checks"]["frappe"] = {
            "database": True,
            "redis_cache": True,
            "redis_queue": True,
            "exact_role_users": len(users),
        }
    except Exception as exc:
        result["errors"].append(f"frappe: {type(exc).__name__}: {exc}")

    if args.unit:
        unit_states = {}
        for unit in args.unit:
            completed = subprocess.run(
                ["systemctl", "is-active", unit],
                text=True,
                capture_output=True,
                check=False,
            )
            state = completed.stdout.strip() or completed.stderr.strip()
            unit_states[unit] = state
            if completed.returncode != 0 or state != "active":
                result["errors"].append(f"systemd: {unit} is {state!r}")
        result["checks"]["systemd"] = unit_states

    if result["errors"]:
        result["status"] = "fail"

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
