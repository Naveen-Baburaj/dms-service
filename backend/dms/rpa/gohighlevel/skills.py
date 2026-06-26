from __future__ import annotations

import re
import time
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
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except Exception as exc:
        raise RuntimeError(
            "Playwright is not installed in the Frappe/bench environment. "
            "Install it into ~/frappe/dms-frappe-bench/env/bin/python."
        ) from exc


def _screenshot(page, session_name: str, prefix: str) -> str | None:
    path = screenshot_dir(session_name) / f"{prefix}_{int(time.time())}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return None


def _body_text(page, timeout: int = 3000) -> str:
    try:
        return page.locator("body").inner_text(timeout=timeout)
    except Exception:
        return ""


def _is_loading_text(text: str) -> bool:
    lowered = text.lower()
    return (
        "loading" in lowered
        or "please wait" in lowered
        or "fetching" in lowered
        or "spinner" in lowered
    )


def _safe_count(locator) -> int:
    try:
        return locator.count()
    except Exception:
        return 0


def _visible_add_contact_count(page) -> int:
    locators = [
        page.get_by_role("button", name=re.compile(r"^\s*\+?\s*Add Contact\s*$", re.I)),
        page.get_by_role("button", name=re.compile(r"Add Contact", re.I)),
        page.locator("button").filter(has_text=re.compile(r"Add Contact", re.I)),
        page.locator("a").filter(has_text=re.compile(r"Add Contact", re.I)),
        page.locator("[role='button']").filter(has_text=re.compile(r"Add Contact", re.I)),
        page.locator("text=/^\\s*\\+?\\s*Add Contact\\s*$/i"),
    ]
    total = 0
    for loc in locators:
        total += _safe_count(loc)
    return total


def _close_possible_popups(page) -> None:
    for loc in [
        page.get_by_role("button", name=re.compile(r"close|dismiss|got it|not now|skip", re.I)),
        page.locator("[aria-label='Close']"),
        page.locator("button").filter(has_text=re.compile(r"Close|Dismiss|Got it|Not now|Skip", re.I)),
    ]:
        try:
            if loc.count() > 0:
                loc.first.click(timeout=1500)
                page.wait_for_timeout(500)
        except Exception:
            continue


def _wait_for_contacts_ready(page, contacts_url: str, max_seconds: int = 180) -> None:
    """Wait until GHL Contacts page is usable, not just navigated.

    GHL often reaches the smart-list URL while the table/sidebar is still loading.
    The previous implementation clicked Add Contact too early. This function polls
    until either Add Contact is visible/clickable or the Contacts UI text is stable.
    """
    deadline = time.monotonic() + max_seconds
    last_text = ""
    last_url = ""

    while time.monotonic() < deadline:
        try:
            last_url = page.url or ""
            _close_possible_popups(page)

            # Strong readiness signal.
            if _visible_add_contact_count(page) > 0:
                page.wait_for_timeout(1500)
                return

            text = _body_text(page, timeout=4000)
            last_text = text[:1000]

            # Moderate readiness signals. Wait extra because Add Contact can render after table header.
            has_contacts_shell = (
                "Contacts" in text
                and (
                    "Smart Lists" in text
                    or "Contact name" in text
                    or "Phone" in text
                    or "Email" in text
                    or "Business name" in text
                    or "Tags" in text
                )
            )
            if has_contacts_shell and not _is_loading_text(text):
                page.wait_for_timeout(3000)
                if _visible_add_contact_count(page) > 0:
                    return

            # If GHL is still loading, just wait.
            page.wait_for_timeout(2500)

            # Every ~30 seconds, reload the same smart list if page is stuck.
            remaining = deadline - time.monotonic()
            elapsed = max_seconds - remaining
            if int(elapsed) in {30, 60, 90, 120, 150}:
                try:
                    page.goto(contacts_url, wait_until="domcontentloaded", timeout=operation_timeout_ms())
                    page.wait_for_timeout(5000)
                except Exception:
                    pass

        except Exception:
            page.wait_for_timeout(2500)

    raise RuntimeError(
        "GoHighLevel Contacts page did not become ready within "
        f"{max_seconds} seconds. Last URL: {last_url}. Last visible text: {last_text[:500]!r}"
    )


