# PostgreSQL history migration contract

## Purpose

Move durable TWSE historical snapshots out of Google Sheets without interrupting the existing weekday collector.

Current evidence on 2026-08-11:

- `Historical_BWIBBU` contains valid history through `2026-08-10`.
- `Historical_STOCK_DAY_ALL` contains valid history through `2026-08-07` and currently ends at row `277287`.
- The same collection pipeline therefore has partial-success risk: one dataset can complete while another dataset fails.

## Source / target roles

During migration:

- TWSE OpenAPI remains the upstream source.
- Existing Vercel collector remains active until the PostgreSQL path is verified.
- Existing Google Sheets remain migration source / compatibility evidence.
- `stock_history` PostgreSQL becomes the target durable-history store.

After parity:

- PostgreSQL is the durable historical store.
- A lightweight Sheet current/dashboard projection may remain if it still has practical value.
- Append-only historical Sheet writes may be retired only after explicit parity verification.

## Idempotent business keys

### BWIBBU

`(snapshot_date, code)`

### STOCK_DAY_ALL

`(snapshot_date, code)`

Repeated ingestion of the same market day must UPSERT or no-op on these keys; it must never create duplicate history rows.

## Dataset completeness

Every dataset/date pair must record an `ingestion_runs` row. A run is `COMPLETE` only after all target rows for that dataset are committed. BWIBBU completion must not imply STOCK_DAY_ALL completion, and vice versa.

This explicitly prevents the current failure mode where the collector can write one history dataset and fail later in the same request.

## Migration order

1. Create empty PostgreSQL schema.
2. Read-only export existing Sheet history in bounded batches.
3. Normalize values and load transactionally by dataset/date.
4. Compare date coverage and per-date row counts against Sheets.
5. Add shadow write from the collector to PostgreSQL while preserving existing Sheet writes.
6. Observe repeated weekday runs and verify both datasets complete independently.
7. Make PostgreSQL durable history canonical.
8. Only then downgrade historical Sheet append behavior.

## Safety boundaries

- Do not stop the existing collector before PostgreSQL shadow writes are verified.
- Do not truncate or rewrite historical Sheets during migration.
- Do not infer successful collection from only one dataset.
- Do not expose PostgreSQL publicly; reuse the existing life-core private runtime/control boundary.
- Do not add investment-advice semantics as part of the storage migration.
