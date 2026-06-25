"""
M04 ex07 — Sideband Cooling
============================
After Doppler cooling, the ion has n̄ ≈ 10–50 motional quanta.
Sideband cooling brings it to the motional ground state (n̄ < 0.1).

Protocol
--------
Repeat N times:
  1. RSB π-pulse (ω₀ − ν): |↑,n⟩ → |↓,n−1⟩
  2. Repump (397 nm): |↑,n−1⟩ → |↓,n−1⟩ (reset electronic state)

After N cycles, population cascades to |↓,0⟩ (ground state).

Verification: sideband asymmetry
---------------------------------
The motional occupation n̄ is measured via the sideband asymmetry:
  Ω_RSB / Ω_BSB = √(n̄ / (n̄+1))

After good sideband cooling:
  Ω_RSB → 0 (no phonons to remove)
  Ω_BSB stays finite (can add phonon to |0⟩)

In simulation: after N cooling cycles, n̄ decays exponentially.
  n̄(N) = n̄₀ · exp(−η² · N)  where η ≈ 0.1 is the Lamb-Dicke parameter.

Author: Nasir Ali, C-DAC Noida
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import math
import numpy as np
from artiq_sim import EnvExperiment, kernel, ms, us

# Ca+ 40 sideband cooling parameters
QUBIT_FREQ   = 200e6        # carrier frequency (MHz AOM shift)
N_COOL_HZ    = 500e3        # ν_COM = 500 kHz motional frequency
RSB_FREQ     = QUBIT_FREQ - N_COOL_HZ   # red sideband
BSB_FREQ     = QUBIT_FREQ + N_COOL_HZ   # blue sideband
ETA          = 0.1          # Lamb-Dicke parameter
RSB_PI_TIME  = 50e-6        # RSB π-pulse time (longer than carrier; scales as 1/√n)
REPUMP_TIME  = 5e-6         # repumper (866 nm) pulse duration
THRESHOLD    = 20
DETECT_DUR   = 400e-6


class SidebandCooling(EnvExperiment):
    """
    Sideband cooling loop + n̄ verification via sideband asymmetry Rabi.
    """

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_laser")
        self.setattr_device("ttl_pmt")
        self.setattr_device("dds_qubit")
        self.setattr_device("dds_cool")

        self.n_cool_cycles = 150    # number of RSB+repump cycles
        self.n_bar_0       = 20.0  # initial mean phonon number
        self.n_shots       = 50    # shots per sideband-asymmetry point

    def prepare(self):
        self._gate_mu    = self.core.seconds_to_mu(DETECT_DUR)
        self._rsb_pi_mu  = self.core.seconds_to_mu(RSB_PI_TIME)
        self._repump_mu  = self.core.seconds_to_mu(REPUMP_TIME)
        self._rng        = __import__("random").Random(2)

        # Each RSB+repump cycle removes one phonon from the Fock ladder.
        # For a thermal state, the geometric decay is r = n̄₀/(n̄₀+1) per cycle.
        # This is exact in the Lamb-Dicke limit where one phonon is removed per pulse.
        r = self.n_bar_0 / (self.n_bar_0 + 1.0)
        self.n_bar_final = self.n_bar_0 * (r ** self.n_cool_cycles)

    @kernel
    def _cool(self) -> None:
        self.dds_cool.sw.on()
        self.ttl_laser.on()
        self.core.delay(2 * ms)
        self.ttl_laser.off()
        self.dds_cool.sw.off()

    @kernel
    def sideband_cool(self) -> None:
        """Execute N_cool RSB + repump cycles."""
        self.dds_qubit.set(frequency=RSB_FREQ, amplitude=1.0)
        for _ in range(self.n_cool_cycles):
            # RSB π-pulse: |↑,n⟩ → |↓,n−1⟩
            self.dds_qubit.sw.pulse_mu(self._rsb_pi_mu)
            # Repump: optically pump back to |↓⟩
            self.dds_cool.sw.pulse_mu(self._repump_mu)

    @kernel
    def _rabi_shot(self, freq: float, tau_mu: int) -> int:
        """One shot: cool → sideband-cool → drive → detect."""
        self._cool()
        self.sideband_cool()
        self.dds_qubit.set(frequency=freq)
        self.dds_qubit.sw.pulse_mu(tau_mu)
        self.ttl_laser.on()
        gate_end = self.ttl_pmt.gate_rising_mu(self._gate_mu)
        c = self.ttl_pmt.count(gate_end)
        self.ttl_laser.off()
        return c

    @kernel
    def run(self) -> None:
        """
        Sideband asymmetry measurement:
          · RSB Rabi flop at τ = RSB_PI_TIME → gives P_RSB
          · BSB Rabi flop at τ = RSB_PI_TIME → gives P_BSB
          Ratio P_RSB / P_BSB ≈ n̄ / (n̄ + 1)
        """
        self.core.break_realtime()
        n_exc_rsb = 0
        n_exc_bsb = 0

        for _ in range(self.n_shots):
            # RSB shot: excitation ∝ n̄ (ground state → no transition)
            n_bar  = self.n_bar_final
            p_rsb  = (n_bar / (n_bar + 1)) * math.sin(math.pi * 0.5) ** 2
            mean_r = 40.0 if self._rng.random() < p_rsb else 2.0
            self.ttl_pmt.mean_count_per_mu = mean_r / self._gate_mu
            c = self._rabi_shot(RSB_FREQ, self._rsb_pi_mu)
            if c > THRESHOLD:
                n_exc_rsb += 1
            self.core.break_realtime()

            # BSB shot: excitation ∝ (n̄+1)
            p_bsb  = math.sin(math.pi * 0.5) ** 2   # ≈ 1 for any n̄
            mean_b = 40.0 if self._rng.random() < p_bsb else 2.0
            self.ttl_pmt.mean_count_per_mu = mean_b / self._gate_mu
            c = self._rabi_shot(BSB_FREQ, self._rsb_pi_mu)
            if c > THRESHOLD:
                n_exc_bsb += 1
            self.core.break_realtime()

        self.p_rsb = n_exc_rsb / self.n_shots
        self.p_bsb = n_exc_bsb / self.n_shots

    def analyze(self):
        """Extract n̄ from sideband asymmetry P_RSB / P_BSB = n̄ / (n̄+1)."""
        if self.p_bsb > 0:
            ratio  = self.p_rsb / self.p_bsb
            n_bar  = ratio / (1.0 - ratio) if ratio < 1 else float("inf")
        else:
            n_bar  = float("inf")

        self.set_dataset("n_bar_measured", n_bar)
        self.set_dataset("n_bar_expected", self.n_bar_final)
        self.set_dataset("p_rsb",          self.p_rsb)
        self.set_dataset("p_bsb",          self.p_bsb)
