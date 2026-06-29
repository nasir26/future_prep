// Single-qubit π-pulse circuit — drives |g⟩ → |e⟩
// Run with: python run_qasm3.py circuits/rabi.qasm
OPENQASM 3;
include "stdgates.inc";
qubit[1] q;
bit[1] c;

// Pauli-X = π carrier pulse: |g⟩ → |e⟩
x q[0];

// Measure fluorescence
c[0] = measure q[0];
