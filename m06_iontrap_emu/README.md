# M06 — Ion-Trap Quantum Emulator

**Author:** Nasir Ali  
**Org:** C-DAC Noida  
**Goal:** Build a full-featured trapped-ion physics emulator in Python/QuTiP that covers
single-ion Rabi dynamics, sideband cooling, fluorescence readout, two-ion MS gate, noise
models, and a JSON TCP server — everything you'd explain in a quantum-hardware interview.

---

## Tool table

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11.15 | Runtime |
| QuTiP | 5.3.0 | Density-matrix ODE solver (mesolve) |
| NumPy / SciPy | 2.x / 1.x | Arrays, Poisson stats, curve fitting |
| pytest | 9.x | 61-test suite |

---

## Module layout

```
m06_iontrap_emu/
├── iontrap/
│   ├── __init__.py       ← public exports
│   ├── operators.py      ← QuTiP Hilbert-space building blocks
│   ├── ion.py            ← IonTrap: carrier/RSB/BSB Rabi
│   ├── cooling.py        ← Doppler + sideband cooling (analytic + mesolve)
│   ├── readout.py        ← Fluorescence readout, threshold, sideband asymmetry
│   ├── ms_gate.py        ← Two-ion Mølmer-Sørensen gate
│   ├── noise.py          ← Heating, laser phase noise, B-field drift
│   └── server.py         ← asyncio TCP/JSON server on 127.0.0.1:7777
└── tests/
    ├── test_single_ion.py   (10 tests)
    ├── test_cooling.py      ( 8 tests)
    ├── test_readout.py      (13 tests)
    ├── test_noise.py        (16 tests)
    ├── test_ms_gate.py      ( 7 tests)
    └── test_server.py       ( 7 tests)
```

---

## Exercise ladder

### ex01 — operators.py: Hilbert-space building blocks

Qubit convention: `|g⟩ = basis(2,0)`, `|e⟩ = basis(2,1)`.  
`build_single_ion_ops(N_fock)` → dict with `a, a†, n̂, σ+, σ-, Pₑ, Pg, σx, I`.  
Motional truncation: `N_fock = 20` (default); thermal state via `qt.thermal_dm`.

### ex02 — ion.py: Single-ion Rabi oscillations

Three interaction-picture Hamiltonians (Lamb-Dicke regime):

| Drive | Hamiltonian | Key property |
|-------|-------------|--------------|
| Carrier | `ℏΩ/2 σx ⊗ Im` | Motionally blind in LD limit |
| RSB | `ℏηΩ/2 (σ+ a + σ- a†)` | Dark state at `|g,0⟩`; drives `|g,n⟩→|e,n-1⟩` |
| BSB | `ℏηΩ/2 (σ+ a† + σ- a)` | Drives `|g,0⟩→|e,1⟩`; π-time = `π/(ηΩ)` |

**QuTiP 5 fix:** `mesolve(..., e_ops=[op])` — `e_ops` is keyword-only.  
**tlist fix:** always include `t=0` as `tlist[0]`; single-element `[t_final]` returns initial state.

### ex03 — cooling.py: Cooling models

**Analytic SBC:** each RSB+repump cycle removes one phonon (geometric decay):
```
n̄_N = n̄_0 × r^N,   r = n̄_0 / (n̄_0 + 1)
```

**QuTiP SBC:** Lindblad simulation with RSB Hamiltonian + `√Γ_rep σ-` collapse op.  
Cooling time constant (overdamped): `τ_cool = Γ_rep / (ηΩ)²`.  
Fastest cooling near `Γ_rep ≈ ηΩ` (critically damped regime).

**Doppler equilibrium:** `n̄_D = Γ / (2η²ν_trap)` (Lamb-Dicke, weak-binding limit).

### ex04 — readout.py: Fluorescence readout

Bright (|g⟩) → Poisson(μ_bright ≈ 25 photons).  
Dark (|e⟩) → Poisson(μ_dark ≈ 1 photon).  
`discriminate(counts, τ)`: counts < τ → dark (1), counts ≥ τ → bright (0).  
`optimal_threshold()`: iterate τ from 1, minimize P(bright < τ) + P(dark ≥ τ).  
`sideband_asymmetry(...)`: `n̄ = R/(1-R)`, `R = P_RSB / P_BSB`.

