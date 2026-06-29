"""
test_compiler.py — QASM3 → pulse instruction compiler (7 tests)

Verifies that each supported gate maps to the correct instruction type(s)
and that the Bell/Rabi circuits compile to the expected instruction lists.
"""

import math

import pytest

from qpu.compiler import (
    compile_qasm3,
    CarrierPulse, VirtualZ, EntangleGate, MeasureOp,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _types(instrs):
    return [type(i).__name__ for i in instrs]


# ── Tests ───────────────────────────────────────────────────────────────────

def test_h_gate_maps_to_carrier_plus_virtual_z():
    """h q[0] → CarrierPulse(π/2, π/2) + VirtualZ(π)."""
    instrs = compile_qasm3("OPENQASM 3;\nh q[0];")
    assert len(instrs) == 2
    assert isinstance(instrs[0], CarrierPulse)
    assert abs(instrs[0].theta - math.pi / 2) < 1e-9
    assert abs(instrs[0].phi  - math.pi / 2) < 1e-9
    assert isinstance(instrs[1], VirtualZ)
    assert abs(instrs[1].phi - math.pi) < 1e-9


def test_x_gate_maps_to_pi_pulse():
    """x q[0] → CarrierPulse(π, 0)."""
    instrs = compile_qasm3("OPENQASM 3;\nx q[0];")
    assert len(instrs) == 1
    cp = instrs[0]
    assert isinstance(cp, CarrierPulse)
    assert abs(cp.theta - math.pi) < 1e-9
    assert abs(cp.phi) < 1e-9


def test_rz_gate_maps_to_virtual_z():
    """rz(1.5707963) q[0] → VirtualZ(phi ≈ π/2)."""
    instrs = compile_qasm3("OPENQASM 3;\nrz(1.5707963) q[0];")
    assert len(instrs) == 1
    assert isinstance(instrs[0], VirtualZ)
    assert abs(instrs[0].phi - math.pi / 2) < 1e-5


def test_cx_gate_maps_to_entangle_gate():
    """cx q[0], q[1] → EntangleGate(0, 1)."""
    instrs = compile_qasm3("OPENQASM 3;\ncx q[0], q[1];")
    assert len(instrs) == 1
    eg = instrs[0]
    assert isinstance(eg, EntangleGate)
    assert eg.qubit0 == 0
    assert eg.qubit1 == 1


def test_measure_maps_to_measure_op():
    """c[0] = measure q[0] → MeasureOp(qubit=0, cbit=0)."""
    instrs = compile_qasm3("OPENQASM 3;\nc[0] = measure q[0];")
    assert len(instrs) == 1
    mo = instrs[0]
    assert isinstance(mo, MeasureOp)
    assert mo.qubit == 0
    assert mo.cbit  == 0


def test_bell_circuit_instruction_count():
    """
    Full Bell circuit compiles to exactly 5 instructions:
      H → [CarrierPulse, VirtualZ]     (2)
      CX → [EntangleGate]              (1)
      measure×2 → [MeasureOp, MeasureOp] (2)
    """
    src = """
    OPENQASM 3;
    include "stdgates.inc";
    qubit[2] q;
    bit[2] c;
    h q[0];
    cx q[0], q[1];
    c[0] = measure q[0];
    c[1] = measure q[1];
    """
    instrs = compile_qasm3(src)
    assert len(instrs) == 5
    assert _types(instrs) == [
        "CarrierPulse", "VirtualZ", "EntangleGate", "MeasureOp", "MeasureOp"
    ]
    # The second MeasureOp covers qubit 1
    assert instrs[-1].qubit == 1
    assert instrs[-1].cbit  == 1


def test_header_lines_ignored():
    """OPENQASM, include, qubit, bit declarations do not produce instructions."""
    src = """
    OPENQASM 3;
    include "stdgates.inc";
    qubit[2] q;
    bit[2] c;
    x q[0];
    """
    instrs = compile_qasm3(src)
    assert len(instrs) == 1
    assert isinstance(instrs[0], CarrierPulse)
