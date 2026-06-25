"""
M06 ex05 — Noise Models
========================
Three realistic noise channels for a trapped-ion qubit:

1. Motional heating (phonon gain from electric-field noise):
   Adds phonons at rate ṅ (phonons/s). Modelled as Lindblad: c = √ṅ · a†.
   Fidelity impact: ΔF ≈ η² ṅ t_gate per gate.

2. Laser phase noise (linewidth dephasing):
   Phase diffusion at rate Δω_L (= 2πΔν, rad/s).
   Modelled as a z-axis dephasing collapse: c = √(Δω_L) σ_z/2.
   Fidelity impact: ΔF ≈ 1 − exp(−Δω_L t_gate / 2).

3. B-field drift (slow qubit frequency drift, Ornstein-Uhlenbeck):
   dω(t) = −γ_OU ω dt + D dW  (OU process)
   Steady-state: ⟨ω²⟩ = D / (2γ_OU) → variance σ_ω².
   Effect: random qubit frequency → phase accumulation → Ramsey decay.
   T2* ≈ 1 / σ_ω (inhomogeneous dephasing limit).

Interview note: in real systems the dominant noise is (1) at short times
(fast gate) and (3) at long times (sequences > 100 ms). Laser phase noise (2)
is the limiting factor in optical qubits (Ca+, Sr+, Yb+).

Author: Nasir Ali, C-DAC Noida
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


# ── 1. Motional heating ───────────────────────────────────────────────────────

@dataclass
class HeatingModel:
    """
    Secular (anomalous) motional heating.

    Typical values: ṅ = 10–1000 quanta/s for room-temperature traps.
    Cryogenic traps: ṅ < 1 quanta/s.
    """
    n_dot : float = 100.0   # phonons/s (heating rate)

    def phonons_added(self, t: float) -> float:
        """Mean phonons added in time t: Δn̄ = ṅ × t."""
        return self.n_dot * t

    def fidelity_loss(self, eta: float, t_gate: float) -> float:
        """
        Approximate gate fidelity loss due to heating:
          ΔF ≈ η² ṅ t_gate

        (Linearised in the weak-heating limit.)
        """
        return eta**2 * self.n_dot * t_gate

    def lindblad_op(self, ops: dict) -> object:
        """
        Return collapse operator for use with qt.mesolve.
        c = √ṅ · a†
        """
        import math
        import qutip as qt
        return math.sqrt(self.n_dot) * ops["ad"]


# ── 2. Laser phase noise ──────────────────────────────────────────────────────

@dataclass
class LaserPhaseNoise:
    """
    Laser linewidth → dephasing of the qubit.

    delta_nu : Hz — full laser linewidth (FWHM)
    The phase diffusion rate is Δω = 2π × delta_nu.
    """
    delta_nu : float = 1e3    # Hz (1 kHz laser linewidth)

    @property
    def dephasing_rate(self) -> float:
        """Dephasing rate γ_φ = 2π × delta_nu (rad/s)."""
        return 2 * math.pi * self.delta_nu

    def coherence_decay(self, t: float) -> float:
        """
        Off-diagonal coherence decay factor for time t:
          |ρ_ge(t)| / |ρ_ge(0)| = exp(−γ_φ t / 2)
        """
        return math.exp(-self.dephasing_rate * t / 2)

    def T2_laser(self) -> float:
        """T2 limited by laser linewidth: T2 = 2 / γ_φ."""
        return 2.0 / self.dephasing_rate

    def fidelity_loss(self, t_gate: float) -> float:
        """Gate fidelity loss ≈ 1 − exp(−γ_φ t_gate / 2)."""
        return 1.0 - self.coherence_decay(t_gate)

    def lindblad_op(self, ops: dict):
        """
        Return collapse operator for qt.mesolve.
        c = √γ_φ · σ_z / 2
        """
        import math, qutip as qt
        return math.sqrt(self.dephasing_rate) * ops.get("sz", qt.sigmaz()) / 2


# ── 3. B-field drift (Ornstein-Uhlenbeck) ────────────────────────────────────

@dataclass
class BFieldDrift:
    """
    Slow qubit-frequency drift modelled as an Ornstein-Uhlenbeck (OU) process.

    dx = −γ x dt + σ dW   (Langevin form)

    Parameters
    ----------
    gamma_ou : float — OU relaxation rate (1/s); 1/γ = correlation time
    sigma_ou : float — OU noise amplitude (rad/s / √s); sets steady-state std
    """
    gamma_ou : float = 1.0        # 1/s  (relaxation rate; τ_corr = 1/γ)
    sigma_ou : float = 2*math.pi*50   # rad/s / √s

    def steady_state_std(self) -> float:
        """σ_ω = σ_OU / √(2 γ) — RMS frequency fluctuation at steady state."""
        return self.sigma_ou / math.sqrt(2 * self.gamma_ou)

    def T2_star(self) -> float:
        """Inhomogeneous dephasing: T2* ≈ √2 / σ_ω (Gaussian phase noise)."""
        return math.sqrt(2) / self.steady_state_std()

    def ramsey_contrast(self, t: float) -> float:
        """
        Expected Ramsey fringe contrast at interrogation time t,
        assuming quasi-static OU noise:

          C(t) = exp(−t² σ_ω² / 2)  [Gaussian inhomogeneous broadening]
        """
        sigma_w = self.steady_state_std()
        return math.exp(-0.5 * (sigma_w * t) ** 2)

    def simulate(
        self,
        t_total  : float,
        dt       : float = 1e-3,
        seed     : int   = 42,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Simulate one OU trajectory.

        Returns
        -------
        t_arr : ndarray — time axis (0 to t_total)
        x_arr : ndarray — ω(t) (rad/s) trajectory
        """
        rng  = np.random.default_rng(seed)
        N    = int(t_total / dt) + 1
        t    = np.linspace(0, t_total, N)
        x    = np.zeros(N)
        sqrt_dt = math.sqrt(dt)
        for i in range(1, N):
            x[i] = x[i-1] - self.gamma_ou * x[i-1] * dt + self.sigma_ou * sqrt_dt * rng.standard_normal()
        return t, x

    def ramsey_shots(
        self,
        t_ramsey    : float,
        n_shots     : int = 200,
        seed        : int = 0,
    ) -> np.ndarray:
        """
        Simulate n_shots Ramsey experiments with random B-field (quasi-static).

        Each shot draws an independent ω from N(0, σ_ω), computes qubit phase
        τ_ramsey × ω, and returns cos²(phase/2) — the Ramsey fringe outcome.

        Returns
        -------
        p_excited : ndarray (n_shots,) — measured excited-state probabilities
        """
        rng    = np.random.default_rng(seed)
        sigma  = self.steady_state_std()
        omegas = rng.normal(0, sigma, size=n_shots)   # iid quasi-static draws
        phases = omegas * t_ramsey
        return np.cos(phases / 2) ** 2
