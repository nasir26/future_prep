"""
M04 tests — ex01 TTL basics, ex02 photon counting, ex03 DDS control
====================================================================
Author: Nasir Ali, C-DAC Noida
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from artiq_sim.core import RTIOUnderflow


# ═══════════════════════════════════════════════════════════════════════════
#  ex01 — TTL basics
# ═══════════════════════════════════════════════════════════════════════════

class TestTTLBasics:

    def test_break_realtime_advances_cursor(self, ttl_basics):
        """break_realtime() must put cursor at least SLACK_MU ahead of hw_now."""
        core = ttl_basics.core
        t0 = core.now_mu()
        core.break_realtime()
        assert core.now_mu() >= t0 + core.slack_mu

    def test_run_produces_ttl_events(self, ttl_basics):
        """Kernel must produce at least 10 TTL edge events."""
        ttl_basics.run()
        evts = ttl_basics.core.events_of_type("ttl_out")
        assert len(evts) >= 10, f"Expected ≥10 TTL events, got {len(evts)}"

    def test_events_in_forward_time_order(self, ttl_basics):
        """All RTIO events must be in non-decreasing time order."""
        ttl_basics.run()
        times = [e["time_mu"] for e in ttl_basics.core.event_log]
        assert times == sorted(times), "Events out of time order (underflow)"

    def test_burst_alternates_on_off(self, ttl_basics):
        """Exercise 2 burst: 5 on+off pairs → 10 consecutive events alternating."""
        ttl_basics.run()
        evts = [e for e in ttl_basics.core.events_of_type("ttl_out")
                if e["channel"] == "ttl_laser"]
        # Levels must alternate: on(1), off(0), on(1), ...
        levels = [e["level"] for e in evts]
        for i in range(1, len(levels)):
            assert levels[i] != levels[i - 1] or levels[i] == 0, (
                f"Consecutive same-level events at index {i}: {levels[i-2:i+2]}"
            )

    def test_underflow_raises(self, ttl_basics):
        """Going backwards in time must raise RTIOUnderflow."""
        assert ttl_basics.underflow_demo() is True

    def test_at_mu_places_events_precisely(self, ttl_basics):
        """Exercise 3 at_mu: three pulses at anchored absolute times."""
        ttl_basics.run()
        evts = ttl_basics.core.events_of_type("ttl_out")
        on_evts = [e for e in evts if e["level"] == 1]
        # Last 3 on-events come from exercise 3 and should be ≥50 µs apart
        core  = ttl_basics.core
        gap_mu = core.seconds_to_mu(50e-6)
        ex3_on = on_evts[-3:]
        for i in range(1, len(ex3_on)):
            delta = ex3_on[i]["time_mu"] - ex3_on[i-1]["time_mu"]
            assert delta >= gap_mu - 5, (   # ±5 mu tolerance
                f"Absolute-time events {i-1} and {i} less than 50 µs apart "
                f"(delta={delta} mu)"
            )


# ═══════════════════════════════════════════════════════════════════════════
#  ex02 — Photon counting
# ═══════════════════════════════════════════════════════════════════════════

class TestPhotonCounting:

    def test_histogram_mean_bright(self, photon_counting):
        """Bright-state mean count must be close to n_bright=40."""
        import numpy as np
        photon_counting.n_shots = 200
        photon_counting.run()
        photon_counting.analyze()
        mean_b = photon_counting.get_dataset("bright_mean")
        assert 25 <= mean_b <= 55, f"Bright mean {mean_b:.1f} far from 40"

    def test_histogram_mean_dark(self, photon_counting):
        """Dark-state mean count must be close to n_dark=2."""
        import numpy as np
        photon_counting.n_shots = 200
        photon_counting.run()
        photon_counting.analyze()
        mean_d = photon_counting.get_dataset("dark_mean")
        assert 0 <= mean_d <= 6, f"Dark mean {mean_d:.1f} far from 2"

    def test_bright_fidelity(self, photon_counting):
        """Discrimination fidelity for bright state must exceed 95%."""
        photon_counting.n_shots = 500
        photon_counting.run()
        photon_counting.analyze()
        f = photon_counting.get_dataset("fidelity_bright")
        assert f >= 0.95, f"Bright fidelity {f:.3f} < 95%"

    def test_gate_events_logged(self, photon_counting):
        """Each shot must produce a gate_open + photon_count event."""
        photon_counting.n_shots = 10
        photon_counting.run()
        n_gates  = len(photon_counting.core.events_of_type("gate_open"))
        n_counts = len(photon_counting.core.events_of_type("photon_count"))
        assert n_gates  == 10, f"Expected 10 gate_open events, got {n_gates}"
        assert n_counts == 10, f"Expected 10 photon_count events, got {n_counts}"


# ═══════════════════════════════════════════════════════════════════════════
#  ex03 — DDS control
# ═══════════════════════════════════════════════════════════════════════════

class TestDDSControl:

    def test_run_produces_dds_events(self, dds_ctrl):
        """Kernel must produce at least 5 DDS set events."""
        dds_ctrl.run()
        evts = dds_ctrl.core.events_of_type("dds_set")
        assert len(evts) >= 5, f"Expected ≥5 dds_set events, got {len(evts)}"

    def test_cooling_dds_frequency(self, dds_ctrl):
        """Cooling DDS must be programmed to COOL_FREQ_HZ = 100 MHz."""
        dds_ctrl.run()
        cool_evts = [e for e in dds_ctrl.core.events_of_type("dds_set")
                     if e["channel"] == "dds_cool"]
        assert cool_evts, "No dds_cool set events"
        assert abs(cool_evts[0]["freq_hz"] - 100e6) < 1.0, (
            f"Cool freq {cool_evts[0]['freq_hz']/1e6:.3f} MHz != 100 MHz"
        )

    def test_qubit_dds_frequency(self, dds_ctrl):
        """Qubit DDS must be programmed to QUBIT_FREQ_HZ = 200 MHz."""
        dds_ctrl.run()
        q_evts = [e for e in dds_ctrl.core.events_of_type("dds_set")
                  if e["channel"] == "dds_qubit"]
        freqs = [e["freq_hz"] for e in q_evts]
        assert any(abs(f - 200e6) < 1.0 for f in freqs), (
            f"No 200 MHz qubit event; got {[f/1e6 for f in freqs]}"
        )

    def test_phase_shifted_event(self, dds_ctrl):
        """Exercise 3 must produce a DDS set with phase=0.25 turns (90°)."""
        dds_ctrl.run()
        q_evts = [e for e in dds_ctrl.core.events_of_type("dds_set")
                  if e["channel"] == "dds_qubit"]
        phases = [e["phase_turns"] for e in q_evts]
        assert any(abs(p - 0.25) < 0.001 for p in phases), (
            f"No 90° phase event; got phases {phases}"
        )

    def test_ftw_roundtrip(self, dds_ctrl):
        """FTW encoding: frequency_to_ftw(f) → set_mu → stored freq within 1 Hz."""
        dds_ctrl.run()
        dds = dds_ctrl.dds_qubit
        # Check last FTW-mode set event
        mu_evts = [e for e in dds_ctrl.core.events_of_type("dds_set")
                   if e["channel"] == "dds_qubit" and "ftw" in e]
        assert mu_evts, "No FTW set events found"
        e = mu_evts[-1]
        recovered = e["ftw"] * dds.SYSCLK / (2**32)
        assert abs(recovered - e["freq_hz"]) < 1.0, (
            f"FTW roundtrip error: {recovered:.3f} Hz vs {e['freq_hz']:.3f} Hz"
        )

    def test_freq_ramp_produces_n_steps(self, dds_ctrl):
        """freq_ramp(100M, 200M, n=10) must produce 10 DDS events + 10 TTL pulses."""
        dds_ctrl.core.break_realtime()
        dds_ctrl.freq_ramp(f_start=100e6, f_stop=200e6, n_steps=10, step_us=1.0)
        q_evts = [e for e in dds_ctrl.core.events_of_type("dds_set")
                  if e["channel"] == "dds_qubit"]
        assert len(q_evts) >= 10, f"Expected ≥10 DDS ramp events, got {len(q_evts)}"
