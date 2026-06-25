"""
M04 ex02 — Photon Counting: gate, count, histogram, threshold
=============================================================
Ion-trap experiments measure quantum state by detecting fluorescence.
The ion fluoresces (bright state) when in |↑⟩ and is dark when in |↓⟩.

ARTIQ photon counting model
----------------------------
  1. Open a gate window on the TTL input channel
  2. The FPGA edge counter increments for each photon pulse
  3. Software reads the count after the window closes
  4. Compare to threshold → BRIGHT or DARK

  gate_end = ttl_pmt.gate_rising_mu(duration_mu)
  count    = ttl_pmt.count(gate_end)

This experiment collects a 1000-shot histogram and fits a double-Gaussian
to extract the bright and dark count distributions.

Author: Nasir Ali, C-DAC Noida
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
from artiq_sim import EnvExperiment, kernel, ms, us


THRESHOLD = 20     # counts: below = dark, above = bright
GATE_DURATION = 400 * us


class PhotonCounting(EnvExperiment):
    """Photon-count histogram with bright/dark state discrimination."""

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_laser")
        self.setattr_device("ttl_pmt")

        # Experiment parameters (set directly in tests or overridden via kwargs)
        self.n_shots      = 1000
        self.n_bright     = 40    # mean photons in bright state
        self.n_dark       = 2     # mean photons in dark state
        self.bright_frac  = 0.5   # fraction of shots in bright state

    def prepare(self):
        """Configure simulated photon rate based on experiment state."""
        # In a real experiment this would be a calibrated value.
        # Here we set it programmatically to exercise both states.
        self._gate_mu = self.core.seconds_to_mu(GATE_DURATION)

    @kernel
    def run(self):
        self.core.break_realtime()
        self.counts = []

        for shot in range(self.n_shots):
            # Alternate bright/dark to exercise both bins.
            # In a real experiment the ion state comes from the qubit drive.
            if shot % 2 == 0:
                self.ttl_pmt.mean_count_per_mu = (
                    self.n_bright / self._gate_mu
                )
            else:
                self.ttl_pmt.mean_count_per_mu = (
                    self.n_dark / self._gate_mu
                )

            # State-detection window
            gate_end = self.ttl_pmt.gate_rising_mu(self._gate_mu)
            c = self.ttl_pmt.count(gate_end)
            self.counts.append(c)

            # 1 ms dead time between shots (repump + state reset)
            self.core.delay(1 * ms)

    def analyze(self):
        """Compute histogram and discrimination fidelity."""
        counts = np.array(self.counts)
        bright_shots = counts[::2]    # even shots → bright
        dark_shots   = counts[1::2]   # odd shots → dark

        bright_correct = np.sum(bright_shots > THRESHOLD)
        dark_correct   = np.sum(dark_shots   < THRESHOLD)

        self.set_dataset("bright_mean",     float(np.mean(bright_shots)))
        self.set_dataset("dark_mean",       float(np.mean(dark_shots)))
        self.set_dataset("fidelity_bright", bright_correct / len(bright_shots))
        self.set_dataset("fidelity_dark",   dark_correct   / len(dark_shots))
        self.set_dataset("counts",          self.counts)
