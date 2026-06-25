"""
M06 ex02 — Doppler and Sideband Cooling Models
===============================================
Two cooling models with different levels of realism:

1. Doppler cooling — analytic equilibrium + exponential approach:
   n̄_D = Γ / (2 η² ν)  where Γ = laser linewidth, ν = trap frequency
   In practice n̄_D ≈ 5–20 for 40Ca+ at ν=1 MHz, Γ=2π×22 MHz.

2. Sideband cooling — per-cycle geometric model (physical):
   Each RSB + repump cycle removes exactly one phonon from the Fock ladder
   in the ideal Lamb-Dicke limit.
   After N cycles:  n̄_N = n̄_0 · r^N  where r = n̄_0 / (n̄_0 + 1)
   This was derived in M04; here we verify it with QuTiP mesolve.

3. QuTiP mesolve version — open-system sideband cooling using Lindblad:
   Collapse operators:
     c1 = sqrt(Γ_rep) * σ_m ⊗ I_m   (repump: |e,n-1⟩ → |g,n-1⟩)
     c2 = sqrt(n_heat) * a†           (heating: residual phonon gain)
   Hamiltonian:
     H = ηΩ/2 (σ+ a + σ- a†)         (RSB drive: removes phonons)

Author: Nasir Ali, C-DAC Noida
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import qutip as qt

from .operators import KET_G, build_single_ion_ops, thermal_dm, ion_state


# ── Analytic models ───────────────────────────────────────────────────────────

def doppler_equilibrium(
    Gamma   : float,   # laser linewidth (rad/s), e.g., 2π×22 MHz for Ca+ S→P
    eta     : float,   # Lamb-Dicke parameter
    nu_trap : float,   # trap frequency (rad/s), e.g., 2π×1 MHz
) -> float:
    """
    Doppler cooling equilibrium phonon number.

    n̄_D = Γ / (2 η² ν_trap)

    This is the Lamb-Dicke approximation valid when n̄ η² ≪ 1.
    """
    return Gamma / (2 * eta**2 * nu_trap)


def sideband_cooling_analytic(
    n_bar_0  : float,   # initial mean phonon number
    n_cycles : int,     # number of RSB + repump cycles
) -> float:
    """
    Analytic sideband cooling after N ideal RSB + repump cycles.

    Each cycle: n̄ → n̄ · r  where r = n̄ / (n̄ + 1)
    Physical picture: RSB maps |g,n⟩ → |e,n-1⟩; repump resets to |g,n-1⟩.
    Net: one phonon removed per cycle in the Lamb-Dicke + weak-binding limit.

    After N cycles: n̄_N = n̄_0 · r^N  (r = n̄_0 / (n̄_0 + 1))
    """
    r = n_bar_0 / (n_bar_0 + 1.0)
    return n_bar_0 * (r ** n_cycles)


@dataclass
class SidebandCooling:
    """
    QuTiP open-system sideband cooling simulation.

    Simulates N_cycles of RSB drive + instantaneous repump using mesolve.
    Repump is modelled as a collapse operator with large rate Gamma_rep,
    which rapidly resets the qubit to |g⟩ after each RSB-induced excitation.

    This is not a pulse-by-pulse simulation: instead, the RSB drive and the
    repump collapse operator act simultaneously, giving the Lindblad steady
    state equivalent to the per-cycle geometric model.
    """
    Omega_R   : float = 2 * math.pi * 50e3   # RSB Rabi frequency (rad/s)
    eta       : float = 0.1                   # Lamb-Dicke parameter
    Gamma_rep : float = 2 * math.pi * 200e3  # repump rate (rad/s); >> Omega_R
    n_heat    : float = 0.0                   # heating rate (phonons/s)
    N_fock    : int   = 15

    def simulate(
        self,
        n_bar_0  : float,
        t_total  : float,    # total cooling time (s)
        n_steps  : int = 200,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Run cooling simulation for t_total seconds.

        Returns
        -------
        t_list : ndarray (n_steps,) — time axis
        n_bar  : ndarray (n_steps,) — ⟨n̂⟩ vs time
        """
        ops  = build_single_ion_ops(self.N_fock)
        rho0 = ion_state(KET_G, thermal_dm(n_bar_0, self.N_fock))
        t_list = np.linspace(0, t_total, n_steps)

        # RSB Hamiltonian (removes phonons)
        H = (self.eta * self.Omega_R / 2) * (
            ops["sp"] * ops["a"] + ops["sm"] * ops["ad"]
        )

        # Collapse operators
        c_ops = [
            math.sqrt(self.Gamma_rep) * ops["sm"],   # fast repump |e⟩→|g⟩
        ]
        if self.n_heat > 0:
            c_ops.append(math.sqrt(self.n_heat) * ops["ad"])

        res = qt.mesolve(H, rho0, t_list, c_ops, e_ops=[ops["n_op"]])
        return t_list, np.array(res.expect[0]).real

    def final_n_bar(self, n_bar_0: float, t_total: float, n_steps: int = 200) -> float:
        _, n_bar_arr = self.simulate(n_bar_0, t_total, n_steps)
        return float(n_bar_arr[-1])
