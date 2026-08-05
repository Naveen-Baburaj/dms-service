from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

import frappe

from dms.agent.context import build_tool_context
from dms.agent.registry import (
    execute_tool,
    openai_tool_definitions,
    registry_probe,
)


def _conf_bool(name: str, default: bool) -> bool:
    value = os.getenv(name.upper()) or frappe.conf.get(name)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _conf_int(
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = os.getenv(name.upper()) or frappe.conf.get(name) or default
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def is_agentic_enabled() -> bool:
    return _conf_bool("dms_agentic_enabled", True)


def _base():
    from dms.api import ai_agent
    return ai_agent


def _openai_headers(
    api_key: str,
    *,
    client_request_id: str,
) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "X-Client-Request-Id": client_request_id,
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


def _post_response(
    payload: dict[str, Any],
    *,
    api_key: str,
    timeout_seconds: int,
    max_retries: int,
) -> tuple[dict[str, Any], str]:
    last_error = "OpenAI Responses request failed"
    for attempt in range(max_retries + 1):
        client_request_id = str(uuid.uuid4())
        try:
            request = urllib.request.Request(
                "https://api.openai.com/v1/responses",
                data=json.dumps(payload).encode("utf-8"),
                headers=_openai_headers(
                    api_key,
                    client_request_id=client_request_id,
                ),
                method="POST",
            )
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
            ) as response:
                return (
                    json.loads(response.read().decode("utf-8")),
                    client_request_id,
                )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}: {body[:1800]}"
            retryable = exc.code in {
                408, 409, 429, 500, 502, 503, 504,
            }
            if not retryable or attempt >= max_retries:
                break
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:1800]}"
            if attempt >= max_retries:
                break
        time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(last_error)


