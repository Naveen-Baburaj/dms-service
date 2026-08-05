# OpenAI-only DMS AI provider

The dashboard agent uses OpenAI as its only language-model provider.

## Active path

`POST /api/method/dms.api.ai_agent.query` performs deterministic tenant authorization, builds an ultra-compact structured RAG data pack from authorized Frappe DocTypes, calls the OpenAI Responses API with strict JSON Schema, and converts the result into backend-controlled text, tables, and charts.

OpenAI does not grant permissions or execute database queries directly. If OpenAI is unavailable, the endpoint returns a controlled `backend_llm_error`; it does not fall back to another model provider.

## Required production variables

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=<secret>
OPENAI_MODEL=gpt-5.4-mini
OPENAI_TIMEOUT_SECONDS=75
OPENAI_MAX_OUTPUT_TOKENS=1400
OPENAI_MAX_RETRIES=2
```

Optional organization and project routing variables are `OPENAI_ORG_ID` and `OPENAI_PROJECT_ID`.

## Status endpoint

`GET /api/method/dms.api.ai_agent.llm_status`

The endpoint exposes provider/model state without exposing secrets.
