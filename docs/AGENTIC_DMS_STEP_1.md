# Agentic DMS — Step 1

## Scope completed

This step introduces the agentic backend kernel on the existing `main` branch.

### Implemented

- Dynamic capability registry using Python decorators.
- Automatic discovery of modules under `dms.agent.tools`.
- Strict OpenAI function-tool schemas.
- Per-call tenant and role context.
- Backend argument validation and read-only enforcement.
- Exact authorised record querying.
- Exact count/sum/average/min/max aggregation.
- Grouping by company, month, company+month, status and model.
- Initial DMS semantic and metric catalog.
- Multi-step OpenAI Responses tool loop.
- Configurable reasoning effort, step limit and tool-call limit.
- OpenAI request IDs and structured tool execution traces.
- Automatic fallback to the existing single-pass implementation.
- Runtime registry probe.
- Live OpenAI-to-backend-tool smoke test.

## Extension model

Add a module under `backend/dms/agent/tools/` and decorate its handler with
`@register_tool(...)`. The registry discovers it automatically. The main chat
endpoint does not need to be rewritten for every new backend capability.

## Configuration

- `dms_agentic_enabled = 1`
- `dms_agentic_max_steps = 8`
- `dms_agentic_max_tool_calls = 16`
- `dms_agentic_reasoning_effort = high`
- `dms_agentic_fallback_enabled = 1`

## Deliberately deferred

1. Result snapshots and exact chart/table transformations.
2. Rich multi-series analytical UI schema.
3. Full semantic metric catalog and cross-resource joins.
4. Hybrid vector knowledge retrieval.
5. High-load queues, streaming, caching and observability.
6. Automated analytical evaluation suite.
