import duckdb
from pathlib import Path

SCHEMA_SQL = """
-- Execution-level records (concurrent parallel appends)
CREATE TABLE IF NOT EXISTS raw_execution_events (
    receipt_id UUID PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    job_id VARCHAR(128) NOT NULL,
    workload_name VARCHAR(256) NOT NULL,
    settlement_window_utc TIMESTAMP NOT NULL,
    dispatched_at_utc TIMESTAMP NOT NULL,
    completed_at_utc TIMESTAMP,
    duration_seconds INTEGER,
    kwh_consumed DOUBLE,
    -- Stream A: Statutory SECR Location-based (Average Emissions Factor)
    intensity_aef_gco2 DOUBLE NOT NULL,
    statutory_emissions_gco2 DOUBLE,
    -- Stream B: Consequential Impact (Marginal Emissions Factor)
    intensity_mef_gco2 DOUBLE NOT NULL,
    avoided_emissions_mef_gco2 DOUBLE,
    spot_price_gbp_per_mwh DOUBLE,
    cost_savings_gbp DOUBLE,
    -- Audit & State flags
    is_override BOOLEAN NOT NULL DEFAULT FALSE,
    override_reason VARCHAR(64),
    code_payload_hash VARCHAR(64) NOT NULL,
    record_hash VARCHAR(64) NOT NULL
);

-- Settlement block headers (Merkle-stamped every 30 minutes)
CREATE TABLE IF NOT EXISTS settlement_merkle_blocks (
    block_id UUID PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    settlement_window_utc TIMESTAMP NOT NULL,
    job_count INTEGER NOT NULL,
    total_kwh DOUBLE NOT NULL,
    statutory_total_gco2 DOUBLE NOT NULL,
    avoided_total_gco2 DOUBLE NOT NULL,
    merkle_root_hash VARCHAR(64) NOT NULL,
    stamped_at_utc TIMESTAMP NOT NULL,
    audit_pack_sealed BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_tenant_settlement 
ON raw_execution_events (tenant_id, settlement_window_utc);
"""

def init_ledger_db(db_path: str = "greenops_ledger.duckdb") -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(db_path)
    conn.execute(SCHEMA_SQL)
    return conn

if __name__ == "__main__":
    conn = init_ledger_db()
    print("DuckDB v0.2.0 dual-accounting schema initialized successfully.")
    conn.close()
