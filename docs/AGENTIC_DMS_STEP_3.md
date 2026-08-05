# Agentic DMS Step 3 — Database-Native Exact Analytics

## Status

Step 3 replaces the bounded Python aggregation path used by
`aggregate_dms_records` with database-side filtering, grouping and arithmetic.

The public OpenAI tool name and strict input schema are unchanged.

## Scope

The implementation supports the eight existing resources:

- customers
- leads
- sales
- invoices
- bookings
- test drives
- service jobs
- vehicles

Supported operations remain:

- count
- sum
- average
- minimum
- maximum

Supported groupings remain:

- none
- company
- month
- company and month
- status
- model

## Security contract

Tenant scope is derived from the trusted backend `ToolContext`.

A tenant user cannot broaden access by:

- omitting the company argument;
- passing `all`;
- naming another tenant;
- supplying a different tenant identifier in the natural-language request.

For tenant users, the effective database predicate is always the authenticated
company scope. Requested companies are validated against that scope.

For group administrators, an empty company list means all authorised companies.
A non-empty list creates a validated database predicate for those companies.

All table and field identifiers come from the semantic catalog and live Frappe
DocType metadata. User- or LLM-controlled strings are passed only as bound SQL
parameters.

## Exactness contract

The native path performs three database responsibilities:

1. calculate the exact matching row count and exact overall aggregate;
2. calculate the exact number of groups;
3. return only the configured number of ordered groups.

The group payload limit never limits source records or the overall calculation.

`overall_value` semantics are:

- count: exact filtered record count;
- sum: exact sum over filtered records;
- average: exact average over filtered non-null values;
- minimum: exact minimum over filtered non-null values;
- maximum: exact maximum over filtered non-null values.

`total_value` is retained as a compatibility alias for Step 2 snapshots.

## Empty-result contract

For zero matching records:

- count and sum return zero;
- average, minimum and maximum return null;
- rows are empty;
- total_groups and returned_groups are zero;
- truncated_groups is false.

## Date boundaries

Date fields use inclusive `>= date_from` and `<= date_to` predicates.

Datetime fields use:

- `>= date_from 00:00:00`
- `< day_after_date_to 00:00:00`

This includes the complete final day.

## Snapshot compatibility

`result_store.py` prefers `overall_value` when present and falls back to the
legacy `total_value` field.

Native database numeric types are normalized before snapshot construction:

- counts become integers;
- monetary and decimal aggregates become JSON-safe numbers;
- null aggregates remain null.

Step 2 snapshot IDs, deterministic source hashes, multi-series datasets and
presentation-only reuse remain unchanged.

## Runtime probes

Read-only probes are available through the installed DMS app:

```bash
bench --site dms.localhost execute \
  dms.agent.native_analytics.runtime_probe

bench --site dms.localhost execute \
  dms.agent.native_analytics.validation_probe

bench --site dms.localhost execute \
  dms.agent.native_analytics.snapshot_contract_probe
```

The validation probe compares native resource counts and sales arithmetic
against independent database queries, exercises every grouping, checks payload
truncation, validates empty-result semantics, verifies tenant denial and checks
same-day Datetime inclusion.

## Deployment

Step 3 adds no DocType and requires no migration.

Local deterministic probes and one live OpenAI tool-loop smoke test must pass
before committing and pushing the implementation.
