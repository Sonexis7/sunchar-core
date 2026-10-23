import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from sunchar_core.telemetry.collector import DualStreamTelemetryCollector
from sunchar_core.engine.gating import GatingEvaluator, GatingRequest
from sunchar_core.engine.attestation import HypervisorAttestor, ComputeTelemetryAttestationRequest
from sunchar_core.ledger.tenant_db import get_tenant_db, archive_worm_block
from sunchar_core.ledger.merkle import SettlementMerkleTree, sha256_hash
from sunchar_core.security.kms_signer import CloudKMSSigner
from sunchar_core.security.auth import get_current_tenant
from sunchar_core.audit.generator import AuditPackGenerator

app = FastAPI(
    title="Sunchar Core",
    version="0.2.0-kms-attested",
    description="Enterprise Compliance Evidence Infrastructure with KMS Signatures and Hypervisor Attestation"
)

telemetry_collector = DualStreamTelemetryCollector()
kms_signer = CloudKMSSigner()
audit_generator = AuditPackGenerator()

class SecureGatingRequest(BaseModel):
    job_id: str
    workload_name: str
    sla_deadline_utc: datetime
    estimated_duration_sec: int = Field(..., gt=0, lt=86400)
    buffer_sec: int = Field(default=900, ge=0)
    carbon_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    cost_weight: float = Field(default=0.4, ge=0.0, le=1.0)

class AttestedJobPayload(BaseModel):
    receipt_id: str
    job_id: str
    workload_name: str
    duration_seconds: int = Field(..., gt=0, lt=86400)
    kwh_consumed: float = Field(..., gt=0.0)
    instance_type: str = Field(default="m5.2xlarge")
    node_count: int = Field(default=1, ge=1)
    cpu_utilization_pct: float = Field(default=75.0, ge=0.0, le=100.0)
    spot_price_gbp: float = Field(default=65.0, ge=0.0)
    counterfactual_mef_gco2: float = Field(default=480.0, ge=50.0, le=900.0)
    code_payload_hash: str = Field(..., min_length=16)

@app.get("/health")
def health_check():
    return {
        "status": "HEALTHY",
        "version": "0.2.0",
        "kms_signer": "ACTIVE",
        "attestation_engine": "ACTIVE"
    }

@app.get("/v1/security/public-key", response_class=PlainTextResponse)
def get_auditor_public_key():
    """Returns the public key PEM for auditor signature verification."""
    return kms_signer.get_public_key_pem()

@app.post("/v1/gate/await")
def await_gate(
    request: SecureGatingRequest,
    tenant_id: str = Depends(get_current_tenant)
):
    telemetry = telemetry_collector.fetch_live_telemetry()
    internal_req = GatingRequest(
        job_id=request.job_id,
        tenant_id=tenant_id,
        workload_name=request.workload_name,
        sla_deadline_utc=request.sla_deadline_utc,
        estimated_duration_sec=request.estimated_duration_sec,
        buffer_sec=request.buffer_sec,
        carbon_weight=request.carbon_weight,
        cost_weight=request.cost_weight
    )
    should_dispatch, reason, metrics = GatingEvaluator.evaluate(internal_req, telemetry)
    receipt_id = str(uuid.uuid4())
    
    auth_envelope = f"{receipt_id}:{tenant_id}:{reason}:{telemetry['intensity_aef_gco2']}"
    digital_signature, sign_mode = kms_signer.sign_payload(auth_envelope)

    return {
        "status": "APPROVED" if should_dispatch else "HOLD",
        "decision_reason": reason,
        "receipt_id": receipt_id,
        "telemetry_snapshot": telemetry,
        "evaluation_metrics": metrics,
        "signature": digital_signature,
        "signing_tier": sign_mode
    }

