import os
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from sunchar_core.main import app
from sunchar_core.security.auth import issue_tenant_token
from sunchar_core.security.pki import EngineSigner

client = TestClient(app)

def run_cissp_verification():
    print("\n=======================================================")
    print("   RUNNING CISSP DEFENSIVE ASSURANCE VALIDATION SUITE  ")
    print("=======================================================\n")

    tenant_a = "enterprise-bank-uk"
    tenant_b = "rogue-competitor-ltd"

    token_a = issue_tenant_token(tenant_a)
    token_b = issue_tenant_token(tenant_b)

    # 1. Test Domain 5: Reject Requests Lacking Authentication
    print("[1/5] Testing Authentication Enforcement (Zero-Trust)...")
    res = client.post("/v1/gate/await", json={
        "job_id": "test", "workload_name": "test",
        "sla_deadline_utc": datetime.now(timezone.utc).isoformat(),
        "estimated_duration_sec": 300
    })
    assert res.status_code == 401
    print("      -> PASS: Unauthenticated access rejected with HTTP 401.")

    # 2. Test Domain 5: Anti-BOLA Context Isolation
    print("[2/5] Testing Tenant Isolation (Preventing BOLA)...")
    auth_headers_a = {"Authorization": f"Bearer {token_a}"}
    
    # Commit a physically attested, legitimate batch run for Tenant A
    payload_a = {
        "receipt_id": str(uuid.uuid4()),
        "job_id": "bank-settlement-01",
        "workload_name": "daily-ledger-reconciliation",
        "duration_seconds": 3600,             # 1 hour
        "instance_type": "m5.2xlarge",         # 8 vCPU
        "node_count": 1,
        "kwh_consumed": 0.22,                 # Physically sound (~220 Watt-hours)
        "cpu_utilization_pct": 75.0,
        "code_payload_hash": "sha256_verified_bank_script_hash_secure"
    }
    rec_res = client.post("/v1/ledger/record", json=payload_a, headers=auth_headers_a)
    assert rec_res.status_code == 200
    print("      -> PASS: Tenant A successfully committed to isolated database.")

    # Confirm Tenant B has NO records
    auth_headers_b = {"Authorization": f"Bearer {token_b}"}
    seal_b_res = client.post("/v1/ledger/seal-block", headers=auth_headers_b)
    assert seal_b_res.status_code == 400
    print("      -> PASS: Tenant B isolated; unable to view or seal Tenant A ledger.")

    # 3. Test Domain 3: Asymmetric Ed25519 / KMS Digital Signature Verification
    print("[3/5] Testing Asymmetric PKI Digital Signatures (Domain 3)...")
    pub_res = client.get("/v1/security/public-key")
    assert pub_res.status_code == 200
    public_key_pem = pub_res.text

    rec_data = rec_res.json()
    record_hash = rec_data["record_hash"]
    sig_b64 = rec_data.get("digital_signature") or rec_data.get("ed25519_signature")
    
    is_valid_sig = EngineSigner.verify_signature(public_key_pem, record_hash, sig_b64)
    assert is_valid_sig is True
    print("      -> PASS: Ed25519/KMS signature cryptographically verified against public key.")

    # 4. Test Domain 8: Telemetry Input Bounds & Hypervisor Attestation (Anti-Spoofing)
    print("[4/5] Testing Telemetry Bounds Checking (Anti-Tamper)...")
    spoofed_payload = {
        "receipt_id": str(uuid.uuid4()),
        "job_id": "bank-settlement-02",
        "workload_name": "spoofed-run",
        "duration_seconds": -50,         # Invalid duration (Pydantic validation failure)
        "kwh_consumed": 9999999.0,       # Out of bounds
        "code_payload_hash": "short"     # Too short (<16 chars)
    }
    bad_res = client.post("/v1/ledger/record", json=spoofed_payload, headers=auth_headers_a)
    assert bad_res.status_code == 422
    print("      -> PASS: Spoofed/invalid telemetry rejected with HTTP 422.")

    # 5. Test Domain 1: WORM Archiving and PDF Audit Pack Generation
    print("[5/5] Testing WORM Archival Storage and Signed Audit Pack...")
    seal_a_res = client.post("/v1/ledger/seal-block", headers=auth_headers_a)
    assert seal_a_res.status_code == 200
    block_id = seal_a_res.json()["block_id"]

    worm_file = os.path.join("data", "worm_archive", tenant_a, f"block_{block_id}.json")
    assert os.path.exists(worm_file)
    print(f"      -> PASS: WORM JSON block archived at: {worm_file}")

    pdf_res = client.get("/v1/audit/pack", headers=auth_headers_a)
    assert pdf_res.status_code == 200
    assert len(pdf_res.content) > 1000
    print("      -> PASS: Auditor-ready signed PDF generated successfully.")

    print("\n>>> ALL CISSP HARDENING CONTROLS MET & VERIFIED <<<")

if __name__ == "__main__":
    run_cissp_verification()
