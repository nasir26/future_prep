"""
artiq_sim.devices — Simulated ARTIQ hardware devices
=====================================================
Each class here mimics the ARTIQ Python API for that device type.  The
implementation records events to core.event_log (for test inspection) and
generates simulated photon counts via a seeded PRNG.

Device classes
--------------
TTLOut      — digital output channel (TTL pulses)
TTLIn       — digital input with edge counter (photon gating)
EdgeCounter — alias for TTLIn gating mode
AD9910      — Urukul DDS (frequency / phase / amplitude control)
CoreDMA     — DMA trace recorder / playback engine

Author: Nasir Ali, C-DAC Noida
"""

import random
import math


# ═══════════════════════════════════════════════════════════════════════════
#  TTLOut
# ═══════════════════════════════════════════════════════════════════════════

class TTLOut:
    """
    Simulated ARTIQ TTL output channel.

    Real ARTIQ API methods:
        on()            — set output high at cursor
        off()           — set output low at cursor
        pulse(t)        — on → delay(t) → off (advance cursor)
        pulse_mu(t_mu)  — same in machine units
    """

    def __init__(self, core, name: str):
        self.core  = core
        self.name  = name
        self._high = False

    def on(self) -> None:
        self._high = True
        self.core._stamp({"type": "ttl_out", "channel": self.name, "level": 1})

    def off(self) -> None:
        self._high = False
        self.core._stamp({"type": "ttl_out", "channel": self.name, "level": 0})

    def pulse_mu(self, duration: int) -> None:
        """Assert high for duration mu, then low; advance cursor by duration."""
        self.on()
        self.core.delay_mu(duration)
        self.off()

    def pulse(self, duration: float) -> None:
        """Assert high for duration seconds, then low."""
        self.pulse_mu(self.core.seconds_to_mu(duration))


# ═══════════════════════════════════════════════════════════════════════════
#  TTLIn / EdgeCounter
# ═══════════════════════════════════════════════════════════════════════════

class TTLIn:
    """
    Simulated ARTIQ TTL input channel with photon-count gating.

    In the real ARTIQ model:
      1. gate_rising_mu(t) — open gate for t mu, return gate_end timestamp
      2. count(gate_end)   — wait until gate_end, return edge count

    In simulation: edge count is drawn from a Poisson distribution with
    mean = mean_count_per_mu * gate_duration_mu.

    Attributes
    ----------
    mean_count_per_mu : float
        Expected photon count per machine unit (set by test or kernel).
        Default corresponds to ~0 (dark state).
    """

    def __init__(self, core, name: str, mean_count_per_mu: float = 0.0):
        self.core              = core
        self.name              = name
        self.mean_count_per_mu = mean_count_per_mu
        self._rng              = random.Random(42)   # seeded for reproducibility

    def set_mean_count(self, mean: float, gate_duration_s: float = 400e-6) -> None:
        """Convenience: set mean counts per gate window, stored as rate."""
        gate_mu = self.core.seconds_to_mu(gate_duration_s)
        self.mean_count_per_mu = mean / gate_mu if gate_mu > 0 else 0.0

    def gate_rising_mu(self, duration: int) -> int:
        """
        Open photon-counting gate for duration mu.
        Stamps gate-open and gate-close events; returns gate_end timestamp.
        """
        gate_start = self.core.now_mu()
        self.core._stamp({
            "type": "gate_open", "channel": self.name,
            "duration_mu": duration,
        })
        self.core.delay_mu(duration)
        gate_end = self.core.now_mu()
        self.core._stamp({"type": "gate_close", "channel": self.name})
        return gate_end

    def gate_rising(self, duration: float) -> int:
        return self.gate_rising_mu(self.core.seconds_to_mu(duration))

    def count(self, up_to_time_mu: int) -> int:
        """
        Wait until up_to_time_mu, return simulated edge count.

        The count is Poisson-distributed with mean proportional to the gate
        duration.  Tests can override mean_count_per_mu to inject specific
        photon rates (bright/dark state simulation).
        """
        # Find the most recent gate_open event
        opens = [e for e in self.core.event_log
                 if e.get("type") == "gate_open" and e.get("channel") == self.name]
        if opens:
            gate_mu = opens[-1]["duration_mu"]
        else:
            gate_mu = max(0, up_to_time_mu - self.core.now_mu())

        mean = self.mean_count_per_mu * gate_mu
        count = self._rng.poisson(mean) if hasattr(self._rng, "poisson") \
                else self._poisson(mean)

        self.core.wait_until_mu(up_to_time_mu)
        self.core._stamp({
            "type": "photon_count", "channel": self.name,
            "count": count, "mean": mean, "gate_mu": gate_mu,
        })
        return count

    def _poisson(self, lam: float) -> int:
        """Pure-Python Poisson sampler (Knuth algorithm)."""
        if lam <= 0:
            return 0
        L = math.exp(-lam)
        k, p = 0, 1.0
        while p > L:
            k += 1
            p *= self._rng.random()
        return k - 1


