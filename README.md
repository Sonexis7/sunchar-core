# greenops-client

Autonomous carbon-aware compute scheduling and Scope 2 audit ledger for enterprise data pipelines.

## Installation

bash
pip install greenops-client


## Quickstart

python
from greenops import GreenOpsClient

client = GreenOpsClient(api_key="gop_live_your_key_here")

@client.gate(
    job_name="nightly-batch-risk",
    cluster_power_kw=50.0,
    runtime_hours=2.0,
    max_wait_seconds=1800,
    force_on_timeout=True
)
def run_pipeline():
    print("Executing workload under optimal grid conditions...")

## Features
- **Active Gating:** Delays non-urgent compute until renewable power floods the grid.
- **SLA Fallback:** `force_on_timeout=True` guarantees execution if windows do not clear within buffer.
- **Scope 2 Ledger:** Writes microsecond-level grid audit records to MotherDuck automatically.
