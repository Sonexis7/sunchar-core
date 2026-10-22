import pytest
from fastapi.testclient import TestClient
from api import app, init_database

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    init_database()

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_unauthorized_request():
    response = client.get("/v1/grid/live")
    assert response.status_code == 401

def test_create_tenant_dynamic_api_key():
    payload = {"client_name": "Acme Corp Analytics", "tenant_id": "tenant_acme_corp"}
    response = client.post(
        "/v1/admin/tenants",
        json=payload,
        headers={"X-API-Key": "dev_secret_key_12345"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "tenant_acme_corp"
    assert data["client_name"] == "Acme Corp Analytics"
    assert data["api_key"].startswith("gop_live_")
    assert data["is_active"] is True

def test_tenant_data_isolation():
    # 1. Register Client Alpha
    res_a = client.post(
        "/v1/admin/tenants",
        json={"client_name": "Alpha Labs", "tenant_id": "tenant_alpha"},
        headers={"X-API-Key": "dev_secret_key_12345"}
    )
    key_a = res_a.json()["api_key"]

    # 2. Register Client Beta
    res_b = client.post(
        "/v1/admin/tenants",
        json={"client_name": "Beta Corp", "tenant_id": "tenant_beta"},
        headers={"X-API-Key": "dev_secret_key_12345"}
    )
    key_b = res_b.json()["api_key"]

    # 3. Client Alpha executes a 50kW workload
    client.post(
        "/v1/dispatch/evaluate",
        json={"job_name": "alpha-heavy-etl", "cluster_power_kw": 50.0, "runtime_hours": 2.0},
        headers={"X-API-Key": key_a}
    )

    # 4. Verify Client Alpha sees their record in the ledger
    ledger_a = client.get("/v1/ledger/recent", headers={"X-API-Key": key_a}).json()
    assert len(ledger_a) == 1
    assert ledger_a[0]["job_name"] == "alpha-heavy-etl"
    assert ledger_a[0]["tenant_id"] == "tenant_alpha"

    # 5. Verify Client Beta sees ZERO records in their ledger (Strict Isolation)
    ledger_b = client.get("/v1/ledger/recent", headers={"X-API-Key": key_b}).json()
    assert len(ledger_b) == 0

    # 6. Verify ESG report aggregates are completely isolated
    esg_a = client.get("/v1/reports/esg?format=json", headers={"X-API-Key": key_a}).json()
    assert esg_a["tenant_id"] == "tenant_alpha"
    assert esg_a["audit_summary"]["total_workloads_optimized"] == 1

    esg_b = client.get("/v1/reports/esg?format=json", headers={"X-API-Key": key_b}).json()
    assert esg_b["tenant_id"] == "tenant_beta"
    assert esg_b["audit_summary"]["total_workloads_optimized"] == 0