# Alias: in ARTIQ, EdgeCounter is a separate class but functionally similar
EdgeCounter = TTLIn


# ═══════════════════════════════════════════════════════════════════════════
#  AD9910 (Urukul DDS)
# ═══════════════════════════════════════════════════════════════════════════

class AD9910:
    """
    Simulated Urukul AD9910 DDS channel.

    The AD9910 runs at SYSCLK (1 GHz typical).
    Frequency tuning word: FTW = round(freq * 2^32 / SYSCLK)
    Phase offset word:     POW = round(phase_turns * 2^16)
    Amplitude scale factor: ASF = round(amplitude * 0x3FFF)

    Real ARTIQ API methods (implemented here):
        set(frequency, phase, amplitude)   — program at cursor
        set_mu(ftw, pow_, asf)             — same in hardware words
        set_att(att_dB)                    — set attenuator (dB)
        sw.on() / sw.off()                 — RF switch (TTLOut alias)
        cfg_sw.on()                        — enable channel (config switch)
    """

    SYSCLK = 1e9   # 1 GHz AD9910 system clock

    def __init__(self, core, name: str, sysclk: float = 1e9):
        self.core    = core
        self.name    = name
        self.SYSCLK  = sysclk
        self.sw      = TTLOut(core, f"{name}_sw")     # RF switch
        self.cfg_sw  = TTLOut(core, f"{name}_cfg_sw") # config switch
        self._freq   = 0.0
        self._phase  = 0.0
        self._amp    = 1.0
        self._att_dB = 0.0

    # ─── Hz / turns → FTW / POW / ASF ───────────────────────────────────

    def frequency_to_ftw(self, f: float) -> int:
        return int(round(f * (2**32) / self.SYSCLK)) & 0xFFFF_FFFF

    def turns_to_pow(self, turns: float) -> int:
        return int(round(turns * 2**16)) & 0xFFFF

    def amplitude_to_asf(self, amplitude: float) -> int:
        return int(round(amplitude * 0x3FFF)) & 0x3FFF

    # ─── Primary API ─────────────────────────────────────────────────────

    def set(self, frequency: float = None, phase: float = 0.0,
            amplitude: float = 1.0) -> None:
        """
        Program DDS at current cursor position.

        Parameters
        ----------
        frequency : Hz
        phase     : turns (0.0 = 0°, 0.25 = 90°, 0.5 = 180°)
        amplitude : 0.0–1.0
        """
        if frequency is not None:
            self._freq  = frequency
        self._phase = phase
        self._amp   = amplitude
        self.core._stamp({
            "type": "dds_set", "channel": self.name,
            "freq_hz":    self._freq,
            "phase_turns": self._phase,
            "amplitude":   self._amp,
            "ftw": self.frequency_to_ftw(self._freq),
            "pow": self.turns_to_pow(self._phase),
            "asf": self.amplitude_to_asf(self._amp),
        })

    def set_mu(self, ftw: int, pow_: int = 0, asf: int = 0x3FFF) -> None:
        """Program DDS using raw hardware words."""
        self._freq  = ftw  * self.SYSCLK / (2**32)
        self._phase = pow_ / (2**16)
        self._amp   = asf  / 0x3FFF
        self.core._stamp({
            "type": "dds_set", "channel": self.name,
            "freq_hz":    self._freq,
            "phase_turns": self._phase,
            "amplitude":   self._amp,
            "ftw": ftw, "pow": pow_, "asf": asf,
        })

    def set_att(self, att_dB: float) -> None:
        """Set digital attenuator value in dB."""
        self._att_dB = att_dB
        self.core._stamp({
            "type": "dds_att", "channel": self.name, "att_dB": att_dB,
        })

    def init(self) -> None:
        """Device initialization (no-op in simulation)."""
        self.core._stamp({"type": "dds_init", "channel": self.name})

    @property
    def frequency(self) -> float:
        return self._freq

    @property
    def phase(self) -> float:
        return self._phase

    @property
    def amplitude(self) -> float:
        return self._amp


