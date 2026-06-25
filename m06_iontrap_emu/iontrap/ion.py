"""
M06 ex01 — Single-Ion Dynamics
================================
Carrier, RSB, and BSB Rabi oscillations using QuTiP density-matrix evolution
(qt.mesolve / qt.sesolve) in the Lamb-Dicke regime.

Physics summary
---------------
In the frame rotating at the qubit frequency ω_q and trap frequency ω_trap:

  Carrier:     H = ℏΩ/2  ·  σ_x ⊗ I_m
  RSB (−ω_t): H = ℏηΩ/2 · (σ+ ⊗ a  + σ- ⊗ a†)   — removes one phonon
  BSB (+ω_t): H = ℏηΩ/2 · (σ+ ⊗ a† + σ- ⊗ a )   — adds one phonon

  η = Lamb-Dicke parameter = k·x_zpf ≈ 0.05–0.15 (typical 40Ca+ linear trap)
  Ω = bare Rabi frequency (e.g., 2π × 50 kHz for dipole/quadrupole transition)

Thermal state  ρ_thermal = Σ P_n(n̄)|n⟩⟨n|,  P_n(n̄) = n̄^n / (n̄+1)^(n+1)

For a carrier Rabi on a thermal state:
  P_e(t) = ½ [1 - Σ_n P_n(n̄) cos(Ω t)]   ← envelope decay from dephasing

For RSB starting in |g,n⟩:
  P_e(t) = sin²(η Ω √n · t / 2)   ← "number-selective" frequency η Ω √n

Author: Nasir Ali, C-DAC Noida
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
import qutip as qt

from .operators import (
    KET_G, KET_E, SP, SM, PE, SX,
    build_single_ion_ops, thermal_dm, ion_state,
    DEFAULT_N_FOCK,
)


@dataclass
class IonTrap:
    """
    Single-ion qubit + motional mode.

    Parameters
    ----------
    Omega_R : float — bare Rabi frequency (rad/s)
    eta     : float — Lamb-Dicke parameter
    N_fock  : int   — Fock-space truncation
    gamma   : float — spontaneous emission rate (rad/s); 0 for closed system
    n_heat  : float — secular heating rate (phonons/s); 0 for no heating
    """
    Omega_R : float = 2 * math.pi * 50e3
    eta     : float = 0.1
    N_fock  : int   = DEFAULT_N_FOCK
    gamma   : float = 0.0      # spontaneous emission (s^-1)
    n_heat  : float = 0.0      # heating rate (phonons/s)

    def __post_init__(self):
        self._ops = build_single_ion_ops(self.N_fock)

    # ── Hamiltonians ────────────────────────────────────────────────────────

    def _H_carrier(self, phi: float = 0.0) -> qt.Qobj:
        """H_carrier = ℏΩ/2 (σ+ e^iφ + σ- e^-iφ) ⊗ I_m"""
        op = self._ops
        return (self.Omega_R / 2) * (
            np.exp(1j * phi) * op["sp"] + np.exp(-1j * phi) * op["sm"]
        )

    def _H_rsb(self) -> qt.Qobj:
        """H_RSB = ℏηΩ/2 (σ+ ⊗ a + σ- ⊗ a†)"""
        op = self._ops
        return (self.eta * self.Omega_R / 2) * (op["sp"] * op["a"] + op["sm"] * op["ad"])

    def _H_bsb(self) -> qt.Qobj:
        """H_BSB = ℏηΩ/2 (σ+ ⊗ a† + σ- ⊗ a)"""
        op = self._ops
        return (self.eta * self.Omega_R / 2) * (op["sp"] * op["ad"] + op["sm"] * op["a"])

    def _collapse_ops(self) -> list:
        """Lindblad operators for spontaneous emission and motional heating."""
        op   = self._ops
        c_ops = []
        if self.gamma > 0:
            # Spontaneous emission: |e⟩ → |g⟩ at rate γ
            c_ops.append(math.sqrt(self.gamma) * op["sm"])
        if self.n_heat > 0:
            # Secular heating: adds phonons at rate n_heat
            c_ops.append(math.sqrt(self.n_heat) * op["ad"])
        return c_ops

    # ── High-level evolution API ────────────────────────────────────────────

    def evolve_carrier(
        self,
        t_list : np.ndarray,
        n_bar  : float = 0.0,
        phi    : float = 0.0,
    ) -> np.ndarray:
        """
        Carrier Rabi oscillations starting from |g, ρ_thermal(n̄)⟩.

        Returns
        -------
        p_e : ndarray, shape (len(t_list),) — excited-state population
        """
        rho0 = ion_state(KET_G, thermal_dm(n_bar, self.N_fock))
        H    = self._H_carrier(phi)
        op   = self._ops
        res  = qt.mesolve(H, rho0, t_list, self._collapse_ops(), e_ops=[op["pe"]])
        return np.array(res.expect[0])

    def evolve_rsb(
        self,
        t_list : np.ndarray,
        n_bar  : float = 0.0,
    ) -> np.ndarray:
        """RSB Rabi: |g, ρ_thermal(n̄)⟩ driven by red sideband."""
        rho0 = ion_state(KET_G, thermal_dm(n_bar, self.N_fock))
        H    = self._H_rsb()
        op   = self._ops
        res  = qt.mesolve(H, rho0, t_list, self._collapse_ops(), e_ops=[op["pe"]])
        return np.array(res.expect[0])

    def evolve_bsb(
        self,
        t_list : np.ndarray,
        n_bar  : float = 0.0,
    ) -> np.ndarray:
        """BSB Rabi: |g, ρ_thermal(n̄)⟩ driven by blue sideband."""
        rho0 = ion_state(KET_G, thermal_dm(n_bar, self.N_fock))
        H    = self._H_bsb()
        op   = self._ops
        res  = qt.mesolve(H, rho0, t_list, self._collapse_ops(), e_ops=[op["pe"]])
        return np.array(res.expect[0])

    # ── Convenience ─────────────────────────────────────────────────────────

    def pi_time(self) -> float:
        """π-pulse time on the carrier: t_π = π / Ω_R."""
        return math.pi / self.Omega_R

    def rsb_pi_time(self, n: int) -> float:
        """RSB π-pulse time for Fock state |n⟩: t_π = π / (η Ω_R √n)."""
        if n == 0:
            return float("inf")   # |g,0⟩ is a dark state for RSB
        return math.pi / (self.eta * self.Omega_R * math.sqrt(n))

    def mean_phonon(self, rho: qt.Qobj) -> float:
        """Return ⟨n̂⟩ from a full system density matrix."""
        return float(qt.expect(self._ops["n_op"], rho).real)


# ── Analytical helpers ────────────────────────────────────────────────────────

def carrier_rabi_analytic(
    t_list : np.ndarray,
    Omega_R: float,
    n_bar  : float,
    N_fock : int = DEFAULT_N_FOCK,
) -> np.ndarray:
    """
    Analytical carrier Rabi on a thermal motional state (closed-system, Lamb-Dicke).

    P_e(t) = ½ [1 - Σ_n P_n(n̄) cos(Ω t)]

    The thermal dephasing is due to the identical Rabi frequency for all n.
    (In the Lamb-Dicke regime there is NO motional frequency shift for the
     carrier — hence the cosine does NOT depend on n, and P_e(t) = sin²(Ωt/2)
     regardless of the thermal state.)
    """
    # In the strict Lamb-Dicke limit, carrier is truly motionally blind.
    return np.sin(Omega_R * np.array(t_list) / 2) ** 2


def rsb_rabi_analytic(
    t_list : np.ndarray,
    Omega_R: float,
    eta    : float,
    n      : int,
) -> np.ndarray:
    """
    RSB Rabi for a pure Fock state |g, n⟩.

    P_e(t) = sin²(η Ω_R √n · t / 2)
    """
    if n == 0:
        return np.zeros(len(t_list))
    omega_n = eta * Omega_R * math.sqrt(n)
    return np.sin(omega_n * np.array(t_list) / 2) ** 2