def _click_locator_candidates(page, locators: Iterable, action_name: str, timeout_each: int = 7000) -> None:
    last_error = None
    for loc in locators:
        try:
            if loc.count() <= 0:
                continue
            candidate = loc.first
            candidate.scroll_into_view_if_needed(timeout=3000)
            candidate.click(timeout=timeout_each)
            return
        except Exception as exc:
            last_error = exc
            continue
    raise RuntimeError(f"Could not click {action_name}. Last error: {last_error}")


def _click_add_contact(page, contacts_url: str) -> None:
    deadline = time.monotonic() + 180
    last_error = None

    while time.monotonic() < deadline:
        try:
            _wait_for_contacts_ready(page, contacts_url, max_seconds=45)
            _close_possible_popups(page)

            locators = [
                page.get_by_role("button", name=re.compile(r"^\s*\+?\s*Add Contact\s*$", re.I)),
                page.get_by_role("button", name=re.compile(r"Add Contact", re.I)),
                page.locator("button").filter(has_text=re.compile(r"Add Contact", re.I)),
                page.locator("a").filter(has_text=re.compile(r"Add Contact", re.I)),
                page.locator("[role='button']").filter(has_text=re.compile(r"Add Contact", re.I)),
                page.locator("text=/^\\s*\\+?\\s*Add Contact\\s*$/i"),
            ]
            _click_locator_candidates(page, locators, "Add Contact button", timeout_each=10000)
            return

        except Exception as exc:
            last_error = exc

            # JS fallback: click any visible element with exact-ish Add Contact text.
            try:
                clicked = page.evaluate(
                    """
                    () => {
                      const els = Array.from(document.querySelectorAll('button,a,[role="button"],div,span'));
                      const target = els.find(el => {
                        const text = (el.innerText || el.textContent || '').trim();
                        const rect = el.getBoundingClientRect();
                        const visible = rect.width > 0 && rect.height > 0;
                        return visible && /^\\+?\\s*Add Contact$/i.test(text);
                      });
                      if (target) {
                        target.click();
                        return true;
                      }
                      return false;
                    }
                    """
                )
                if clicked:
                    return
            except Exception as js_exc:
                last_error = js_exc

            # Top-right coordinate fallback only after contacts page shell is visible.
            try:
                text = _body_text(page)
                if "Contacts" in text:
                    viewport = page.viewport_size or {"width": 1366, "height": 768}
                    page.mouse.click(viewport["width"] - 115, 132)
                    page.wait_for_timeout(2000)
                    if _add_contact_drawer_visible(page):
                        return
            except Exception as coord_exc:
                last_error = coord_exc

            try:
                page.goto(contacts_url, wait_until="domcontentloaded", timeout=operation_timeout_ms())
                page.wait_for_timeout(6000)
            except Exception:
                page.wait_for_timeout(3000)

    raise RuntimeError(f"Could not click Add Contact after extended wait. Last error: {last_error}")


def _add_contact_drawer_visible(page) -> bool:
    text = _body_text(page, timeout=2000)
    if "First name" in text and "Save" in text:
        return True
    for loc in [
        page.get_by_label(re.compile("First name", re.I)),
        page.get_by_placeholder(re.compile("First name", re.I)),
        page.locator("input[name*='first' i]"),
    ]:
        try:
            if loc.count() > 0:
                return True
        except Exception:
            continue
    return False


