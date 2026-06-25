"""
Shared Hilbert-space operators for the ion-trap emulator.

Conventions
-----------
Qubit:
  |g⟩ = basis(2, 0) — ground state
  |e⟩ = basis(2, 1) — excited state
  SP  = |e⟩⟨g| — excitation (σ+ in physics)
  SM  = |g⟩⟨e| — de-excitation (σ- in physics)
  PE  = |e⟩⟨e| — projector onto excited state

Motional:
  N_FOCK — Fock-space truncation (states 0 … N_FOCK-1)
  a      — annihilation operator; a|n⟩ = √n |n-1⟩
  n_op   — number operator

Author: Nasir Ali, C-DAC Noida
"""

import numpy as np
import qutip as qt

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_N_FOCK = 20       # Fock-space truncation for single-ion simulations


# ── Qubit operators ───────────────────────────────────────────────────────────
KET_G = qt.basis(2, 0)          # |g⟩
KET_E = qt.basis(2, 1)          # |e⟩
SP    = KET_E * KET_G.dag()     # σ+  (excite)
SM    = KET_G * KET_E.dag()     # σ-  (de-excite)
PE    = KET_E * KET_E.dag()     # projector onto |e⟩
PG    = KET_G * KET_G.dag()     # projector onto |g⟩
SX    = SP + SM                  # σ_x
SY    = -1j * SP + 1j * SM      # σ_y
SZ    = PE - PG                  # σ_z


def build_single_ion_ops(N_fock: int = DEFAULT_N_FOCK):
    """
    Return operator dict for single-ion qubit ⊗ motional Hilbert space.

    Keys
    ----
    a, ad, n_op           — motional annihilation/creation/number (full space)
    sp, sm, pe, pg, sx    — qubit operators tensored with I_motional
    I                     — identity on full space
    """
    a_m  = qt.destroy(N_fock)
    n_m  = a_m.dag() * a_m
    I_m  = qt.qeye(N_fock)
    I_q  = qt.qeye(2)

    return {
        "a":    qt.tensor(I_q, a_m),
        "ad":   qt.tensor(I_q, a_m.dag()),
        "n_op": qt.tensor(I_q, n_m),
        "sp":   qt.tensor(SP, I_m),
        "sm":   qt.tensor(SM, I_m),
        "pe":   qt.tensor(PE, I_m),
        "pg":   qt.tensor(PG, I_m),
        "sx":   qt.tensor(SX, I_m),
        "I":    qt.tensor(I_q, I_m),
        "N_fock": N_fock,
    }


def thermal_dm(n_bar: float, N_fock: int = DEFAULT_N_FOCK) -> qt.Qobj:
    """Thermal motional state ρ_m = Σ_n P_n(n̄)|n⟩⟨n|."""
    return qt.thermal_dm(N_fock, n_bar)


def ion_state(qubit_ket: qt.Qobj, motional_dm: qt.Qobj) -> qt.Qobj:
    """Full density matrix: |qubit_ket⟩⟨qubit_ket| ⊗ motional_dm."""
    rho_q = qt.ket2dm(qubit_ket)
    return qt.tensor(rho_q, motional_dm)
