// Bell-state circuit — produces (|00⟩ + |11⟩)/√2
// Run with: python run_qasm3.py circuits/bell.qasm
OPENQASM 3;
include "stdgates.inc";
qubit[2] q;
bit[2] c;

// Hadamard on qubit 0 → superposition |+⟩
h q[0];

// CNOT (q[0] control, q[1] target) → entangle
// Compiled to MS gate in hardware
cx q[0], q[1];

// Joint measurement
c[0] = measure q[0];
c[1] = measure q[1];