def _wait_for_add_contact_drawer(page, max_seconds: int = 90) -> None:
    deadline = time.monotonic() + max_seconds
    last_text = ""
    while time.monotonic() < deadline:
        if _add_contact_drawer_visible(page):
            page.wait_for_timeout(1000)
            return
        last_text = _body_text(page)
        page.wait_for_timeout(1500)
    raise RuntimeError(f"Add Contact drawer did not appear. Last visible text: {last_text[:500]!r}")


def _fill_by_label_or_placeholder(page, labels: list[str], value: str | None, required: bool = False) -> bool:
    if value is None or value == "":
        return False

    errors = []
    for label in labels:
        pattern = re.compile(label, re.I)
        candidates = [
            page.get_by_label(pattern),
            page.get_by_placeholder(pattern),
            page.locator(f"input[name*='{label.split()[0]}' i]"),
        ]
        for candidate in candidates:
            try:
                candidate.first.scroll_into_view_if_needed(timeout=3000)
                candidate.first.click(timeout=3000)
                candidate.first.fill(value, timeout=4000)
                return True
            except Exception as exc:
                errors.append(str(exc))

    # Fallback: click near visible label and type.
    for label in labels:
        try:
            text_loc = page.get_by_text(re.compile(label, re.I)).first
            text_loc.scroll_into_view_if_needed(timeout=3000)
            box = text_loc.bounding_box()
            if box:
                page.mouse.click(box["x"] + 180, box["y"] + 34)
                page.keyboard.press("Control+A")
                page.keyboard.type(value)
                return True
        except Exception as exc:
            errors.append(str(exc))

    if required:
        raise RuntimeError(f"Could not fill required field matching {labels}. Last errors: {errors[-3:]}")
    return False


def _fill_phone(page, phone: str | None) -> bool:
    if not phone:
        return False

    candidates = [
        page.locator("input[type='tel']"),
        page.get_by_placeholder(re.compile("phone|mobile|number", re.I)),
        page.get_by_label(re.compile("phone|mobile", re.I)),
        page.locator("input").filter(has_text=re.compile("")),
    ]

    for locator in candidates[:3]:
        try:
            locator.first.scroll_into_view_if_needed(timeout=3000)
            locator.first.click(timeout=3000)
            locator.first.fill(phone, timeout=4000)
            return True
        except Exception:
            continue

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
    tag_search = ghl_tag_search_text()

    try:
        if page.get_by_text(tag_name, exact=True).count() > 0:
            return
    except Exception:
        pass

    clicked = False
    for locator in [
        page.get_by_label(re.compile("tags?", re.I)),
        page.get_by_placeholder(re.compile("tags?|add tags?|select tags?", re.I)),
        page.locator("input").filter(has_text=re.compile("")),
    ][:2]:
        try:
            locator.first.scroll_into_view_if_needed(timeout=4000)
            locator.first.click(timeout=4000)
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
        page.mouse.click(box["x"] + 130, box["y"] + 42)

    page.keyboard.type(tag_search)
    page.wait_for_timeout(1200)

    option_candidates = [
        page.get_by_text(tag_name, exact=True),
        page.locator("[role='option']").filter(has_text=re.compile(re.escape(tag_name), re.I)),
        page.locator("div").filter(has_text=re.compile(rf"^{re.escape(tag_name)}$", re.I)),
    ]
    _click_locator_candidates(page, option_candidates, f"existing tag {tag_name}", timeout_each=8000)

    page.wait_for_timeout(700)
    if page.get_by_text(tag_name, exact=True).count() <= 0:
        raise RuntimeError(f"Tag '{tag_name}' was not visibly selected.")


def _click_save(page) -> None:
    locators = [
        page.get_by_role("button", name=re.compile(r"^Save$", re.I)),
        page.locator("button").filter(has_text=re.compile(r"^Save$", re.I)),
        page.get_by_text(re.compile(r"^Save$", re.I)),
    ]

    last_error = None
    for loc in locators:
        try:
            if loc.count() > 0:
                loc.last.scroll_into_view_if_needed(timeout=3000)
                loc.last.click(timeout=12000)
                return
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Could not click Save. Last error: {last_error}")


