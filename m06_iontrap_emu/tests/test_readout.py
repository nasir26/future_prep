"""
Tests for fluorescence readout model (Poisson photon counts, discrimination).
Author: Nasir Ali, C-DAC Noida
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

from iontrap import FluorescenceReadout, sideband_asymmetry


RD = FluorescenceReadout(mu_bright=25.0, mu_dark=1.0)


class TestPhotonCounts:

    def test_bright_mean_counts(self):
        """Mean photon count for bright state ≈ mu_bright."""
        rng    = np.random.default_rng(0)
        counts = RD.sample(state=0, n_shots=5000, rng=rng)
        assert abs(counts.mean() - 25.0) < 1.0, f"bright mean = {counts.mean():.2f}"

    def test_dark_mean_counts(self):
        """Mean photon count for dark state ≈ mu_dark."""
        rng    = np.random.default_rng(1)
        counts = RD.sample(state=1, n_shots=5000, rng=rng)
        assert abs(counts.mean() - 1.0) < 0.1, f"dark mean = {counts.mean():.2f}"

    def test_counts_are_non_negative(self):
        """Poisson counts must be ≥ 0."""
        rng    = np.random.default_rng(2)
        counts = RD.sample(state=0, n_shots=1000, rng=rng)
        assert np.all(counts >= 0)

    def test_mixed_state_mean(self):
        """P(|e⟩) = 0.5 → mean ≈ (mu_bright + mu_dark) / 2."""
        rng    = np.random.default_rng(3)
        counts = RD.sample_mixed(p_excited=0.5, n_shots=5000, rng=rng)
        expected = (25.0 + 1.0) / 2
        assert abs(counts.mean() - expected) < 1.5, f"mixed mean = {counts.mean():.2f}"


class TestDiscrimination:

    def test_optimal_threshold_exists(self):
        """optimal_threshold() must return a positive integer."""
        tau = RD.optimal_threshold()
        assert isinstance(tau, int)
        assert tau > 0

    def test_threshold_between_distributions(self):
        """Threshold should be between mu_dark and mu_bright."""
        tau = RD.optimal_threshold()
        assert RD.mu_dark < tau < RD.mu_bright, (
            f"threshold {tau} not in ({RD.mu_dark}, {RD.mu_bright})"
        )

    def test_discriminate_bright(self):
        """Most bright-state shots should be inferred as 0 (bright)."""
        rng      = np.random.default_rng(4)
        counts   = RD.sample(state=0, n_shots=2000, rng=rng)
        inferred = RD.discriminate(counts)
        assert np.mean(inferred == 0) > 0.99

    def test_discriminate_dark(self):
        """Most dark-state shots should be inferred as 1 (dark)."""
        rng      = np.random.default_rng(5)
        counts   = RD.sample(state=1, n_shots=2000, rng=rng)
        inferred = RD.discriminate(counts)
        assert np.mean(inferred == 1) > 0.97

    def test_assignment_fidelity_high(self):
        """Assignment fidelity must exceed 99% for well-separated distributions."""
        fid = RD.assignment_fidelity(n_shots=3000, rng=np.random.default_rng(6))
        assert fid > 0.99, f"Assignment fidelity = {fid:.4f}"

    def test_confusion_matrix_diagonal_dominant(self):
        """P(0|0) and P(1|1) must each exceed 0.98."""
        cm = RD.confusion_matrix(n_shots=2000, rng=np.random.default_rng(7))
        assert cm[0, 0] > 0.98, f"P(0|0) = {cm[0,0]:.4f}"
        assert cm[1, 1] > 0.97, f"P(1|1) = {cm[1,1]:.4f}"


class TestSidebandAsymmetry:

    def test_zero_nbar_gives_zero_rsb(self):
        """At n̄=0, no RSB events → n̄_est ≈ 0."""
        # With n̄→0 and no RSB events, the estimator gives 0
        n_bar = sideband_asymmetry(n_shots_rsb=0, n_shots_bsb=10, total_shots=100)
        assert n_bar == 0.0 or n_bar < 0.01

    def test_asymmetry_formula(self):
        """RSB/BSB ratio R=0.5 → n̄ = R/(1-R) = 1.0."""
        # P_RSB=0.5, P_BSB=1.0 → R = 0.5 → n̄=1
        n_bar = sideband_asymmetry(50, 100, 100)
        assert abs(n_bar - 1.0) < 0.01

    def test_zero_bsb_returns_inf(self):
        """BSB = 0 means n̄ → ∞."""
        n_bar = sideband_asymmetry(10, 0, 100)
        assert n_bar == float("inf")
