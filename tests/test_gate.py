import pytest
from client import GreenOpsClient, GreenOpsAirflowSensor

class MockClient(GreenOpsClient):
    def __init__(self, responses):
        super().__init__()
        self.responses = responses
        self.call_count = 0

    def evaluate_workload(self, *args, **kwargs):
        resp = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return resp

def test_gate_executes_when_approved():
    mock_client = MockClient([
        {"status": "APPROVED_OPTIMAL", "target_region": "North Scotland", "current_carbon_gco2": 0.0, "arbitrage_savings_gbp": 20.0}
    ])

    executed = False

    @mock_client.gate(job_name="test-job", cluster_power_kw=10.0, runtime_hours=1.0)
    def dummy_task():
        nonlocal executed
        executed = True

    dummy_task()
    assert executed is True
    assert mock_client.call_count == 1

def test_gate_forces_execution_on_sla_timeout():
    mock_client = MockClient([
        {"status": "DELAY_ADVISED", "target_region": "South England", "current_carbon_gco2": 150.0, "arbitrage_savings_gbp": 0.0}
    ])

    executed = False

    @mock_client.gate(
        job_name="test-job",
        cluster_power_kw=10.0,
        runtime_hours=1.0,
        max_wait_seconds=1,
        poll_interval_seconds=1,
        force_on_timeout=True
    )
    def dummy_task():
        nonlocal executed
        executed = True

    dummy_task()
    assert executed is True

def test_airflow_sensor_poke():
    mock_client = MockClient([
        {"status": "DELAY_ADVISED"},
        {"status": "APPROVED_OPTIMAL"}
    ])

    sensor = GreenOpsAirflowSensor(
        client=mock_client,
        job_name="test-airflow",
        cluster_power_kw=20.0,
        runtime_hours=1.0
    )

    assert sensor.poke() is False
    assert sensor.poke() is True
