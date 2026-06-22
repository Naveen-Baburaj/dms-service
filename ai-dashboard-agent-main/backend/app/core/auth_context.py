from enum import Enum

from fastapi import Header, HTTPException
from pydantic import BaseModel


class UserRole(str, Enum):
    TENANT_USER = "tenant_user"
    SERVICE_CENTRE_ADMIN = "service_centre_admin"


class AuthContext(BaseModel):
    tenant_id: str | None
    user_role: UserRole


def get_auth_context(
    x_tenant_id: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
) -> AuthContext:
    """
    Local development auth resolver.

    Production rule:
    tenant_id and user_role must come from verified auth/JWT/session,
    not from frontend-controlled values.
    """

    if not x_user_role:
        raise HTTPException(
            status_code=401,
            detail="Missing x-user-role header"
        )

    try:
        user_role = UserRole(x_user_role)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="Invalid user role"
        )

    if user_role == UserRole.TENANT_USER and not x_tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Tenant users require tenant_id"
        )

    return AuthContext(
        tenant_id=x_tenant_id,
        user_role=user_role
    )
