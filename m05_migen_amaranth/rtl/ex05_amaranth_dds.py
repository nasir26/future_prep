"""
M05 ex05 — Amaranth: Phase Accumulator DDS with Array LUT
==========================================================
A synthesisable Direct-Digital Synthesis (DDS) core in Amaranth, then
exported to Verilog.  This connects Amaranth back to the M03 RFSoC RTL
module: the same DDS concept, now described in Python HDL.

DDS theory recap
-----------------
Phase accumulator: carries overflow at ΔΦ = PINC / 2^ACC_BITS per cycle.
Output index     : top LUT_BITS of accumulator address the sine LUT.
Sine LUT         : 2^LUT_BITS entries of the form round(A * sin(2π k / N)).

Amaranth features exercised
----------------------------
Array                — 256-entry sine LUT as a Signal array (ROM)
Cat(a, b)            — bit concatenation
Const(v, shape)      — compile-time constant
Shape / unsigned     — explicit signal widths (no magic)
Verilog export       — amaranth.back.verilog.convert()
                       (requires amaranth-yosys; pip install amaranth-yosys)

Interview question this prepares
----------------------------------
"Walk me through the ARTIQ DDS driver: what does set() do at the Migen
 gateware level?"  Answer: calls AD9910 SPI transaction driver, which
 generates a Migen RTL pulse; the frequency word maps to a PINC exactly
 as done here.

Author: Nasir Ali, C-DAC Noida
"""

import math
import os
from amaranth import *
from amaranth.sim import Simulator


# ── LUT generation helper ───────────────────────────────────────────────────

def build_sine_lut(lut_bits: int = 8, data_bits: int = 8) -> list:
    """
    Return list of LUT_N = 2**lut_bits sine samples, full-scale signed.

    For data_bits = 8: samples in range [−128, 127].
    """
    n    = 1 << lut_bits
    peak = (1 << (data_bits - 1)) - 1          # 127 for 8-bit signed
    return [round(peak * math.sin(2 * math.pi * k / n)) for k in range(n)]


# ── RTL ─────────────────────────────────────────────────────────────────────

class DDS(Elaboratable):
    """
    Phase-accumulator DDS with Array-based sine LUT.

    Parameters
    ----------
    acc_bits  : accumulator width (frequency resolution = f_clk / 2**acc_bits)
    lut_bits  : LUT address bits  (LUT depth = 2**lut_bits)
    data_bits : output sample width

    Ports
    -----
    pinc    : input  — phase increment (unsigned, acc_bits wide)
    poff    : input  — phase offset added before LUT lookup (lut_bits wide)
    en      : input  — 1 → accumulate; 0 → hold (and gate output to 0)
    rst     : input  — synchronous reset of accumulator
    phase   : output — current accumulator value (acc_bits)
    sine    : output — sine sample (data_bits, signed)
    """

    def __init__(self, acc_bits: int = 16, lut_bits: int = 8, data_bits: int = 8):
        self._acc_bits  = acc_bits
        self._lut_bits  = lut_bits
        self._data_bits = data_bits

        self.pinc  = Signal(acc_bits)
        self.poff  = Signal(lut_bits)
        self.en    = Signal()
        self.rst   = Signal()
        self.phase = Signal(acc_bits)
        self.sine  = Signal(Shape(data_bits, signed=True))

    def elaborate(self, platform):
        m = Module()

        acc_bits  = self._acc_bits
        lut_bits  = self._lut_bits
        data_bits = self._data_bits

        # ── Sine LUT: Array of constants ──────────────────────────────────
        # In synthesis this becomes a ROM (BRAM or distributed RAM).
        # Array of signals initialised once at elaboration time.
        lut_data = build_sine_lut(lut_bits, data_bits)
        lut      = Array(Const(v, Shape(data_bits, signed=True)) for v in lut_data)

        # ── Phase accumulator ─────────────────────────────────────────────
        acc     = Signal(acc_bits)        # internal accumulator
        lut_idx = Signal(lut_bits)        # LUT address: top lut_bits of acc + poff

        m.d.comb += lut_idx.eq(
            acc[acc_bits - lut_bits : acc_bits] + self.poff
        )

        with m.If(self.rst):
            m.d.sync += acc.eq(0)
        with m.Elif(self.en):
            m.d.sync += acc.eq(acc + self.pinc)

        m.d.comb += self.phase.eq(acc)

        # ── Output ────────────────────────────────────────────────────────
        with m.If(self.en):
            m.d.comb += self.sine.eq(lut[lut_idx])
        with m.Else():
            m.d.comb += self.sine.eq(0)

        return m


