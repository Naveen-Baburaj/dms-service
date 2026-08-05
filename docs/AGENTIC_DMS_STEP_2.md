# Agentic DMS — Step 2

## Completed scope

Step 2 adds persistent, tenant-isolated analytical result snapshots and a
universal frontend analytical renderer.

### Backend

- New `DMS AI Result Snapshot` DocType.
- Explicit post-migrate index provisioning.
- Canonical analytical dataset schema.
- Deterministic SHA-256 source hashes.
- Snapshot creation from successful agent tool results.
- Snapshot access revalidates conversation, owner, scope, status and expiry.
- Same-chat presentation-only follow-ups reuse the exact stored dataset.
- Archiving a conversation archives its active snapshots.
- Agent tool outputs are retained only long enough to build the snapshot.

### Frontend

- New `analytical_view` widget.
- Table, line, area, bar, stacked-bar and pie views.
- Multi-series rendering using a dimension such as company.
- Separate count, revenue and other measures.
- Snapshot ID and source-hash metadata.
- Legacy widgets remain available when no canonical snapshot is produced.

## Presentation-only examples

```text
Show that exact result in table form.
Make the same result a pie chart.
Use a stacked bar chart instead.
Show the saved result as a line chart.
```

These requests do not re-query DMS data when the active snapshot is valid.

## Required deployment commands

```bash
bench --site dms.localhost migrate
bench --site dms.localhost execute \
  dms.ai_result_snapshot_setup.ensure_indexes
bench --site dms.localhost clear-cache
```

## Deliberately deferred

- Database-native unlimited aggregations.
- Cross-resource joins.
- Vector knowledge retrieval.
- Redis queues and horizontal scaling.
- SSE progress streaming.
- Write-capable agent tools.
