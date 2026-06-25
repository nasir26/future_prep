"""
Tests for Doppler and sideband cooling models.
Author: Nasir Ali, C-DAC Noida
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import numpy as np
import pytest

from iontrap import SidebandCooling, sideband_cooling_analytic, doppler_equilibrium


class TestAnalyticCooling:

    def test_doppler_equilibrium_formula(self):
        """n̄_D = Γ/(2η²ν) for typical 40Ca+ values."""
        Gamma   = 2 * math.pi * 22e6   # 40Ca+ S→P linewidth
        eta     = 0.1
        nu      = 2 * math.pi * 1e6    # 1 MHz trap
        n_bar_D = doppler_equilibrium(Gamma, eta, nu)
        # 40Ca+: n̄_D ≈ 22e6 / (2 × 0.01 × 1e6) = 1100
        assert 100 < n_bar_D < 10_000, f"n̄_D = {n_bar_D:.1f}"

    def test_sbc_analytic_geometric_decay(self):
        """n̄_N = n̄_0 × r^N correctly reduces phonon number."""
        n_bar_0  = 10.0
        n_cycles = 50
        r        = n_bar_0 / (n_bar_0 + 1)
        expected = n_bar_0 * (r ** n_cycles)
        got      = sideband_cooling_analytic(n_bar_0, n_cycles)
        assert abs(got - expected) < 1e-10

    def test_sbc_reaches_ground_state(self):
        """After 200 cycles from n̄=20, analytic model gives n̄ < 0.01."""
        n_bar_f = sideband_cooling_analytic(20.0, 200)
        assert n_bar_f < 0.01, f"n̄_final = {n_bar_f:.4f}"

    def test_sbc_monotone_decreasing(self):
        """Each additional cooling cycle must reduce n̄."""
        n_bar_0 = 5.0
        prev = n_bar_0
        for N in [10, 20, 50, 100]:
            curr = sideband_cooling_analytic(n_bar_0, N)
            assert curr < prev, f"n̄ not monotone: N={N} gave {curr} > {prev}"
            prev = curr

    def test_sbc_more_cycles_lower_nbar(self):
        """Higher N_cycles → lower n̄_final."""
        n0  = 15.0
        n50 = sideband_cooling_analytic(n0, 50)
        n100= sideband_cooling_analytic(n0, 100)
        assert n100 < n50


class TestQuTiPCooling:

    def test_open_system_cooling_decreases_nbar(self):
        """
        mesolve SBC: n̄ must decrease over the simulation.

        Cooling time constant in overdamped limit (Γ_rep >> ηΩ):
          τ_cool = Γ_rep / (ηΩ)² ≈ 1.3 ms for default params.
        Use t_total = 4ms (≈ 3 time constants) and check for ≥50% reduction.

        Note: N_fock=10 with n_bar_0=5 truncates the thermal state to n̄≈3
        (missing high-n tail). N_fock=15 gives n̄≈4.2.
        """
        sbc     = SidebandCooling(N_fock=15)
        n_bar_0 = 5.0
        t_total = 4e-3   # 4 ms ≈ 3 cooling time constants
        t_list, n_bar = sbc.simulate(n_bar_0, t_total, n_steps=80)
        assert n_bar[-1] < n_bar[0] / 2, (
            f"n̄ did not cool by 50%: {n_bar[0]:.2f} → {n_bar[-1]:.2f}"
        )

    def test_open_system_cooling_final_nbar(self):
        """
        mesolve SBC: n̄_final < 0.5 with optimally tuned parameters.

        For fastest cooling, Γ_rep ≈ ηΩ (critically damped).
        With Omega_R=2π×200kHz, eta=0.1:
          ηΩ = 2π×20kHz → optimal Gamma_rep ≈ 2π×20kHz
          τ_cool = Γ_rep/(4(ηΩ)²) = (2π×20kHz)/(4×(2π×20kHz)²) ≈ 2μs
        """
        sbc = SidebandCooling(
            Omega_R   = 2 * math.pi * 200e3,
            eta       = 0.1,
            Gamma_rep = 2 * math.pi * 20e3,   # ≈ ηΩ (fast cooling)
            N_fock    = 12,
        )
        n_bar_f = sbc.final_n_bar(n_bar_0=3.0, t_total=5e-4, n_steps=100)
        assert n_bar_f < 0.5, f"n̄_final = {n_bar_f:.3f}"

    def test_cooling_monotone_in_time(self):
        """mesolve SBC: n̄(t) should be non-increasing after initial transient."""
        sbc    = SidebandCooling(N_fock=8)
        _, n_bar = sbc.simulate(n_bar_0=4.0, t_total=3e-4, n_steps=60)
        # Check that the second half is lower than the first half
        assert n_bar[30:].mean() < n_bar[:30].mean()
