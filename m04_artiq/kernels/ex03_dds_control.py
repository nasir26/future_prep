"""
M04 ex03 — DDS Control: Urukul AD9910 frequency / phase / amplitude
====================================================================
Urukul is ARTIQ's quad-DDS board based on the AD9910.
In a typical ion-trap experiment:
  · 397 nm laser → AOM driven by DDS (carrier / sideband frequencies)
  · 729 nm qubit laser → similar setup
  · Microwave → direct DDS output at GHz frequencies

Key parameters
--------------
  Frequency tuning word (FTW): FTW = round(f × 2^32 / SYSCLK)
  Phase offset word (POW):     POW = round(phase_turns × 2^16)
  Amplitude scale factor (ASF): ASF = round(amplitude × 0x3FFF)

  SYSCLK = 1 GHz (AD9910 system clock)
  Frequency resolution: SYSCLK / 2^32 ≈ 0.233 Hz

DDS RF switch (sw)
------------------
Each DDS channel has an RF switch TTL output.  To gate a pulse:
  dds.sw.on()      # RF on
  delay(t_pulse)
  dds.sw.off()     # RF off
  # or: dds.sw.pulse(t_pulse)

This is faster than reprogramming the frequency register and avoids
the ~1 µs DDS initialization latency.

Author: Nasir Ali, C-DAC Noida
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from artiq_sim import EnvExperiment, kernel, ms, us, ns

# Typical ion-trap frequencies (Ca+ 40 transition example)
QUBIT_FREQ_HZ    = 200e6    # 200 MHz AOM shift on 729 nm
SIDEBAND_FREQ_HZ = 200.5e6  # carrier + motional frequency (500 kHz)
COOL_FREQ_HZ     = 100e6    # 397 nm Doppler cooling AOM


class DDSControl(EnvExperiment):
    """
    Exercises all DDS control primitives: set, set_mu, SW gating, phase.
    """

    def build(self):
        self.setattr_device("core")
        self.setattr_device("dds_qubit")
        self.setattr_device("dds_cool")
        self.setattr_device("ttl_laser")

    @kernel
    def run(self):
        self.core.break_realtime()

        # ── 1: Set cooling DDS and enable for 1 ms ─────────────────────
        self.dds_cool.set(frequency=COOL_FREQ_HZ, amplitude=0.8)
        self.dds_cool.sw.on()
        self.core.delay(1 * ms)
        self.dds_cool.sw.off()

        # ── 2: Program qubit DDS then gate pulse ───────────────────────
        # Always program BEFORE gating: write takes ~1 µs to settle.
        self.dds_qubit.set(frequency=QUBIT_FREQ_HZ,
                           phase=0.0, amplitude=1.0)
        # π-pulse (assume π-time = 10 µs for qubit_freq)
        self.dds_qubit.sw.pulse(10 * us)

        # ── 3: Phase-shifted pulse — Ramsey free evolution phase set ───
        # In Ramsey: second π/2 pulse has phase φ.
        # phase in turns: 0.0=0°, 0.25=90°, 0.5=180°
        self.dds_qubit.set(frequency=QUBIT_FREQ_HZ, phase=0.25)  # 90° phase
        self.dds_qubit.sw.pulse(5 * us)    # π/2-pulse duration

        # ── 4: Frequency sweep (carrier → sideband) ────────────────────
        # Switch to red sideband without an RF gap:
        #   1. Pre-program sideband frequency
        #   2. Gate switch in same timeline slot
        self.dds_qubit.set(frequency=SIDEBAND_FREQ_HZ, phase=0.0)
        self.core.delay(100 * ns)   # settling time (AD9910 SPI transfer)
        self.dds_qubit.sw.pulse(20 * us)   # RSB π-pulse

        # ── 5: Raw FTW/POW programming (for maximum timing precision) ──
        # Avoids floating-point conversion on the kernel side.
        # In real ARTIQ, integer arithmetic is ~8x faster than FP.
        ftw = self.dds_qubit.frequency_to_ftw(QUBIT_FREQ_HZ)
        pow_ = self.dds_qubit.turns_to_pow(0.0)
        asf  = self.dds_qubit.amplitude_to_asf(1.0)
        self.dds_qubit.set_mu(ftw, pow_, asf)
        self.dds_qubit.sw.pulse(10 * us)

    @kernel
    def freq_ramp(self, f_start: float, f_stop: float,
                  n_steps: int, step_us: float) -> None:
        """
        Linear frequency ramp from f_start to f_stop over n_steps.

        Used for frequency chirps (adiabatic passage, frequency tracking).
        """
        self.core.break_realtime()
        df = (f_stop - f_start) / (n_steps - 1)
        for k in range(n_steps):
            self.dds_qubit.set(frequency=f_start + k * df)
            self.dds_qubit.sw.on()
            self.core.delay(step_us * us)
            self.dds_qubit.sw.off()
