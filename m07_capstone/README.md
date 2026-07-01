# M07 — Capstone: Full-Stack Quantum Control

**Author:** Nasir Ali  
**Org:** C-DAC Noida  
**Goal:** Wire all prior modules into a working end-to-end quantum control
stack — from QASM3 source → pulse compiler → asyncio scheduler →
ion-trap physics backend → two-node distributed entanglement.

---

## Tool table

| Tool / Library | Version | Role |
|----------------|---------|------|
| Python | 3.11.15 | Runtime |
| QuTiP | 5.3.0 | Physics backend (via M06) |
| asyncio | stdlib | Experiment scheduler |
| scipy | 1.x | Calibration curve fitting |
| openqasm3 | 1.0.1 | AST types (parser uses regex subset) |
| pytest | 9.x | 34-test suite |

---

## Stack diagram

```
  QASM3 circuit file
        │
  compiler.py          ← regex parser; h/x/rz/cx/measure → pulse IR
        │
  scheduler.py         ← asyncio queue; priority ordering; result store
        │
  backend.py           ← QPUBackend: shot-based API wrapping M06 physics
        │           ┌── IonTrap.evolve_carrier()   (carrier Rabi)
        └── M06 ───┤── ms_fidelity_analytic()      (MS gate)
                    └── FluorescenceReadout         (discriminated readout)
        │
  calibration.py       ← freq_scan / rabi_pi_time / ramsey_track / recal_daemon
        │
  node.py              ← QPUNode: local ops + heralded photonic entanglement
```

---

## Module layout

```
m07_capstone/
├── qpu/
│   ├── __init__.py
│   ├── backend.py       ← QPUBackend (single-node shot API)
│   ├── compiler.py      ← QASM3 → pulse instruction list
│   ├── scheduler.py     ← asyncio ExperimentScheduler
│   ├── calibration.py   ← ParamStore + 4 calibration coroutines
│   └── node.py          ← QPUNode for two-node distributed entanglement
├── circuits/
│   ├── bell.qasm        ← Bell-state circuit (H + CX + measure)
│   └── rabi.qasm        ← Single-qubit π-pulse (X + measure)
├── tests/
│   ├── conftest.py
│   ├── test_backend.py      (6 tests)
│   ├── test_compiler.py     (7 tests)
│   ├── test_scheduler.py    (6 tests)
│   ├── test_calibration.py  (8 tests)
│   └── test_distributed.py  (7 tests)
├── run_qasm3.py         ← CLI: python run_qasm3.py <circuit.qasm>
├── Makefile
└── README.md
```

---

## Exercise ladder

### ex01 — backend.py: QPUBackend shot API
Wraps M06 `IonTrap` and `FluorescenceReadout` behind a clean dict-returning
interface (`run_carrier`, `run_ms_gate`, `execute_circuit`).  Shows how
physics simulators are encapsulated behind hardware-agnostic APIs.

**Key concept:** `t_pulse = θ / Ω_R` — pulse duration is the rotation angle
divided by the Rabi frequency; `P_e = sin²(θ/2)` for on-resonance carrier.

### ex02 — compiler.py: QASM3 subset parser
Regex-based parser mapping QASM3 gates to pulse IR:
- `h` → `CarrierPulse(π/2, π/2)` + `VirtualZ(π)` (Hadamard decomposition)
- `x` → `CarrierPulse(π, 0)` (π-pulse)
- `rz(θ)` → `VirtualZ(θ)` (zero hardware cost: DDS phase update)
- `cx` → `EntangleGate` (MS gate)
- `measure` → `MeasureOp`

**Key concept:** Virtual Z gates have zero physical cost in trapped-ion
hardware — the DDS phase offset is simply advanced.  This is why rz is
"free" and is preferred over physical rotations.

### ex03 — scheduler.py: asyncio experiment scheduler
Priority queue + async execution engine.  Demonstrates the asyncio
coroutine pattern for hardware control loops (submit → await run_all).

**Key concept:** `await asyncio.sleep(0)` inside calibration coroutines
yields control to the event loop — critical for interleaving multiple
experiments or background health checks without blocking.

### ex04 — calibration.py: Four calibration routines
1. **freq_scan**: Generalised Rabi line scan → `omega_0` (qubit frequency).
2. **rabi_pi_time**: Pulse-duration sweep + sin² fit → `t_pi`.
3. **ramsey_track**: Phase scan of second π/2 pulse → `delta_omega`.
4. **recal_daemon**: Closed-loop Ramsey polling for drift compensation.

**Key concept:** Ramsey is ×100 more frequency-sensitive than Rabi for the
same measurement time.  A Rabi scan resolves frequency to ~1/t_π;
a Ramsey scan resolves to ~1/(N t_π) for N free-precession periods.

### ex05 — node.py: Two-node distributed entanglement
Simulates the photonic link protocol used in ion-trap quantum networks:
- Per-attempt herald probability: `p = η² / 2` (two-photon coincidence).
- Heralded state: `|Ψ-⟩ = (|01⟩ − |10⟩) / √2`.
- Attempt rate vs fidelity tradeoff: lower η → fewer events, same fidelity.

**Key concept:** The herald rate scales as η², so doubling collection
efficiency quadruples the entanglement rate — a key figure of merit for
photonic quantum network links.

---

## Quick start

```bash
source ~/future_prep/scripts/activate_qprep.sh
cd m07_capstone

# Run all 34 tests
make test

# Demo: run Bell circuit end-to-end
make demo
```

Expected `make demo` output (Bell circuit):
```
Circuit: bell.qasm
Compiled instructions (6):
  [0] CarrierPulse(qubit=0, theta=1.5707963..., phi=1.5707963...)
  [1] VirtualZ(qubit=0, phi=3.14159...)
  [2] EntangleGate(qubit0=0, qubit1=1, theta=0.7853...)
  [3] MeasureOp(qubit=0, cbit=0)
  [4] MeasureOp(qubit=1, cbit=1)

Results (500 shots, n̄=0.0, η=0.1):
  00: ████████████████████  245 ( 49.0%)
  01: █                       5 (  1.0%)
  10: █                       5 (  1.0%)
  11: ████████████████████  245 ( 49.0%)
```

---

## Definition of Command (DoC)

Pass ALL of the following **without references**:

1. **QASM3 → hardware**: Explain how `rz(θ)` compiles to a virtual Z rotation
   and why it costs zero gate time on a trapped-ion processor.

2. **Bell circuit trace**: Starting from `bell.qasm`, trace the stack:
   parse → CarrierPulse+VirtualZ+EntangleGate → MS gate → P("00")=P("11")≈½.

3. **MS gate fidelity**: State the formula `F ≈ 1 − 2η²(n̄ + ½)` and explain
   the two noise sources it captures (thermal motion + Lamb-Dicke correction).

4. **Calibration hierarchy**: Explain why Ramsey gives tighter frequency
   resolution than Rabi spectroscopy for the same total interrogation time.

5. **Scheduler design**: Explain why `await asyncio.sleep(0)` inside
   calibration coroutines is important even when there's no real delay.

6. **Photonic link scaling**: If η_link doubles from 0.3 to 0.6, by what
   factor does the entanglement generation rate increase?  (Answer: ×4.)

7. **End-to-end demo**: Run `python run_qasm3.py circuits/bell.qasm` from
   a fresh shell and explain each output line without looking at the code.
