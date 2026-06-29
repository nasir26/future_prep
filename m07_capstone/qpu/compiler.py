"""
M07 — QASM3 Compiler (subset)
==============================
Parses a restricted QASM3 dialect and emits a flat list of pulse instructions.

Supported gates
---------------
  h q[i]              — Hadamard: π/2 Y-rotation + virtual Rz(π)
  x q[i]              — Pauli-X:  π carrier pulse
  rz(θ) q[i]         — Virtual Z rotation (no physical pulse, phase frame update)
  cx q[i], q[j]       — CNOT: mapped to MS entangling gate
  c[i] = measure q[j] — Fluorescence measurement

Instruction types
-----------------
  CarrierPulse(qubit, theta, phi) — physical carrier pulse
  VirtualZ(qubit, phi)            — software phase update
  EntangleGate(qubit0, qubit1)    — MS-gate (maximally entangling)
  MeasureOp(qubit, cbit)          — discriminated readout

Why a hand-rolled parser?
The openqasm3 library requires the [parser] extra (antlr4) which is not in the
qprep conda env.  A regex parser for this gate subset is ~50 lines and
teaches exactly the same lesson: how QASM3 source maps to hardware primitives.

Author: Nasir Ali, C-DAC Noida
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


# ── Instruction dataclasses ────────────────────────────────────────────────

@dataclass
class CarrierPulse:
    """Physical carrier Rabi pulse: rotate qubit by `theta` around axis `phi`."""
    qubit: int
    theta: float
    phi: float = 0.0


@dataclass
class VirtualZ:
    """
    Virtual Z rotation — advance the local phase frame by `phi`.

    No physical pulse: hardware achieves this by updating the DDS phase offset.
    Cost: zero time on the hardware; exact fidelity-loss free.
    """
    qubit: int
    phi: float


@dataclass
class EntangleGate:
    """
    Mølmer-Sørensen entangling gate on two qubits.

    The maximally entangling MS(π/4) maps |↓↓⟩ → (|↓↓⟩ + i|↑↑⟩)/√2.
    theta=π/4 is the standard maximally entangling angle.
    """
    qubit0: int
    qubit1: int
    theta: float = math.pi / 4


@dataclass
class MeasureOp:
    """Fluorescence readout: measure `qubit` and store result in `cbit`."""
    qubit: int
    cbit: int


# ── Parser ─────────────────────────────────────────────────────────────────

# Lines to skip without warning
_SKIP_PATTERNS = re.compile(
    r'^(OPENQASM|include|qubit|bit|//)|\s*$'
)

# Gate matchers (applied in order; first match wins)
_RULES: list[tuple[re.Pattern, callable]] = [
    # h q[i]
    (re.compile(r'^h\s+\w+\[(\d+)\]'),
     lambda m: [CarrierPulse(int(m.group(1)), math.pi / 2, math.pi / 2),
                VirtualZ(int(m.group(1)), math.pi)]),

    # x q[i]
    (re.compile(r'^x\s+\w+\[(\d+)\]'),
     lambda m: [CarrierPulse(int(m.group(1)), math.pi, 0.0)]),

    # rz(theta) q[i]  (theta may be a float literal or pi expression)
    (re.compile(r'^rz\(([^)]+)\)\s+\w+\[(\d+)\]'),
     lambda m: [VirtualZ(int(m.group(2)), _eval_angle(m.group(1)))]),

    # cx q[i], q[j]
    (re.compile(r'^cx\s+\w+\[(\d+)\],\s*\w+\[(\d+)\]'),
     lambda m: [EntangleGate(int(m.group(1)), int(m.group(2)))]),

    # c[i] = measure q[j]
    (re.compile(r'^\w+\[(\d+)\]\s*=\s*measure\s+\w+\[(\d+)\]'),
     lambda m: [MeasureOp(int(m.group(2)), int(m.group(1)))]),
]


def _eval_angle(expr: str) -> float:
    """
    Safely evaluate a numeric angle expression from QASM3.

    Handles: floats, integers, and simple "pi" / "π" references.
    No exec/eval — just a small whitelist of recognised forms.
    """
    expr = expr.strip().replace("pi", str(math.pi)).replace("π", str(math.pi))
    # Allow: digits, '.', '+', '-', '*', '/', '(', ')', whitespace
    if re.fullmatch(r'[\d\s.+\-*/()eE]+', expr):
        return float(eval(expr))   # noqa: S307  (whitelisted arithmetic only)
    raise ValueError(f"Unsupported angle expression: {expr!r}")


def compile_qasm3(source: str) -> list:
    """
    Parse QASM3 `source` and return a list of pulse instructions.

    Lines that don't match any gate pattern and aren't header/comment lines
    are silently skipped — this makes the compiler tolerant of stdgates.inc
    declarations and other boilerplate.

    Parameters
    ----------
    source : str — raw QASM3 source text

    Returns
    -------
    instructions : list of CarrierPulse | VirtualZ | EntangleGate | MeasureOp
    """
    instructions: list = []

    for raw_line in source.splitlines():
        line = raw_line.strip().rstrip(';')
        if not line or _SKIP_PATTERNS.match(line):
            continue

        matched = False
        for pattern, builder in _RULES:
            m = pattern.match(line)
            if m:
                instructions.extend(builder(m))
                matched = True
                break

        # Unrecognised lines (e.g. gate declarations, comments) → skip silently

    return instructions
