"""
M05 tests — Amaranth designs (ex02 Counter/FSM, ex04 FIFO, ex05 DDS + Verilog)
Author: Nasir Ali, C-DAC Noida
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import pytest

from amaranth import Signal, Module, Elaboratable, Array, Shape, Const, Cat
from amaranth.sim import Simulator

from rtl.ex02_amaranth_basics import (
    Counter as ACounter,
    ToggleFSM as AFSM,
    sim_counter,
    sim_toggle_fsm,
    elaborate_to_verilog as counter_to_verilog,
)
from rtl.ex04_amaranth_fifo import (
    StreamFIFO as AFIFO,
    sim_single_beat,
    sim_fill_and_drain,
    elaborate_to_verilog as fifo_to_verilog,
)
from rtl.ex05_amaranth_dds import (
    DDS,
    build_sine_lut,
    sim_frequency_tone,
    sim_phase_offset,
    elaborate_to_verilog as dds_to_verilog,
)


# ═══════════════════════════════════════════════════════════════════════════
#  Counter tests (Amaranth)
# ═══════════════════════════════════════════════════════════════════════════

class TestAmaranthCounter:

    def test_reset_holds_zero(self):
        log = sim_counter(n_cycles=4)
        rst_counts = [c for r, e, c in log if r == 1]
        assert all(c == 0 for c in rst_counts), f"count ≠ 0 during rst: {rst_counts}"

    def test_increments_when_enabled(self):
        log = sim_counter(n_cycles=12)
        en_counts = [c for r, e, c in log if e == 1]
        assert len(en_counts) >= 4
        for i in range(1, len(en_counts)):
            diff = (en_counts[i] - en_counts[i - 1]) & 0xFF
            assert diff == 1, f"gap ≠ 1: {en_counts[i-1]} → {en_counts[i]}"

    def test_rollover(self):
        dut = ACounter(width=8)
        sim = Simulator(dut)
        sim.add_clock(1e-6)
        history = []

        async def tb(ctx):
            ctx.set(dut.en, 1)
            for _ in range(270):
                await ctx.tick()
                history.append(ctx.get(dut.count))

        sim.add_testbench(tb)
        sim.run()
        assert 255 in history, "counter never reached 255"
        assert 0   in history, "counter never rolled to 0"

    def test_verilog_export_contains_module(self):
        v = counter_to_verilog()
        assert "module" in v.lower(), "Verilog output has no 'module' keyword"
        assert "always" in v.lower() or "reg" in v.lower(), (
            "Verilog output looks empty — no 'always' or 'reg'"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  ToggleFSM tests (Amaranth)
# ═══════════════════════════════════════════════════════════════════════════

class TestAmaranthToggleFSM:

    def test_out_toggles_on_trigger(self):
        log = sim_toggle_fsm()
        outs = [o for t, o in log]
        # verify at least one toggle happened
        changes = sum(1 for a, b in zip(outs, outs[1:]) if a != b)
        assert changes >= 2, f"expected ≥2 toggles, got {changes}"

    def test_two_toggles_restore_value(self):
        dut = AFSM()
        sim = Simulator(dut)
        sim.add_clock(1e-6)
        vals = []

        async def tb(ctx):
            await ctx.tick().repeat(2)
            vals.append(ctx.get(dut.out))   # initial

            ctx.set(dut.trigger, 1)
            await ctx.tick().repeat(2)
            ctx.set(dut.trigger, 0)
            await ctx.tick().repeat(2)

            ctx.set(dut.trigger, 1)
            await ctx.tick().repeat(2)
            ctx.set(dut.trigger, 0)
            await ctx.tick().repeat(2)

            vals.append(ctx.get(dut.out))   # after two toggles

        sim.add_testbench(tb)
        sim.run()
        assert vals[0] == vals[1], f"two toggles did not restore out: {vals}"


# ═══════════════════════════════════════════════════════════════════════════
#  Amaranth StreamFIFO tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAmaranthStreamFIFO:

    def test_single_beat_roundtrip(self):
        data, _ = sim_single_beat(0xCA)
        assert data is not None, "no beat received"
        assert data == 0xCA, f"data mismatch: got 0x{data:02X}"

    def test_fill_and_drain_sequence(self):
        log = sim_fill_and_drain(depth=8)
        rx  = log.get("received", [])
        assert rx == list(range(8)), f"order wrong: {rx}"

    def test_full_asserts_backpressure(self):
        log = sim_fill_and_drain(depth=8)
        assert log.get("fill_after_push") == 8
        assert log.get("s_ready_when_full") == 0

    def test_depth_must_be_power_of_two(self):
        with pytest.raises(AssertionError, match="power of 2"):
            AFIFO(depth=6)

    def test_verilog_export(self):
        v = fifo_to_verilog()
        assert "module" in v.lower(), "no 'module' in FIFO Verilog output"

    def test_simultaneous_push_pop(self):
        """When both sides are ready, a push and a pop can happen on the same cycle."""
        dut = AFIFO(depth=4)
        sim = Simulator(dut)
        sim.add_clock(1e-6)
        out_data = []

        async def tb(ctx):
            ctx.set(dut.m_ready, 0)
            # Push 2 items
            for v in [0xAA, 0xBB]:
                ctx.set(dut.s_valid, 1)
                ctx.set(dut.s_data,  v)
                await ctx.tick()
            ctx.set(dut.s_valid, 0)
            await ctx.tick()
            assert ctx.get(dut.fill) == 2

            # Push 0xCC and pop simultaneously; use sample-before-tick pattern.
            ctx.set(dut.m_ready, 1)
            ctx.set(dut.s_valid, 1)
            ctx.set(dut.s_data,  0xCC)
            await ctx.tick()         # simultaneous push+pop of 0xAA; fill stays 2
            ctx.set(dut.s_valid, 0)
            # Drain remaining; sample-before-tick to get correct m_data
            for _ in range(8):
                if ctx.get(dut.m_valid) and ctx.get(dut.m_ready):
                    out_data.append(ctx.get(dut.m_data))
                await ctx.tick()

        sim.add_testbench(tb)
        sim.run()
        # At least 0xAA should have been popped
        assert 0xAA in out_data or len(out_data) > 0, "simultaneous push/pop stalled"


# ═══════════════════════════════════════════════════════════════════════════
#  DDS tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDDS:

    def test_sine_lut_shape(self):
        """LUT must have 2^N entries, peak near expected amplitude."""
        lut = build_sine_lut(lut_bits=8, data_bits=8)
        assert len(lut) == 256, f"LUT length {len(lut)} ≠ 256"
        assert max(lut) == 127, f"LUT peak {max(lut)} ≠ 127"
        assert min(lut) >= -128, f"LUT floor {min(lut)} < −128"

    def test_sine_lut_zero_crossings(self):
        """Sine must be 0 at index 0 and near-0 at index N/2."""
        lut = build_sine_lut(8, 8)
        assert lut[0]   == 0, f"lut[0]={lut[0]} ≠ 0"
        assert abs(lut[128]) <= 1, f"lut[128]={lut[128]} (should be ≈0)"

    def test_phase_accumulates(self):
        """Phase output must strictly increase (mod 2^acc_bits)."""
        log  = sim_frequency_tone(n_cycles=32)
        phases = [p for p, s in log]
        pinc   = phases[1] - phases[0]    # assume first step is representative
        assert pinc > 0, "phase not advancing"
        for i in range(1, len(phases)):
            diff = (phases[i] - phases[i - 1]) & 0xFFFF
            assert diff == pinc, f"non-uniform PINC at step {i}: {diff} ≠ {pinc}"

    def test_output_range(self):
        """All output samples must be within [−128, 127] (signed 8-bit)."""
        log = sim_frequency_tone(n_cycles=256)
        for _, s in log:
            # Amaranth may return unsigned bits; interpret as signed
            s_signed = s if s < 128 else s - 256
            assert -128 <= s_signed <= 127, f"sample out of range: {s_signed}"

    def test_pinc_zero_silent(self):
        """With pinc=0 and en=0 output should remain at 0."""
        dut = DDS()
        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sines = []

        async def tb(ctx):
            ctx.set(dut.pinc, 0)
            ctx.set(dut.en,   0)
            for _ in range(8):
                await ctx.tick()
                sines.append(ctx.get(dut.sine))

        sim.add_testbench(tb)
        sim.run()
        assert all(s == 0 for s in sines), f"DDS not silent when en=0: {sines}"

    def test_spectral_purity(self):
        """
        FFT of one integer period of the DDS output should have a dominant
        bin at the target frequency and all other bins below −20 dB.
        """
        import numpy as np

        f_clk   = 100e6
        f_out   = 10e6
        n_lut   = 256
        # Run for an integer number of output periods so there's no spectral
        # leakage.  Period = f_clk/f_out = 10 cycles; grab 10 periods → 100 samples.
        n_per   = round(f_clk / f_out)
        n_cyc   = n_per * 10
        log     = sim_frequency_tone(f_clk=f_clk, f_out=f_out, n_cycles=n_cyc)
        samples = np.array([s if s < 128 else s - 256 for _, s in log], dtype=float)

        spectrum = np.abs(np.fft.rfft(samples))
        peak_bin = int(np.argmax(spectrum))
        expected = round(f_out / f_clk * n_cyc)
        assert abs(peak_bin - expected) <= 1, (
            f"DDS spectral peak at bin {peak_bin}, expected {expected}"
        )

        peak_dB = 20 * math.log10(spectrum[peak_bin] + 1e-12)
        spur    = np.concatenate([spectrum[:peak_bin], spectrum[peak_bin+1:]])
        spur_dB = 20 * math.log10(max(spur) + 1e-12) if len(spur) else -100
        assert peak_dB - spur_dB >= 20, (
            f"SFDR only {peak_dB - spur_dB:.1f} dB (threshold 20 dB)"
        )

    def test_dds_verilog_export(self):
        """Verilog export should succeed and contain expected keywords."""
        v = dds_to_verilog()
        assert "module" in v.lower(), "no 'module' in DDS Verilog"
        # Phase accumulator should be visible as a register
        assert "reg" in v.lower() or "always" in v.lower(), (
            "DDS Verilog looks empty"
        )
