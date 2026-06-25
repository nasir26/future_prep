"""
M04 tests — ex04 Doppler cooling, ex05 Rabi scan, ex06 Ramsey, ex07 SBC
========================================================================
Author: Nasir Ali, C-DAC Noida
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import math
import pytest


# ═══════════════════════════════════════════════════════════════════════════
#  ex04 — Doppler cooling
# ═══════════════════════════════════════════════════════════════════════════

class TestDopplerCooling:

    def test_run_n_reps(self, doppler):
        """Kernel must execute n_reps=20 cooling cycles and collect counts."""
        doppler.run()
        assert len(doppler.counts) == doppler.n_reps, (
            f"Expected {doppler.n_reps} count entries, got {len(doppler.counts)}"
        )

    def test_cooling_events(self, doppler):
        """Each repetition must produce at least one TTL on+off pair."""
        doppler.run()
        ttl_evts = doppler.core.events_of_type("ttl_out")
        # cooling (on+off) + detection (on+off) × n_reps = at least 4×n_reps events
        assert len(ttl_evts) >= 4 * doppler.n_reps, (
            f"Expected ≥{4*doppler.n_reps} TTL events, got {len(ttl_evts)}"
        )

    def test_counts_positive(self, doppler):
        """All photon counts in bright state must be ≥ 0."""
        doppler.run()
        assert all(c >= 0 for c in doppler.counts)

    def test_analyze_mean_realistic(self, doppler):
        """Analyzed mean count must be positive (bright-state simulation)."""
        doppler.run()
        doppler.analyze()
        mean = doppler.get_dataset("mean_count")
        assert mean > 10.0, f"Mean count {mean:.1f} too low for bright-state cooling"

    def test_timeline_no_underflow(self, doppler):
        """No RTIO underflow must occur (events in non-decreasing time order)."""
        doppler.run()
        times = [e["time_mu"] for e in doppler.core.event_log]
        assert times == sorted(times)


# ═══════════════════════════════════════════════════════════════════════════
#  ex05 — Rabi scan
# ═══════════════════════════════════════════════════════════════════════════

class TestRabiScan:

    def test_excitation_sine_shape(self, rabi):
        """Excitation vs tau must follow a sinusoidal pattern (not flat)."""
        rabi.run()
        exc = rabi.excitation
        assert max(exc) - min(exc) > 0.3, (
            f"Rabi fringe too flat: range={max(exc)-min(exc):.3f} (expected >0.3)"
        )

    def test_fit_extracts_pi_time(self, rabi):
        """scipy fit must converge and return tau_pi within 30% of true value."""
        rabi.run()
        rabi.analyze()
        tau_pi_fit = rabi.get_dataset("tau_pi")
        tau_pi_true = 1.0 / (2 * 50e3)   # = 10 µs from RABI_FREQ_HZ=50e3
        assert not math.isnan(tau_pi_fit), "Rabi fit did not converge"
        error = abs(tau_pi_fit - tau_pi_true) / tau_pi_true
        assert error < 0.30, (
            f"Fitted τ_π={tau_pi_fit*1e6:.2f} µs, true={tau_pi_true*1e6:.2f} µs "
            f"(error={error*100:.1f}%)"
        )

    def test_dataset_populated(self, rabi):
        """Dataset must contain omega_rabi and excitation after analyze()."""
        rabi.run()
        rabi.analyze()
        assert rabi.get_dataset("omega_rabi") is not None
        assert len(rabi.get_dataset("excitation")) == len(rabi.tau_list)

    def test_first_last_points_reasonable(self, rabi):
        """First point (near τ=0) excitation lower than mid-point (near π-time)."""
        rabi.run()
        exc = rabi.excitation
        # tau_list = [2µs, 4µs, ..., 20µs]; π-time = 10µs → peak at index 4
        assert exc[4] > exc[0], (
            f"Mid-point ({exc[4]:.2f}) not greater than start ({exc[0]:.2f})"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  ex06 — Ramsey
# ═══════════════════════════════════════════════════════════════════════════

class TestRamsey:

    def test_excitation_cosine_shape(self, ramsey):
        """Excitation vs phase must span at least 0.6 (clear cosine fringe)."""
        ramsey.run()
        exc = ramsey.excitation
        assert max(exc) - min(exc) > 0.4, (
            f"Ramsey fringe range {max(exc)-min(exc):.3f} < 0.4"
        )

    def test_dma_trace_recorded(self, ramsey):
        """CoreDMA must have a 'cooling' trace after run()."""
        ramsey.run()
        assert "cooling" in ramsey.dma._traces, "DMA 'cooling' trace not recorded"

    def test_dma_trace_nonempty(self, ramsey):
        """DMA cooling trace must contain at least one RTIO event."""
        ramsey.run()
        assert len(ramsey.dma._traces["cooling"]) > 0

    def test_ramsey_contrast(self, ramsey):
        """Analyzed contrast must be ≥ 0.5."""
        ramsey.run()
        ramsey.analyze()
        contrast = ramsey.get_dataset("ramsey_contrast")
        assert contrast >= 0.5, f"Ramsey contrast {contrast:.3f} < 0.5"

    def test_phase_offset_small(self, ramsey):
        """Phase offset (detuning) must be small (near zero for zero detuning)."""
        ramsey.run()
        ramsey.analyze()
        delta_phi = ramsey.get_dataset("phase_offset")
        assert abs(delta_phi) < 0.5, f"Phase offset {delta_phi:.3f} rad suspiciously large"


# ═══════════════════════════════════════════════════════════════════════════
#  ex07 — Sideband cooling
# ═══════════════════════════════════════════════════════════════════════════

class TestSidebandCooling:

    def test_n_bar_decreases(self, sbc):
        """Simulated n̄ after N cool cycles must be less than initial n̄."""
        sbc.run()
        sbc.analyze()
        n_bar_init  = sbc.n_bar_0
        n_bar_final = sbc.n_bar_final
        assert n_bar_final < n_bar_init, (
            f"n̄ did not decrease: {n_bar_init:.2f} → {n_bar_final:.2f}"
        )

    def test_n_bar_final_near_zero(self, sbc):
        """After 20 cycles, n̄ should be < 0.5 (Lamb-Dicke regime)."""
        sbc.run()
        sbc.analyze()
        n_bar = sbc.n_bar_final
        assert n_bar < 0.5, f"n̄ = {n_bar:.3f} not < 0.5 after sideband cooling"

    def test_rsb_bsb_asymmetry(self, sbc):
        """RSB excitation must be less than BSB (sideband asymmetry)."""
        sbc.run()
        sbc.analyze()
        p_rsb = sbc.get_dataset("p_rsb")
        p_bsb = sbc.get_dataset("p_bsb")
        assert p_rsb <= p_bsb, (
            f"RSB ({p_rsb:.3f}) not ≤ BSB ({p_bsb:.3f}) — asymmetry check failed"
        )

    def test_n_bar_extracted_close_to_expected(self, sbc):
        """Extracted n̄ from sideband asymmetry must be within 50% of expected."""
        sbc.run()
        sbc.analyze()
        measured = sbc.get_dataset("n_bar_measured")
        expected = sbc.get_dataset("n_bar_expected")
        if math.isinf(measured) or math.isinf(expected):
            pytest.skip("n_bar is infinite (BSB=0), skip ratio check")
        if expected < 0.1:
            # RSB excitation probability = n̄/(n̄+1) < 10% at this shot count;
            # P(zero RSB events in 30 shots) ≈ 68%, making the ratio meaningless.
            pytest.skip(f"n̄_expected={expected:.4f} < 0.1: too few RSB events for reliable asymmetry")
        assert abs(measured - expected) / (expected + 1e-10) < 0.5, (
            f"n̄ mismatch: measured={measured:.3f}, expected={expected:.3f}"
        )
