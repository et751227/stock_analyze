# Stock Debate v0.1 — integration gate
Status: PR #6 source only; no production write or release.

Canonical flow: private experiment.json -> validator -> PostgreSQL -> read-only projection -> governed private API -> Vercel server-side gateway -> Dashboard.

1. Preserve original experiment.json in private owned storage, not the public repository.
2. Review db/migrations/001_stock_research.sql against the live DB and current backup; test on isolated database first.
3. Run scripts/import_experiment.py without --apply for validation, then import to DB under approved scoped credentials. Repeat to verify idempotency.
4. Read-after-write expected: one run, one source snapshot, six argument rows, two score rows, one verdict, one pending outcome.
5. scripts/research_repository.py provides the database projection. Frontend expects GET /api/research_latest?code=2330 -> {ok:true,data:projection}. Gateway is NOT implemented until private ingress and authentication are verified.
6. Confirm authorization is enforced server-side and secrets never appear in browser, then CI, production release and semantic smoke.
7. Do not activate scheduler yet. Scores measure argument quality, not investment return probability.

The public JSON projection was intentionally removed from the PR; data must not compete with PostgreSQL as Source of Truth.