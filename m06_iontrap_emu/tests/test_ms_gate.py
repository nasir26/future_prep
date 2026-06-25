"""
Tests for two-ion MS gate (Bell state generation, fidelity).
Author: Nasir Ali, C-DAC Noida
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import numpy as np
import pytest

from iontrap import MSGate, ms_fidelity_analytic


class TestMSGateAnalytic:

    def test_ideal_fidelity_cold(self):
        """Analytic fidelity at n̄=0, η=0.1: F ≈ 1 − 2×0.01×0.5 = 0.99."""
        F = ms_fidelity_analytic(eta=0.1, n_bar=0.0)
        assert abs(F - 0.99) < 1e-6

    def test_fidelity_decreases_with_nbar(self):
        """Fidelity must decrease as motional temperature rises."""
        F0  = ms_fidelity_analytic(0.1, 0.0)
        F5  = ms_fidelity_analytic(0.1, 5.0)
        F20 = ms_fidelity_analytic(0.1, 20.0)
        assert F0 > F5 > F20

    def test_fidelity_decreases_with_eta(self):
        """Fidelity must decrease for larger Lamb-Dicke parameter."""
        F_small = ms_fidelity_analytic(0.05, 0.0)
        F_large = ms_fidelity_analytic(0.20, 0.0)
        assert F_small > F_large

    def test_fidelity_clamped_to_zero(self):
        """Fidelity should not go negative for extreme parameters."""
        F = ms_fidelity_analytic(eta=0.5, n_bar=100.0)
        assert F >= 0.0

    def test_gate_time_formula(self):
        """t_gate = π δ / (8 (ηΩ)²) — derived for single-loop closure at δ=4ηΩ."""
        gate = MSGate(Omega_R=2*math.pi*50e3, eta=0.1, delta=2*math.pi*5e3)
        expected = math.pi * gate.delta / (8 * (gate.eta * gate.Omega_R)**2)
        assert abs(gate.gate_time() - expected) < 1e-15


class TestMSGateQuTiP:

    def test_bell_fidelity_ideal(self):
        """
        Bell fidelity > 0.90 at ideal gate time with n̄=0.

        Gate physics: H = ηΩ (σ_x^1 + σ_x^2)(a e^{iδt} + h.c.).
        Magnus expansion for M closed loops: U = exp(-iθ σ_x^1σ_x^2),
          θ = 4πM(ηΩ)²/δ².
        For θ = π/4 with M=1 (single loop): δ = 4ηΩ.
        Gate time from gate_time() = πδ/(8(ηΩ)²) = π/(2ηΩ) = 2π/δ  ✓

        Result: (|gg⟩ - i|ee⟩)/√2  (Bell state with -i phase).
        """
        eta     = 0.1
        Omega_R = 2 * math.pi * 50e3
        delta   = 4 * eta * Omega_R         # = 2π×20 kHz, satisfies δ = 4ηΩ
        gate = MSGate(
            Omega_R = Omega_R,
            eta     = eta,
            delta   = delta,
            N_fock  = 8,
            n_bar   = 0.0,
        )
        F = gate.bell_fidelity()
        assert F > 0.90, f"Bell fidelity = {F:.4f}"

    def test_entanglement_signature(self):
        """
        After the MS gate (δ=4ηΩ, single closed loop), each ion has P_e ≈ 0.5.

        For Bell state (|gg⟩-i|ee⟩)/√2: reduced state of each qubit is
        ρ = I/2, so ⟨P_e⟩ = 0.5 — the signature of maximal entanglement
        (not achievable from a product state).
        """
        eta     = 0.1
        Omega_R = 2 * math.pi * 50e3
        delta   = 4 * eta * Omega_R   # = 2π×20 kHz, loop-closure condition
        gate    = MSGate(Omega_R=Omega_R, eta=eta, delta=delta, N_fock=6, n_bar=0.0)
        t_gate  = gate.gate_time()
        t_list  = np.linspace(0, t_gate, 60)
        _, p1, p2 = gate.run(t_list)
        assert 0.3 < p1[-1] < 0.7, f"P_e(ion1) at t_gate = {p1[-1]:.3f}"
        assert 0.3 < p2[-1] < 0.7, f"P_e(ion2) at t_gate = {p2[-1]:.3f}"
