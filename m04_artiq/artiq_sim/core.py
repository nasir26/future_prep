"""
artiq_sim.core — Virtual ARTIQ Core device
===========================================
ARTIQ's key innovation is a deterministic hardware timeline.  Every event
(TTL pulse, DDS update) is stamped with an absolute machine-unit time and
sent to the FPGA RTIO fabric ahead of time.  The software cursor tracks the
next available time slot.

Timeline model
--------------
                       NOW_MU (software cursor)
                           │
    ─────────────────────┤├────────────────────────────▶ time
                    ^ SLACK ^
              RTT_MU ahead of hardware wall time

The core clock runs at ref_period Hz (default 8 ns → 125 MHz).
  1 mu = ref_period  (typically 8 ns on Kasli / KC705)

Key methods (mirror real ARTIQ Core)
--------------------------------------
  now_mu()             — return current cursor in mu
  at_mu(t)             — set cursor to absolute time t; raise UnderflowError if t < hw_now
  delay_mu(dt)         — advance cursor by dt mu
  delay(dt_s)          — advance by dt_s seconds (converted internally)
  break_realtime()     — jump cursor forward to hw_now + SLACK_MU (safe reset)
  seconds_to_mu(s)     — convert seconds → mu (rounded)
  mu_to_seconds(mu)    — convert mu → seconds
  wait_until_mu(t)     — block simulation until t (models DMA / wait)

UnderflowError
--------------
Raised when an event is scheduled in the past.  On real hardware this is a
fatal RTIO error; in sim we raise it immediately.

Author: Nasir Ali, C-DAC Noida
"""

import time


class TerminationRequested(Exception):
    """Raised by core.break_realtime() in experiment-abort scenarios."""


class RTIOUnderflow(Exception):
    """Raised when an event is stamped before the hardware cursor."""


class Core:
    """
    Simulated ARTIQ Core device.

    Parameters
    ----------
    ref_period : float
        Duration of one machine unit in seconds.  Default 8 ns (Kasli FPGA).
    slack_mu : int
        Safety slack added by break_realtime() in mu.  Default 125_000 mu = 1 ms.
    wall_origin_s : float
        Simulated wall-clock origin (seconds).  Default 0.
    """

    def __init__(self, ref_period: float = 8e-9, slack_mu: int = 125_000):
        self.ref_period = ref_period          # 8 ns → 125 MHz on Kasli
        self.slack_mu   = slack_mu            # 1 ms default slack
        self._cursor_mu = 0                   # software timeline cursor
        self._hw_now_mu = 0                   # simulated hardware "wall" time
        # Event log: list of {"time_mu": int, "type": str, ...}
        self.event_log  = []

    # ─── mu ↔ seconds conversion ────────────────────────────────────────────

    def seconds_to_mu(self, t_s: float) -> int:
        """Convert seconds to machine units (rounds to nearest mu)."""
        return int(round(t_s / self.ref_period))

    def mu_to_seconds(self, t_mu: int) -> float:
        """Convert machine units to seconds."""
        return t_mu * self.ref_period

    # ─── Timeline primitives ─────────────────────────────────────────────────

    def now_mu(self) -> int:
        """Return the current software timeline cursor in mu."""
        return self._cursor_mu

    def at_mu(self, t: int) -> None:
        """
        Set cursor to absolute time t (mu).

        Raises RTIOUnderflow if t < hw_now (event in the past).
        Real ARTIQ raises this as a fatal kernel exception.
        """
        if t < self._hw_now_mu:
            raise RTIOUnderflow(
                f"at_mu({t}): underflow — hw_now={self._hw_now_mu} "
                f"(delta={t - self._hw_now_mu} mu = "
                f"{self.mu_to_seconds(t - self._hw_now_mu)*1e9:.1f} ns)"
            )
        self._cursor_mu = t

    def delay_mu(self, dt: int) -> None:
        """Advance timeline cursor by dt machine units."""
        self._cursor_mu += dt

    def delay(self, dt_s: float) -> None:
        """Advance timeline cursor by dt_s seconds."""
        self.delay_mu(self.seconds_to_mu(dt_s))

    def break_realtime(self) -> None:
        """
        Reset cursor to hw_now + SLACK_MU.

        Call this at the start of every experiment (or after a long Python
        computation) to prevent RTIO underflows caused by the time spent in
        Python.  Equivalent to: self.core.reset()
        """
        self._hw_now_mu  = self._cursor_mu   # advance hw time to current position
        self._cursor_mu  = self._hw_now_mu + self.slack_mu

    def reset(self) -> None:
        """Alias for break_realtime() — matches real ARTIQ API."""
        self.break_realtime()

    def wait_until_mu(self, t: int) -> None:
        """
        Stall until the timeline cursor reaches t.

        In simulation, this just advances the hw_now pointer (no actual
        sleeping); on hardware this would block the CPU until the RTIO
        FIFO is drained to time t.
        """
        if t > self._cursor_mu:
            self._cursor_mu = t
        self._hw_now_mu = max(self._hw_now_mu, t)

    # ─── Internal helpers used by devices ───────────────────────────────────

    def _stamp(self, event: dict) -> None:
        """Record an RTIO output event at the current cursor."""
        event["time_mu"] = self._cursor_mu
        event["time_s"]  = self.mu_to_seconds(self._cursor_mu)
        self.event_log.append(event)
        # Advance hw_now to track what has been submitted
        self._hw_now_mu = max(self._hw_now_mu, self._cursor_mu)

    def clear_log(self) -> None:
        """Reset event log (call between experiments)."""
        self.event_log.clear()

    def events_of_type(self, type_: str) -> list:
        return [e for e in self.event_log if e.get("type") == type_]
