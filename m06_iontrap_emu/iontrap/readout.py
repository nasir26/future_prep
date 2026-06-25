"""
M06 ex03 — State-Dependent Fluorescence Readout Model
======================================================
Ion readout: scatter photons under an S/P cycling beam for t_detect.
Bright state (|g⟩): scatter ≈ eta_bright × R × t_detect photons
Dark state  (|e⟩): scatter ≈ eta_dark  × R × t_detect photons

Photon counts are Poisson-distributed.

Typical numbers for 40Ca+:
  eta_bright ≈ 25 photons / ms  (open channel)
  eta_dark   ≈  1 photon  / ms  (off-resonant scatter / leak)
  t_detect   ≈  1 ms

Threshold discrimination: choose τ such that P(dark ≥ τ) and P(bright < τ) are
both minimised — optimal τ is found by scanning over integers.

Author: Nasir Ali, C-DAC Noida
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy import stats


@dataclass
class FluorescenceReadout:
    """
    Fluorescence-based qubit readout model.

    Parameters
    ----------
    mu_bright : float — mean photon count for bright (|g⟩) state
    mu_dark   : float — mean photon count for dark  (|e⟩) state
    """
    mu_bright : float = 25.0   # photons / detection window (|g⟩)
    mu_dark   : float = 1.0    # photons / detection window (|e⟩)

    def sample(self, state: int, n_shots: int = 1, rng: np.random.Generator = None) -> np.ndarray:
        """
        Sample photon counts for `n_shots` measurement attempts.

        Parameters
        ----------
        state  : 0 = ground (bright), 1 = excited (dark)
        n_shots: number of independent measurements

        Returns
        -------
        counts : int array of shape (n_shots,)
        """
        if rng is None:
            rng = np.random.default_rng()
        mu = self.mu_dark if state == 1 else self.mu_bright
        return rng.poisson(mu, size=n_shots)

    def sample_mixed(
        self,
        p_excited : float,
        n_shots   : int,
        rng       : np.random.Generator = None,
    ) -> np.ndarray:
        """
        Sample photon counts from a mixed qubit state with P(|e⟩) = p_excited.

        Internally samples qubit outcome first (Bernoulli), then photon count.
        """
        if rng is None:
            rng = np.random.default_rng()
        is_dark = rng.binomial(1, p_excited, size=n_shots)   # 1 = dark
        mus     = np.where(is_dark, self.mu_dark, self.mu_bright)
        return rng.poisson(mus)

    def optimal_threshold(self) -> int:
        """
        Find integer threshold τ that minimises total error probability.

        Convention: counts ≥ τ → bright (state 0); counts < τ → dark (state 1).
        Error = P(bright < τ) + P(dark ≥ τ)   [unweighted; 50-50 prior]

        Returns
        -------
        tau : int
        """
        max_count = int(self.mu_bright * 5)
        errors    = []
        for tau in range(1, max_count + 1):
            # P(bright < τ) = CDF_Poisson(τ-1, mu_bright)  [false dark]
            p_false_dark   = stats.poisson.cdf(tau - 1, self.mu_bright)
            # P(dark ≥ τ) = 1 - CDF_Poisson(τ-1, mu_dark)  [false bright]
            p_false_bright = 1 - stats.poisson.cdf(tau - 1, self.mu_dark)
            errors.append((p_false_dark + p_false_bright, tau))
        return min(errors)[1]

    def discriminate(self, counts: np.ndarray, threshold: int = None) -> np.ndarray:
        """
        Binary discrimination: 0 = bright (ground), 1 = dark (excited).

        Convention: counts ≥ τ → 0 (bright, many photons, |g⟩);
                    counts < τ → 1 (dark,   few  photons, |e⟩).
        """
        if threshold is None:
            threshold = self.optimal_threshold()
        return (np.asarray(counts) < threshold).astype(int)

    def confusion_matrix(
        self,
        n_shots    : int = 2000,
        threshold  : int = None,
        rng        : np.random.Generator = None,
    ) -> np.ndarray:
        """
        Return 2×2 confusion matrix [[P(0|0), P(1|0)], [P(0|1), P(1|1)]].

        Where row = true state, col = inferred state.
        """
        if threshold is None:
            threshold = self.optimal_threshold()
        if rng is None:
            rng = np.random.default_rng(42)
        cm = np.zeros((2, 2))
        for true_state in (0, 1):
            counts    = self.sample(true_state, n_shots, rng)
            inferred  = self.discriminate(counts, threshold)
            cm[true_state, 0] = np.mean(inferred == 0)
            cm[true_state, 1] = np.mean(inferred == 1)
        return cm

    def assignment_fidelity(
        self,
        n_shots   : int = 2000,
        threshold : int = None,
        rng       : np.random.Generator = None,
    ) -> float:
        """
        Average assignment fidelity = (P(0|0) + P(1|1)) / 2.
        """
        cm = self.confusion_matrix(n_shots, threshold, rng)
        return (cm[0, 0] + cm[1, 1]) / 2


def sideband_asymmetry(
    n_shots_rsb : int,
    n_shots_bsb : int,
    total_shots : int,
) -> float:
    """
    Estimate n̄ from RSB/BSB excitation ratio.

    P_RSB / P_BSB = n̄ / (n̄ + 1)
    → n̄ = R / (1 - R)  where R = P_RSB / P_BSB

    Parameters
    ----------
    n_shots_rsb : measured excitation events on RSB in total_shots
    n_shots_bsb : measured excitation events on BSB in total_shots
    total_shots : total shots per sideband

    Returns
    -------
    n_bar_est : estimated mean phonon number (inf if bsb=0)
    """
    p_rsb = n_shots_rsb / total_shots
    p_bsb = n_shots_bsb / total_shots
    if p_bsb < 1e-9:
        return float("inf")
    R = p_rsb / p_bsb
    return R / (1.0 - R) if R < 1 else float("inf")
