"""
Backward-compatibility shim.
Directs imports from root client.py to the packaged sunchar_core library.
"""
from sunchar_core import GreenOpsClient, GreenOpsAirflowSensor

__all__ = ["GreenOpsClient", "GreenOpsAirflowSensor"]
