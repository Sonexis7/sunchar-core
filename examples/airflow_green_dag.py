"""
Example Apache Airflow DAG demonstrating GreenOps integration.
Place this file into your Airflow dags/ folder.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from client import GreenOpsClient, GreenOpsAirflowSensor

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

client = GreenOpsClient()

def heavy_spark_job():
    print("Executing heavy compute workload under zero-carbon window...")

with DAG(
    "greenops_carbon_aware_pipeline",
    default_args=default_args,
    schedule_interval="0 3,15 * * *",
    catchup=False,
    tags=["greenops", "esg", "finops"]
) as dag:

    # 1. Airflow Sensor: Wait for clean grid window
    wait_for_green_window = PythonOperator(
        task_id="wait_for_green_window",
        python_callable=GreenOpsAirflowSensor(
            client=client,
            job_name="airflow-nightly-job",
            cluster_power_kw=75.0,
            runtime_hours=1.5,
            preferred_region="North Scotland"
        ).poke
    )

    # 2. Main Workload Task
    execute_workload = PythonOperator(
        task_id="execute_heavy_spark_job",
        python_callable=heavy_spark_job
    )

    wait_for_green_window >> execute_workload
