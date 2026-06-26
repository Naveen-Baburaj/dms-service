from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Iterable

from .config import (
    ghl_contacts_url,
    ghl_tag_name,
    ghl_tag_search_text,
    operation_timeout_ms,
    playwright_headless,
    playwright_slow_mo_ms,
    safe_session_name,
    screenshot_dir,
    storage_state_path,
)
from .schemas import ContactPayload, GHLLoginRequired, RPAResult
from .session import is_probably_logged_in


def _require_playwright():
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import expect, sync_playwright
        return sync_playwright, expect, PlaywrightTimeoutError
    except Exception as exc:
        raise RuntimeError(
            "Playwright is not installed in the Frappe environment. "
            "Install it with: pip install playwright && python -m playwright install chromium"
        ) from exc


def _screenshot(page, session_name: str, prefix: str) -> str | None:
    path = screenshot_dir(session_name) / f"{prefix}_{int(time.time())}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return None


def _first_working(candidates: Iterable, action_name: str = "element"):
    last_error = None
    for candidate in candidates:
        try:
            if candidate.count() > 0:
                return candidate.first
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError(f"Could not locate {action_name}.")


def _click_first(page, locators: Iterable, action_name: str, timeout: int = 5000) -> None:
    last_error = None
    for locator in locators:
        try:
            locator.first.click(timeout=timeout)
            return
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not click {action_name}. Last error: {last_error}")


def _fill_by_label_or_placeholder(page, labels: list[str], value: str | None, required: bool = False) -> bool:
    if value is None or value == "":
        return False

    errors = []
    for label in labels:
        pattern = re.compile(label, re.I)
        candidates = [
            page.get_by_label(pattern),
            page.get_by_placeholder(pattern),
        ]
        for candidate in candidates:
            try:
                candidate.first.fill(value, timeout=4000)
                return True
            except Exception as exc:
                errors.append(str(exc))

    if required:
        raise RuntimeError(f"Could not fill required field matching {labels}. Errors: {errors[-2:]}")
    return False


def _fill_phone(page, phone: str | None) -> bool:
    if not phone:
        return False

    candidates = [
        page.locator("input[type='tel']"),
        page.get_by_placeholder(re.compile("phone|mobile|number", re.I)),
        page.get_by_label(re.compile("phone|mobile", re.I)),
    ]

    for locator in candidates:
        try:
            locator.first.click(timeout=3000)
            locator.first.fill(phone, timeout=3000)
            return True
        except Exception:
            continue

    # Last fallback: click near the visible Phone label, but slightly to the right/below to avoid country dropdown.
    try:
        label = page.get_by_text(re.compile("^Phone$", re.I)).last
        label.scroll_into_view_if_needed(timeout=3000)
        box = label.bounding_box()
        if box:
            page.mouse.click(box["x"] + 170, box["y"] + 42)
            page.keyboard.press("Control+A")
            page.keyboard.type(phone)
            return True
    except Exception:
        pass

    raise RuntimeError("Could not fill GoHighLevel phone input.")


def _select_tag(page, tag_name: str) -> None:
    """Select the existing dms_rpa_demo tag from the GHL Tags dropdown.

    The recording showed that typing `dms` returns both:
      + Create 'dms'
      dms_rpa_demo

    This function intentionally clicks the exact existing tag and never clicks the create option.
    """
    tag_search = ghl_tag_search_text()

    # If tag is already selected, do nothing.
    try:
        if page.get_by_text(tag_name, exact=True).count() > 0:
            return
    except Exception:
        pass

    # Scroll to/click the Tags field.
    clicked = False
    for locator in [
        page.get_by_label(re.compile("tags?", re.I)),
        page.get_by_placeholder(re.compile("tags?|add tags?|select tags?", re.I)),
    ]:
        try:
            locator.first.scroll_into_view_if_needed(timeout=3000)
            locator.first.click(timeout=3000)
            clicked = True
            break
        except Exception:
            continue

    if not clicked:
        label = page.get_by_text(re.compile("^Tags$", re.I)).last
        label.scroll_into_view_if_needed(timeout=5000)
        box = label.bounding_box()
        if not box:
            raise RuntimeError("Could not locate the Tags field label.")
        # Click below/right of the label to focus the custom dropdown input.
        page.mouse.click(box["x"] + 120, box["y"] + 40)

    page.keyboard.type(tag_search)
    page.wait_for_timeout(500)

    # Click exact existing tag. Avoid '+ Create ...'.
    option = page.get_by_text(tag_name, exact=True).last
    option.click(timeout=6000)

    # Verify the selected chip is visible.
    page.wait_for_timeout(500)
    if page.get_by_text(tag_name, exact=True).count() <= 0:
        raise RuntimeError(f"Tag '{tag_name}' was not visibly selected.")


def _click_add_contact(page) -> None:
    _click_first(
        page,
        [
            page.get_by_role("button", name=re.compile(r"^\+?\s*Add Contact$", re.I)),
            page.get_by_role("button", name=re.compile(r"Add Contact", re.I)),
            page.get_by_text(re.compile(r"^\+?\s*Add Contact$", re.I)),
        ],
        "Add Contact button",
        timeout=8000,
    )


