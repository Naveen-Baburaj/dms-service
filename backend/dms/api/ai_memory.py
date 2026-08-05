from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

import frappe
from frappe.utils import now_datetime

CONVERSATION_DOCTYPE = "DMS AI Conversation"
MESSAGE_DOCTYPE = "DMS AI Message"

MAX_CONVERSATIONS = 50
MAX_MESSAGES_PER_LOAD = 500
MAX_MEMORY_SUMMARY_CHARS = 4000
DEFAULT_TITLE = "New conversation"


def _base():
    from dms.api import ai_agent

    return ai_agent


def _header(name: str) -> str | None:
    try:
        return frappe.get_request_header(name)
    except Exception:
        return None


def _request_payload() -> dict[str, Any]:
    return _base()._data_agent_request_payload()


def _owner_context() -> dict[str, Any]:
    base = _base()
    is_admin, company_id, company_name = base._data_agent_current_scope()

    session_user = None
    try:
        candidate = str(frappe.session.user or "").strip()
        if candidate and candidate != "Guest":
            session_user = candidate
    except Exception:
        session_user = None

    client_user_id = (
        _header("x-client-user-id")
        or _header("x-demo-user-id")
        or ""
    ).strip()

    role = (_header("x-user-role") or "").strip()
    tenant = (_header("x-tenant-id") or "").strip()

    identity = session_user or client_user_id
    if not identity:
        identity = f"demo:{role or 'unknown'}:{tenant or company_name or 'unknown'}"

    owner_seed = (
        f"{identity}|{role}|{tenant}|"
        f"{company_id or ''}|{company_name or ''}|{int(bool(is_admin))}"
    )
    owner_key = hashlib.sha256(owner_seed.encode("utf-8")).hexdigest()

    if is_admin:
        scope_key = "group-admin:all-companies"
    else:
        scope_key = f"tenant:{company_id or company_name or tenant or 'unknown'}"

    return {
        "owner_key": owner_key,
        "owner_label": identity[:140],
        "scope_key": scope_key[:140],
        "is_group_admin": bool(is_admin),
        "company_id": company_id,
        "company_name": company_name or ("Group" if is_admin else None),
    }


def _safe_json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return copy.deepcopy(default)

    try:
        return json.loads(value)
    except Exception:
        return copy.deepcopy(default)


def _default_memory_state() -> dict[str, Any]:
    return {
        "summary": "",
        "active_resource": None,
        "companies": [],
        "time_range": None,
        "metric": None,
        "chart_type": "none",
        "last_user_goal": "",
        "unresolved_references": [],
    }


def _get_conversation(conversation_id: str, *, required: bool = True):
    if not conversation_id:
        if required:
            frappe.throw("Conversation ID is required.", frappe.ValidationError)
        return None

    try:
        doc = frappe.get_doc(CONVERSATION_DOCTYPE, conversation_id)
    except Exception:
        if required:
            frappe.throw("Conversation not found.", frappe.DoesNotExistError)
        return None

    owner = _owner_context()
    if doc.owner_key != owner["owner_key"] or doc.scope_key != owner["scope_key"]:
        frappe.throw(
            "You do not have access to this conversation.",
            frappe.PermissionError,
        )

    if getattr(doc, "status", "Active") != "Active":
        frappe.throw("This conversation is archived.", frappe.PermissionError)

    return doc


