"""
M04 ex09 — Mid-Circuit Measurement + Conditional Feedback
==========================================================
Mid-circuit measurement (MCM) allows the control software to read a qubit
state during the experiment and conditionally apply a correction — all
within a single experimental sequence (no re-initialization between shots).

Ion-trap implementation
-----------------------
Ions are measured via fluorescence without irreversibly destroying the
state (the electronic state is reset by the measurement, but the qubit
is re-initialized by a fresh pump pulse).

Sequences
---------
1. Simple MCM: prepare → measure → conditional X → measure again
   Tests that the feedback corrects the state.

2. Heralded entanglement attempt:
   - Attempt: generate entangled state (e.g., via photon emission)
   - Herald: detect photon with probability p_success
   - If no herald: retry (up to N_MAX_ATTEMPTS)
   - If herald: proceed with experiment

The heralded loop is a key pattern in photonic-link quantum networking
(the topic of the role this prep targets).

ARTIQ implementation note
--------------------------
In real ARTIQ, the conditional is executed on the ARTIQ core (FPGA host)
via: if self.ttl_pmt.count(gate_end) > THRESHOLD: ...
The branch is inside the @kernel so it runs at RTIO speed without a
host round-trip.

Author: Nasir Ali, C-DAC Noida
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import math
from artiq_sim import EnvExperiment, kernel, ms, us

THRESHOLD    = 20
DETECT_DUR   = 400e-6
QUBIT_FREQ   = 200e6
PI_TIME      = 10e-6      # π-pulse time
HALF_PI_TIME = 5e-6       # π/2-pulse time


class MidCircuitMeasure(EnvExperiment):
    """
    Demonstrates mid-circuit measurement and conditional X correction.

    Scenario: prepare |↑⟩, measure (should be bright), if NOT bright apply
    an X correction (π-pulse), measure again.  After correction, the second
    measurement should always be bright.
    """

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_laser")
        self.setattr_device("ttl_pmt")
        self.setattr_device("dds_qubit")
        self.setattr_device("dds_cool")

        self.n_shots       = 100
        self.p_state_flip  = 0.2    # probability of error on first preparation

    def prepare(self):
        self._gate_mu   = self.core.seconds_to_mu(DETECT_DUR)
        self._pi_mu     = self.core.seconds_to_mu(PI_TIME)
        self._rng       = __import__("random").Random(4)

    @kernel
    def _cool(self) -> None:
        self.dds_cool.sw.on()
        self.ttl_laser.on()
        self.core.delay(2 * ms)
        self.ttl_laser.off()
        self.dds_cool.sw.off()

    @kernel
    def _measure(self) -> int:
        self.ttl_laser.on()
        gate_end = self.ttl_pmt.gate_rising_mu(self._gate_mu)
        c = self.ttl_pmt.count(gate_end)
        self.ttl_laser.off()
        return c

    @kernel
    def run(self) -> None:
        """
        Per shot:
          1. Cool + pump to |↓⟩
          2. Apply X (π-pulse) → nominally |↑⟩ (bright)
          3. With probability p_flip, simulate a state error
          4. Measure: if dark → apply X correction
          5. Second measurement should always be bright
        """
        self.core.break_realtime()
        self.dds_qubit.set(frequency=QUBIT_FREQ, amplitude=1.0)

        self.n_corrected   = 0
        self.n_uncorrected = 0
        second_counts = []

        for _ in range(self.n_shots):
            self._cool()

            # Prepare |↑⟩ with π-pulse (imperfect → p_flip chance of |↓⟩)
            self.dds_qubit.sw.pulse_mu(self._pi_mu)

            # Simulate state after preparation
            is_up = self._rng.random() > self.p_state_flip
            self.ttl_pmt.mean_count_per_mu = (
                40.0 / self._gate_mu if is_up else 2.0 / self._gate_mu
            )

            # Mid-circuit measurement
            c1 = self._measure()

            # Conditional X correction (RTIO-speed decision)
            if c1 <= THRESHOLD:
                # Detected dark: apply X to flip to bright
                self.dds_qubit.sw.pulse_mu(self._pi_mu)
                self.n_corrected += 1
                self.ttl_pmt.mean_count_per_mu = 40.0 / self._gate_mu
            else:
                self.n_uncorrected += 1
                # Already bright — no correction
                self.ttl_pmt.mean_count_per_mu = 40.0 / self._gate_mu

            # Second measurement — should always be bright after correction
            c2 = self._measure()
            second_counts.append(c2)

            self.core.break_realtime()
            self.core.delay(1 * ms)

        self.second_counts = second_counts

    def analyze(self):
        import numpy as np
        arr = np.array(self.second_counts)
        # After MCM + correction, virtually all second measurements should be bright
        p_bright_second = float(np.mean(arr > THRESHOLD))
        self.set_dataset("p_bright_second", p_bright_second)
        self.set_dataset("n_corrected",     self.n_corrected)
        self.set_dataset("n_uncorrected",   self.n_uncorrected)


class HeraldedEntanglement(EnvExperiment):
    """
    Photonic-link heralded entanglement: attempt until a photon is detected.

    Relevant for the quantum networking role at QubitCore.

    The sequence:
      1. Cool + pump both ions to |↓⟩
      2. Apply π/2 to create |↓⟩+|↑⟩ superposition on each ion
      3. Each ion attempts to emit a photon (coupling event)
      4. If photon detected (herald): entanglement succeeds → proceed
      5. If no photon: reset and retry (up to MAX_ATTEMPTS)
    """

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_laser")
        self.setattr_device("ttl_pmt")
        self.setattr_device("dds_qubit")
        self.setattr_device("dds_cool")

        self.n_experiments   = 50
        self.p_success       = 0.3    # photon emission probability per attempt
        self.max_attempts    = 20     # give up after this many misses

    def prepare(self):
        self._gate_mu      = self.core.seconds_to_mu(DETECT_DUR)
        self._half_pi_mu   = self.core.seconds_to_mu(HALF_PI_TIME)
        self._rng          = __import__("random").Random(5)
        self.herald_counts = []   # number of attempts before success

    @kernel
    def _cool(self) -> None:
        self.dds_cool.sw.on()
        self.ttl_laser.on()
        self.core.delay(2 * ms)
        self.ttl_laser.off()
        self.dds_cool.sw.off()

    @kernel
    def _attempt_herald(self) -> bool:
        """One herald attempt: returns True if photon detected."""
        # π/2 pulse (electron → photon coupling attempt)
        self.dds_qubit.sw.pulse_mu(self._half_pi_mu)

        # Gate for herald photon
        gate_end = self.ttl_pmt.gate_rising_mu(
            self.core.seconds_to_mu(1e-6)   # 1 µs photon window
        )
        # Inject success or failure into PMT
        if self._rng.random() < self.p_success:
            self.ttl_pmt.mean_count_per_mu = 1.0 / self.core.seconds_to_mu(1e-6)
        else:
            self.ttl_pmt.mean_count_per_mu = 0.0
        c = self.ttl_pmt.count(gate_end)
        return c > 0

    @kernel
    def run(self) -> None:
        self.core.break_realtime()
        self.dds_qubit.set(frequency=QUBIT_FREQ, amplitude=1.0)
        n_success = 0
        total_attempts = 0

        for _ in range(self.n_experiments):
            self._cool()

            heralded = False
            for attempt in range(1, self.max_attempts + 1):
                if self._attempt_herald():
                    n_success += 1
                    total_attempts += attempt
                    self.herald_counts.append(attempt)
                    heralded = True
                    break
                # Failed: re-cool and retry
                self._cool()

            if not heralded:
                self.herald_counts.append(self.max_attempts + 1)  # sentinel

            self.core.break_realtime()
            self.core.delay(1 * ms)

        self.n_success      = n_success
        self.total_attempts = total_attempts

    def analyze(self):
        import numpy as np
        successes = [c for c in self.herald_counts if c <= self.max_attempts]
        success_rate  = len(successes) / self.n_experiments
        mean_attempts = float(np.mean(successes)) if successes else float("inf")

        # Geometric distribution mean = 1/p_success
        expected_mean_attempts = 1.0 / self.p_success

        self.set_dataset("success_rate",         success_rate)
        self.set_dataset("mean_attempts",         mean_attempts)
        self.set_dataset("expected_mean_attempts", expected_mean_attempts)
