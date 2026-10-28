-- Stock debate experimental schema; reviewed migration, NOT executed on life-core.
CREATE SCHEMA IF NOT EXISTS stock_research;
CREATE TABLE IF NOT EXISTS stock_research.source_snapshots (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_id TEXT NOT NULL, stock_code TEXT NOT NULL, market_date DATE NOT NULL,
 retrieved_at TIMESTAMPTZ NOT NULL, source_url TEXT NOT NULL,
 sha256 CHAR(64) NOT NULL, raw_record JSONB NOT NULL,
 open_price NUMERIC(16,4), high_price NUMERIC(16,4), low_price NUMERIC(16,4),
 close_price NUMERIC(16,4), trade_volume BIGINT,
 UNIQUE(source_id,stock_code,market_date,sha256)
);
CREATE TABLE IF NOT EXISTS stock_research.runs (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 run_key TEXT NOT NULL UNIQUE, stock_code TEXT NOT NULL,
 market_date DATE NOT NULL, completed_at TIMESTAMPTZ NOT NULL,
 snapshot_id BIGINT NOT NULL REFERENCES stock_research.source_snapshots(id),
 research_status TEXT NOT NULL CHECK (research_status IN ('COMPLETED','INVALID')),
 horizon_trading_days INTEGER NOT NULL CHECK (horizon_trading_days>0),
 qc_status TEXT NOT NULL DEFAULT 'QC_PENDING' CHECK(qc_status IN ('QC_PENDING','QC_PASS','QC_FAIL'))
);
CREATE TABLE IF NOT EXISTS stock_research.agent_arguments (
 run_id BIGINT NOT NULL REFERENCES stock_research.runs(id) ON DELETE RESTRICT,
 agent_role CHAR(1) NOT NULL CHECK(agent_role IN ('A','B')),
 ordinal INTEGER NOT NULL CHECK(ordinal>0),
 observed_fact TEXT NOT NULL, conditional_inference TEXT NOT NULL, unknown_fact TEXT NOT NULL,
 PRIMARY KEY(run_id,agent_role,ordinal)
);
CREATE TABLE IF NOT EXISTS stock_research.agent_scores (
 run_id BIGINT NOT NULL REFERENCES stock_research.runs(id) ON DELETE RESTRICT,
 agent_role CHAR(1) NOT NULL CHECK(agent_role IN ('A','B')),
 evidence_fidelity SMALLINT NOT NULL CHECK(evidence_fidelity BETWEEN 0 AND 40),
 inference_quality SMALLINT NOT NULL CHECK(inference_quality BETWEEN 0 AND 25),
 counterevidence_handling SMALLINT NOT NULL CHECK(counterevidence_handling BETWEEN 0 AND 20),
 falsifiability SMALLINT NOT NULL CHECK(falsifiability BETWEEN 0 AND 15),
 total SMALLINT GENERATED ALWAYS AS (evidence_fidelity+inference_quality+counterevidence_handling+falsifiability) STORED,
 PRIMARY KEY(run_id,agent_role)
);
CREATE TABLE IF NOT EXISTS stock_research.verdicts (
 run_id BIGINT PRIMARY KEY REFERENCES stock_research.runs(id) ON DELETE RESTRICT,
 verdict TEXT NOT NULL, tie_threshold INTEGER NOT NULL,
 explanation TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stock_research.outcomes (
 run_id BIGINT NOT NULL REFERENCES stock_research.runs(id) ON DELETE RESTRICT,
 horizon_trading_days INTEGER NOT NULL CHECK(horizon_trading_days>0),
 due_market_date DATE, observed_market_date DATE, observed_close NUMERIC(16,4),
 return_pct NUMERIC(12,6), status TEXT NOT NULL CHECK(status IN ('PENDING','OBSERVED','UNAVAILABLE')),
 PRIMARY KEY(run_id,horizon_trading_days)
);
CREATE INDEX IF NOT EXISTS stock_research_runs_completed_idx ON stock_research.runs(completed_at DESC);
-- Access: do not grant public/anonymous direct DB access. API uses a least-privilege role.
