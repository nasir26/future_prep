"""
Tests for noise models (heating, laser phase noise, B-field drift).
Author: Nasir Ali, C-DAC Noida
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import numpy as np
import pytest

from iontrap import HeatingModel, LaserPhaseNoise, BFieldDrift


class TestHeatingModel:

    def test_phonons_added(self):
        """ṅ=100/s for 1 ms → 0.1 phonons added."""
        h = HeatingModel(n_dot=100.0)
        assert abs(h.phonons_added(1e-3) - 0.1) < 1e-12

    def test_fidelity_loss_formula(self):
        """ΔF = η² ṅ t_gate."""
        h    = HeatingModel(n_dot=100.0)
        eta  = 0.1
        t    = 1e-3
        expected = 0.01 * 100 * t   # = 0.001
        assert abs(h.fidelity_loss(eta, t) - expected) < 1e-12

    def test_zero_heating_zero_loss(self):
        h = HeatingModel(n_dot=0.0)
        assert h.fidelity_loss(0.1, 1e-3) == 0.0

    def test_fidelity_loss_increases_with_nDot(self):
        t   = 1e-3
        eta = 0.1
        ΔF1 = HeatingModel(n_dot=100).fidelity_loss(eta, t)
        ΔF2 = HeatingModel(n_dot=1000).fidelity_loss(eta, t)
        assert ΔF2 > ΔF1


class TestLaserPhaseNoise:

    def test_dephasing_rate(self):
        """Dephasing rate = 2π × delta_nu."""
        lpn = LaserPhaseNoise(delta_nu=1e3)
        assert abs(lpn.dephasing_rate - 2 * math.pi * 1e3) < 1e-6

    def test_T2_formula(self):
        """T2 = 2 / γ_φ."""
        lpn = LaserPhaseNoise(delta_nu=1e3)
        T2  = 2.0 / lpn.dephasing_rate
        assert abs(lpn.T2_laser() - T2) < 1e-12

    def test_coherence_decay_at_t0(self):
        """Coherence at t=0 must be 1."""
        lpn = LaserPhaseNoise(delta_nu=1e3)
        assert abs(lpn.coherence_decay(0.0) - 1.0) < 1e-12

    def test_coherence_decay_exponential(self):
        """Coherence must decay exponentially."""
        lpn = LaserPhaseNoise(delta_nu=1e3)
        t   = lpn.T2_laser()
        # At t = T2: |ρ_ge| / |ρ_ge(0)| = e^(-γ T2/2) = e^(-1) ≈ 0.368
        assert abs(lpn.coherence_decay(t) - math.exp(-1)) < 0.01

    def test_fidelity_loss_zero_at_t0(self):
        lpn = LaserPhaseNoise(delta_nu=1e3)
        assert lpn.fidelity_loss(0.0) == 0.0

    def test_narrow_laser_less_loss(self):
        """Narrower laser → lower fidelity loss."""
        t    = 1e-4
        ΔF_narrow = LaserPhaseNoise(delta_nu=100).fidelity_loss(t)
        ΔF_wide   = LaserPhaseNoise(delta_nu=10e3).fidelity_loss(t)
        assert ΔF_narrow < ΔF_wide


class TestBFieldDrift:

    def test_steady_state_std(self):
        """σ_ω = σ_OU / √(2 γ)."""
        bfd    = BFieldDrift(gamma_ou=1.0, sigma_ou=10.0)
        expected = 10.0 / math.sqrt(2)
        assert abs(bfd.steady_state_std() - expected) < 1e-10

    def test_T2star_formula(self):
        """T2* = √2 / σ_ω (Gaussian inhomogeneous broadening)."""
        bfd    = BFieldDrift(gamma_ou=1.0, sigma_ou=2*math.pi*50)
        T2star = math.sqrt(2) / bfd.steady_state_std()
        assert abs(bfd.T2_star() - T2star) < 1e-10

    def test_ramsey_contrast_unity_at_t0(self):
        """Ramsey contrast at t=0 must be 1."""
        bfd = BFieldDrift()
        assert abs(bfd.ramsey_contrast(0.0) - 1.0) < 1e-12

    def test_ramsey_contrast_decays(self):
        """Ramsey contrast at t=T2* must be ≈ e^(-1) ≈ 0.368.

        T2* = √2/σ_ω  →  C(T2*) = exp(-0.5 σ_ω² (√2/σ_ω)²) = exp(-1).
        """
        bfd    = BFieldDrift()
        T2star = bfd.T2_star()
        C      = bfd.ramsey_contrast(T2star)
        assert abs(C - math.exp(-1)) < 0.01

    def test_ou_trajectory_mean_zero(self):
        """OU trajectory should have mean ≈ 0 (zero-mean process)."""
        bfd = BFieldDrift(gamma_ou=10.0, sigma_ou=2*math.pi*50)
        t, x = bfd.simulate(t_total=10.0, dt=1e-3, seed=0)
        assert abs(x.mean()) < 50.0   # loose: std is σ/√(2γ) ≈ 70 rad/s

    def test_ramsey_shots_mean_decays(self):
        """
        Mean Ramsey P_e = ½(1 + C(τ)), where C(τ) = exp(-½σ²τ²).

        cos²(ωτ/2) averages to ½ + ½⟨cos(ωτ)⟩ = ½ + ½·exp(-σ²τ²/2).
        """
        bfd      = BFieldDrift(gamma_ou=1.0, sigma_ou=2*math.pi*50)
        t_ram    = bfd.T2_star() * 0.5
        shots    = bfd.ramsey_shots(t_ram, n_shots=5000, seed=0)
        contrast = bfd.ramsey_contrast(t_ram)
        expected = 0.5 + 0.5 * contrast
        assert abs(shots.mean() - expected) < 0.05, (
            f"Ramsey shots mean = {shots.mean():.3f}, expected {expected:.3f}"
        )
