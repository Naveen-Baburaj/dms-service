from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolContext:
    request_id: str
    user: str
    role: str
    tenant_id: str | None
    is_admin: bool
    company_id: str | None
    company_name: str | None

    def public_scope(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "user": self.user,
            "role": self.role,
            "tenant_id": self.tenant_id,
            "is_admin": self.is_admin,
            "company_id": self.company_id,
            "company_name": self.company_name,
        }


ToolHandler = Callable[[ToolContext, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    allowed_roles: frozenset[str]
    read_only: bool = True
    timeout_seconds: int = 20
    max_output_chars: int = 80_000
