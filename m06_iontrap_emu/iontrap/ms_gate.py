"""
M06 ex04 — Two-Ion Mølmer-Sørensen Gate
=========================================
The MS gate produces maximally entangled Bell states using a bichromatic
laser field at ω_L = ω_q ± δ (red and blue motional sideband simultaneously).

Physical mechanism
------------------
The bichromatic drive (RB + BB simultaneously) couples the two ions' spin states
via the shared COM mode. In the Lamb-Dicke regime and for δ close to ν_trap:

  H_MS = ℏηΩ (J_x^(1) + J_x^(2)) · (a e^(iδt) + a† e^(-iδt))

where J_x^(k) = (σ+^(k) + σ-^(k))/2 and a/a† are COM phonons.

The motional mode acts as a "quantum bus": it entangles the two ions and
then disentangles at t_gate = 1/(ε) = 2π/ε where ε = (ηΩ)²/(2δ).
The geometric phase accumulated is θ = π/4 for a maximally entangling gate.

Hilbert space: qubit₁ ⊗ qubit₂ ⊗ COM  (ℂ² ⊗ ℂ² ⊗ ℂ^N_fock)

For speed in simulation we implement the time-dependent Hamiltonian by
integrating in short steps with qutip.sesolve.

After the gate:
  |↓↓, 0⟩ → (|↓↓, 0⟩ + i|↑↑, 0⟩) / √2   (Bell state Φ+)
  Fidelity with Bell state as a function of t or δ tells us gate quality.

Analytic MS fidelity (Roos et al.):
  F ≈ 1 − 2η²(n̄_COM + ½)   (Lamb-Dicke, low-heating limit)

Author: Nasir Ali, C-DAC Noida
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import qutip as qt

from .operators import KET_G, KET_E, SP, SM, SX, PE, PG, thermal_dm, DEFAULT_N_FOCK


def _build_two_ion_ops(N_fock: int):
    """
    Build operators for qubit₁ ⊗ qubit₂ ⊗ COM Hilbert space.
    """
    I2 = qt.qeye(2)
    Im = qt.qeye(N_fock)
    a  = qt.destroy(N_fock)

    sp1 = qt.tensor(SP, I2, Im)
    sm1 = qt.tensor(SM, I2, Im)
    sp2 = qt.tensor(I2, SP, Im)
    sm2 = qt.tensor(I2, SM, Im)
    sx1 = qt.tensor(SX, I2, Im)
    sx2 = qt.tensor(I2, SX, Im)
    pe1 = qt.tensor(PE, I2, Im)
    pe2 = qt.tensor(I2, PE, Im)
    a_f = qt.tensor(I2, I2, a)
    n_f = a_f.dag() * a_f

    return dict(
        sp1=sp1, sm1=sm1, sx1=sx1, pe1=pe1,
        sp2=sp2, sm2=sm2, sx2=sx2, pe2=pe2,
        a=a_f, ad=a_f.dag(), n_op=n_f,
    )


@dataclass
class MSGate:
    """
    Mølmer-Sørensen gate simulator for two trapped ions.

    The gate is driven by a bichromatic beam at ω_q ± δ.
    In the Lamb-Dicke regime the effective Hamiltonian couples spin + COM.

    Parameters
    ----------
    Omega_R : float — single-ion Rabi frequency (rad/s)
    eta     : float — Lamb-Dicke parameter
    delta   : float — bichromatic detuning from sideband (rad/s)
    N_fock  : int   — Fock-space truncation for COM mode
    n_bar   : float — mean phonon number of COM mode (thermal)
    """
    Omega_R : float = 2 * math.pi * 50e3
    eta     : float = 0.1
    delta   : float = 2 * math.pi * 5e3     # gate detuning (rad/s)
    N_fock  : int   = 10
    n_bar   : float = 0.0

    def __post_init__(self):
        self._ops = _build_two_ion_ops(self.N_fock)

    def gate_time(self) -> float:
        """
        Ideal gate time for one closed phase-space loop with entangling phase π/4.

        For H = ηΩ (σ_x^1 + σ_x^2)(a e^{iδt} + a†e^{-iδt}), Magnus expansion gives
        U(T) = exp(-i θ σ_x^1 σ_x^2) × (global phase)  for T = 2π M / δ (M loops), with
          θ = 4πM(ηΩ)²/δ²

        For maximally entangling θ = π/4 with M=1 loop:
          4π(ηΩ)²/δ² = π/4  →  (ηΩ/δ)² = 1/16  →  δ = 4ηΩ

        Setting T = 2π/δ = π/(2ηΩ) and writing in terms of δ:
          T = π δ / (8 (ηΩ)²)

        Requirement: caller must use δ = 4ηΩ for single-loop closure.
        """
        return math.pi * self.delta / (8 * (self.eta * self.Omega_R) ** 2)

    def _H_td(self) -> list:
        """
        Time-dependent bichromatic Hamiltonian (interaction picture).

        H(t) = ηΩ (J_x^1 + J_x^2) (a e^{iδt} + a† e^{-iδt})

        Expressed as [H0, [H1, coeff_fn]] for QuTiP mesolve.
        """
        ops   = self._ops
        J_x   = ops["sx1"] + ops["sx2"]
        eta_O = self.eta * self.Omega_R

        H0  = qt.tensor(qt.qeye(2), qt.qeye(2), qt.qeye(self.N_fock)) * 0  # zero

        # e^{iδt} term: (J_x ⊗ a)
        H_a  = eta_O * J_x * ops["a"]
        H_ad = eta_O * J_x * ops["ad"]

        delta = self.delta

        def coeff_a(t):
            return np.exp(1j * delta * t)

        def coeff_ad(t):
            return np.exp(-1j * delta * t)

        return [H0, [H_a, coeff_a], [H_ad, coeff_ad]]

    def _initial_state(self, qubit_ket: qt.Qobj = None) -> qt.Qobj:
        """
        Full initial density matrix: |ψ_q⟩⟨ψ_q| ⊗ |ψ_q⟩⟨ψ_q| ⊗ ρ_COM.
        Default qubit state: both ions in |g⟩.
        """
        if qubit_ket is None:
            qubit_ket = KET_G
        rho_q   = qt.ket2dm(qubit_ket)
        rho_COM = thermal_dm(self.n_bar, self.N_fock)
        return qt.tensor(rho_q, rho_q, rho_COM)

    def run(
        self,
        t_list: np.ndarray = None,
        c_ops : list = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Simulate the MS gate.

        Returns
        -------
        t_list    : ndarray — time axis
        p_e1      : ndarray — ⟨P_e⟩ for ion 1
        p_e2      : ndarray — ⟨P_e⟩ for ion 2
        """
        if t_list is None:
            t_gate = self.gate_time()
            t_list = np.linspace(0, t_gate, 100)
        if c_ops is None:
            c_ops = []

        ops  = self._ops
        rho0 = self._initial_state()
        H    = self._H_td()
        res  = qt.mesolve(H, rho0, t_list, c_ops, e_ops=[ops["pe1"], ops["pe2"]])
        return t_list, np.array(res.expect[0]).real, np.array(res.expect[1]).real

    def bell_fidelity(self, c_ops: list = None) -> float:
        """
        Fidelity of the output state with the Bell state (|gg⟩ + i|ee⟩)/√2.

        Only meaningful when the COM mode is initially in |0⟩ (n_bar=0).
        """
        if c_ops is None:
            c_ops = []
        t_gate = self.gate_time()
        t_list = np.linspace(0, t_gate, 200)
        ops    = self._ops
        rho0   = self._initial_state()
        H      = self._H_td()
        res    = qt.mesolve(H, rho0, t_list, c_ops, e_ops=[])
        rho_f  = res.states[-1]

        # Trace out COM mode → reduced qubit density matrix
        # (partrace over the motional subsystem, index 2)
        rho_2q = rho_f.ptrace([0, 1])

        # Target Bell state: (|gg⟩ - i|ee⟩) / √2
        # (negative sign because U = exp(-iHt) gives a negative entangling phase)
        g = KET_G
        e = KET_E
        bell = (qt.tensor(g, g) - 1j * qt.tensor(e, e)).unit()
        rho_bell = qt.ket2dm(bell)

        return float(qt.fidelity(rho_2q, rho_bell) ** 2)


def ms_fidelity_analytic(eta: float, n_bar: float) -> float:
    """
    Analytic MS gate fidelity in Lamb-Dicke regime (Roos et al. 2008):

    F ≈ 1 − 2η²(n̄ + ½)

    Valid for small η and moderate n̄.  Fails for n̄η² ≫ 1.
    """
    return max(0.0, 1.0 - 2 * eta**2 * (n_bar + 0.5))
