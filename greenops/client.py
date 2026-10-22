import os
import time
import functools
import requests
from typing import Optional, Dict, Any, Callable

class GreenOpsClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        webhook_url: Optional[str] = None,
        request_timeout: int = 60
    ):
        self.base_url = (base_url or os.getenv("GREENOPS_BASE_URL", "https://greenops-engine.onrender.com")).rstrip("/")
        self.api_key = api_key or os.getenv("GREENOPS_API_KEY", "dev_secret_key_12345")
        self.webhook_url = webhook_url or os.getenv("GREENOPS_WEBHOOK_URL")
        self.request_timeout = request_timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def evaluate_workload(
        self,
        job_name: str,
        cluster_power_kw: float,
        runtime_hours: float,
        preferred_region: Optional[str] = None
    ) -> Dict[str, Any]:
        """Request dispatch decision from the GreenOps Engine API."""
        url = f"{self.base_url}/v1/dispatch/evaluate"
        payload = {
            "job_name": job_name,
            "cluster_power_kw": cluster_power_kw,
            "runtime_hours": runtime_hours,
            "preferred_region": preferred_region
        }
        res = requests.post(url, json=payload, headers=self._headers(), timeout=self.request_timeout)
        res.raise_for_status()
        return res.json()

    def send_alert(self, title: str, text: str, color: str = "#36a64f"):
        """Send an optional notification to a Slack/Discord/Teams incoming webhook."""
        if not self.webhook_url:
            return
        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": title,
                    "text": text,
                    "footer": "GreenOps Autonomous Dispatch Engine"
                }
            ]
        }
        try:
            requests.post(self.webhook_url, json=payload, timeout=5)
        except Exception as e:
            print(f"[Webhook Warning] Could not deliver alert: {e}")

    def gate(
        self,
        job_name: str,
        cluster_power_kw: float,
        runtime_hours: float,
        preferred_region: Optional[str] = None,
        max_wait_seconds: int = 300,
        poll_interval_seconds: int = 15,
        force_on_timeout: bool = True
    ):
        """
        Decorator that gates any Python pipeline behind carbon-arbitrage checks.
        Handles server cold starts, polling intervals, and SLA fallbacks seamlessly.
        """
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                print(f"\n[GreenOps Gate] Evaluating grid conditions for: {job_name}...")

                while True:
                    elapsed = time.time() - start_time

                    try:
                        decision = self.evaluate_workload(
                            job_name=job_name,
                            cluster_power_kw=cluster_power_kw,
                            runtime_hours=runtime_hours,
                            preferred_region=preferred_region
                        )
                    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                        print(f"[GreenOps Gate] ⏳ Service warming up / network handshake in progress ({e.__class__.__name__})...")
                        if elapsed >= max_wait_seconds:
                            if force_on_timeout:
                                warn_msg = f"SLA Timeout reached ({max_wait_seconds}s) during cold start. Forcing execution."
                                print(f"[GreenOps Gate] ⚠️ {warn_msg}")
                                self.send_alert("GreenOps: SLA Timeout (Forced Run)", warn_msg, color="#daa038")
                                return func(*args, **kwargs)
                            raise TimeoutError(f"Engine unreachable within SLA limit of {max_wait_seconds}s.")
                        
                        time.sleep(poll_interval_seconds)
                        continue

                    status = decision.get("status", "UNKNOWN")
                    region = decision.get("target_region", "Unknown")
                    carbon = decision.get("current_carbon_gco2", 0.0)
                    savings = decision.get("arbitrage_savings_gbp", 0.0)

                    if status == "APPROVED_OPTIMAL":
                        msg = f"Window APPROVED in {region} ({carbon} gCO2/kWh). Arbitrage savings: £{savings}."
                        print(f"[GreenOps Gate] ✅ {msg}")
                        self.send_alert("GreenOps: Workload Approved", msg, color="#2eb886")
                        return func(*args, **kwargs)

                    # Carbon intensity is high / delay advised
                    if elapsed >= max_wait_seconds:
                        if force_on_timeout:
                            warn_msg = f"SLA Timeout reached ({max_wait_seconds}s). Forcing execution despite high carbon ({carbon} gCO2/kWh)."
                            print(f"[GreenOps Gate] ⚠️ {warn_msg}")
                            self.send_alert("GreenOps: SLA Timeout (Forced Run)", warn_msg, color="#daa038")
                            return func(*args, **kwargs)
                        else:
                            fail_msg = f"Execution aborted: Green window not reached within {max_wait_seconds}s SLA."
                            print(f"[GreenOps Gate] ❌ {fail_msg}")
                            self.send_alert("GreenOps: Workload Aborted", fail_msg, color="#a30200")
                            raise TimeoutError(fail_msg)

                    print(f"[GreenOps Gate] ⏳ High carbon detected ({carbon} gCO2/kWh). Pausing {poll_interval_seconds}s before re-evaluating...")
                    time.sleep(poll_interval_seconds)

            return wrapper
        return decorator

class GreenOpsAirflowSensor:
    def __init__(self, client: GreenOpsClient, job_name: str, cluster_power_kw: float, runtime_hours: float, preferred_region: Optional[str] = None):
        self.client = client
        self.job_name = job_name
        self.cluster_power_kw = cluster_power_kw
        self.runtime_hours = runtime_hours
        self.preferred_region = preferred_region

    def poke(self, context: Optional[Dict[str, Any]] = None) -> bool:
        try:
            decision = self.client.evaluate_workload(
                job_name=self.job_name,
                cluster_power_kw=self.cluster_power_kw,
                runtime_hours=self.runtime_hours,
                preferred_region=self.preferred_region
            )
            return decision.get("status") == "APPROVED_OPTIMAL"
        except Exception:
            return False
