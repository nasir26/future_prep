"""
Tests for single-ion IonTrap (carrier, RSB, BSB Rabi dynamics).
Author: Nasir Ali, C-DAC Noida
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import numpy as np
import pytest

from iontrap import IonTrap, carrier_rabi_analytic, rsb_rabi_analytic


OMEGA_R = 2 * math.pi * 50e3    # 50 kHz Rabi frequency
ETA     = 0.1


class TestCarrierRabi:

    def test_pi_time_definition(self):
        """t_π = π / Ω_R."""
        ion = IonTrap(Omega_R=OMEGA_R)
        t_pi = ion.pi_time()
        assert abs(t_pi - math.pi / OMEGA_R) < 1e-12

    def test_p_e_at_pi_equals_one(self):
        """P_e(t_π) ≈ 1 for carrier on |g,0⟩ (no heating, no decay).

        tlist must start at 0 (QuTiP convention: tlist[0] = initial time).
        """
        ion    = IonTrap(Omega_R=OMEGA_R, N_fock=5)
        t_pi   = ion.pi_time()
        t_list = np.linspace(0, t_pi, 50)   # include t=0 as initial time
        p_e    = ion.evolve_carrier(t_list, n_bar=0.0)
        assert p_e[-1] > 0.99, f"P_e(t_π) = {p_e[-1]:.4f}, expected ≈ 1"

    def test_p_e_at_zero_is_zero(self):
        """P_e(0) = 0 (start in ground state)."""
        ion = IonTrap(Omega_R=OMEGA_R, N_fock=5)
        p_e = ion.evolve_carrier(np.array([0.0]), n_bar=0.0)
        assert p_e[0] < 0.01

    def test_rabi_oscillation_period(self):
        """P_e must return to < 0.01 at t = 2t_π (full oscillation)."""
        ion    = IonTrap(Omega_R=OMEGA_R, N_fock=5)
        t_pi   = ion.pi_time()
        t_list = np.linspace(0, 2 * t_pi, 60)
        p_e    = ion.evolve_carrier(t_list, n_bar=0.0)
        assert p_e[-1] < 0.02, f"P_e(2t_π) = {p_e[-1]:.4f}, expected ≈ 0"

    def test_matches_analytic(self):
        """QuTiP result must agree with sin²(Ωt/2) within 1% for n_bar=0."""
        ion    = IonTrap(Omega_R=OMEGA_R, N_fock=6)
        t_pi   = ion.pi_time()
        t_list = np.linspace(0, t_pi, 20)
        p_qutip = ion.evolve_carrier(t_list, n_bar=0.0)
        p_anal  = carrier_rabi_analytic(t_list, OMEGA_R, n_bar=0.0)
        err     = np.max(np.abs(p_qutip - p_anal))
        assert err < 0.01, f"Max deviation from analytic: {err:.4f}"

    def test_thermal_state_reduces_contrast(self):
        """Carrier Rabi on thermal state: peak P_e ≈ 1 (carrier is motionally blind in LD).

        tlist must start at 0 (QuTiP convention: tlist[0] = initial time).
        """
        ion    = IonTrap(Omega_R=OMEGA_R, N_fock=15)
        t_pi   = ion.pi_time()
        t_list = np.linspace(0, t_pi, 40)
        p_cold = ion.evolve_carrier(t_list, n_bar=0.0)[-1]
        p_hot  = ion.evolve_carrier(t_list, n_bar=5.0)[-1]
        # In the Lamb-Dicke regime, carrier is motionally blind → peak ≈ 1 for both
        assert p_cold > 0.98
        assert p_hot  > 0.90


class TestRSBRabi:

    def test_dark_state_n0(self):
        """RSB: |g,0⟩ is a dark state — P_e must stay ≈ 0."""
        ion    = IonTrap(Omega_R=OMEGA_R, eta=ETA, N_fock=5)
        t_list = np.linspace(0, ion.pi_time() * 3, 30)
        p_e    = ion.evolve_rsb(t_list, n_bar=0.0)
        assert max(p_e) < 0.05, f"RSB dark-state P_e max = {max(p_e):.4f}"

    def test_rsb_pi_time_n1(self):
        """RSB on |g,1⟩: P_e should reach ≈ 1 at t_π_RSB = π/(η Ω √1).

        tlist must start at 0 (QuTiP convention: tlist[0] = initial time).
        """
        import qutip as qt
        from iontrap.operators import KET_G

        ion    = IonTrap(Omega_R=OMEGA_R, eta=ETA, N_fock=8)
        t_pi_r = ion.rsb_pi_time(n=1)
        n_fock = ion.N_fock

        fock_1 = qt.basis(n_fock, 1)
        rho0   = qt.tensor(qt.ket2dm(KET_G), qt.ket2dm(fock_1))

        H   = ion._H_rsb()
        ops = ion._ops
        # tlist must include t=0; we check the value at the last point
        tlist = np.linspace(0, t_pi_r, 50)
        res   = qt.mesolve(H, rho0, tlist, [], e_ops=[ops["pe"]])
        p_e   = float(res.expect[0][-1])
        assert p_e > 0.95, f"RSB π-time P_e = {p_e:.4f}, expected ≈ 1"

    def test_rsb_analytic_n2(self):
        """Analytic RSB for |g,2⟩: P_e(t_π) = 1 at t_π = π/(ηΩ√2)."""
        n    = 2
        t_pi = math.pi / (ETA * OMEGA_R * math.sqrt(n))
        p_e  = rsb_rabi_analytic(np.array([t_pi]), OMEGA_R, ETA, n)
        assert abs(p_e[0] - 1.0) < 1e-6

    def test_bsb_not_dark_at_n0(self):
        """BSB: |g,0⟩ is NOT dark — it drives |g,0⟩ → |e,1⟩.

        The BSB π-time for |g,0⟩→|e,1⟩ is t_π_BSB = π/(η Ω), which is
        1/η = 10× longer than the carrier π-time.  We must scan to t_π_BSB.
        """
        ion       = IonTrap(Omega_R=OMEGA_R, eta=ETA, N_fock=6)
        t_bsb_pi  = math.pi / (ETA * OMEGA_R)   # = π/(η Ω)
        t_list    = np.linspace(0, t_bsb_pi, 40)
        p_e       = ion.evolve_bsb(t_list, n_bar=0.0)
        assert max(p_e) > 0.5, f"BSB on |g,0⟩ max P_e = {max(p_e):.4f}"
