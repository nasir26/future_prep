"""
qpu — capstone quantum control stack (M07)
Author: Nasir Ali, C-DAC Noida

Layers (bottom → top):
  backend.py    — QPUBackend: shot-based API wrapping M06 physics
  compiler.py   — QASM3 subset → pulse instruction list
  scheduler.py  — asyncio experiment scheduler
  calibration.py — automated calibration routines (freq scan, Rabi, Ramsey)
  node.py       — QPUNode for two-node distributed entanglement
"""

from .backend     import QPUBackend
from .compiler    import (compile_qasm3, CarrierPulse, VirtualZ,
                           EntangleGate, MeasureOp)
from .scheduler   import Experiment, ExperimentScheduler
from .calibration import ParamStore, freq_scan, rabi_pi_time, ramsey_track, recal_daemon
from .node        import QPUNode

__all__ = [
    "QPUBackend",
    "compile_qasm3", "CarrierPulse", "VirtualZ", "EntangleGate", "MeasureOp",
    "Experiment", "ExperimentScheduler",
    "ParamStore", "freq_scan", "rabi_pi_time", "ramsey_track", "recal_daemon",
    "QPUNode",
]
