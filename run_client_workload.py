import os
from client import GreenOpsClient

# Initialize GreenOps Client with the Apex Financial Cloud API key
client = GreenOpsClient(
    base_url="https://greenops-engine.onrender.com",
    api_key="gop_live_8354a340fc001439726f2a9c8a62ac58"
)

@client.gate(
    job_name="apex-portfolio-var-simulation",
    cluster_power_kw=75.0,
    runtime_hours=2.0,
    preferred_region="North Scotland",
    max_wait_seconds=60,
    poll_interval_seconds=10,
    force_on_timeout=True
)
def run_risk_pipeline():
    print("📈 [Apex FinOps] Processing 250,000 portfolio simulations...")
    print("🔒 [Apex FinOps] Execution finished. Risk metrics written to cluster.")

if __name__ == "__main__":
    print("=== Launching Workload: Apex Financial Cloud ===")
    run_risk_pipeline()
