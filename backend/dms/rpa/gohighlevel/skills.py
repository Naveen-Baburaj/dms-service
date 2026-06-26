from __future__ import annotations

from .schemas import ContactPayload, RPAResult


def add_contact_to_gohighlevel(
    contact: ContactPayload,
    contacts_url: str | None = None,
    session_name: str | None = None,
) -> RPAResult:
    """Placeholder for the GoHighLevel contact-entry browser skill.

    The surrounding module is complete: API endpoints, session checking,
    local DocTypes, job logging, target=dms|ghl|both orchestration, and
    admin-only access. The concrete Playwright selector routine must be
    applied locally because this connector blocked the detailed UI-action file.
    """
    raise RuntimeError(
        "GoHighLevel Playwright contact-entry skill is not installed. "
        "Apply the local skills.py routine generated in the handoff before running target=ghl or target=both."
    )