@app.post("/v1/ledger/record")
def record_execution(
    payload: AttestedJobPayload,
    tenant_id: str = Depends(get_current_tenant)
):
    """
    Cross-validates energy claims via Hypervisor Attestation before recording to ledger.
    """
    # 1. Execute Hypervisor Energy Envelope Attestation (Cookie Jar Detective)
    attest_req = ComputeTelemetryAttestationRequest(
        instance_type=payload.instance_type,
        node_count=payload.node_count,
        duration_seconds=payload.duration_seconds,
        reported_kwh=payload.kwh_consumed,
        average_cpu_utilization_pct=payload.cpu_utilization_pct
    )
    is_valid, attest_status, attest_meta = HypervisorAttestor.attest_workload_energy(attest_req)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "HYPERVISOR_ATTESTATION_FAILED",
                "attestation_status": attest_status,
                "evidence": attest_meta
            }
        )

    # 2. Dual Accounting Calculation
    telemetry = telemetry_collector.fetch_live_telemetry()
    aef = telemetry["intensity_aef_gco2"]
    mef = telemetry["intensity_mef_gco2"]
    
    statutory_emissions = round(payload.kwh_consumed * aef, 2)
    avoided_emissions = max(0.0, round((payload.counterfactual_mef_gco2 - mef) * payload.kwh_consumed, 2))
    cost_savings = round(max(0.0, (85.0 - payload.spot_price_gbp) * (payload.kwh_consumed / 1000.0)), 3)
    
    record_hash = sha256_hash(f"{payload.receipt_id}:{statutory_emissions}:{avoided_emissions}:{attest_status}")
    sig_b64, sign_mode = kms_signer.sign_payload(record_hash)

    with get_tenant_db(tenant_id) as conn:
        conn.execute("""
            INSERT INTO raw_execution_events (
                receipt_id, job_id, workload_name, settlement_window_utc,
                dispatched_at_utc, completed_at_utc, duration_seconds, kwh_consumed,
                intensity_aef_gco2, statutory_emissions_gco2,
                intensity_mef_gco2, avoided_emissions_mef_gco2,
                spot_price_gbp_per_mwh, cost_savings_gbp,
                is_override, override_reason, code_payload_hash, 
                record_hash, engine_signature
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload.receipt_id, payload.job_id, payload.workload_name,
            datetime.now(timezone.utc), datetime.now(timezone.utc), datetime.now(timezone.utc),
            payload.duration_seconds, payload.kwh_consumed,
            aef, statutory_emissions, mef, avoided_emissions,
            payload.spot_price_gbp, cost_savings,
            False, None, payload.code_payload_hash,
            record_hash, sig_b64
        ))

    return {
        "status": "COMMITTED_AND_ATTESTED",
        "receipt_id": payload.receipt_id,
        "tenant_id": tenant_id,
        "attestation_status": attest_status,
        "statutory_emissions_gco2": statutory_emissions,
        "avoided_emissions_gco2": avoided_emissions,
        "record_hash": record_hash,
        "digital_signature": sig_b64,
        "signing_tier": sign_mode
    }

@app.post("/v1/ledger/seal-block")
def seal_settlement_block(tenant_id: str = Depends(get_current_tenant)):
    with get_tenant_db(tenant_id) as conn:
        rows = conn.execute("""
            SELECT receipt_id, dispatched_at_utc, intensity_aef_gco2, 
                   intensity_mef_gco2, code_payload_hash, is_override
            FROM raw_execution_events
        """).fetchall()

        if not rows:
            raise HTTPException(status_code=400, detail="No unsealed events for this tenant.")

        records = [
            {
                "receipt_id": r[0], "tenant_id": tenant_id, "dispatched_at_utc": str(r[1]),
                "intensity_aef_gco2": r[2], "intensity_mef_gco2": r[3],
                "code_payload_hash": r[4], "is_override": r[5]
            }
            for r in rows
        ]

        tree = SettlementMerkleTree(records)
        root_sig, sign_mode = kms_signer.sign_payload(tree.root)
        block_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        conn.execute("""
            INSERT INTO settlement_merkle_blocks (
                block_id, settlement_window_utc, job_count, total_kwh,
                statutory_total_gco2, avoided_total_gco2, merkle_root_hash,
                engine_root_signature, stamped_at_utc, audit_pack_sealed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            block_id, now, len(records), 100.0, 12000.0, 3000.0,
            tree.root, root_sig, now, True
        ))

    archive_worm_block(tenant_id, {
        "block_id": block_id,
        "tenant_id": tenant_id,
        "stamped_at_utc": now.isoformat(),
        "job_count": len(records),
        "merkle_root_hash": tree.root,
        "signature": root_sig,
        "signing_tier": sign_mode
    })

    return {
        "status": "SEALED",
        "block_id": block_id,
        "merkle_root_hash": tree.root,
        "signature": root_sig,
        "signing_tier": sign_mode
    }

@app.get("/v1/audit/pack")
def download_audit_pack(tenant_id: str = Depends(get_current_tenant)):
    pdf_filename = f"SECR_Audit_{tenant_id}.pdf"
    pdf_path = audit_generator.generate_pdf_report(tenant_id, pdf_filename)
    return FileResponse(path=pdf_path, filename=pdf_filename, media_type="application/pdf")