def _wait_for_contact_detail_or_success(page, contact: ContactPayload, tag_name: str) -> bool:
    deadline = time.monotonic() + 75
    expected_bits = [contact.first_name]
    if contact.last_name:
        expected_bits.append(contact.last_name)
    if contact.email:
        expected_bits.append(contact.email)

    while time.monotonic() < deadline:
        try:
            text = _body_text(page, timeout=5000)
            if any(bit in text for bit in expected_bits):
                return True
            if tag_name in text and ("Contact" in text or "Contacts" in text):
                return True
        except Exception:
            pass
        page.wait_for_timeout(2000)

    return False


def _verify_in_smart_list(page, contacts_url: str, contact: ContactPayload, tag_name: str) -> bool:
    try:
        page.goto(contacts_url, wait_until="domcontentloaded", timeout=operation_timeout_ms())
        _wait_for_contacts_ready(page, contacts_url, max_seconds=120)

        # If search is available, search by email to reduce list pagination risk.
        if contact.email:
            for loc in [
                page.get_by_placeholder(re.compile("search", re.I)),
                page.get_by_label(re.compile("search", re.I)),
                page.locator("input").filter(has_text=re.compile("")),
            ][:2]:
                try:
                    loc.first.click(timeout=3000)
                    loc.first.fill(contact.email, timeout=4000)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(5000)
                    break
                except Exception:
                    continue

        text = _body_text(page, timeout=8000)
        expected = [contact.first_name]
        if contact.last_name:
            expected.append(contact.last_name)
        if contact.email:
            expected.append(contact.email)

        return any(item in text for item in expected) and tag_name in text
    except Exception:
        return False


def add_contact_to_gohighlevel(
    contact: ContactPayload,
    contacts_url: str | None = None,
    session_name: str | None = None,
) -> RPAResult:
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
    sync_playwright = _require_playwright()

    screenshot_before = None
    screenshot_after = None
    detail_verified = False
    list_verified = False
    final_url = None
    failure_screenshot = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=playwright_headless(), slow_mo=playwright_slow_mo_ms())
        context = browser.new_context(storage_state=str(storage_path))
        page = context.new_page()

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=operation_timeout_ms())
            page.wait_for_timeout(4000)

            if not is_probably_logged_in(page):
                raise GHLLoginRequired("Saved GoHighLevel session is expired or login is required.")

            _wait_for_contacts_ready(page, target_url, max_seconds=180)
            screenshot_before = _screenshot(page, session, "before_add_contact")

            _click_add_contact(page, target_url)
            _wait_for_add_contact_drawer(page, max_seconds=90)

            _fill_by_label_or_placeholder(page, ["First name", "First Name"], contact.first_name, required=True)
            _fill_by_label_or_placeholder(page, ["Last name", "Last Name"], contact.last_name)
            _fill_by_label_or_placeholder(page, ["Email"], contact.email)
            _fill_phone(page, contact.phone)

            if contact.notes:
                _fill_by_label_or_placeholder(page, ["Notes", "Description"], contact.notes)

            _select_tag(page, tag_name)
            _click_save(page)

            detail_verified = _wait_for_contact_detail_or_success(page, contact, tag_name)
            final_url = page.url
            screenshot_after = _screenshot(page, session, "after_add_contact")
            list_verified = _verify_in_smart_list(page, target_url, contact, tag_name)

            context.storage_state(path=str(storage_path))

        except Exception:
            failure_screenshot = _screenshot(page, session, "failure_add_contact")
            raise
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
        screenshot_after=screenshot_after or failure_screenshot,
        details={
            "tag_name": tag_name,
            "detail_verified": detail_verified,
            "smart_list_verified": list_verified,
            "contacts_url": target_url,
            "session_name": session,
        },
    )
