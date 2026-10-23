import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional

NESO_API_URL = "https://api.carbonintensity.org.uk/intensity"

class DualStreamTelemetryCollector:
    """
    Ingests both statutory Average Emissions Factors (AEF) and 
    consequential Marginal Emissions Factors (MEF), alongside cloud spot pricing.
    """
    def __init__(self, timeout_sec: float = 2.5):
        self.timeout_sec = timeout_sec

    def fetch_live_telemetry(self, postcode: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetches live settlement window telemetry. 
        Implements circuit-breaking fallbacks if NESO endpoints fail.
        """
        now_utc = datetime.now(timezone.utc)
        
        try:
            with httpx.Client(timeout=self.timeout_sec) as client:
                resp = client.get(NESO_API_URL)
                resp.raise_for_status()
                data = resp.json()["data"][0]
                
                intensity = data.get("intensity", {})
                aef = intensity.get("actual") or intensity.get("forecast") or 140.0
                intensity_index = intensity.get("index", "moderate")
                
                # Derive Consequential Marginal Emissions Factor (MEF)
                # In the UK, marginal units are predominantly CCGT/OCGT gas peakers
                # When grid AEF is high (>180), marginal gas peakers run at ~480-550 gCO2/kWh.
                # When grid AEF is low (<80), marginal generation is cleaner (~250-320 gCO2/kWh).
                mef = self._calculate_marginal_emissions(float(aef))
                
                # Cloud Spot Price estimation (£/MWh equivalent discount index)
                # Low grid intensity / high renewables correlates with lower wholesale & spot rates
                spot_price_gbp = self._estimate_spot_price(float(aef))

                return {
                    "status": "ONLINE",
                    "timestamp_utc": now_utc.isoformat(),
                    "settlement_window_utc": data.get("from", now_utc.isoformat()),
                    "intensity_aef_gco2": float(aef),
                    "intensity_mef_gco2": float(mef),
                    "intensity_index": intensity_index,
                    "spot_price_gbp_per_mwh": spot_price_gbp,
                    "circuit_breaker_tripped": False
                }

        except Exception as exc:
            # Resilient circuit-breaker fallback: Fail-open with audit flag
            return {
                "status": "DEGRADED",
                "timestamp_utc": now_utc.isoformat(),
                "settlement_window_utc": now_utc.isoformat(),
                "intensity_aef_gco2": 150.0,
                "intensity_mef_gco2": 450.0,
                "intensity_index": "unknown",
                "spot_price_gbp_per_mwh": 85.0,
                "circuit_breaker_tripped": True,
                "error_details": str(exc)
            }

    @staticmethod
    def _calculate_marginal_emissions(aef: float) -> float:
        """Computes dynamic MEF based on the active UK merit-order margin."""
        if aef < 90.0:
            return round(280.0 + (aef * 0.8), 2)
        elif aef < 180.0:
            return round(380.0 + (aef * 0.5), 2)
        else:
            return round(490.0 + (aef * 0.25), 2)

    @staticmethod
    def _estimate_spot_price(aef: float) -> float:
        """Estimates off-peak wholesale power / spot index (£/MWh)."""
        base_price = 55.0
        return round(base_price + (aef * 0.22), 2)

if __name__ == "__main__":
    collector = DualStreamTelemetryCollector()
    result = collector.fetch_live_telemetry()
    print("Dual-Stream Telemetry Ingested:")
    for k, v in result.items():
        print(f"  {k}: {v}")
