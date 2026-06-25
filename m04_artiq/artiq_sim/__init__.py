"""
artiq_sim — Minimal ARTIQ API simulation layer
================================================
Implements enough of the ARTIQ Python API to run experiment kernels in pure
software.  Kernel code written against this layer is 1:1 portable to a real
ARTIQ system with a real device_db.py — only the import and device references
change.

Exported names mirror the real artiq.experiment module:
  kernel, rpc, portable, ms, us, ns, EnvExperiment

Modules
-------
  core       — Core device: timeline cursor, mu conversion, underflow detection
  devices    — TTLOut, TTLIn, AD9910 (Urukul), CoreDMA, EdgeCounter
  environment— EnvExperiment base + HasEnvironment mixin

Author: Nasir Ali, C-DAC Noida
"""

from .core        import Core, TerminationRequested
from .devices     import TTLOut, TTLIn, AD9910, CoreDMA, EdgeCounter
from .environment import EnvExperiment, HasEnvironment

# Unit constants (same as artiq.experiment)
ns = 1e-9
us = 1e-6
ms = 1e-3


def kernel(fn):
    """Decorator: marks a method as an ARTIQ kernel.  In simulation, passthrough."""
    fn._artiq_kernel = True
    return fn


def rpc(fn=None, *, flags=frozenset()):
    """Decorator: marks a method as an ARTIQ host RPC.  In simulation, passthrough."""
    if fn is None:
        def decorator(f):
            f._artiq_rpc = True
            return f
        return decorator
    fn._artiq_rpc = True
    return fn


def portable(fn):
    """Decorator: marks a method as portable (runs on both host and kernel)."""
    fn._artiq_portable = True
    return fn


__all__ = [
    "Core", "TerminationRequested",
    "TTLOut", "TTLIn", "AD9910", "CoreDMA", "EdgeCounter",
    "EnvExperiment", "HasEnvironment",
    "kernel", "rpc", "portable",
    "ns", "us", "ms",
]
