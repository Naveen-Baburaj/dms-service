"""Railway liveness wrapper around the Frappe WSGI application."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from frappe.app import application as frappe_application


StartResponse = Callable[[str, list[tuple[str, str]]], Any]


def application(
    environ: dict[str, Any], start_response: StartResponse
) -> Iterable[bytes]:
    """Answer Railway's liveness probe without requiring a tenant Host header."""

    if environ.get("PATH_INFO") == "/_health":
        body = b"ok\n"
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ],
        )
        if environ.get("REQUEST_METHOD") == "HEAD":
            return [b""]
        return [body]

    return frappe_application(environ, start_response)
