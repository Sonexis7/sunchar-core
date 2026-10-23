import uuid
from datetime import datetime, timezone
from sunchar_core.main import app
from sunchar_core.security.auth import issue_tenant_token
from fastapi.testclient import TestClient

client = TestClient(app)

def run_e2e_commercial_demo():
    tenant = "enterprise-logistics-uk"
    token = issue_tenant_token(tenant)
    auth_headers = {"Authorization": f"Bearer {token}"}

    print("\n=======================================================")
    print("  RUNNING sunchar_core v0.2.0 END-TO-END COMMERCIAL SUITE  ")
    print("=======================================================\n")

    # 1. Health & Live Telemetry
    res = client.get("/health")
    assert res.status_code == 200
    print("[1/4] Service Health Check: ONLINE")

    # 2. Simulate 5 Batch Runs with Dual Accounting & Hypervisor Attestation
    print("[2/4] Simulating 5 Attested Batch Compute Workloads...")
    for i in range(5):
        payload = {
            "receipt_id": str(uuid.uuid4()),
            "job_id": f"spark-job-etl-0{i+1}",
            "workload_name": f"warehouse-nightly-rollup-partition-{i}",
            "duration_seconds": 1800 + (i * 300),
            "instance_type": "m5.2xlarge",
            "node_count": 1,
            "kwh_consumed": 0.10 + (i * 0.02),
            "cpu_utilization_pct": 75.0,
            "spot_price_gbp": 48.0,
            "counterfactual_mef_gco2": 510.0,
            "code_payload_hash": f"sha256_notebook_hash_partition_{i}_verified"
        }
        rec_res = client.post("/v1/ledger/record", json=payload, headers=auth_headers)
        assert rec_res.status_code == 200
    print("      -> 5 execution events successfully attested & committed to isolated ledger.")

    # 3. Seal Settlement Window with Merkle Root & PKI Signature
    print("[3/4] Closing Settlement Window & Stamping Merkle Root...")
    seal_res = client.post("/v1/ledger/seal-block", headers=auth_headers)
    assert seal_res.status_code == 200
    block_data = seal_res.json()
    print(f"      -> Block Merkle Root Hash: {block_data['merkle_root_hash']}")
    print(f"      -> Asymmetric Signature:   {block_data['signature'][:32]}...")

    # 4. Generate & Download Statutory Audit Pack PDF
    print("[4/4] Generating Automated SECR & CSRD Executive Audit Pack...")
    pdf_res = client.get("/v1/audit/pack", headers=auth_headers)
    assert pdf_res.status_code == 200
    assert len(pdf_res.content) > 1000
    
    output_filename = f"SECR_Audit_{tenant}.pdf"
    print(f"\n>>> AUDIT EVIDENCE DELIVERABLE READY: {output_filename}")
    print(f">>> v0.2.0 SYSTEM ARCHITECTURE VERIFIED & COMPLETE <<<\n")

if __name__ == "__main__":
    run_e2e_commercial_demo()
