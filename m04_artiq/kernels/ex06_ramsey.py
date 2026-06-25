"""
M04 ex06 — Ramsey Spectroscopy + CoreDMA
=========================================
Ramsey spectroscopy measures the qubit frequency with higher precision
than a Rabi scan by exploiting free precession.

Sequence
--------
  1. π/2 pulse at phase 0
  2. Free evolution for time T
  3. π/2 pulse at phase φ   ← scan φ to get the Ramsey fringe
  4. Detect

The excitation probability is:
  P(φ) = 0.5 · (1 + cos(φ + Δω · T))

where Δω = ω_qubit − ω_drive is the detuning.  Fitting the cosine
gives ω_qubit with precision ~1/(T · √N) where N is the number of shots.

CoreDMA usage
-------------
In a Ramsey scan with many shots, the Doppler cooling sequence is
identical every repetition.  CoreDMA records it once and replays it
via FPGA DMA, saving ~3 µs of kernel overhead per shot.

  with self.dma.record("cooling"):
      self._cool()
  h = self.dma.get_handle("cooling")
  # in shot loop:
  self.dma.playback(h)

Author: Nasir Ali, C-DAC Noida
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import math
import numpy as np
from scipy.optimize import curve_fit
from artiq_sim import EnvExperiment, kernel, ms, us

THRESHOLD       = 20
DETECT_DURATION = 400 * us
QUBIT_FREQ      = 200e6
HALF_PI_TIME    = 5e-6       # π/2-pulse duration (10 µs π-time / 2)
FREE_EVOL_TIME  = 50e-6      # free evolution window T


class Ramsey(EnvExperiment):
    """
    Ramsey fringe via phase scan; uses CoreDMA to record cooling sequence.

    Experiment parameters
    ---------------------
    phase_list     : list of phases in turns (0–1)
    n_shots        : shots per phase point
    free_evol_s    : free evolution time T
    """

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_laser")
        self.setattr_device("ttl_pmt")
        self.setattr_device("dds_qubit")
        self.setattr_device("dds_cool")
        self.setattr_device("dma")

        self.phase_list  = [k / 20 for k in range(20)]   # 0..0.95 in turns
        self.n_shots     = 50
        self.free_evol_s = FREE_EVOL_TIME
        self.n_bright    = 40
        self.n_dark      = 2

    def prepare(self):
        self._gate_mu   = self.core.seconds_to_mu(DETECT_DURATION)
        self._half_pi_mu = self.core.seconds_to_mu(HALF_PI_TIME)
        self._rng       = __import__("random").Random(1)

    @kernel
    def _cool(self) -> None:
        self.dds_cool.sw.on()
        self.ttl_laser.on()
        self.core.delay(2 * ms)
        self.ttl_laser.off()
        self.dds_cool.sw.off()

    @kernel
    def _detect(self) -> int:
        self.ttl_laser.on()
        gate_end = self.ttl_pmt.gate_rising_mu(self._gate_mu)
        c = self.ttl_pmt.count(gate_end)
        self.ttl_laser.off()
        return c

    @kernel
    def run(self) -> None:
        self.core.break_realtime()

        # ── Record cooling sequence into DMA trace ──────────────────────
        with self.dma.record("cooling"):
            self._cool()
        cool_h = self.dma.get_handle("cooling")

        # Pre-program qubit DDS (frequency fixed, phase varies)
        self.dds_qubit.set(frequency=QUBIT_FREQ, phase=0.0, amplitude=1.0)

        self.excitation = []

        for phase in self.phase_list:
            n_exc = 0

            for _ in range(self.n_shots):
                # Replay cooling via DMA
                self.dma.playback(cool_h)

                # π/2 pulse (phase 0)
                self.dds_qubit.set(frequency=QUBIT_FREQ, phase=0.0)
                self.dds_qubit.sw.pulse_mu(self._half_pi_mu)

                # Free evolution T
                self.core.delay(self.free_evol_s)

                # π/2 pulse with scan phase φ
                self.dds_qubit.set(frequency=QUBIT_FREQ, phase=phase)
                self.dds_qubit.sw.pulse_mu(self._half_pi_mu)

                # Simulate Ramsey physics: P = 0.5(1 + cos(2π·phase))
                # (detuning = 0 for simplicity; real experiment has Δω·T term)
                p_exc = 0.5 * (1 + math.cos(2 * math.pi * phase))
                mean = self.n_bright if self._rng.random() < p_exc else self.n_dark
                self.ttl_pmt.mean_count_per_mu = mean / self._gate_mu

                c = self._detect()
                if c > THRESHOLD:
                    n_exc += 1

                self.core.break_realtime()
                self.core.delay(1 * ms)

            self.excitation.append(n_exc / self.n_shots)

    def analyze(self):
        phases = np.array(self.phase_list) * 2 * math.pi   # convert to radians
        exc    = np.array(self.excitation)

        def model(phi, amp, delta_phi, offset):
            return amp * np.cos(phi + delta_phi) + offset

        popt, _ = curve_fit(
            model, phases, exc,
            p0=[0.5, 0.0, 0.5],
            bounds=([0.0, -math.pi, 0.0], [1.0, math.pi, 1.0]),
        )
        amp, delta_phi, offset = popt

        self.set_dataset("ramsey_contrast", 2 * amp)
        self.set_dataset("phase_offset",    delta_phi)
        self.set_dataset("excitation",      list(exc))
