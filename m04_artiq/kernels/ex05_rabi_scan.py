"""
M04 ex05 — Rabi Flop Scan (carrier + sideband)
===============================================
A Rabi scan is the first calibration run after every major alignment.
It sweeps the qubit-drive pulse duration and measures the excitation
probability P(|↑⟩) vs τ.

P_excited(τ) = sin²(Ω τ / 2)  →  fitted to extract π-time τ_π

The scan is run separately on:
  · Carrier (com → qubit, no motional quanta change)
  · Red sideband (RSB): com → qubit − 1 phonon (motional cooling / BSB gate)
  · Blue sideband (BSB): com → qubit + 1 phonon

From the sideband Rabi frequencies, the Lamb-Dicke parameter η and mean
motional occupation n̄ are extracted.

Full experiment sequence (per point, per shot)
----------------------------------------------
  1. cool_and_pump()
  2. dds_qubit.set(freq, phase=0)
  3. dds_qubit.sw.pulse(tau)     ← scan this
  4. detect()  → count
  5. count > THRESHOLD → "excited"

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
CARRIER_FREQ    = 200e6      # 200 MHz qubit drive AOM frequency
SIDEBAND_FREQ   = 200.5e6    # +500 kHz motional sideband
RABI_FREQ_HZ    = 50e3       # Ω/2π = 50 kHz → π-time = 10 µs


def _poisson_sample(rng, mean: float) -> int:
    """Quick Poisson draw."""
    if mean <= 0:
        return 0
    import math
    L = math.exp(-mean)
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return k - 1


class RabiScan(EnvExperiment):
    """
    Sweep pulse duration τ, fit P_excited(τ) = sin²(Ω τ / 2).

    Attributes set in tests
    -----------------------
    tau_list  : list of floats — pulse durations in seconds
    n_shots   : int — shots per point (default 100)
    frequency : float — DDS frequency (default CARRIER_FREQ)
    """

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_laser")
        self.setattr_device("ttl_pmt")
        self.setattr_device("dds_qubit")
        self.setattr_device("dds_cool")

        # Defaults — override in test
        self.tau_list  = [k * 2e-6 for k in range(1, 11)]  # 2..20 µs
        self.n_shots   = 50
        self.frequency = CARRIER_FREQ
        self.n_bright  = 40   # photons in bright state
        self.n_dark    = 2    # photons in dark state

    def prepare(self):
        self._gate_mu = self.core.seconds_to_mu(DETECT_DURATION)
        self._rng = __import__("random").Random(0)

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
        count = self.ttl_pmt.count(gate_end)
        self.ttl_laser.off()
        return count

    @kernel
    def _rabi_shot(self, tau_mu: int) -> int:
        """One Rabi shot: cool → drive τ → detect → return count."""
        self._cool()
        self.dds_qubit.sw.pulse_mu(tau_mu)
        return self._detect()

    @kernel
    def run(self) -> None:
        self.core.break_realtime()
        self.dds_qubit.set(frequency=self.frequency, phase=0.0, amplitude=1.0)
        self.excitation = []    # P_excited per τ point

        for tau in self.tau_list:
            tau_mu  = self.core.seconds_to_mu(tau)
            n_exc   = 0

            for _ in range(self.n_shots):
                # Rabi formula: P_exc = sin²(Ω τ / 2) = sin²(π f_Rabi τ)
                # At τ_π = 1/(2 f_Rabi): P = sin²(π/2) = 1  (full flip)
                p_exc  = math.sin(math.pi * RABI_FREQ_HZ * tau) ** 2
                # Draw photon count from Poisson based on state
                mean = self.n_bright if self._rng.random() < p_exc else self.n_dark
                self.ttl_pmt.mean_count_per_mu = (
                    mean / self._gate_mu
                )
                c = self._rabi_shot(tau_mu)
                if c > THRESHOLD:
                    n_exc += 1

                self.core.break_realtime()
                self.core.delay(1 * ms)

            self.excitation.append(n_exc / self.n_shots)

    def analyze(self):
        """Fit P(τ) = A sin²(Ω τ / 2) + B, extract π-time."""
        tau_arr = np.array(self.tau_list)
        exc_arr = np.array(self.excitation)

        def model(tau, omega, offset):
            return np.sin(omega * tau / 2) ** 2 + offset

        try:
            popt, _ = curve_fit(
                model, tau_arr, exc_arr,
                p0=[2 * math.pi * RABI_FREQ_HZ, 0.0],
                bounds=([0, -0.1], [2 * math.pi * 1e6, 0.1]),
                maxfev=5000,
            )
            omega_fit, offset_fit = popt
            tau_pi_fit = math.pi / omega_fit

            self.set_dataset("omega_rabi",  omega_fit)
            self.set_dataset("tau_pi",      tau_pi_fit)
            self.set_dataset("excitation",  list(exc_arr))

        except RuntimeError:
            self.set_dataset("omega_rabi", float("nan"))
            self.set_dataset("tau_pi",     float("nan"))
