"""
M07 — QPUBackend
================
Shot-based quantum processing unit backed by the M06 iontrap_emu physics engine.

API contract
------------
All public methods return counts dicts ({"0": int, "1": int} or
{"00": int, ...}) so the rest of the stack can treat the QPU as a black box.

Physics model
-------------
- Single-qubit gate: carrier Rabi at frequency Ω_R.  A rotation by angle θ
  maps |g⟩ → cos(θ/2)|g⟩ − i sin(θ/2)|e⟩, giving P_e = sin²(θ/2).
- Two-qubit gate: Mølmer-Sørensen (MS).  For the maximally entangling case
  the analytic Bell-state fidelity is F = 1 − 2η²(n̄ + ½).
- Readout: Poisson-distributed fluorescence counts discriminated by optimal
  threshold (FluorescenceReadout from M06).

Author: Nasir Ali, C-DAC Noida
"""

from __future__ import annotations

import math
import sys
import pathlib

import numpy as np

# Locate M06 relative to this file: m07_capstone/qpu/ → m06_iontrap_emu/
_M06 = pathlib.Path(__file__).parent.parent.parent / "m06_iontrap_emu"
if str(_M06) not in sys.path:
    sys.path.insert(0, str(_M06))

from iontrap import IonTrap, FluorescenceReadout, ms_fidelity_analytic


class QPUBackend:
    """
    Single-node QPU emulator.

    Parameters
    ----------
    Omega_R : float — carrier Rabi frequency (rad/s)
    eta     : float — Lamb-Dicke parameter
    n_bar   : float — thermal phonon occupancy of COM mode
    N_fock  : int   — Fock-space truncation (smaller → faster tests)
    rng     : Generator — numpy RNG (seeded for reproducible tests)
    """

    def __init__(
        self,
        Omega_R: float = 2 * math.pi * 50e3,
        eta: float = 0.1,
        n_bar: float = 0.0,
        N_fock: int = 10,
        rng: np.random.Generator = None,
    ):
        self.Omega_R = Omega_R
        self.eta = eta
        self.n_bar = n_bar
        self.ion = IonTrap(Omega_R=Omega_R, eta=eta, N_fock=N_fock)
        self.readout = FluorescenceReadout()
        self._rng = rng if rng is not None else np.random.default_rng(42)

    # ── Single-qubit operations ─────────────────────────────────────────────

    def run_carrier(
        self,
        theta: float,
        phi: float = 0.0,
        shots: int = 200,
    ) -> dict[str, int]:
        """
        Apply a carrier pulse of rotation angle `theta` (rad) and measure.

        t_pulse = θ / Ω_R so that Ω_R · t_pulse = θ.
        Readout is discriminated fluorescence (Poisson, optimal threshold).

        Returns {"0": n_ground, "1": n_excited}.
        """
        t_pulse = abs(theta) / self.Omega_R
        t_list = np.array([0.0, t_pulse])
        p_e = self.ion.evolve_carrier(t_list, n_bar=self.n_bar, phi=phi)[-1]
        photon_counts = self.readout.sample_mixed(p_e, n_shots=shots, rng=self._rng)
        tau = self.readout.optimal_threshold()
        bits = self.readout.discriminate(photon_counts, tau)   # 1 = dark = excited
        n_excited = int(np.sum(bits))
        return {"0": shots - n_excited, "1": n_excited}

    def excited_prob_carrier(self, theta: float, phi: float = 0.0) -> float:
        """
        Noiseless P_e after a carrier rotation by `theta`.

        Calls mesolve (same code path as run_carrier) but returns the
        expectation value directly, avoiding shot noise.  Used by calibration
        routines that need a clean P_e curve to fit.
        """
        t_pulse = abs(theta) / self.Omega_R
        t_list = np.array([0.0, t_pulse])
        return float(self.ion.evolve_carrier(t_list, n_bar=self.n_bar, phi=phi)[-1])

    # ── Two-qubit (MS) operation ────────────────────────────────────────────

    def run_ms_gate(self, shots: int = 200) -> dict[str, int]:
        """
        Simulate the maximally entangling MS gate and measure both ions.

        Starting from |↓↓, n̄⟩:
          |↓↓⟩ → (|↓↓⟩ + i|↑↑⟩) / √2   (Bell state Φ+)

        Fidelity model: F = 1 − 2η²(n̄ + ½).
        With fidelity F:
          P(00) = P(11) = F/2
          P(01) = P(10) = (1−F)/2

        Returns {"00": int, "01": int, "10": int, "11": int}.
        """
        F = ms_fidelity_analytic(self.eta, self.n_bar)
        probs = np.array([F / 2, (1 - F) / 2, (1 - F) / 2, F / 2])
        probs = np.clip(probs, 0.0, 1.0)
        probs /= probs.sum()

        indices = self._rng.choice(4, size=shots, p=probs)
        labels = ["00", "01", "10", "11"]
        return {lbl: int(np.sum(indices == i)) for i, lbl in enumerate(labels)}

    # ── Circuit execution ───────────────────────────────────────────────────

    def execute_circuit(self, instructions: list, shots: int = 200) -> dict[str, int]:
        """
        Execute a compiled instruction list.

        Execution model (intentionally simplified for the capstone):
        - If any EntangleGate is present → run_ms_gate (two-qubit Bell state).
        - Otherwise, accumulate CarrierPulse angles and VirtualZ phases on
          the first measured qubit, then call run_carrier.
        - VirtualZ contributes to the effective rotation phase but not angle.
        """
        from .compiler import CarrierPulse, VirtualZ, EntangleGate, MeasureOp

        if any(isinstance(i, EntangleGate) for i in instructions):
            return self.run_ms_gate(shots=shots)

        theta_total = 0.0
        phi_eff = 0.0
        has_measure = False
        for instr in instructions:
            if isinstance(instr, CarrierPulse):
                theta_total += instr.theta
                phi_eff = instr.phi
            elif isinstance(instr, VirtualZ):
                phi_eff += instr.phi
            elif isinstance(instr, MeasureOp):
                has_measure = True

        if has_measure:
            return self.run_carrier(theta_total, phi_eff, shots)
        return {}

    # ── Utility ─────────────────────────────────────────────────────────────

    def pi_time(self) -> float:
        """Carrier π-pulse duration: t_π = π / Ω_R."""
        return self.ion.pi_time()
