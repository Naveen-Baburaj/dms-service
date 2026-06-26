from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


class RPAValidationError(ValueError):
    """Raised when frontend/backend input is not suitable for RPA execution."""


class GHLLoginRequired(RuntimeError):
    """Raised when a GHL browser session is missing or expired."""


@dataclass
class ContactPayload:
    first_name: str
    last_name: str = ""
    email: str = ""
    phone: str = ""
    vehicle_interest: str = ""
    source: str = "DMS RPA Demo"
    notes: str = ""

    @property
    def contact_name(self) -> str:
        name = " ".join(part for part in [self.first_name, self.last_name] if part).strip()
        return name or self.email or self.phone or "Unnamed Contact"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"contact_name": self.contact_name}

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "ContactPayload":
        raw = raw or {}

        first_name = str(
            raw.get("first_name")
            or raw.get("firstName")
            or raw.get("first")
            or ""
        ).strip()

        full_name = str(raw.get("contact_name") or raw.get("name") or "").strip()
        last_name = str(raw.get("last_name") or raw.get("lastName") or raw.get("last") or "").strip()

        if not first_name and full_name:
            parts = full_name.split()
            first_name = parts[0]
            if not last_name and len(parts) > 1:
                last_name = " ".join(parts[1:])

        email = str(raw.get("email") or "").strip()
        phone = str(raw.get("phone") or raw.get("mobile_no") or raw.get("mobile") or "").strip()

        if not first_name:
            raise RPAValidationError("First name is required for GoHighLevel contact creation.")

        return cls(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            vehicle_interest=str(raw.get("vehicle_interest") or raw.get("vehicleInterest") or "").strip(),
            source=str(raw.get("source") or "DMS RPA Demo").strip() or "DMS RPA Demo",
            notes=str(raw.get("notes") or "").strip(),
        )


@dataclass
class RPAResult:
    success: bool
    status: str
    message: str
    contact_name: str | None = None
    contact_url: str | None = None
    screenshot_before: str | None = None
    screenshot_after: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_target(value: str | None) -> str:
    target = (value or "both").strip().lower().replace("-", "_")
    aliases = {
        "local": "dms",
        "backend": "dms",
        "frappe": "dms",
        "ghl_only": "ghl",
        "gohighlevel": "ghl",
        "crm": "ghl",
        "both": "both",
        "all": "both",
    }
    target = aliases.get(target, target)

    if target not in {"dms", "ghl", "both"}:
        raise RPAValidationError("target must be one of: dms, ghl, both")

    return target


def target_label(target: str) -> str:
    return {
        "dms": "DMS Only",
        "ghl": "GoHighLevel Only",
        "both": "Both",
    }[normalize_target(target)]
