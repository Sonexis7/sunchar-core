# GreenOps Engine: 14-Day Proof of Value (PoV) Charter

## 1. Scope & Objective
GreenOps Engine evaluates grid telemetry and executes carbon/price arbitrage on non-critical batch workloads without impacting operational delivery schedules.

## 2. Customer Integration (5 Minutes)
- Install client: `pip install greenops-client`
- Decorate target workload:
```python
from greenops import GreenOpsClient
client = GreenOpsClient(api_key="gop_live_<TENANT_KEY>")

@client.gate(
    job_name="nightly-batch",
    cluster_power_kw=50.0,
    runtime_hours=2.0,
    max_wait_seconds=1800,
    force_on_timeout=True
)
def run():
    print("Executing workload under optimal grid conditions...")