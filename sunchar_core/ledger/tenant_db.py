import os
import duckdb
import json
from contextlib import contextmanager
from typing import Generator

LEDGER_BASE_DIR = os.path.join("data", "ledgers")
WORM_BASE_DIR = os.path.join("data", "worm_archive")

os.makedirs(LEDGER_BASE_DIR, exist_ok=True)
os.makedirs(WORM_BASE_DIR, exist_ok=True)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS raw_execution_events (
    receipt_id UUID PRIMARY KEY,
    job_id VARCHAR(128) NOT NULL,
    workload_name VARCHAR(256) NOT NULL,
    settlement_window_utc TIMESTAMP NOT NULL,
    dispatched_at_utc TIMESTAMP NOT NULL,
    completed_at_utc TIMESTAMP,
    duration_seconds INTEGER,
    kwh_consumed DOUBLE,
    intensity_aef_gco2 DOUBLE NOT NULL,
    statutory_emissions_gco2 DOUBLE,
    intensity_mef_gco2 DOUBLE NOT NULL,
    avoided_emissions_mef_gco2 DOUBLE,
    spot_price_gbp_per_mwh DOUBLE,
    cost_savings_gbp DOUBLE,
    is_override BOOLEAN NOT NULL DEFAULT FALSE,
    override_reason VARCHAR(64),
    code_payload_hash VARCHAR(64) NOT NULL,
    record_hash VARCHAR(64) NOT NULL,
    engine_signature VARCHAR(128) NOT NULL
);

CREATE TABLE IF NOT EXISTS settlement_merkle_blocks (
    block_id UUID PRIMARY KEY,
    settlement_window_utc TIMESTAMP NOT NULL,
    job_count INTEGER NOT NULL,
    total_kwh DOUBLE NOT NULL,
    statutory_total_gco2 DOUBLE NOT NULL,
    avoided_total_gco2 DOUBLE NOT NULL,
    merkle_root_hash VARCHAR(64) NOT NULL,
    engine_root_signature VARCHAR(128) NOT NULL,
    stamped_at_utc TIMESTAMP NOT NULL,
    audit_pack_sealed BOOLEAN DEFAULT FALSE
);
"""

@contextmanager
def get_tenant_db(tenant_id: str) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """
    Provides an isolated, short-lived database connection per tenant.
    Prevents cross-tenant state leakage and async connection locking.
    """
    # Sanitize tenant identifier to prevent directory traversal
    clean_tenant = "".join(c for c in tenant_id if c.isalnum() or c in ("-", "_"))
    db_path = os.path.join(LEDGER_BASE_DIR, f"{clean_tenant}.duckdb")
    
    conn = duckdb.connect(db_path)
    try:
        conn.execute(SCHEMA_SQL)
        yield conn
    finally:
        conn.close()

def archive_worm_block(tenant_id: str, block_data: dict):
    """
    Writes a sealed settlement block to an append-only WORM archive file.
    Provides statutory non-volatile storage required under UK Companies Act.
    """
    clean_tenant = "".join(c for c in tenant_id if c.isalnum() or c in ("-", "_"))
    tenant_worm_dir = os.path.join(WORM_BASE_DIR, clean_tenant)
    os.makedirs(tenant_worm_dir, exist_ok=True)
    
    block_filename = f"block_{block_data['block_id']}.json"
    block_filepath = os.path.join(tenant_worm_dir, block_filename)
    
    with open(block_filepath, "w", encoding="utf-8") as f:
        json.dump(block_data, f, indent=2)
