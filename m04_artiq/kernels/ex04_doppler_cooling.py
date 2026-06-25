"""
M04 ex04 — Doppler Cooling + State Preparation
===============================================
Every ion-trap experiment begins with Doppler cooling followed by
state-preparation (optical pumping to |↓⟩).

Physical sequence (Ca+ 40)
--------------------------
  1. Doppler cooling:
     - 397 nm laser on (near-resonant, σ⁻ polarized) + 866 nm repumper
     - Duration: ~1–5 ms
     - Result: ion near Lamb-Dicke regime (n̄ ≈ 10–50)

  2. Optical pumping to |↓⟩:
     - 397 nm σ⁺ pumps ion into |S₁/₂, m=-1/2⟩ (our |↓⟩)
     - Duration: ~100–500 µs
     - Result: ion in |↓⟩ with >99.9% probability

  3. Sideband cooling (M04 ex07) follows → motional ground state

ARTIQ implementation
--------------------
In the experiment class, Doppler cooling is factored into a subroutine
that is called at the start of every repetition.  The subroutine is
decorated @kernel so it can be called from the main kernel without
cross-RPCs.

Author: Nasir Ali, C-DAC Noida
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from artiq_sim import EnvExperiment, kernel, portable, ms, us

# Cooling parameters (typical Ca+ numbers)
DOPPLER_DURATION     = 2 * ms       # Doppler cooling window
REPUMP_DURATION      = 2 * ms       # 866 nm repumper (same window)
PUMP_DURATION        = 200 * us     # optical pumping to |↓⟩
DETECT_DURATION      = 400 * us     # state detection window


class DopplerCooling(EnvExperiment):
    """
    Full Doppler cooling + state preparation + detection sequence.

    The 'run' kernel repeatedly executes:
      cool → pump → (probe pulse) → detect

    This is the skeleton for every real ion-trap experiment.
    """

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_laser")   # 397 nm Doppler / pump gate
        self.setattr_device("ttl_pmt")     # photon counter
        self.setattr_device("dds_cool")    # 397 nm AOM
        self.setattr_device("dds_qubit")   # qubit drive (unused in this ex)

        self.n_reps      = 100
        self.probe_us    = 0.0   # no qubit drive in bare cooling experiment

    def prepare(self):
        self._gate_mu  = self.core.seconds_to_mu(DETECT_DURATION)
        # Simulate bright state after cooling: ~40 counts/window
        self.ttl_pmt.set_mean_count(40.0, DETECT_DURATION)

    @kernel
    def cool_and_pump(self) -> None:
        """
        Subroutine: Doppler cooling followed by optical pumping.

        Call this at the start of every shot.  It consumes:
          DOPPLER_DURATION + PUMP_DURATION of timeline.
        """
        # Doppler cooling: both 397 and 866 on simultaneously
        self.ttl_laser.on()           # 397 nm gate
        self.dds_cool.sw.on()         # 866 nm repumper (routed through dds_cool.sw)
        self.core.delay(DOPPLER_DURATION)
        self.ttl_laser.off()
        self.dds_cool.sw.off()

        # Optical pumping to |↓⟩ (σ⁺ light, shorter duration)
        self.ttl_laser.on()
        self.core.delay(PUMP_DURATION)
        self.ttl_laser.off()

    @kernel
    def detect(self) -> int:
        """
        State detection: open PMT gate, return photon count.

        Returns
        -------
        int : number of photons detected in DETECT_DURATION window
        """
        self.ttl_laser.on()   # detection light (σ⁻ polarized for cycling)
        gate_end = self.ttl_pmt.gate_rising_mu(self._gate_mu)
        count = self.ttl_pmt.count(gate_end)
        self.ttl_laser.off()
        return count

    @kernel
    def run(self) -> None:
        self.core.break_realtime()
        self.counts = []

        for _ in range(self.n_reps):
            self.cool_and_pump()

            # Optional probe pulse (overridden in subclasses / Rabi ex)
            if self.probe_us > 0:
                self.dds_qubit.sw.pulse(self.probe_us * us)

            count = self.detect()
            self.counts.append(count)

            # Inter-shot dead time
            self.core.delay(1 * ms)
            # Reset cursor margin for next shot
            self.core.break_realtime()

    def analyze(self):
        import numpy as np
        counts = np.array(self.counts)
        self.set_dataset("mean_count",  float(np.mean(counts)))
        self.set_dataset("std_count",   float(np.std(counts)))
        self.set_dataset("counts",      self.counts)
