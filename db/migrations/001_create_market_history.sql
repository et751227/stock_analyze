BEGIN;

CREATE SCHEMA IF NOT EXISTS stock_history;

CREATE TABLE IF NOT EXISTS stock_history.ingestion_runs (
    dataset text NOT NULL CHECK (dataset IN ('BWIBBU', 'STOCK_DAY_ALL')),
    snapshot_date date NOT NULL,
    source text NOT NULL DEFAULT 'TWSE_OPENAPI',
    row_count integer NOT NULL CHECK (row_count >= 0),
    status text NOT NULL CHECK (status IN ('STARTED', 'COMPLETE', 'FAILED')),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    error_code text,
    PRIMARY KEY (dataset, snapshot_date)
);

CREATE TABLE IF NOT EXISTS stock_history.bwibbu_snapshots (
    snapshot_date date NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    dividend_yield numeric,
    pe_ratio numeric,
    pb_ratio numeric,
    fiscal_year_quarter text,
    source text NOT NULL DEFAULT 'TWSE_OPENAPI_BWIBBU_D',
    ingested_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (snapshot_date, code)
);

CREATE INDEX IF NOT EXISTS idx_bwibbu_code_snapshot_date
    ON stock_history.bwibbu_snapshots (code, snapshot_date DESC);

CREATE TABLE IF NOT EXISTS stock_history.stock_day_snapshots (
    snapshot_date date NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    open_price numeric,
    high_price numeric,
    low_price numeric,
    close_price numeric,
    change_value numeric,
    trade_volume bigint,
    trade_value bigint,
    transaction_count bigint,
    source text NOT NULL DEFAULT 'TWSE_OPENAPI_STOCK_DAY_ALL',
    ingested_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (snapshot_date, code)
);

CREATE INDEX IF NOT EXISTS idx_stock_day_code_snapshot_date
    ON stock_history.stock_day_snapshots (code, snapshot_date DESC);

COMMIT;
