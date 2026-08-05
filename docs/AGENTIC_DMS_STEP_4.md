# Agentic DMS Step 4 — Production Execution Guardrails

## Status

Step 4 hardens the existing read-only Agentic DMS runtime. It does not add
write-capable tools, cross-resource joins, vector retrieval, or deployment.

## Controls

### Request authentication boundary

The AI endpoint remains compatible with the current local mock-login phase
while `dms_production_auth_required` is disabled.

When `dms_production_auth_required` is enabled:

- `Guest` sessions are rejected;
- development authority headers (`x-user-role` and `x-tenant-id`) are rejected;
- a real authenticated Frappe session is required.

The production flag must be enabled only after the frontend has migrated from
mock headers to real Frappe authentication.

### Redis-backed request rate limiting

Request limits are enforced atomically in Redis. The default is 60 requests per
60-second window for a stable, hashed request identity.

### Redis-backed distributed concurrency

A sorted-set lease limits concurrent AI requests across workers. Expired leases
are removed atomically. The default is two concurrent requests per identity
with a 180-second safety lease.

### Tool rate limiting

Every registered tool call receives a separate Redis-backed limit. The default
is 240 tool executions per 60-second window for each authorised identity and
tool.

### Tool timeout

`AgentTool.timeout_seconds` is now enforced. In the normal synchronous Unix
worker path, `SIGALRM`/`setitimer` interrupts an overlong tool. A measured
elapsed-deadline fallback is retained for non-main-thread runtimes.

### Structured audit log

Requests and tool executions are written to the site-aware
`dms_agent_audit` logger. Audit records contain:

- request and audit IDs;
- duration and outcome;
- tool name;
- rate/concurrency decisions;
- hashes of inputs, arguments, outputs and scope;
- timeout and truncation state;
- error type and an error fingerprint.

Raw prompts, raw tool arguments, raw database rows, credentials, tokens and
full error text are not stored in the audit event.

## Configuration

```text
dms_agent_controls_enabled = 1
dms_agent_controls_fail_closed = 1
dms_agent_audit_enabled = 1
dms_agent_rate_limit_requests = 60
dms_agent_rate_limit_tools = 240
dms_agent_rate_limit_window_seconds = 60
dms_agent_max_concurrent_requests = 2
dms_agent_concurrency_lease_seconds = 180
dms_production_auth_required = 0
```

The production-auth flag intentionally remains disabled while the frontend is
still using development headers.

## Runtime verification

```bash
cd ~/frappe/dms-frappe-bench

bench --site dms.localhost execute \
  dms.agent.controls.runtime_probe

bench --site dms.localhost execute \
  dms.agent.orchestrator.runtime_probe

bench --site dms.localhost execute \
  dms.agent.native_analytics.validation_probe

bench --site dms.localhost execute \
  dms.agent.orchestrator.live_smoke_test
```

The controls probe validates Redis atomic rate limiting, distributed
concurrency denial/release, hard timeout behavior, audit logging, and the
production-auth decision matrix.

## Production activation

After real Frappe login is working end to end and the frontend no longer sends
`x-user-role` or `x-tenant-id` as authority:

```bash
cd ~/frappe/dms-frappe-bench
bench --site dms.localhost set-config dms_production_auth_required 1
bench --site dms.localhost clear-cache
```

Do not activate that flag during the mock-login phase.

## Deferred work

The following remain later phases:

- persistent audit DocType and retention UI;
- cross-resource analytical joins;
- vector retrieval for unstructured documents;
- write-capable tools and approval workflows;
- deployment-specific reverse-proxy limits and external observability.