# ── Simulation helpers ───────────────────────────────────────────────────────

def sim_frequency_tone(
    f_clk:    float = 100e6,
    f_out:    float = 10e6,
    n_cycles: int   = 64,
) -> list:
    """
    Run DDS for n_cycles, return list of (phase, sine) tuples.

    Example: f_out/f_clk = 0.1  → period = 10 samples.
    """
    dut      = DDS()
    acc_bits = dut._acc_bits
    pinc_val = round(f_out / f_clk * (1 << acc_bits))

    sim = Simulator(dut)
    sim.add_clock(1 / f_clk)
    log = []

    async def tb(ctx):
        ctx.set(dut.en,   1)
        ctx.set(dut.pinc, pinc_val)
        ctx.set(dut.poff, 0)
        ctx.set(dut.rst,  0)
        for _ in range(n_cycles):
            await ctx.tick()
            log.append((ctx.get(dut.phase), ctx.get(dut.sine)))

    sim.add_testbench(tb)
    sim.run()
    return log


def sim_phase_offset(offset_turns: float = 0.25, n_cycles: int = 4) -> list:
    """
    Push two tones with the same PINC but different POFF.
    Returns (sine_ref, sine_offset) pairs.
    """
    dut      = DDS()
    acc_bits = dut._acc_bits
    lut_bits = dut._lut_bits
    pinc_val = round(0.1 * (1 << acc_bits))       # f_out = 0.1 × f_clk
    poff_val = round(offset_turns * (1 << lut_bits)) & ((1 << lut_bits) - 1)

    results = []

    for off in [0, poff_val]:
        inner_dut = DDS()
        inner_sim = Simulator(inner_dut)
        inner_sim.add_clock(1e-8)
        inner_log = []

        async def tb(ctx, poff=off):
            ctx.set(inner_dut.en,   1)
            ctx.set(inner_dut.pinc, pinc_val)
            ctx.set(inner_dut.poff, poff)
            for _ in range(n_cycles):
                await ctx.tick()
                inner_log.append(ctx.get(inner_dut.sine))

        inner_sim.add_testbench(tb)
        inner_sim.run()
        results.append(inner_log)

    return list(zip(results[0], results[1]))


def elaborate_to_verilog(outfile: str = None) -> str:
    """Export DDS to Verilog; optionally write to disk."""
    from amaranth.back.verilog import convert
    dut = DDS()
    v   = convert(dut, ports=[
        dut.pinc, dut.poff, dut.en, dut.rst, dut.phase, dut.sine
    ])
    if outfile:
        with open(outfile, "w") as f:
            f.write(v)
    return v


if __name__ == "__main__":
    waves    = os.path.expanduser("~/future_prep/waves")
    f_clk    = 100e6
    f_out    = 10e6
    acc_bits = 16
    pinc_val = round(f_out / f_clk * (1 << acc_bits))    # 6554

    dut = DDS()
    sim = Simulator(dut)
    sim.add_clock(1 / f_clk)

    async def tb(ctx):
        ctx.set(dut.en,   1)
        ctx.set(dut.pinc, pinc_val)
        for _ in range(256):
            await ctx.tick()

    sim.add_testbench(tb)
    with sim.write_vcd(f"{waves}/m05_amaranth_dds.vcd"):
        sim.run()
    print("VCD written to waves/m05_amaranth_dds.vcd")
    print(f"PINC={pinc_val} → f_out ≈ {pinc_val / (1<<acc_bits) * f_clk / 1e6:.3f} MHz")

    # Also export Verilog
    v = elaborate_to_verilog(f"{waves}/../m05_migen_amaranth/rtl/dds_gen.v")
    print(f"Verilog: {len(v.splitlines())} lines written to rtl/dds_gen.v")