### ex05 — ms_gate.py: Two-ion Mølmer-Sørensen gate

Bichromatic drive at `ω_q ± δ` creates spin-motion coupling:
```
H(t) = ηΩ (σx¹ + σx²)(a e^{iδt} + a† e^{-iδt})
```

**Magnus expansion** for M closed loops (T = 2πM/δ):
```
U = exp(-i θ σx¹σx²)   with   θ = 4πM(ηΩ)²/δ²
```

**Maximally entangling gate** (θ = π/4) with M=1 loop requires **δ = 4ηΩ**.  
**Gate time:** `t_gate = πδ / (8(ηΩ)²) = 2π/δ` (one complete phase-space loop).  
**Output state:** `(|gg⟩ − i|ee⟩)/√2` (Bell state, −i phase from U = exp(−iHt)).  
**Analytic fidelity:** `F ≈ 1 − 2η²(n̄ + ½)` (Lamb-Dicke, Roos et al. 2008).

### ex06 — noise.py: Decoherence models

| Model | Key formula |
|-------|-------------|
| Secular heating | `⟨n̂⟩(t) = ṅ t`; fidelity loss `η²ṅt` |
| Laser phase noise | `γ = 2πΔν`; `T₂ = 2/γ`; coherence `exp(−γt/2)` |
| B-field OU drift | Ramsey contrast `C(t) = exp(−σ_ω²t²/2)`; `T₂* = √2/σ_ω` |

Ramsey fringe mean: `⟨P_e⟩ = ½(1 + C(τ))`, NOT `C(τ)`.

### ex07 — server.py: asyncio TCP/JSON control

Port `127.0.0.1:7777`, newline-delimited JSON.  
Commands: `rabi_scan`, `sideband_cooling`, `readout`, `ms_gate`.

---

## Running the tests

```bash
source ~/future_prep/scripts/activate_qprep.sh
cd m06_iontrap_emu
python -m pytest tests/ -v
# → 61 passed
```

---

## Definition of Command (DoC)

Pass ALL of the following **without references**:

1. **Carrier vs RSB vs BSB:** explain the Hamiltonian, dark state, and π-time for each.
   - Carrier: `H = ℏΩ/2 σx ⊗ Im` — motionally blind; π-time = `π/Ω`
   - RSB: `H = ℏηΩ/2 (σ+a + σ-a†)` — dark at `|g,0⟩`; π-time for `|g,n⟩` = `π/(ηΩ√n)`
   - BSB: `H = ℏηΩ/2 (σ+a† + σ-a)` — drives `|g,0⟩→|e,1⟩`; π-time = `π/(ηΩ)`

2. **QuTiP 5 API:** explain why `qt.mesolve(H, ρ₀, tlist, c_ops, e_ops=[...])` and why
   tlist must start at 0.

3. **Sideband cooling:** derive `n̄_N = n̄_0 × r^N` (r = n̄₀/(n̄₀+1)) from the per-cycle
   RSB+repump picture. State the Lindblad cooling time constant `τ_cool = Γ_rep/(ηΩ)²`.

4. **Fluorescence readout:** bright vs dark convention (high counts → bright/|g⟩ → output 0).
   Derive the optimal threshold criterion.

5. **MS gate loop-closure:** explain why `δ = 4ηΩ` is required for `θ = π/4` in a single
   phase-space loop using the Magnus formula `θ = 4πM(ηΩ)²/δ²`.

6. **B-field Ramsey:** sketch `C(t) = exp(−σ_ω²t²/2)`, locate `T₂* = √2/σ_ω`, and state
   why `⟨P_e(τ)⟩ = ½(1 + C(τ))` not `C(τ)`.

7. **Server protocol:** send a JSON request to port 7777 for a rabi_scan and decode the
   response (P_e list). Show the asyncio client code from memory.

8. **N_fock truncation:** explain why `qt.thermal_dm(N_fock=10, n_bar=5)` gives n̄ ≈ 3
   and how to choose N_fock to minimise truncation error (rule: `N_fock ≥ 3 × n̄_max`).
