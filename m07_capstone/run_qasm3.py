"""
run_qasm3.py — M07 Capstone CLI
================================
Parse a QASM3 circuit, compile it to pulse instructions, execute on the
QPU emulator backend, and print the measurement distribution.

Usage
-----
    python run_qasm3.py circuits/bell.qasm
    python run_qasm3.py circuits/rabi.qasm --shots 500
    python run_qasm3.py circuits/bell.qasm --shots 1000 --n-bar 0.05

Full stack path for bell.qasm
------------------------------
  bell.qasm ──parse──▶ [CarrierPulse, VirtualZ, EntangleGate, MeasureOp×2]
             ──exec──▶ QPUBackend.run_ms_gate(shots)    ← M06 physics
             ──print▶  {"00": 249, "01": 4, "10": 3, "11": 244}

Author: Nasir Ali, C-DAC Noida
"""

from __future__ import annotations

import argparse
import math
import pathlib
import sys

# Make qpu package and M06 importable regardless of where script is run from
_HERE = pathlib.Path(__file__).parent
_M06  = _HERE.parent / "m06_iontrap_emu"
for _p in (str(_HERE), str(_M06)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from qpu import QPUBackend, compile_qasm3


def _count_bar(counts: dict, total: int, width: int = 40) -> str:
    """Render a simple ASCII bar chart of the counts dict."""
    lines = []
    for state, n in sorted(counts.items()):
        bar = "█" * int(width * n / total)
        pct = 100 * n / total
        lines.append(f"  {state}: {bar:<{width}}  {n:>6} ({pct:5.1f}%)")
    return "\n".join(lines)


def main(argv: list[str] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a QASM3 circuit on the M07 QPU emulator."
    )
    parser.add_argument("circuit", help="Path to .qasm file")
    parser.add_argument("--shots",  type=int,   default=500,  help="Measurement shots (default: 500)")
    parser.add_argument("--n-bar",  type=float, default=0.0,  help="COM mode thermal occupancy n̄ (default: 0.0)")
    parser.add_argument("--eta",    type=float, default=0.1,  help="Lamb-Dicke parameter η (default: 0.1)")
    parser.add_argument("--seed",   type=int,   default=42,   help="RNG seed (default: 42)")
    args = parser.parse_args(argv)

    circuit_path = pathlib.Path(args.circuit)
    if not circuit_path.exists():
        print(f"ERROR: circuit file not found: {circuit_path}", file=sys.stderr)
        return 1

    source = circuit_path.read_text()

    # ── Compile ────────────────────────────────────────────────────────────
    instructions = compile_qasm3(source)
    if not instructions:
        print("WARNING: no instructions compiled — check circuit syntax.", file=sys.stderr)
        return 1

    print(f"\nCircuit: {circuit_path.name}")
    print(f"Compiled instructions ({len(instructions)}):")
    for i, instr in enumerate(instructions):
        print(f"  [{i}] {instr}")

    # ── Execute ────────────────────────────────────────────────────────────
    import numpy as np
    backend = QPUBackend(
        n_bar=args.n_bar,
        eta=args.eta,
        rng=np.random.default_rng(args.seed),
    )
    counts = backend.execute_circuit(instructions, shots=args.shots)

    # ── Report ─────────────────────────────────────────────────────────────
    total = sum(counts.values())
    print(f"\nResults ({total} shots, n̄={args.n_bar}, η={args.eta}):")
    print(_count_bar(counts, total))
    print(f"\nRaw counts: {counts}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