def _create_conversation(title: str | None = None):
    owner = _owner_context()
    clean_title = (title or DEFAULT_TITLE).strip()[:120] or DEFAULT_TITLE

    doc = frappe.get_doc(
        {
            "doctype": CONVERSATION_DOCTYPE,
            "title": clean_title,
            "owner_key": owner["owner_key"],
            "owner_label": owner["owner_label"],
            "scope_key": owner["scope_key"],
            "company_id": owner["company_id"],
            "company_name": owner["company_name"],
            "is_group_admin": int(owner["is_group_admin"]),
            "memory_summary": "",
            "memory_state_json": json.dumps(
                _default_memory_state(),
                separators=(",", ":"),
            ),
            "last_intent": "",
            "last_resource": "",
            "last_message_at": now_datetime(),
            "message_count": 0,
            "status": "Active",
            "last_openai_response_id": "",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def _conversation_memory(doc) -> dict[str, Any]:
    state = _safe_json_loads(
        getattr(doc, "memory_state_json", None),
        _default_memory_state(),
    )
    if not isinstance(state, dict):
        state = _default_memory_state()

    summary = str(
        getattr(doc, "memory_summary", "")
        or state.get("summary")
        or ""
    ).strip()
    state["summary"] = summary
    return {"summary": summary, "state": state}


def _conversation_context_text(doc) -> str:
    memory = _conversation_memory(doc)
    return json.dumps(
        {
            "conversation_summary": memory["summary"],
            "structured_memory": memory["state"],
            "context_policy": (
                "This is a compact summary of this chat only. "
                "No raw transcript is included."
            ),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _is_contextual_follow_up(query_text: str) -> bool:
    q = str(query_text or "").strip().lower()
    words = re.findall(r"[a-z0-9]+", q)

    referential_terms = [
        "that",
        "those",
        "them",
        "it",
        "same",
        "above",
        "previous",
        "earlier",
        "what about",
        "and for",
        "then",
        "instead",
        "make it",
        "turn it",
        "show it",
        "chart of",
        "graph of",
        "pie of",
    ]
    if any(term in q for term in referential_terms):
        return True

    visualization_terms = [
        "pie",
        "donut",
        "bar chart",
        "line chart",
        "chart",
        "graph",
        "table",
        "visualize",
    ]
    domain_terms = [
        "customer",
        "lead",
        "sale",
        "sold",
        "revenue",
        "invoice",
        "booking",
        "test drive",
        "service",
        "inventory",
        "stock",
        "vehicle",
        "honda",
        "nexa",
        "jaguar",
    ]

    if (
        len(words) <= 12
        and any(term in q for term in visualization_terms)
        and not any(term in q for term in domain_terms)
    ):
        return True

    if len(words) <= 7 and q.startswith(("and ", "also ", "then ", "now ")):
        return True

    return False


def _memory_retrieval_hint(memory: dict[str, Any]) -> str:
    state = memory.get("state") or {}
    parts = []

    if state.get("last_user_goal"):
        parts.append(f"Previous goal: {state['last_user_goal']}")
    if state.get("active_resource"):
        parts.append(f"Resource: {state['active_resource']}")

    companies = state.get("companies") or []
    if companies:
        parts.append("Companies: " + ", ".join(str(item) for item in companies))

    if state.get("time_range"):
        parts.append(f"Time range: {state['time_range']}")
    if state.get("metric"):
        parts.append(f"Metric: {state['metric']}")
    if memory.get("summary"):
        parts.append(f"Summary: {memory['summary']}")

    return "\n".join(parts)


def _effective_retrieval_query(user_query: str, memory: dict[str, Any]) -> str:
    query_text = str(user_query or "").strip()

    if "pie" in query_text.lower() and "chart" not in query_text.lower():
        query_text = f"{query_text} pie chart"

    if not memory.get("summary") or not _is_contextual_follow_up(query_text):
        return query_text

    return (
        f"{_memory_retrieval_hint(memory)}\n"
        f"Current follow-up request: {query_text}"
    ).strip()


def _augment_admin_general_pack(
    data_pack: dict[str, Any],
    retrieval_query: str,
) -> dict[str, Any]:
    base = _base()
    scope = data_pack.get("scope") or {}
    intent = (data_pack.get("retrieval") or {}).get("intent") or {}

    if not scope.get("is_admin") or intent.get("mode") != "general":
        return data_pack

    resources = data_pack.setdefault("resources", {})
    catalog = base._data_agent_catalog()

    for resource, meta in catalog.items():
        if resource in resources:
            continue

        doctype = meta["doctype"]
        augmented_intent = {**intent, "resources": list(catalog.keys())}
        all_rows = base._ultra_fetch(
            resource,
            doctype,
            retrieval_query,
            augmented_intent,
        )
        ranked = base._ultra_rank(all_rows, augmented_intent)
        rows_for_llm = ranked[:30]

        resources[resource] = {
            "doctype": doctype,
            "title": meta["title"],
            "fields": base._ultra_fields(resource, doctype),
            "row_count": len(rows_for_llm),
            "total_rows_available": len(all_rows),
            "summary": base._ultra_summary(all_rows),
            "rows": rows_for_llm,
        }

    data_pack["_debug_context_chars"] = len(
        json.dumps(
            data_pack,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )
    )
    return data_pack


def _filter_rows_to_companies(
    rows: list[dict[str, Any]],
    companies: list[str],
) -> list[dict[str, Any]]:
    wanted = {str(company).strip().lower() for company in companies if company}
    if not wanted:
        return rows

    filtered = []
    for row in rows:
        company = str(
            row.get("company_name")
            or row.get("company_id")
            or ""
        ).strip().lower()
        if company in wanted:
            filtered.append(row)

    return filtered


def _build_data_packs(
    user_query: str,
    conversation_doc,
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    """Build a compact LLM pack and a full deterministic execution pack.

    The LLM sees only summaries and top-ranked rows. Widget calculations use
    the full authorised, date-filtered, company-filtered rows so charts and
    totals are not truncated by the prompt-size optimisation.
    """

    base = _base()
    memory = _conversation_memory(conversation_doc)
    memory_context = _conversation_context_text(conversation_doc)
    retrieval_query = _effective_retrieval_query(user_query, memory)

    initial_pack = base._ultra_build_pack(retrieval_query, memory_context)
    initial_pack = _augment_admin_general_pack(
        initial_pack,
        retrieval_query,
    )

    intent = (initial_pack.get("retrieval") or {}).get("intent") or {}
    resource_names = list((initial_pack.get("resources") or {}).keys())
    catalog = base._data_agent_catalog()
    requested_companies = [
        str(company)
        for company in (intent.get("companies") or [])
        if company
    ]

    llm_pack = copy.deepcopy(initial_pack)
    execution_pack = copy.deepcopy(initial_pack)
    llm_resources: dict[str, Any] = {}
    execution_resources: dict[str, Any] = {}

    for resource in resource_names:
        meta = catalog.get(resource)
        if not meta:
            continue

        doctype = meta["doctype"]
        all_rows = base._ultra_fetch(
            resource,
            doctype,
            retrieval_query,
            intent,
        )
        all_rows = _filter_rows_to_companies(
            all_rows,
            requested_companies,
        )
        ranked = base._ultra_rank(all_rows, intent)

        if intent.get("mode") == "exact_contact_or_join":
            compact_limit = 12
        elif intent.get("is_chart"):
            compact_limit = 24
        elif intent.get("mode") in {"inventory", "sales", "invoice"}:
            compact_limit = 40
        else:
            compact_limit = 30

        common = {
            "doctype": doctype,
            "title": meta["title"],
            "fields": base._ultra_fields(resource, doctype),
            "total_rows_available": len(all_rows),
            "summary": base._ultra_summary(all_rows),
        }

        llm_resources[resource] = {
            **common,
            "row_count": min(len(ranked), compact_limit),
            "rows": ranked[:compact_limit],
        }
        execution_resources[resource] = {
            **common,
            "row_count": len(ranked),
            "rows": ranked,
        }

    llm_pack["resources"] = llm_resources
    execution_pack["resources"] = execution_resources

    memory_payload = {
        "summary_only": True,
        "summary": memory["summary"],
        "state": memory["state"],
    }
    llm_pack["conversation_memory"] = memory_payload
    execution_pack["conversation_memory"] = memory_payload

    llm_pack["_debug_context_chars"] = len(
        json.dumps(
            llm_pack,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )
    )
    execution_pack["_debug_context_chars"] = llm_pack[
        "_debug_context_chars"
    ]

    return (
        llm_pack,
        execution_pack,
        memory_context,
        retrieval_query,
    )


def _memory_output_schema() -> dict[str, Any]:
    base = _base()
    schema = copy.deepcopy(base._data_agent_output_schema())

    schema["properties"]["conversation_title"] = {"type": "string"}
    schema["properties"]["memory"] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "active_resource": {
                "anyOf": [
                    {
                        "type": "string",
                        "enum": list(base._data_agent_catalog().keys()),
                    },
                    {"type": "null"},
                ]
            },
            "companies": {
                "type": "array",
                "items": {"type": "string"},
            },
            "time_range": {
                "anyOf": [{"type": "string"}, {"type": "null"}]
            },
            "metric": {
                "anyOf": [{"type": "string"}, {"type": "null"}]
            },
            "chart_type": {
                "type": "string",
                "enum": ["none", "table", "bar", "line", "pie"],
            },
            "last_user_goal": {"type": "string"},
            "unresolved_references": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "summary",
            "active_resource",
            "companies",
            "time_range",
            "metric",
            "chart_type",
            "last_user_goal",
            "unresolved_references",
        ],
    }
    schema["required"].extend(["conversation_title", "memory"])
    return schema


def _memory_prompt(
    user_query: str,
    memory_context: str,
    data_pack: dict[str, Any],
) -> str:
    compact_pack = json.dumps(
        data_pack,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )

    return f"""You are Vividity, the intelligent analytical controller for a multi-tenant Dealer Management System.

The backend already enforced permissions and supplied only authorised DMS data. You control read-only analytical interpretation: relevant resources, fields, filters, aggregation, answer format, and useful visualisation. Never request database writes, raw SQL, permission changes, or actions outside the supplied data.

ADMIN CAPABILITY
- When scope.is_admin is true, answer any reasonable read-only question about the authorised DMS resources and all companies represented in the data pack.
- Inspect all supplied resources before saying information is unavailable.
- Compare companies, compute KPIs, search records, and build useful charts whenever requested.

TENANT CAPABILITY
- When scope.is_admin is false, answer only from the tenant-scoped data pack.
- Never infer or mention another company's private data.

CONVERSATION MEMORY
- The memory below is a compact summary of this chatbox only, not the raw transcript.
- Resolve references such as "that", "same", "those", "what about", "and for Jaguar", "make it a chart", and "give me a pie chart of that" from this memory.
- An explicit new subject in the current request overrides the previous subject.
- A new chatbox has empty memory and must not inherit another chatbox's context.

VISUALISATION
- For "pie chart of that", preserve the remembered resource, companies, time range, metric, and aggregation, then return a generic_charts widget with chart_type="pie".
- Use group_by="company" for company comparisons.
- Use group_by="month" for time trends.
- Use aggregation="count" for record or unit counts.
- Use aggregation="sum" with the correct value_field for revenue or monetary totals.
- Use record_table for useful lists or details.
- Do not add a widget for one direct value unless requested.

ACCURACY
- Answer only from the authorised data pack.
- Do not invent records or values.
- Distinguish vehicle-sale count from revenue.
- Current user instructions override remembered presentation preferences.

MEMORY UPDATE
Return a compact memory for the next turn:
- summary: a cumulative compact summary of the whole chat, about 2,500 characters maximum. Preserve earlier important topics and results while clearly marking the active subject. Include resolved resource, companies, period, metric, aggregation, key result, and current visualisation.
- active_resource: the main DMS resource.
- companies: companies currently referenced.
- time_range: active date range.
- metric: active metric or aggregation.
- chart_type: current presentation type.
- last_user_goal: resolved intent of this request.
- unresolved_references: anything still needing clarification.
Never put raw message history in the summary.

CONVERSATION TITLE
Return a stable 3-8 word title representing this chat.

Current user request:
{user_query}

Conversation memory summary:
{memory_context}

Authorised DMS data pack:
{compact_pack}
""".strip()


def _openai_headers(api_key: str) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    organization = (
        os.getenv("OPENAI_ORG_ID")
        or frappe.conf.get("openai_org_id")
        or frappe.conf.get("OPENAI_ORG_ID")
    )
    project = (
        os.getenv("OPENAI_PROJECT_ID")
        or frappe.conf.get("openai_project_id")
        or frappe.conf.get("OPENAI_PROJECT_ID")
    )

    if organization:
        headers["OpenAI-Organization"] = str(organization)
    if project:
        headers["OpenAI-Project"] = str(project)
    return headers


def _call_openai_single_pass(
    user_query: str,
    memory_context: str,
    data_pack: dict[str, Any],
) -> dict[str, Any]:
    base = _base()
    _provider, api_key, model = base._data_agent_provider_config()

    if not api_key:
        return {
            "_llm_status": "missing_api_key",
            "_llm_error": "OPENAI_API_KEY/openai_api_key is not configured",
            "_llm_provider": "openai",
            "_llm_model": model,
        }

    timeout_seconds = int(
        os.getenv("OPENAI_TIMEOUT_SECONDS")
        or frappe.conf.get("openai_timeout_seconds")
        or 75
    )
    max_output_tokens = int(
        os.getenv("OPENAI_MAX_OUTPUT_TOKENS")
        or frappe.conf.get("openai_max_output_tokens")
        or 1800
    )
    max_retries = max(
        0,
        min(
            int(
                os.getenv("OPENAI_MAX_RETRIES")
                or frappe.conf.get("openai_max_retries")
                or 2
            ),
            3,
        ),
    )

    payload = {
        "model": model,
        "input": _memory_prompt(user_query, memory_context, data_pack),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "dms_threaded_memory_answer",
                "strict": True,
                "schema": _memory_output_schema(),
            }
        },
        "max_output_tokens": max_output_tokens,
        "store": False,
    }

    last_error = "OpenAI request failed"

    for attempt in range(max_retries + 1):
        try:
            request = urllib.request.Request(
                "https://api.openai.com/v1/responses",
                data=json.dumps(payload).encode("utf-8"),
                headers=_openai_headers(api_key),
                method="POST",
            )

            with urllib.request.urlopen(
                request,
                timeout=max(15, min(timeout_seconds, 180)),
            ) as response:
                response_json = json.loads(
                    response.read().decode("utf-8")
                )

            output_text = base._data_agent_extract_openai_text(response_json)
            parsed = base._safe_json_loads(output_text)

            if not isinstance(parsed, dict):
                return {
                    "_llm_status": "invalid_response",
                    "_llm_error": (
                        "OpenAI returned an empty or non-object structured response"
                    ),
                    "_llm_provider": "openai",
                    "_llm_model": model,
                }

            parsed["_llm_status"] = "ok"
            parsed["_llm_error"] = None
            parsed["_llm_provider"] = "openai"
            parsed["_llm_model"] = model
            parsed["_openai_response_id"] = response_json.get("id")
            return parsed

        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}: {body[:1500]}"
            if (
                exc.code not in {408, 409, 429, 500, 502, 503, 504}
                or attempt >= max_retries
            ):
                break
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:1500]}"
            if attempt >= max_retries:
                break

        time.sleep(0.5 * (2 ** attempt))

    return {
        "_llm_status": "call_failed",
        "_llm_error": last_error,
        "_llm_provider": "openai",
        "_llm_model": model,
    }