def _function_calls(
    response_json: dict[str, Any],
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for item in response_json.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        raw_arguments = item.get("arguments") or "{}"
        try:
            arguments = (
                json.loads(raw_arguments)
                if isinstance(raw_arguments, str)
                else dict(raw_arguments)
            )
        except Exception as exc:
            arguments = {
                "_invalid_arguments": (
                    f"{type(exc).__name__}: {str(exc)}"
                )
            }
        calls.append(
            {
                "call_id": item.get("call_id") or item.get("id"),
                "name": item.get("name"),
                "arguments": arguments,
            }
        )
    return calls


def _final_text(response_json: dict[str, Any]) -> str:
    return str(
        _base()._data_agent_extract_openai_text(response_json) or ""
    ).strip()


def _compact_seed_overview(
    seed_data_pack: dict[str, Any],
) -> dict[str, Any]:
    resources = seed_data_pack.get("resources") or {}
    return {
        "scope": seed_data_pack.get("scope") or {},
        "retrieval": seed_data_pack.get("retrieval") or {},
        "available_seed_resources": list(resources),
        "resource_summaries": {
            name: {
                "title": value.get("title"),
                "doctype": value.get("doctype"),
                "summary": value.get("summary"),
                "total_rows_available": value.get(
                    "total_rows_available"
                ),
            }
            for name, value in resources.items()
            if isinstance(value, dict)
        },
    }


def _agent_instructions() -> str:
    return """You are the reasoning and orchestration layer for a secure
multi-tenant Dealer Management System.

The backend owns permissions, tenant isolation, database access, exact
calculations and tool execution. Use only registered read-only tools. Never
invent a tool result, database row, total or business metric.

For DMS factual or analytical questions:
1. Inspect capabilities or resource semantics when the request is broad.
2. Call one or more backend tools for authoritative results.
3. Resolve ambiguous words such as sales by clearly separating unit count
   and revenue when both are useful.
4. Use exact aggregation tools for totals.
5. Use multiple tool calls when different measures/resources are needed.
6. Explain meaningful business implications, not only raw figures.
7. Preserve only the current chat's memory.
8. Return the final answer in the supplied strict JSON schema.
9. Never expose credentials, raw SQL or hidden reasoning.
10. If a capability is missing, identify it precisely.

Tenant scope is enforced inside every tool regardless of generated arguments.
""".strip()


def _run_tool_loop(
    *,
    prompt: str,
    output_schema: dict[str, Any],
    tool_names: list[str] | None = None,
    force_first_tool: str | None = None,
) -> dict[str, Any]:
    base = _base()
    provider, api_key, model = base._data_agent_provider_config()
    if provider != "openai":
        raise RuntimeError("The agentic orchestrator requires OpenAI.")
    if not api_key:
        raise RuntimeError("OpenAI API key is not configured.")

    context = build_tool_context()
    tools = openai_tool_definitions(context, names=tool_names)
    if not tools:
        raise RuntimeError("No authorised backend capabilities are available.")

    timeout_seconds = _conf_int("openai_timeout_seconds", 75, 15, 180)
    max_retries = _conf_int("openai_max_retries", 2, 0, 3)
    max_output_tokens = _conf_int(
        "openai_max_output_tokens",
        2400,
        800,
        12_000,
    )
    max_steps = _conf_int("dms_agentic_max_steps", 8, 2, 16)
    max_tool_calls = _conf_int(
        "dms_agentic_max_tool_calls",
        16,
        1,
        40,
    )
    reasoning_effort = str(
        os.getenv("DMS_AGENTIC_REASONING_EFFORT")
        or frappe.conf.get("dms_agentic_reasoning_effort")
        or "high"
    ).strip().lower()
    if reasoning_effort not in {
        "minimal", "low", "medium", "high", "xhigh",
    }:
        reasoning_effort = "high"

    history: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt}
            ],
        }
    ]
    trace: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    request_ids: list[str] = []
    total_tool_calls = 0

    for step in range(1, max_steps + 1):
        tool_choice: str | dict[str, str] = "auto"
        if step == 1 and force_first_tool:
            tool_choice = {
                "type": "function",
                "name": force_first_tool,
            }

        payload: dict[str, Any] = {
            "model": model,
            "instructions": _agent_instructions(),
            "input": history,
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": True,
            "reasoning": {"effort": reasoning_effort},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "dms_agentic_answer",
                    "strict": True,
                    "schema": output_schema,
                }
            },
            "max_output_tokens": max_output_tokens,
            "store": False,
        }

        try:
            response_json, client_request_id = _post_response(
                payload,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
        except RuntimeError as exc:
            message = str(exc).lower()
            if "reasoning" in message or "parallel_tool_calls" in message:
                payload.pop("reasoning", None)
                payload.pop("parallel_tool_calls", None)
                response_json, client_request_id = _post_response(
                    payload,
                    api_key=api_key,
                    timeout_seconds=timeout_seconds,
                    max_retries=max_retries,
                )
            else:
                raise

        request_ids.append(client_request_id)
        output_items = [
            item
            for item in (response_json.get("output") or [])
            if isinstance(item, dict)
        ]
        history.extend(output_items)

        calls = _function_calls(response_json)
        if calls:
            for call in calls:
                total_tool_calls += 1
                if total_tool_calls > max_tool_calls:
                    raise RuntimeError(
                        "Agent exceeded the configured tool-call limit."
                    )

                arguments = call["arguments"]
                if "_invalid_arguments" in arguments:
                    tool_payload = {
                        "ok": False,
                        "tool": call["name"],
                        "error": arguments["_invalid_arguments"],
                    }
                    tool_trace = {
                        "tool": call["name"],
                        "ok": False,
                        "read_only": True,
                        "duration_ms": 0,
                        "output_chars": len(json.dumps(tool_payload)),
                        "truncated": False,
                        "error": tool_payload["error"],
                    }
                else:
                    tool_payload, tool_trace = execute_tool(
                        name=call["name"],
                        arguments=arguments,
                        context=context,
                    )

                tool_trace["step"] = step
                trace.append(tool_trace)
                tool_results.append(
                    {
                        "tool": call["name"],
                        "arguments": arguments,
                        "output": tool_payload,
                    }
                )
                history.append(
                    {
                        "type": "function_call_output",
                        "call_id": call["call_id"],
                        "output": json.dumps(
                            tool_payload,
                            ensure_ascii=False,
                            default=str,
                            separators=(",", ":"),
                        ),
                    }
                )
            continue

        output_text = _final_text(response_json)
        parsed = base._safe_json_loads(output_text)
        if not isinstance(parsed, dict):
            raise RuntimeError(
                "OpenAI returned an empty or invalid final JSON object."
            )

        parsed["_llm_status"] = "ok"
        parsed["_llm_error"] = None
        parsed["_llm_provider"] = "openai"
        parsed["_llm_model"] = model
        parsed["_openai_response_id"] = response_json.get("id")
        parsed["_agentic_used"] = True
        parsed["_agentic_steps"] = step
        parsed["_agentic_tool_calls"] = total_tool_calls
        parsed["_agentic_trace"] = trace
        parsed["_agentic_request_ids"] = request_ids
        parsed["_agentic_tool_results"] = tool_results
        return parsed

    raise RuntimeError(
        "Agent reached maximum reasoning steps without a final answer."
    )


def run_agentic_plan(
    *,
    user_query: str,
    memory_context: str,
    seed_data_pack: dict[str, Any],
    output_schema: dict[str, Any],
) -> dict[str, Any]:
    overview = _compact_seed_overview(seed_data_pack)
    prompt = f"""Resolve the user's DMS request using registered backend tools.

Current user request:
{user_query}

Current-chat memory:
{memory_context}

Backend seed overview:
{json.dumps(overview, ensure_ascii=False, default=str)}

Use tools for authoritative facts and calculations. The seed overview is
metadata and compact summaries, not a substitute for exact tool execution.
Return the final response using the required DMS response schema.
""".strip()
    return _run_tool_loop(
        prompt=prompt,
        output_schema=output_schema,
    )


def runtime_probe() -> dict[str, Any]:
    context = build_tool_context()
    return {
        "enabled": is_agentic_enabled(),
        "context": context.public_scope(),
        "registry": registry_probe(context),
        "max_steps": _conf_int("dms_agentic_max_steps", 8, 2, 16),
        "max_tool_calls": _conf_int(
            "dms_agentic_max_tool_calls",
            16,
            1,
            40,
        ),
        "reasoning_effort": str(
            frappe.conf.get("dms_agentic_reasoning_effort")
            or "high"
        ),
    }


def live_smoke_test() -> dict[str, Any]:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "tool_used": {"type": "string"},
        },
        "required": ["summary", "tool_used"],
    }
    result = _run_tool_loop(
        prompt=(
            "Call aggregate_dms_records to count authorised sales records "
            "grouped by company. Use empty company/status filters, null date "
            "bounds, group_by=company, aggregation=count, value_field=null "
            "and limit_groups=20. Then return a one-sentence summary and "
            "the exact tool name."
        ),
        output_schema=schema,
        tool_names=["aggregate_dms_records"],
        force_first_tool="aggregate_dms_records",
    )
    trace = result.get("_agentic_trace") or []
    return {
        "status": result.get("_llm_status"),
        "tool_calls": result.get("_agentic_tool_calls"),
        "tool_names": [item.get("tool") for item in trace],
        "all_tools_ok": bool(trace)
        and all(item.get("ok") for item in trace),
        "summary": result.get("summary"),
        "model": result.get("_llm_model"),
    }
