import uuid
from fastapi.testclient import TestClient
from sunchar_core.main import app
from sunchar_core.security.auth import issue_tenant_token
from sunchar_core.security.kms_signer import CloudKMSSigner
from sunchar_core.security.pki import EngineSigner

client = TestClient(app)

def test_kms_and_attestation():
    print("\n=======================================================")
    print("   TESTING KMS SIGNING & HYPERVISOR ATTESTATION        ")
    print("=======================================================\n")

    tenant = "verified-bank-plc"
    token = issue_tenant_token(tenant)
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Test KMS Signer Verification
    print("[1/3] Testing Cloud KMS / Hardware Signing Service...")
    kms = CloudKMSSigner()
    sig, mode = kms.sign_payload("statutory-audit-record-2026")
    pub_key_pem = kms.get_public_key_pem()
    assert EngineSigner.verify_signature(pub_key_pem, "statutory-audit-record-2026", sig) is True
    print(f"      -> PASS: KMS Signature successfully verified (Tier: {mode})")

    # 2. Test Hypervisor Attestation Rejecting Dishonest Client
    print("[2/3] Testing Hypervisor Attestation (Catching Energy Fraud)...")
    cheating_payload = {
        "receipt_id": str(uuid.uuid4()),
        "job_id": "fraudulent-spark-job",
        "workload_name": "falsified-low-energy-batch",
        "duration_seconds": 3600,             # 1 full hour
        "instance_type": "m5.2xlarge",         # 8 vCPU, 32GB RAM (Idle power ~55 Watts)
        "kwh_consumed": 0.005,                # Claiming only 5 Watt-hours (Physically impossible!)
        "cpu_utilization_pct": 80.0,
        "code_payload_hash": "sha256_notebook_hash_12345"
    }
    cheat_res = client.post("/v1/ledger/record", json=cheating_payload, headers=auth_headers)
    assert cheat_res.status_code == 422
    err_detail = cheat_res.json()["detail"]
    assert err_detail["attestation_status"] == "ATTESTATION_REJECTED_IMPOSSIBLY_LOW_ENERGY"
    print("      -> PASS: Dishonest telemetry detected and rejected by hypervisor envelope.")

    # 3. Test Hypervisor Attestation Accepting Honest Client
    print("[3/3] Testing Hypervisor Attestation (Approving Legitimate Workload)...")
    honest_payload = {
        "receipt_id": str(uuid.uuid4()),
        "job_id": "legitimate-spark-job",
        "workload_name": "risk-reconciliation-run",
        "duration_seconds": 3600,             # 1 hour
        "instance_type": "m5.2xlarge",         # 8 vCPU
        "kwh_consumed": 0.24,                 # ~240 Watt-hours (Right in the expected thermal band)
        "cpu_utilization_pct": 80.0,
        "code_payload_hash": "sha256_notebook_hash_12345"
    }
    honest_res = client.post("/v1/ledger/record", json=honest_payload, headers=auth_headers)
    assert honest_res.status_code == 200
    res_data = honest_res.json()
    assert res_data["attestation_status"] == "ATTESTATION_VERIFIED_PHYSICALLY_BOUNDED"
    print(f"      -> PASS: Honest workload attested, verified, and sealed.")
    print(f"      -> Digital Signature Stamped: {res_data['digital_signature'][:24]}...")

    print("\n>>> ALL KMS AND HYPERVISOR ATTESTATION CHECKS PASSED <<<")

if __name__ == "__main__":
    test_kms_and_attestation()