def _call_openai(
    user_query: str,
    memory_context: str,
    data_pack: dict[str, Any],
) -> dict[str, Any]:
    agentic_error = None

    try:
        from dms.agent.orchestrator import (
            is_agentic_enabled,
            run_agentic_plan,
        )

        if is_agentic_enabled():
            result = run_agentic_plan(
                user_query=user_query,
                memory_context=memory_context,
                seed_data_pack=data_pack,
                output_schema=_memory_output_schema(),
            )
            if result.get("_llm_status") == "ok":
                return result

            agentic_error = str(
                result.get("_llm_error")
                or "Agentic orchestrator returned a non-success status."
            )[:1800]

            fallback_enabled = str(
                frappe.conf.get("dms_agentic_fallback_enabled")
                if frappe.conf.get("dms_agentic_fallback_enabled")
                is not None
                else "1"
            ).strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            if not fallback_enabled:
                return result

    except Exception as exc:
        agentic_error = (
            f"{type(exc).__name__}: {str(exc)[:1800]}"
        )

        fallback_enabled = str(
            frappe.conf.get("dms_agentic_fallback_enabled")
            if frappe.conf.get("dms_agentic_fallback_enabled")
            is not None
            else "1"
        ).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not fallback_enabled:
            return {
                "_llm_status": "agentic_failure",
                "_llm_error": agentic_error,
                "_llm_provider": "openai",
                "_llm_model": (
                    frappe.conf.get("openai_model")
                    or "unknown"
                ),
                "_agentic_used": True,
                "_agentic_steps": 0,
                "_agentic_tool_calls": 0,
                "_agentic_trace": [],
                "_agentic_request_ids": [],
            }

    legacy = _call_openai_single_pass(
        user_query,
        memory_context,
        data_pack,
    )
    legacy["_agentic_used"] = False
    legacy["_agentic_steps"] = 0
    legacy["_agentic_tool_calls"] = 0
    legacy["_agentic_trace"] = []
    legacy["_agentic_request_ids"] = []
    legacy["_agentic_fallback_error"] = agentic_error
    return legacy


