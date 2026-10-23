from datetime import datetime, timezone
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field

class GatingRequest(BaseModel):
    job_id: str
    tenant_id: str
    workload_name: str
    sla_deadline_utc: datetime
    estimated_duration_sec: int
    buffer_sec: int = 900
    carbon_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    cost_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    max_acceptable_score: float = 250.0  # Normalized composite threshold

class GatingEvaluator:
    """
    Evaluates runtime batch dispatch against statutory SLAs,
    marginal carbon emissions (MEF), and cloud spot compute prices.
    """
    @staticmethod
    def evaluate(
        request: GatingRequest, 
        telemetry: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Returns (should_dispatch, reason, metrics).
        Ensures enterprise SLA is NEVER breached.
        """
        now = datetime.now(timezone.utc)
        
        # 1. Evaluate Hard Boundary Condition (Drop-dead critical timestamp)
        remaining_sec = (request.sla_deadline_utc - now).total_seconds()
        required_headroom_sec = request.estimated_duration_sec + request.buffer_sec
        
        # Case A: SLA Invariant Breach (Forced Release)
        if remaining_sec <= required_headroom_sec:
            return True, "SLA_EXPIRATION_OVERRIDE", {
                "decision": "FORCE_DISPATCH",
                "is_override": True,
                "reason": "Approaching hard SLA boundary. Compute protected."
            }

        # Case B: Circuit Breaker Trip (Fail-Open Release)
        if telemetry.get("circuit_breaker_tripped", False):
            return True, "CIRCUIT_BREAKER_FAIL_OPEN", {
                "decision": "FORCE_DISPATCH",
                "is_override": True,
                "reason": "Upstream telemetry partition. Pipeline continuity preserved."
            }

        # Case C: Dual-Objective Co-Optimization Score
        # Score = w_carbon * MEF_normalized + w_cost * Spot_normalized
        mef = telemetry["intensity_mef_gco2"]
        spot = telemetry["spot_price_gbp_per_mwh"]
        
        # Normalization factors
        mef_norm = mef * 0.5
        spot_norm = spot * 1.5
        composite_score = (request.carbon_weight * mef_norm) + (request.cost_weight * spot_norm)

        if composite_score <= request.max_acceptable_score:
            return True, "CO_OPTIMIZED_GREEN_DISPATCH", {
                "decision": "APPROVED",
                "is_override": False,
                "composite_score": round(composite_score, 2),
                "mef_gco2": mef,
                "spot_gbp": spot
            }

        # Case D: Grid dirty & cost elevated -> Hold Compute
        return False, "HOLD_AWAITING_RENEWABLE_SURGE", {
            "decision": "HOLD",
            "is_override": False,
            "composite_score": round(composite_score, 2),
            "headroom_sec_remaining": round(remaining_sec - required_headroom_sec, 0)
        }
