# M04 — ARTIQ Kernels: Ion-Trap Experiment Control

**Author:** Nasir Ali, C-DAC Noida

## Goal

Master the ARTIQ Python API for real-time quantum-control experiments:
timeline model, TTL/DDS primitives, photon counting, and full experiment
sequences from Doppler cooling through MS gate and heralded entanglement.

## Why a simulation layer?

ARTIQ is Nix-only (no pip install) and requires specific FPGA hardware.
`artiq_sim/` implements the exact same Python API (same class names, method
signatures, decorator names, unit constants) so kernel code is **1:1
portable** to a real ARTIQ system — only the import path and device_db change.

## Tool table

| Tool | Role |
|------|------|
| Python 3.11 | Experiment kernel language |
| artiq_sim/ | Faithful ARTIQ API simulation (no Nix needed) |
| numpy / scipy | Analysis: histogram, curve_fit |
| pytest | Experiment verification |

## artiq_sim package

```
artiq_sim/
├── __init__.py     — exports: kernel, rpc, portable, ns/us/ms, Core, TTLOut…
├── core.py         — Core device: timeline cursor, mu conversion, underflow
├── devices.py      — TTLOut, TTLIn, AD9910 (Urukul), CoreDMA
└── environment.py  — EnvExperiment base, HasEnvironment, make_experiment()
```

## Exercise ladder

| # | File | Concept | Tests |
|---|------|---------|-------|
| ex01 | `kernels/ex01_ttl_basics.py` | Timeline, delay, at_mu, underflow | 6 |
| ex02 | `kernels/ex02_photon_counting.py` | Gate, count, histogram, discrimination | 4 |
| ex03 | `kernels/ex03_dds_control.py` | FTW/POW/ASF, phase, RF switch, freq ramp | 6 |
| ex04 | `kernels/ex04_doppler_cooling.py` | cool_and_pump(), detect() subroutines | 5 |
| ex05 | `kernels/ex05_rabi_scan.py` | Carrier Rabi sweep, sin² fit, τ_π extraction | 4 |
| ex06 | `kernels/ex06_ramsey.py` | Ramsey fringe, CoreDMA trace recording/playback | 5 |
| ex07 | `kernels/ex07_sideband_cooling.py` | RSB+repump loop, sideband asymmetry, n̄ | 3+1skip |
| ex08 | `kernels/ex08_ms_gate.py` | Bichromatic MS gate pulse, fidelity model | 4 |
| ex09 | `kernels/ex09_mid_circuit.py` | MCM + conditional X; heralded entanglement | 8 |

**Total: 45 PASS, 1 SKIP**

## Quick start

```bash
source ~/future_prep/scripts/activate_qprep.sh
cd ~/future_prep
python -m pytest m04_artiq/tests/ -v
# or: make -C m04_artiq test
```

## Key concepts

### ARTIQ timeline model (ex01)
Every device output is an RTIO (Real-Time I/O) event timestamped in
machine units (mu).  The software cursor advances with `delay()` / `at_mu()`.

```
    ← SLACK_MU →
hw_now          cursor (now_mu)
    |                |
    ────────────────────────────────────▶ time
```

`break_realtime()` resets the cursor to `hw_now + SLACK_MU` (1 ms by default),
giving Python enough time to run before the next event must fire.

**Underflow**: scheduling past → RTIOUnderflow.  Always call
`core.break_realtime()` at the start of every experiment.

### FTW precision (ex03)
`FTW = round(f × 2³²/SYSCLK)` → frequency resolution = SYSCLK/2³² ≈ 0.233 Hz at 1 GHz.
Phase: `POW = round(turns × 2¹⁶)`.
Use integer arithmetic on the kernel for ~8× speedup vs floats.

### Rabi formula (ex05)
`P_excited(τ) = sin²(Ω τ / 2) = sin²(π f_Rabi τ)`
- π-time: τ_π = 1/(2 f_Rabi)
- At τ = τ_π: P = sin²(π/2) = 1 (full flip) ← NOT sin²(π) = 0

### CoreDMA (ex06)
Record a sequence once: `with dma.record("name"): ...`
Replay many times: `dma.playback(handle)` — zero software overhead on FPGA.
Use for cooling pulses (identical every shot).

### Sideband asymmetry (ex07)
n̄ = P_RSB / (P_BSB − P_RSB) from:
  Ω_RSB / Ω_BSB = √(n̄/(n̄+1))
At ground state: Ω_RSB → 0, Ω_BSB stays finite.

### MS gate (ex08)
Bichromatic drive at ω_q ± δ closes a loop in phase space.
After τ_gate = 1/ε: geometric phase = π/4 → maximally entangling XX gate.
Gate time τ_gate = 1/(ν_COM − δ) = 200 µs for δ = 5 kHz.

### Heralded entanglement (ex09)
Attempt → detect photon → success (herald) or retry.
Mean attempts = 1/p_success (geometric distribution).
This is the core loop in quantum networking / photonic-link entanglement.

## Definition of Command (DoC)

Pass all of the following **without references**:

1. Write a minimal ARTIQ `@kernel` with `break_realtime()`, a `ttl.pulse()`,
   and a photon-counting gate.  Explain what underflow is.
2. Compute `PINC` for a 200 MHz DDS tone on a 1 GHz AD9910.
3. Write the Rabi excitation formula.  What is the π-time for Ω/2π = 50 kHz?
4. Draw the Doppler-cooling → sideband-cooling → detection timeline.
5. Explain the CoreDMA benefit and when to use it.
6. Explain the MS gate: what two tones, why bichromatic, what geometric phase.
7. Write the mid-circuit measurement + conditional X sequence from memory.
8. Explain heralded entanglement: success probability, mean attempts, retry loop.
