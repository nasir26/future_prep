"""
M04 ex08 — Mølmer-Sørensen (MS) Gate
=======================================
The MS gate is the workhorse two-qubit gate in ion-trap quantum computing.
It entangles two ions through their shared motional mode.

Physics
-------
Drive BOTH ions simultaneously with two tones at ω_q ± δ:
  · Tone 1: ω_q + δ (blue of carrier, red of motional mode)
  · Tone 2: ω_q − δ (red of carrier, blue of motional mode)

The detuning δ drives a closed loop in phase space, accumulating a
geometric phase.  For the MS gate, we set:
  δ = ν_COM − ε   (slightly off the motional resonance)

After a gate time τ_gate = 1/ε, the geometric phase φ = π/4, giving
the maximally entangling XX gate:
  |00⟩ + |11⟩ (Bell state)

Two-tone DDS pulse
------------------
In ARTIQ, each ion can be driven by a separate DDS channel, or both by the
same channel switching rapidly between tones (bichromatic drive).
Here we simulate a bichromatic drive on a single DDS by rapidly
toggling frequency:
  for each modulation cycle (period 1/2δ):
    set(ω_q + δ); sw.pulse(T_half)
    set(ω_q − δ); sw.pulse(T_half)

Gate fidelity (ideal)
---------------------
F = 1 − (2η² n̄) · correction  for n̄ ≈ 0 after sideband cooling.

Author: Nasir Ali, C-DAC Noida
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import math
import numpy as np
from artiq_sim import EnvExperiment, kernel, ms, us

# Gate parameters
QUBIT_FREQ = 200e6
MOTIONAL_FREQ = 500e3        # ν_COM in Hz
GATE_DETUNING = 5e3          # ε in Hz; δ = ν − ε
GATE_DELTA    = MOTIONAL_FREQ - GATE_DETUNING
GATE_TIME     = 1 / GATE_DETUNING     # τ_gate = 1/ε = 200 µs
ETA           = 0.1          # Lamb-Dicke parameter
N_MODCYCLES   = int(GATE_DELTA * GATE_TIME)   # ~100 modulation cycles
DETECT_DUR    = 400e-6
THRESHOLD     = 20


class MSGate(EnvExperiment):
    """
    Two-qubit MS gate pulse skeleton with Bell-state fidelity estimation.

    In simulation, we compute the ideal gate fidelity from the Lamb-Dicke
    parameter and mean phonon number, rather than a full density-matrix
    simulation (that is covered in M06 iontrap_emu).
    """

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_laser")
        self.setattr_device("ttl_pmt")
        self.setattr_device("dds_qubit")
        self.setattr_device("dds_cool")

        self.n_shots     = 50
        self.n_bar       = 0.05    # motional occupation after sideband cooling
        self.eta         = ETA

    def prepare(self):
        self._gate_mu     = self.core.seconds_to_mu(DETECT_DUR)
        self._half_t_mu   = self.core.seconds_to_mu(GATE_TIME / (2 * N_MODCYCLES))
        # Ideal gate fidelity (Sørensen-Mølmer formula, simplified)
        # F_ideal = 1 - 2η²(n̄ + 1/2) * correction_from_detuning_error
        self.fidelity_ideal = 1.0 - 2 * (self.eta**2) * (self.n_bar + 0.5) * 0.01
        self._rng = __import__("random").Random(3)

    @kernel
    def _cool(self) -> None:
        self.dds_cool.sw.on()
        self.ttl_laser.on()
        self.core.delay(2 * ms)
        self.ttl_laser.off()
        self.dds_cool.sw.off()

    @kernel
    def ms_gate_pulse(self) -> None:
        """
        Bichromatic MS gate pulse.

        Drives two tones at ω_q ± δ by rapidly alternating the DDS frequency.
        N_MODCYCLES sets the bichromatic period count over the gate time.
        """
        f_blue = QUBIT_FREQ + GATE_DELTA
        f_red  = QUBIT_FREQ - GATE_DELTA

        for _ in range(N_MODCYCLES):
            self.dds_qubit.set(frequency=f_blue, amplitude=1.0)
            self.dds_qubit.sw.pulse_mu(self._half_t_mu)
            self.dds_qubit.set(frequency=f_red, amplitude=1.0)
            self.dds_qubit.sw.pulse_mu(self._half_t_mu)

    @kernel
    def _detect_both(self):
        """
        Detect both ions (same PMT in trapped-ion systems typically, or separate).
        Here we detect one PMT and infer Bell correlations.
        """
        self.ttl_laser.on()
        gate_end = self.ttl_pmt.gate_rising_mu(self._gate_mu)
        c = self.ttl_pmt.count(gate_end)
        self.ttl_laser.off()
        return c

    @kernel
    def run(self) -> None:
        self.core.break_realtime()
        n_bell = 0   # shots that yielded a Bell-state outcome

        for _ in range(self.n_shots):
            self._cool()
            self.ms_gate_pulse()
            c = self._detect_both()

            # Simulate Bell-state outcome: both bright or both dark
            # P(Bell) = fidelity_ideal; rest is mixed state
            is_bell = self._rng.random() < self.fidelity_ideal
            if is_bell:
                # In Bell state: half the shots give 00 (dark), half give 11 (bright)
                mean = 40.0 if self._rng.random() < 0.5 else 2.0
            else:
                mean = 20.0   # mixed
            self.ttl_pmt.mean_count_per_mu = mean / self._gate_mu

            if c > THRESHOLD:
                n_bell += 1

            self.core.break_realtime()
            self.core.delay(1 * ms)

        self.p_bell = n_bell / self.n_shots

    def analyze(self):
        # True Bell-state fidelity requires parity measurement (not done here).
        # We report the raw bright-state probability as a proxy.
        self.set_dataset("p_bell_proxy",  self.p_bell)
        self.set_dataset("fidelity_ideal", self.fidelity_ideal)
        self.set_dataset("n_gate_cycles",  N_MODCYCLES)
