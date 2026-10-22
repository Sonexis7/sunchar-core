import uuid
from datetime import datetime, timedelta, timezone
from greenops.telemetry.collector import DualStreamTelemetryCollector
from greenops.engine.gating import GatingEvaluator, GatingRequest
from greenops.ledger.database import init_ledger_db

def test_full_pipeline_flow():
    print("\n--- 1. Testing Live Dual Telemetry Fetch ---")
    collector = DualStreamTelemetryCollector()
    telemetry = collector.fetch_live_telemetry()
    assert telemetry["intensity_aef_gco2"] > 0
    assert telemetry["intensity_mef_gco2"] >= telemetry["intensity_aef_gco2"]
    print(f"AEF (Statutory SECR): {telemetry['intensity_aef_gco2']} gCO2/kWh")
    print(f"MEF (Consequential):  {telemetry['intensity_mef_gco2']} gCO2/kWh")
    print(f"Spot Index:           £{telemetry['spot_price_gbp_per_mwh']}/MWh")

    print("\n--- 2. Testing Hard SLA Timeout Invariant ---")
    # Simulate a job whose deadline is only 20 minutes away, but takes 15 mins to run + 10 min buffer
    urgent_req = GatingRequest(
        job_id=str(uuid.uuid4()),
        tenant_id="enterprise-pilot-01",
        workload_name="nightly-financial-rollups",
        sla_deadline_utc=datetime.now(timezone.utc) + timedelta(minutes=20),
        estimated_duration_sec=900,
        buffer_sec=600
    )
    should_dispatch, reason, metrics = GatingEvaluator.evaluate(urgent_req, telemetry)
    assert should_dispatch is True
    assert reason == "SLA_EXPIRATION_OVERRIDE"
    print(f"SLA Invariant Enforcement: PASS (Decision: {reason})")

    print("\n--- 3. Testing DuckDB Event Ledger Commitment ---")
    conn = init_ledger_db("test_run.duckdb")
    receipt_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    conn.execute("""
        INSERT INTO raw_execution_events (
            receipt_id, tenant_id, job_id, workload_name, settlement_window_utc,
            dispatched_at_utc, intensity_aef_gco2, intensity_mef_gco2,
            spot_price_gbp_per_mwh, is_override, override_reason,
            code_payload_hash, record_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        receipt_id, urgent_req.tenant_id, urgent_req.job_id, urgent_req.workload_name,
        now, now, telemetry["intensity_aef_gco2"], telemetry["intensity_mef_gco2"],
        telemetry["spot_price_gbp_per_mwh"], True, reason,
        "dummy_payload_sha256", "dummy_record_sha256"
    ))
    
    row_count = conn.execute("SELECT COUNT(*) FROM raw_execution_events").fetchone()[0]
    assert row_count >= 1
    print(f"DuckDB Commit: PASS (Total records: {row_count})")
    conn.close()
    print("\n>>> ALL V0.2.0 CORE PIPELINE TESTS PASSED <<<")

if __name__ == "__main__":
    test_full_pipeline_flow()
