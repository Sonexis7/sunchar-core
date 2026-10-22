# GreenOps Engine 🌍⚡

[![GreenOps CI Pipeline](https://github.com/Sonexis7/greenops-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Sonexis7/greenops-engine/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![DuckDB](https://img.shields.io/badge/DuckDB-v1.5.6-FFF000.svg?logo=duckdb&logoColor=black)](https://duckdb.org)
[![MotherDuck](https://img.shields.io/badge/MotherDuck-Cloud%20Lakehouse-blue.svg)](https://motherduck.com)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com)
[![Render](https://img.shields.io/badge/Render-Deployed%20Live-46E3B7.svg?logo=render&logoColor=black)](https://greenops-engine.onrender.com/health)

A cloud-native carbon arbitrage and workload dispatch engine. GreenOps Engine queries live regional grid telemetry from UK NESO via MotherDuck/DuckDB, evaluates carbon intensity against electricity tariff spreads, and issues automated scheduling recommendations to run heavy compute workloads during zero-carbon or low-cost windows.

---

## 🏗️ System Architecture

```text
               +-------------------------------------------+
               |  UK National Energy System Operator (NESO)|
               +-------------------------------------------+
                                     │ (Live Telemetry)
                                     ▼
                     +───────────────────────────────+
                     |    MotherDuck Cloud Lakehouse |
                     |   (Regional Carbon & Tariffs) |
                     +───────────────────────────────+
                                     │
                                     ▼ (DuckDB v1.5.6)
+─────────────────────────────────────────────────────────────────────────+
| Render Cloud Service (https://greenops-engine.onrender.com)             |
|                                                                         |
|  [Security Gate] ──► X-API-Key Authentication                           |
|  [Pydantic V2]   ──► Strict Contract Validation                         |
|  [FastAPI Engine]──► /v1/grid/live  &  /v1/dispatch/evaluate            |
+─────────────────────────────────────────────────────────────────────────+
                                     ▲
                                     │ (HTTPS / TLS)
+────────────────────────────────────┴────────────────────────────────────+
| Client Workload Layer (Python SDK / run_workload.py)                     |
|                                                                         |
|  - Queries regional telemetry                                           |
|  - Dispatches batch clusters during optimal carbon-negative windows     |
+─────────────────────────────────────────────────────────────────────────+
```

---

## 🚀 Live Endpoints

Base URL: `https://greenops-engine.onrender.com`

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | No | Service liveness probe and MotherDuck backend status |
| `GET` | `/v1/grid/live` | `X-API-Key` | Live regional grid carbon intensity and tariffs |
| `POST` | `/v1/dispatch/evaluate` | `X-API-Key` | Carbon arbitrage evaluation for planned compute workloads |

### Sample Dispatch Evaluation Payload

```json
{
  "job_name": "daily-medallion-aggregation",
  "cluster_power_kw": 50.0,
  "runtime_hours": 2.0,
  "preferred_region": "North Scotland"
}
```

### Sample Engine Response

```json
{
  "status": "APPROVED_OPTIMAL",
  "target_region": "North Scotland",
  "current_carbon_gco2": 0.0,
  "tariff_rate_gbp": 0.09,
  "estimated_cost_gbp": 18.0,
  "arbitrage_savings_gbp": 40.0,
  "carbon_reduction_pct": 100.0,
  "message": "Optimal green window confirmed. Dispatching compute clusters now."
}
```

---

## 🛠️ Local Setup & Quickstart

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/Sonexis7/greenops-engine.git
cd greenops-engine
python -m venv venv
```

Activate the virtual environment:
* **Windows (PowerShell):** `.\venv\Scripts\Activate.ps1`
* **macOS / Linux:** `source venv/bin/activate`

Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```ini
MOTHERDUCK_TOKEN=your_motherduck_token_here
GREENOPS_API_KEY=dev_secret_key_12345
```

### 3. Run Automated Unit & Contract Tests

Run the full pytest suite locally:

```bash
python -m pytest -v
```

### 4. Execute Batch Workload via Client SDK

Trigger the client arbitrage evaluation against the live Render production service:

```bash
python run_workload.py
```

---

## 🔄 CI/CD Automation Pipeline

Continuous Integration and Continuous Deployment are managed automatically via GitHub Actions (`.github/workflows/ci.yml`):

1. **Automated Testing (`test` job):**
   * Spins up an isolated `ubuntu-latest` runner.
   * Configures Python 3.11 and installs pinned requirements.
   * Reads encrypted GitHub Secrets (`MOTHERDUCK_TOKEN`, `GREENOPS_API_KEY`).
   * Runs the complete `pytest` validation suite against live MotherDuck connections.
2. **Container Build Verification (`docker-build` job):**
   * Sequenced to run only if `test` succeeds (`needs: test`).
   * Builds the Docker image from scratch using `python:3.11-slim` to ensure deployment readiness.
3. **Public Deployment:**
   * Automated web service builds on Render hosting `https://greenops-engine.onrender.com`.

---

## 📦 Project Structure

```text
greenops-engine/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI/CD pipeline
├── tests/
│   └── test_api.py             # Contract and integration test suite
├── api.py                      # FastAPI core engine and routing logic
├── client.py                   # Reusable Python Client SDK
├── Dockerfile                  # Container build instructions
├── pytest.ini                  # Pytest environment discovery configuration
├── README.md                   # System architecture and documentation
├── requirements.txt            # Pinned production and test dependencies
└── run_workload.py             # Production compute job dispatch script
```