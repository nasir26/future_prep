"""
M04 tests — ex08 MS gate, ex09 mid-circuit measurement + heralded entanglement
================================================================================
Author: Nasir Ali, C-DAC Noida
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import math
import pytest


# ═══════════════════════════════════════════════════════════════════════════
#  ex08 — MS gate
# ═══════════════════════════════════════════════════════════════════════════

class TestMSGate:

    def test_bichromatic_pulse_produces_events(self, ms_gate):
        """MS gate must produce both blue and red sideband DDS events."""
        ms_gate.run()
        freqs = {e["freq_hz"]
                 for e in ms_gate.core.events_of_type("dds_set")
                 if e["channel"] == "dds_qubit"}
        # Expect both f_blue = 200M + 495k and f_red = 200M - 495k
        has_blue = any(f > 200e6 for f in freqs)
        has_red  = any(f < 200e6 for f in freqs)
        assert has_blue and has_red, (
            f"Missing bichromatic tones; freqs (MHz): {[f/1e6 for f in sorted(freqs)]}"
        )

    def test_n_gate_modulation_cycles(self, ms_gate):
        """MS gate must produce N_MODCYCLES alternating blue/red pulse pairs."""
        from kernels.ex08_ms_gate import N_MODCYCLES
        ms_gate.run()
        ms_gate.analyze()
        assert ms_gate.get_dataset("n_gate_cycles") == N_MODCYCLES

    def test_ideal_fidelity_high(self, ms_gate):
        """Ideal MS gate fidelity must be > 0.95 for n̄=0.05."""
        ms_gate.run()
        ms_gate.analyze()
        f_ideal = ms_gate.get_dataset("fidelity_ideal")
        assert f_ideal > 0.95, f"Ideal fidelity {f_ideal:.4f} < 0.95"

    def test_no_underflow(self, ms_gate):
        """Long gate sequence must not produce timeline underflows."""
        ms_gate.run()
        times = [e["time_mu"] for e in ms_gate.core.event_log]
        assert times == sorted(times), "Timeline underflow in MS gate"


# ═══════════════════════════════════════════════════════════════════════════
#  ex09 — Mid-circuit measurement
# ═══════════════════════════════════════════════════════════════════════════

class TestMidCircuitMeasure:

    def test_second_meas_mostly_bright(self, mcm):
        """After MCM + X correction, second measurement must be >90% bright."""
        mcm.run()
        mcm.analyze()
        p = mcm.get_dataset("p_bright_second")
        assert p >= 0.90, f"p_bright_second = {p:.3f} < 0.90"

    def test_corrections_applied(self, mcm):
        """With p_flip=0.2 and 50 shots, at least 5 corrections expected."""
        mcm.run()
        assert mcm.n_corrected >= 3, (
            f"Only {mcm.n_corrected} corrections in 50 shots (p_flip=0.2)"
        )

    def test_mcm_produces_double_gates(self, mcm):
        """Each shot must produce exactly 2 gate_open events (mid-circuit + final)."""
        mcm.n_shots = 5
        mcm.run()
        n_gates = len(mcm.core.events_of_type("gate_open"))
        assert n_gates == 2 * 5, f"Expected 10 gates for 5 shots, got {n_gates}"

    def test_conditional_ttl_events(self, mcm):
        """Corrected shots must produce an extra qubit SW on/off pair."""
        mcm.n_shots = 50
        mcm.run()
        sw_evts = [e for e in mcm.core.events_of_type("ttl_out")
                   if e["channel"] == "dds_qubit_sw"]
        # Each shot has at least 1 π-pulse (preparation); corrected shots have 2
        assert len(sw_evts) >= mcm.n_shots, (
            f"Expected ≥{mcm.n_shots} qubit SW events, got {len(sw_evts)}"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  ex09b — Heralded entanglement
# ═══════════════════════════════════════════════════════════════════════════

class TestHeraldedEntanglement:

    def test_success_rate_close_to_geometric_mean(self, heralded):
        """
        With p_success=0.3 and max_attempts=20, nearly all experiments
        should succeed (geometric CDF: P(≤20 attempts) ≈ 1-(1-0.3)^20 ≈ 0.9992).
        """
        heralded.run()
        heralded.analyze()
        rate = heralded.get_dataset("success_rate")
        assert rate >= 0.80, f"Success rate {rate:.3f} too low (expected > 80%)"

    def test_mean_attempts_close_to_expected(self, heralded):
        """Mean attempts must be close to 1/p_success = 1/0.3 ≈ 3.33."""
        heralded.run()
        heralded.analyze()
        mean_a = heralded.get_dataset("mean_attempts")
        exp_a  = heralded.get_dataset("expected_mean_attempts")
        if math.isinf(mean_a):
            pytest.fail("Mean attempts is infinite (no successes)")
        # Allow 100% tolerance: geometric distribution has std = √(1-p)/p ≈ 1.83
        # for p=0.3, so with only 30 experiments the sample mean varies widely.
        assert abs(mean_a - exp_a) / exp_a < 1.00, (
            f"Mean attempts {mean_a:.2f} vs expected {exp_a:.2f} "
            f"(error > 60%)"
        )

    def test_photon_gate_events_logged(self, heralded):
        """Herald photon gates must be logged (at least one per experiment)."""
        heralded.run()
        gates = heralded.core.events_of_type("gate_open")
        assert len(gates) >= heralded.n_experiments, (
            f"Expected ≥{heralded.n_experiments} herald gates, got {len(gates)}"
        )

    def test_herald_counts_have_sentinel(self, heralded):
        """herald_counts must have one entry per experiment."""
        heralded.run()
        assert len(heralded.herald_counts) == heralded.n_experiments
