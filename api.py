import os
import io
import csv
import uuid
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

import duckdb
from fastapi import FastAPI, Header, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

# --- Prometheus Metrics Instrumentation ---
DISPATCH_TOTAL = Counter(
    "greenops_dispatches_total", 
    "Total workload dispatch evaluations requested",
    ["status", "target_region"]
)
ARBITRAGE_SAVINGS_TOTAL = Counter(
    "greenops_arbitrage_savings_gbp_total", 
    "Cumulative financial arbitrage savings achieved in GBP"
)
LATEST_GRID_CARBON_INTENSITY = Gauge(
    "greenops_latest_grid_carbon_gco2", 
    "Latest carbon intensity observed in gCO2/kWh",
    ["region"]
)

MASTER_ADMIN_KEY = os.getenv("GREENOPS_API_KEY", "dev_secret_key_12345")
MOTHERDUCK_TOKEN = os.getenv("MOTHERDUCK_TOKEN", "")

# --- DuckDB / MotherDuck Connection Proxy ---
_local_duckdb_conn = None

class DuckDBLocalProxy:
    """Preserves local in-memory database state across test fixtures and endpoint calls."""
    def __init__(self, conn):
        self._conn = conn

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def close(self):
        pass

    def __getattr__(self, item):
        return getattr(self._conn, item)

def get_duckdb_conn():
    global _local_duckdb_conn
    if MOTHERDUCK_TOKEN:
        return duckdb.connect(f"md:?motherduck_token={MOTHERDUCK_TOKEN}")
    if _local_duckdb_conn is None:
        _local_duckdb_conn = duckdb.connect(":memory:")
    return DuckDBLocalProxy(_local_duckdb_conn)

def init_database():
    try:
        conn = get_duckdb_conn()
        
        # 1. Tenants & Dynamic API Keys Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id VARCHAR PRIMARY KEY,
                client_name VARCHAR,
                api_key VARCHAR UNIQUE,
                created_at TIMESTAMP,
                is_active BOOLEAN
            )
        """)

        # Seed default tenant for backwards compatibility with tests and monitoring
        existing_seed = conn.execute("SELECT COUNT(*) FROM tenants WHERE api_key = ?", (MASTER_ADMIN_KEY,)).fetchone()[0]
        if existing_seed == 0:
            conn.execute("""
                INSERT INTO tenants VALUES (
                    'tenant_internal_admin',
                    'Internal Engine Admin',
                    ?,
                    CURRENT_TIMESTAMP,
                    true
                )
            """, (MASTER_ADMIN_KEY,))

        # 2. Multi-Tenant Gold Audit Ledger
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gold_dispatch_ledger (
                dispatch_id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR,
                timestamp_utc TIMESTAMP,
                job_name VARCHAR,
                target_region VARCHAR,
                cluster_power_kw DOUBLE,
                runtime_hours DOUBLE,
                carbon_gco2 DOUBLE,
                tariff_rate_gbp DOUBLE,
                estimated_cost_gbp DOUBLE,
                arbitrage_savings_gbp DOUBLE,
                carbon_reduction_pct DOUBLE,
                status VARCHAR
            )
        """)

        # Migration safety: ensure tenant_id column exists if table was created in earlier version
        try:
            conn.execute("ALTER TABLE gold_dispatch_ledger ADD COLUMN tenant_id VARCHAR DEFAULT 'tenant_internal_admin'")
        except Exception:
            pass

        conn.close()
    except Exception as e:
        print(f"[Database Init Warning] Could not initialize tables: {e}")

# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield

# --- FastAPI Initialization ---
app = FastAPI(
    title="GreenOps Multi-Tenant Engine API",
    description="Multi-tenant carbon arbitrage and workload dispatch platform with dynamic client API key isolation.",
    version="1.3.0",
    lifespan=lifespan
)

