"""
Backward-compatibility shim.
Directs imports from root client.py to the packaged greenops library.
"""
from greenops import GreenOpsClient, GreenOpsAirflowSensor

__all__ = ["GreenOpsClient", "GreenOpsAirflowSensor"]