def _attach_agentic_plan_metadata(
    other: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    other["agentic_mode"] = bool(
        plan.get("_agentic_used")
    )
    other["agentic_steps"] = int(
        plan.get("_agentic_steps") or 0
    )
    other["agentic_tool_calls"] = int(
        plan.get("_agentic_tool_calls") or 0
    )
    other["agentic_tool_trace"] = (
        plan.get("_agentic_trace") or []
    )
    other["agentic_request_ids"] = (
        plan.get("_agentic_request_ids") or []
    )
    other["agentic_fallback_error"] = (
        plan.get("_agentic_fallback_error")
    )


def _message_agent_data(value: str | None) -> dict[str, Any] | None:
    parsed = _safe_json_loads(value, None)
    return parsed if isinstance(parsed, dict) else None


def _save_message(
    conversation_doc,
    *,
    role: str,
    content: str,
    agent_data: dict[str, Any] | None = None,
    intent: str | None = None,
    response_id: str | None = None,
    is_error: bool = False,
):
    sequence_no = int(conversation_doc.message_count or 0) + 1

    message = frappe.get_doc(
        {
            "doctype": MESSAGE_DOCTYPE,
            "conversation_id": conversation_doc.name,
            "owner_key": conversation_doc.owner_key,
            "sequence_no": sequence_no,
            "role": role,
            "content": str(content or "")[:20000],
            "intent": str(intent or "")[:140],
            "agent_data_json": (
                json.dumps(
                    agent_data,
                    ensure_ascii=False,
                    default=str,
                    separators=(",", ":"),
                )
                if agent_data
                else ""
            ),
            "openai_response_id": str(response_id or "")[:140],
            "is_error": int(bool(is_error)),
        }
    )
    message.insert(ignore_permissions=True)

    conversation_doc.message_count = sequence_no
    conversation_doc.last_message_at = now_datetime()
    conversation_doc.save(ignore_permissions=True)
    return message


def _sanitise_title(value: str | None) -> str:
    title = re.sub(r"\s+", " ", str(value or "")).strip()
    title = re.sub(r"[\r\n\t]+", " ", title)
    return title[:120] or DEFAULT_TITLE


def _normalise_memory(plan: dict[str, Any]) -> dict[str, Any]:
    memory = plan.get("memory")
    if not isinstance(memory, dict):
        memory = _default_memory_state()

    return {
        "summary": str(memory.get("summary") or "").strip()[
            :MAX_MEMORY_SUMMARY_CHARS
        ],
        "active_resource": memory.get("active_resource"),
        "companies": [
            str(item)
            for item in (memory.get("companies") or [])
            if item
        ][:10],
        "time_range": memory.get("time_range"),
        "metric": memory.get("metric"),
        "chart_type": (
            memory.get("chart_type")
            if memory.get("chart_type")
            in {"none", "table", "bar", "line", "pie"}
            else "none"
        ),
        "last_user_goal": str(memory.get("last_user_goal") or "")[:500],
        "unresolved_references": [
            str(item)[:300]
            for item in (memory.get("unresolved_references") or [])
            if item
        ][:10],
    }


def _update_conversation_from_plan(conversation_doc, plan: dict[str, Any]):
    memory = _normalise_memory(plan)
    conversation_doc.memory_summary = memory["summary"]
    conversation_doc.memory_state_json = json.dumps(
        memory,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    conversation_doc.last_intent = str(plan.get("intent") or "")[:140]
    conversation_doc.last_resource = str(
        memory.get("active_resource") or ""
    )[:140]
    conversation_doc.last_openai_response_id = str(
        plan.get("_openai_response_id") or ""
    )[:140]
    conversation_doc.last_message_at = now_datetime()

    proposed_title = _sanitise_title(plan.get("conversation_title"))
    if (
        conversation_doc.title == DEFAULT_TITLE
        or int(conversation_doc.message_count or 0) <= 2
    ):
        conversation_doc.title = proposed_title

    conversation_doc.save(ignore_permissions=True)


def _attach_conversation_metadata(
    data: dict[str, Any],
    conversation_doc,
) -> dict[str, Any]:
    data["conversation_id"] = conversation_doc.name
    data["conversation_title"] = conversation_doc.title
    data["memory_summary"] = conversation_doc.memory_summary or ""

    other = data.setdefault("filters_applied", {}).setdefault("other", {})
    other["memory_context_mode"] = "summary_only"
    other["conversation_id"] = conversation_doc.name
    other["conversation_message_count"] = int(
        conversation_doc.message_count or 0
    )
    other["memory_summary_chars"] = len(
        conversation_doc.memory_summary or ""
    )
    return data


def _serialize_conversation(doc) -> dict[str, Any]:
    return {
        "id": doc.name,
        "title": doc.title or DEFAULT_TITLE,
        "company_name": doc.company_name,
        "is_group_admin": bool(doc.is_group_admin),
        "message_count": int(doc.message_count or 0),
        "memory_summary": doc.memory_summary or "",
        "last_intent": doc.last_intent or "",
        "last_resource": doc.last_resource or "",
        "last_message_at": str(
            doc.last_message_at or doc.modified or ""
        ),
        "created_at": str(doc.creation or ""),
        "updated_at": str(doc.modified or ""),
        "status": doc.status or "Active",
    }


def _serialize_message(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("name"),
        "role": row.get("role"),
        "content": row.get("content") or "",
        "timestamp": str(row.get("creation") or ""),
        "sequence_no": int(row.get("sequence_no") or 0),
        "intent": row.get("intent") or "",
        "agent_data": _message_agent_data(row.get("agent_data_json")),
        "error": bool(row.get("is_error")),
    }


def create_conversation(title: str | None = None):
    payload = _request_payload()
    doc = _create_conversation(title or payload.get("title"))
    return _base().success(data=_serialize_conversation(doc))


def list_conversations():
    owner = _owner_context()
    rows = frappe.get_all(
        CONVERSATION_DOCTYPE,
        filters={
            "owner_key": owner["owner_key"],
            "scope_key": owner["scope_key"],
            "status": "Active",
        },
        fields=[
            "name",
            "title",
            "company_name",
            "is_group_admin",
            "message_count",
            "memory_summary",
            "last_intent",
            "last_resource",
            "last_message_at",
            "creation",
            "modified",
            "status",
        ],
        order_by="last_message_at desc, modified desc",
        limit_page_length=MAX_CONVERSATIONS,
    )

    conversations = []
    for row in rows:
        item = dict(row)
        item["id"] = item.pop("name")
        item["created_at"] = str(item.pop("creation") or "")
        item["updated_at"] = str(item.pop("modified") or "")
        item["last_message_at"] = str(item.get("last_message_at") or "")
        item["is_group_admin"] = bool(item.get("is_group_admin"))
        item["message_count"] = int(item.get("message_count") or 0)
        conversations.append(item)

    return _base().success(data=conversations)


def get_conversation(conversation_id: str | None = None):
    payload = _request_payload()
    conversation_id = (
        conversation_id
        or payload.get("conversation_id")
        or payload.get("id")
    )
    doc = _get_conversation(str(conversation_id or ""))

    rows = frappe.get_all(
        MESSAGE_DOCTYPE,
        filters={
            "conversation_id": doc.name,
            "owner_key": doc.owner_key,
        },
        fields=[
            "name",
            "role",
            "content",
            "creation",
            "sequence_no",
            "intent",
            "agent_data_json",
            "openai_response_id",
            "is_error",
        ],
        order_by="sequence_no asc, creation asc",
        limit_page_length=MAX_MESSAGES_PER_LOAD,
    )

    return _base().success(
        data={
            "conversation": _serialize_conversation(doc),
            "messages": [
                _serialize_message(dict(row))
                for row in rows
            ],
        }
    )


def archive_conversation(conversation_id: str | None = None):
    payload = _request_payload()
    conversation_id = (
        conversation_id
        or payload.get("conversation_id")
        or payload.get("id")
    )
    doc = _get_conversation(str(conversation_id or ""))
    doc.status = "Archived"
    doc.save(ignore_permissions=True)
    return _base().success(data={"id": doc.name, "status": "Archived"})


def query_with_memory(
    query: str | None = None,
    conversation_id: str | None = None,
    **kwargs,
):
    base = _base()
    provider, _api_key, model = base._data_agent_provider_config()

    payload = _request_payload()
    payload.update(kwargs or {})

    user_query = str(
        query
        or payload.get("query")
        or payload.get("message")
        or payload.get("text")
        or ""
    ).strip()
    conversation_id = str(
        conversation_id
        or payload.get("conversation_id")
        or ""
    ).strip()

    if not user_query:
        data = base._base_response(
            intent="out_of_scope",
            metric=None,
            time_range=None,
            company_id=None,
            company_name=None,
            widgets_to_show=[],
            text_response="Please ask a DMS data question.",
            widget_payloads={},
            other={"answer_type": "empty_query"},
        )
        return base.success(data=data)

    if provider != "openai":
        data = base._data_agent_llm_error(
            {
                "_llm_status": "unsupported_provider",
                "_llm_error": "The mandatory LLM provider must be OpenAI.",
                "_llm_provider": provider,
                "_llm_model": model,
            },
            user_query,
        )
        return base.success(data=data)

    conversation_doc = (
        _get_conversation(conversation_id)
        if conversation_id
        else _create_conversation()
    )

    _save_message(conversation_doc, role="user", content=user_query)

    denial = base._data_agent_cross_tenant_denial(user_query)
    if denial:
        denial = _attach_conversation_metadata(denial, conversation_doc)
        _save_message(
            conversation_doc,
            role="assistant",
            content=denial.get("text_response") or "",
            agent_data=denial,
            intent=denial.get("intent"),
        )
        denial = _attach_conversation_metadata(denial, conversation_doc)
        return base.success(data=denial)

    (
        llm_pack,
        execution_pack,
        memory_context,
        _retrieval_query,
    ) = _build_data_packs(
        user_query,
        conversation_doc,
    )
    plan = _call_openai(user_query, memory_context, llm_pack)

    if plan.get("_llm_status") != "ok":
        data = base._data_agent_llm_error(plan, user_query)
        other = data["filters_applied"]["other"]
        other["rag_mode"] = "ultra_compact_structured_rag"
        other["memory_context_mode"] = "summary_only"
        other["rag_context_chars"] = llm_pack.get("_debug_context_chars")
        other["rag_resources"] = list(
            (llm_pack.get("resources") or {}).keys()
        )
        _attach_agentic_plan_metadata(other, plan)

        data = _attach_conversation_metadata(data, conversation_doc)
        _save_message(
            conversation_doc,
            role="assistant",
            content=data.get("text_response") or "",
            agent_data=data,
            intent=data.get("intent"),
            response_id=plan.get("_openai_response_id"),
            is_error=True,
        )
        data = _attach_conversation_metadata(data, conversation_doc)
        return base.success(data=data)

    data = base._data_agent_response(plan, execution_pack, user_query)
    other = data["filters_applied"]["other"]
    other["rag_mode"] = "ultra_compact_structured_rag"
    other["memory_context_mode"] = "summary_only"
    other["rag_context_chars"] = llm_pack.get("_debug_context_chars")
    other["rag_resources"] = list(
        (llm_pack.get("resources") or {}).keys()
    )
    _attach_agentic_plan_metadata(other, plan)

    _update_conversation_from_plan(conversation_doc, plan)
    data = _attach_conversation_metadata(data, conversation_doc)

    _save_message(
        conversation_doc,
        role="assistant",
        content=data.get("text_response") or "",
        agent_data=data,
        intent=data.get("intent"),
        response_id=plan.get("_openai_response_id"),
    )

    conversation_doc.reload()
    data = _attach_conversation_metadata(data, conversation_doc)
    return base.success(data=data)