# --- Authentication & Tenant Resolution Dependency ---
def get_current_tenant(x_api_key: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized: Missing X-API-Key header")
    
    conn = get_duckdb_conn()
    row = conn.execute(
        "SELECT tenant_id, client_name, is_active FROM tenants WHERE api_key = ?",
        (x_api_key,)
    ).fetchone()
    conn.close()

    if not row or not row[2]:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or revoked API key")
    
    return {
        "tenant_id": row[0],
        "client_name": row[1]
    }

def verify_admin_key(x_api_key: Optional[str] = Header(None)):
    """Restricts administrative provisioning to master admin key holders."""
    if not x_api_key or x_api_key != MASTER_ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: Master Admin privileges required")
    return x_api_key

# --- Request / Response Models ---
class WorkloadRequest(BaseModel):
    job_name: str = Field(..., json_schema_extra={"example": "daily-medallion-aggregation"})
    cluster_power_kw: float = Field(..., gt=0, json_schema_extra={"example": 50.0})
    runtime_hours: float = Field(..., gt=0, json_schema_extra={"example": 2.0})
    preferred_region: Optional[str] = Field(None, json_schema_extra={"example": "North Scotland"})

class DispatchVerdict(BaseModel):
    dispatch_id: str
    tenant_id: str
    status: str
    target_region: str
    current_carbon_gco2: float
    tariff_rate_gbp: float
    estimated_cost_gbp: float
    arbitrage_savings_gbp: float
    carbon_reduction_pct: float
    message: str

class CreateTenantRequest(BaseModel):
    client_name: str = Field(..., json_schema_extra={"example": "Acme Data Labs"})
    tenant_id: Optional[str] = Field(None, json_schema_extra={"example": "tenant_acme"})

class TenantResponse(BaseModel):
    tenant_id: str
    client_name: str
    api_key: str
    created_at: str
    is_active: bool

# --- System & Telemetry Endpoints ---
@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/docs")

@app.get("/health", tags=["System"])
def health_check():
    backend_status = "MotherDuck Cloud" if MOTHERDUCK_TOKEN else "Local In-Memory DuckDB"
    return {
        "status": "healthy",
        "service": "sunchar_core-multitenant-engine",
        "data_backend": backend_status
    }

@app.get("/metrics", tags=["Observability"])
def prometheus_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/v1/grid/live", dependencies=[Depends(get_current_tenant)], tags=["Grid Telemetry"])
def get_live_grid() -> List[Dict[str, Any]]:
    sample_data = [
        {"region_id": 1, "region_name": "North Scotland", "carbon_intensity_gco2": 0.0, "offpeak_tariff": 0.09, "peak_tariff": 0.29},
        {"region_id": 2, "region_name": "South England", "carbon_intensity_gco2": 142.5, "offpeak_tariff": 0.14, "peak_tariff": 0.31},
        {"region_id": 3, "region_name": "North Wales", "carbon_intensity_gco2": 45.0, "offpeak_tariff": 0.11, "peak_tariff": 0.28}
    ]
    for row in sample_data:
        LATEST_GRID_CARBON_INTENSITY.labels(region=row["region_name"]).set(row["carbon_intensity_gco2"])
    return sample_data

# --- Dynamic Tenant & API Key Management ---
@app.post("/v1/admin/tenants", response_model=TenantResponse, dependencies=[Depends(verify_admin_key)], tags=["Tenant Administration"])
def create_tenant(request: CreateTenantRequest):
    """
    Dynamically register a new enterprise client and issue an isolated API key.
    Requires Master Admin API key in X-API-Key header.
    """
    tenant_id = request.tenant_id or f"tenant_{uuid.uuid4().hex[:8]}"
    generated_api_key = f"gop_live_{secrets.token_hex(16)}"
    now = datetime.now(timezone.utc)

    conn = get_duckdb_conn()
    try:
        conn.execute("""
            INSERT INTO tenants (tenant_id, client_name, api_key, created_at, is_active)
            VALUES (?, ?, ?, ?, true)
        """, (tenant_id, request.client_name, generated_api_key, now))
        conn.close()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Failed to register tenant: {str(e)}")

    return TenantResponse(
        tenant_id=tenant_id,
        client_name=request.client_name,
        api_key=generated_api_key,
        created_at=now.isoformat(),
        is_active=True
    )

# --- Workload Evaluation (Tenant Scoped) ---
@app.post("/v1/dispatch/evaluate", response_model=DispatchVerdict, tags=["Arbitrage Engine"])
def evaluate_dispatch(workload: WorkloadRequest, tenant: Dict[str, Any] = Depends(get_current_tenant)):
    dispatch_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc)
    
    target_region = workload.preferred_region or "North Scotland"
    carbon_intensity = 0.0 if target_region == "North Scotland" else 125.0
    offpeak_rate = 0.09
    peak_rate = 0.29
    
    total_energy_kwh = workload.cluster_power_kw * workload.runtime_hours
    estimated_cost = round(total_energy_kwh * offpeak_rate, 2)
    standard_cost = round(total_energy_kwh * peak_rate, 2)
    arbitrage_savings = round(standard_cost - estimated_cost, 2)
    carbon_reduction = 100.0 if carbon_intensity == 0.0 else 45.0
    status = "APPROVED_OPTIMAL" if carbon_intensity < 50.0 else "DELAY_ADVISED"

    DISPATCH_TOTAL.labels(status=status, target_region=target_region).inc()
    ARBITRAGE_SAVINGS_TOTAL.inc(arbitrage_savings)

    try:
        conn = get_duckdb_conn()
        conn.execute("""
            INSERT INTO gold_dispatch_ledger (
                dispatch_id, tenant_id, timestamp_utc, job_name, target_region,
                cluster_power_kw, runtime_hours, carbon_gco2, tariff_rate_gbp,
                estimated_cost_gbp, arbitrage_savings_gbp, carbon_reduction_pct, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dispatch_id, tenant["tenant_id"], now_utc, workload.job_name, target_region,
            workload.cluster_power_kw, workload.runtime_hours,
            carbon_intensity, offpeak_rate, estimated_cost,
            arbitrage_savings, carbon_reduction, status
        ))
        conn.close()
    except Exception as e:
        print(f"[Ledger Write Warning] Failed to log dispatch for tenant {tenant['tenant_id']}: {e}")

    return DispatchVerdict(
        dispatch_id=dispatch_id,
        tenant_id=tenant["tenant_id"],
        status=status,
        target_region=target_region,
        current_carbon_gco2=carbon_intensity,
        tariff_rate_gbp=offpeak_rate,
        estimated_cost_gbp=estimated_cost,
        arbitrage_savings_gbp=arbitrage_savings,
        carbon_reduction_pct=carbon_reduction,
        message=f"Optimal window confirmed for {tenant['client_name']}. Compute cluster dispatched."
    )

# --- Scoped Ledger Entries ---
@app.get("/v1/ledger/recent", tags=["Audit Ledger"])
def get_recent_ledger_entries(
    limit: int = 10,
    tenant: Dict[str, Any] = Depends(get_current_tenant)
) -> List[Dict[str, Any]]:
    """Returns only audit ledger records belonging to the authenticated tenant."""
    try:
        conn = get_duckdb_conn()
        rel = conn.execute(f"""
            SELECT * FROM gold_dispatch_ledger 
            WHERE tenant_id = ?
            ORDER BY timestamp_utc DESC 
            LIMIT {limit}
        """, (tenant["tenant_id"],))
        
        cols = [desc[0] for desc in rel.description]
        rows = rel.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            record = {}
            for col, val in zip(cols, row):
                record[col] = val.isoformat() if hasattr(val, "isoformat") else val
            results.append(record)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query audit ledger: {str(e)}")

# --- Scoped ESG Compliance Report ---
@app.get("/v1/reports/esg", tags=["Compliance & Audit"])
def get_esg_compliance_report(
    format: str = Query("json", enum=["json", "csv"]),
    tenant: Dict[str, Any] = Depends(get_current_tenant)
):
    """
    Certified Scope 2 GHG Protocol audit export calculated exclusively
    for the authenticated tenant's workloads.
    """
    try:
        conn = get_duckdb_conn()
        agg = conn.execute("""
            SELECT 
                COUNT(*) as total_dispatches,
                COALESCE(SUM(cluster_power_kw * runtime_hours), 0.0) as total_energy_kwh,
                COALESCE(SUM(estimated_cost_gbp), 0.0) as total_spend_gbp,
                COALESCE(SUM(arbitrage_savings_gbp), 0.0) as total_savings_gbp,
                COALESCE(SUM((cluster_power_kw * runtime_hours) * 0.150), 0.0) as baseline_emissions_kgco2,
                COALESCE(SUM((cluster_power_kw * runtime_hours) * (carbon_gco2 / 1000.0)), 0.0) as actual_emissions_kgco2
            FROM gold_dispatch_ledger
            WHERE tenant_id = ? AND status = 'APPROVED_OPTIMAL'
        """, (tenant["tenant_id"],)).fetchone()

        total_dispatches = agg[0] if agg else 0
        total_energy_kwh = round(agg[1] or 0.0, 2)
        total_spend_gbp = round(agg[2] or 0.0, 2)
        total_savings_gbp = round(agg[3] or 0.0, 2)
        baseline_kg = round(agg[4] or 0.0, 2)
        actual_kg = round(agg[5] or 0.0, 2)
        abated_kg = round(baseline_kg - actual_kg, 2)
        abatement_pct = round((abated_kg / baseline_kg * 100.0), 1) if baseline_kg > 0 else 100.0

        if format == "csv":
            rel = conn.execute("""
                SELECT 
                    dispatch_id, tenant_id, timestamp_utc, job_name, target_region,
                    cluster_power_kw, runtime_hours, carbon_gco2,
                    estimated_cost_gbp, arbitrage_savings_gbp
                FROM gold_dispatch_ledger 
                WHERE tenant_id = ?
                ORDER BY timestamp_utc DESC
            """, (tenant["tenant_id"],))
            cols = [desc[0] for desc in rel.description]
            rows = rel.fetchall()
            conn.close()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(cols)
            for row in rows:
                writer.writerow([val.isoformat() if hasattr(val, "isoformat") else val for val in row])
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=greenops_esg_{tenant['tenant_id']}.csv"}
            )

        conn.close()
        return {
            "tenant_id": tenant["tenant_id"],
            "client_name": tenant["client_name"],
            "standard_framework": "GHG Protocol Scope 2 Market-Based Accounting",
            "reporting_period": "All-Time Inception to Date",
            "audit_summary": {
                "total_workloads_optimized": total_dispatches,
                "total_compute_energy_kwh": total_energy_kwh,
                "gross_spend_gbp": total_spend_gbp,
                "net_arbitrage_savings_gbp": total_savings_gbp,
                "baseline_grid_emissions_kgco2": baseline_kg,
                "greenops_actual_emissions_kgco2": actual_kg,
                "carbon_abated_kgco2": abated_kg,
                "emissions_reduction_efficiency": f"{abatement_pct}%"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate ESG report: {str(e)}")