def _click_save(page) -> None:
    # The Add Contact drawer has Save and Save and add another.
    # Prefer exact Save button and click the last one in the drawer/footer.
    candidates = [
        page.get_by_role("button", name=re.compile(r"^Save$", re.I)),
        page.get_by_text(re.compile(r"^Save$", re.I)),
    ]

    last_error = None
    for locator in candidates:
        try:
            locator.last.click(timeout=8000)
            return
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Could not click Save. Last error: {last_error}")


def _wait_for_contact_detail_or_success(page, contact: ContactPayload, tag_name: str) -> bool:
    deadline = time.monotonic() + 25
    expected_bits = [contact.first_name]
    if contact.last_name:
        expected_bits.append(contact.last_name)
    if contact.email:
        expected_bits.append(contact.email)

    while time.monotonic() < deadline:
        try:
            body_text = page.locator("body").inner_text(timeout=3000)
            if tag_name in body_text and any(bit in body_text for bit in expected_bits):
                return True
        except Exception:
            pass
        page.wait_for_timeout(1000)

    return False


def _verify_in_smart_list(page, contacts_url: str, contact: ContactPayload, tag_name: str) -> bool:
    try:
        page.goto(contacts_url, wait_until="domcontentloaded", timeout=operation_timeout_ms())
        page.wait_for_timeout(3000)
        body_text = page.locator("body").inner_text(timeout=5000)
        expected = [contact.first_name]
        if contact.last_name:
            expected.append(contact.last_name)
        if contact.email:
            expected.append(contact.email)
        return any(item in body_text for item in expected) and tag_name in body_text
    except Exception:
        return False


def add_contact_to_gohighlevel(
    contact: ContactPayload,
    contacts_url: str | None = None,
    session_name: str | None = None,
) -> RPAResult:
    """Create a contact in GHL through the browser UI and assign dms_rpa_demo tag."""
    session = safe_session_name(session_name)
    storage_path = storage_state_path(session)
    if not storage_path.exists():
        raise GHLLoginRequired("No saved GoHighLevel session exists. Admin must connect/login first.")

    target_url = contacts_url or ghl_contacts_url()
    if not target_url:
        raise RuntimeError(
            "GoHighLevel Contacts Smart List URL is not configured. "
            "Set GHL_CONTACTS_URL in site_config/env or pass contacts_url in the request."
        )

    tag_name = ghl_tag_name()
    sync_playwright, _expect, _TimeoutError = _require_playwright()

    screenshot_before = None
    screenshot_after = None
    detail_verified = False
    list_verified = False
    final_url = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=playwright_headless(), slow_mo=playwright_slow_mo_ms())
        context = browser.new_context(storage_state=str(storage_path))
        page = context.new_page()

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=operation_timeout_ms())
            page.wait_for_timeout(2000)

            if not is_probably_logged_in(page):
                raise GHLLoginRequired("Saved GoHighLevel session is expired or login is required.")

            screenshot_before = _screenshot(page, session, "before_add_contact")

            _click_add_contact(page)

            # Wait until right-side Add Contact drawer/form appears.
            page.get_by_text(re.compile("Add Contact", re.I)).first.wait_for(timeout=operation_timeout_ms())

            _fill_by_label_or_placeholder(page, ["First name", "First Name"], contact.first_name, required=True)
            _fill_by_label_or_placeholder(page, ["Last name", "Last Name"], contact.last_name)
            _fill_by_label_or_placeholder(page, ["Email"], contact.email)
            _fill_phone(page, contact.phone)

            # GHL default Add Contact drawer may not show vehicle/source/notes.
            # For demo reliability, store those fields locally; if a notes/custom field is visible, fill it.
            if contact.notes:
                _fill_by_label_or_placeholder(page, ["Notes", "Description"], contact.notes)

            _select_tag(page, tag_name)

            _click_save(page)

            detail_verified = _wait_for_contact_detail_or_success(page, contact, tag_name)
            final_url = page.url

            screenshot_after = _screenshot(page, session, "after_add_contact")

            list_verified = _verify_in_smart_list(page, target_url, contact, tag_name)

            context.storage_state(path=str(storage_path))

        finally:
            context.close()
            browser.close()

    success = detail_verified or list_verified
    return RPAResult(
        success=success,
        status="Success" if success else "Failed",
        message=(
            "Contact created in GoHighLevel and verified."
            if success
            else "Contact form was submitted, but verification did not conclusively confirm the record."
        ),
        contact_name=contact.contact_name,
        contact_url=final_url,
        screenshot_before=screenshot_before,
        screenshot_after=screenshot_after,
        details={
            "tag_name": tag_name,
            "detail_verified": detail_verified,
            "smart_list_verified": list_verified,
            "contacts_url": target_url,
            "session_name": session,
        },
    )
