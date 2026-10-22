from client import GreenOpsClient

# Initialize GreenOps Client
client = GreenOpsClient()

# Example production pipeline protected by the GreenOps Gate
@client.gate(
    job_name="daily-medallion-aggregation",
    cluster_power_kw=50.0,
    runtime_hours=2.0,
    preferred_region="North Scotland",
    max_wait_seconds=60,       # Max SLA wait before forced execution
    poll_interval_seconds=10,  # Retry evaluation interval
    force_on_timeout=True
)
def run_lakehouse_aggregation():
    print("🚀 [Pipeline Execution] Running DuckDB & Spark transformations...")
    print("📊 [Pipeline Execution] Gold analytics tables materialized successfully.")

if __name__ == "__main__":
    print("=== Initializing Client Pipeline with GreenOps Gate ===")
    run_lakehouse_aggregation()