# ═══════════════════════════════════════════════════════════════════════════
#  CoreDMA
# ═══════════════════════════════════════════════════════════════════════════

class CoreDMA:
    """
    Simulated ARTIQ CoreDMA: records and replays RTIO event traces.

    CoreDMA allows recording a kernel sequence once and playing it back many
    times with zero software overhead (the trace is replayed by FPGA DMA).
    In simulation we store a snapshot of events and replay them at playback
    time.

    Real ARTIQ API:
        record("name")         — context manager; records events inside the block
        get_handle("name")     — returns an opaque handle
        playback_mu(handle, t) — replay trace starting at time t
        erase("name")          — delete a stored trace
    """

    def __init__(self, core):
        self.core   = core
        self._traces: dict = {}   # name → list of relative events

    def record(self, name: str):
        """Return a context manager that captures RTIO events into a named trace."""
        return _DMARecorder(self, name)

    def get_handle(self, name: str):
        """Return a handle (here, just the name string) for playback."""
        if name not in self._traces:
            raise KeyError(f"CoreDMA: no trace named '{name}'")
        return name

    def playback(self, handle: str) -> None:
        """Replay a named trace starting at the current cursor."""
        self.playback_mu(handle, self.core.now_mu())

    def playback_mu(self, handle: str, start_mu: int) -> None:
        """Replay trace at absolute time start_mu."""
        if handle not in self._traces:
            raise KeyError(f"CoreDMA: no trace named '{handle}'")
        trace = self._traces[handle]
        base  = trace[0]["time_mu"] if trace else start_mu
        for event in trace:
            delta_mu = event["time_mu"] - base
            new_event = dict(event)
            new_event["time_mu"] = start_mu + delta_mu
            new_event["time_s"]  = self.core.mu_to_seconds(new_event["time_mu"])
            new_event["dma_replay"] = True
            self.core.event_log.append(new_event)
        # Advance cursor past the end of the trace
        if trace:
            total_mu = trace[-1]["time_mu"] - base
            self.core._cursor_mu = start_mu + total_mu
        self.core._stamp({"type": "dma_playback", "handle": handle,
                          "start_mu": start_mu, "n_events": len(trace)})

    def erase(self, name: str) -> None:
        self._traces.pop(name, None)


class _DMARecorder:
    """Context manager returned by CoreDMA.record()."""

    def __init__(self, dma: CoreDMA, name: str):
        self._dma   = dma
        self._name  = name
        self._saved = None

    def __enter__(self):
        # Snapshot the current log length; events added inside become the trace
        self._snap_len = len(self._dma.core.event_log)
        return self

    def __exit__(self, *_):
        new_events = self._dma.core.event_log[self._snap_len:]
        self._dma._traces[self._name] = list(new_events)
