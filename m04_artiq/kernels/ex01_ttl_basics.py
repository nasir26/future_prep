"""
M04 ex01 — TTL Basics: timeline, delay, underflow
===================================================
The single most important concept in ARTIQ is the **hardware timeline**.
Instead of "wait N seconds then do X," you say:
  "at time T, output X"
  "at time T+dt, output Y"

The software cursor tracks the next available time slot.  Events are
queued in the FPGA RTIO FIFO and executed precisely.

Key methods taught here
-----------------------
  core.break_realtime()   — reset cursor safely (add slack vs. wall time)
  ttl.on() / ttl.off()   — schedule TTL edges
  ttl.pulse(t)            — schedule a pulse (on → delay → off)
  core.delay(t_s)         — advance cursor by t_s seconds
  core.delay_mu(t_mu)     — advance cursor by t_mu machine units
  core.at_mu(t_abs)       — set cursor to absolute time
  core.now_mu()           — read current cursor

Underflow
---------
If you schedule an event in the past (forgot break_realtime, or too slow
in Python), ARTIQ raises RTIOUnderflow.  The demo shows how it happens
and how break_realtime() prevents it.

Author: Nasir Ali, C-DAC Noida
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from artiq_sim import EnvExperiment, kernel, ms, us, ns
from artiq_sim.core import RTIOUnderflow


class TTLBasics(EnvExperiment):
    """
    Demonstrates the three fundamental TTL timing patterns.

    Exercises
    ---------
    1. Single pulse using pulse()
    2. Burst of N pulses with fixed period
    3. Absolute-time placement with at_mu()
    """

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_laser")    # cooling laser gate

    @kernel
    def run(self):
        # ALWAYS call break_realtime() first.
        # Without it, all events would be scheduled at mu=0, which is in the
        # past by the time the kernel starts running.
        self.core.break_realtime()

        # ── Exercise 1: single 10 µs pulse ──────────────────────────────
        # pulse() is equivalent to: on(); delay(t); off()
        self.ttl_laser.pulse(10 * us)

        # ── Exercise 2: burst of 5 pulses with 20 µs period ─────────────
        # Pattern: on at T, off at T+10µs, on at T+20µs, ...
        period_mu = self.core.seconds_to_mu(20 * us)
        pulse_mu  = self.core.seconds_to_mu(10 * us)
        for _ in range(5):
            self.ttl_laser.on()
            self.core.delay_mu(pulse_mu)
            self.ttl_laser.off()
            self.core.delay_mu(period_mu - pulse_mu)   # dead time

        # ── Exercise 3: absolute placement ──────────────────────────────
        # Jump cursor to a specific absolute time, then place an event.
        t_anchor = self.core.now_mu()
        for k in range(3):
            # Place pulses at t_anchor + k*50µs
            self.core.at_mu(t_anchor + k * self.core.seconds_to_mu(50 * us))
            self.ttl_laser.on()
            self.core.delay(5 * us)
            self.ttl_laser.off()

    def underflow_demo(self):
        """
        Intentionally trigger RTIOUnderflow to show what happens.

        In a real experiment, this would crash the kernel.
        """
        # Reset to a known state
        self.core.break_realtime()
        t_now = self.core.now_mu()

        # Attempt to place an event 2 ms in the PAST.
        # Going back exactly 1 ms would land on _hw_now_mu (break_realtime
        # adds 1 ms of slack), which is not strictly in the past.
        # 2 ms ensures t < _hw_now_mu, triggering the underflow.
        try:
            self.core.at_mu(t_now - 2 * self.core.seconds_to_mu(1 * ms))
            self.ttl_laser.on()
            return False    # should not reach here
        except RTIOUnderflow as e:
            return True     # underflow correctly raised
