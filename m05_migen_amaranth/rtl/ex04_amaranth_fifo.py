"""
M05 ex04 — Amaranth: Same FIFO, Different Syntax
=================================================
The identical AXI-Stream FIFO from ex03, rewritten in Amaranth 0.5 syntax.

Direct syntax comparison table
--------------------------------
Migen                            Amaranth 0.5
──────────────────────────────────────────────────────────────────────────
Array([Signal() for i in ...])   Array([Signal() for i in ...])   ← same
self.comb += sig.eq(expr)        m.d.comb += sig.eq(expr)
self.sync += sig.eq(expr)        m.d.sync += sig.eq(expr)
If(c, ...).Elif(c2, ...).Else()  with m.If(c): / with m.Elif: / with m.Else:
Signal(max=N)                    Signal(range(N))

Simulation comparison
---------------------
Migen: generator-based testbench (yield, yield sig.eq(v))
Amaranth: async testbench (await ctx.tick(), ctx.set(sig, v), ctx.get(sig))

Why this comparison matters
---------------------------
ARTIQ's existing gateware (rtio.core, phys.*) is Migen.
New ARTIQ gateware is being rewritten in Amaranth (e.g., Phaser support).
You will encounter BOTH in the codebase.

Author: Nasir Ali, C-DAC Noida
"""

import os
from amaranth import *
from amaranth.sim import Simulator


class StreamFIFO(Elaboratable):
    """
    AXI-Stream FIFO in Amaranth; functionally identical to ex03_migen_fifo.

    The shapes, port names, and fill logic are all identical — only the
    Python syntax for constructing the RTL differs.
    """

    def __init__(self, data_width: int = 8, depth: int = 16):
        assert (depth & (depth - 1)) == 0, "depth must be a power of 2"
        self._depth      = depth
        self._data_width = data_width
        ptr_bits         = (depth - 1).bit_length()

        self.s_valid = Signal()
        self.s_ready = Signal()
        self.s_data  = Signal(data_width)
        self.m_valid = Signal()
        self.m_ready = Signal()
        self.m_data  = Signal(data_width)
        self.fill    = Signal(range(depth + 1))

        self._ptr_bits = ptr_bits

    def elaborate(self, platform):
        m   = Module()
        depth    = self._depth
        ptr_bits = self._ptr_bits

        mem    = Array(Signal(self._data_width, name=f"cell{i}") for i in range(depth))
        wr_ptr = Signal(ptr_bits)
        rd_ptr = Signal(ptr_bits)

        do_write = Signal()
        do_read  = Signal()

        m.d.comb += [
            self.s_ready.eq(self.fill < depth),
            self.m_valid.eq(self.fill > 0),
            self.m_data.eq(mem[rd_ptr]),
            do_write.eq(self.s_valid & self.s_ready),
            do_read.eq(self.m_valid  & self.m_ready),
        ]

        with m.If(do_write):
            m.d.sync += mem[wr_ptr].eq(self.s_data)
            m.d.sync += wr_ptr.eq(wr_ptr + 1)
        with m.If(do_read):
            m.d.sync += rd_ptr.eq(rd_ptr + 1)

        with m.If(do_write & ~do_read):
            m.d.sync += self.fill.eq(self.fill + 1)
        with m.Elif(do_read & ~do_write):
            m.d.sync += self.fill.eq(self.fill - 1)

        return m


# ═══════════════════════════════════════════════════════════════════════════
#  Simulation helpers — Amaranth async style
# ═══════════════════════════════════════════════════════════════════════════

def sim_single_beat(data: int = 0xAB) -> tuple:
    """
    Push one beat, capture it, return (data, fill).

    Timing note (Amaranth vs Migen):
      In Migen testbenches, `(yield sig)` reads at the RISING EDGE (pre-sync);
      in Amaranth, `ctx.get(sig)` reads POST-edge (after sync registers update).
      We therefore sample m_data BEFORE the tick that would pop the element.
    """
    dut = StreamFIFO()
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    result = []

    async def tb(ctx):
        ctx.set(dut.m_ready, 1)
        await ctx.tick().repeat(2)
        ctx.set(dut.s_valid, 1)
        ctx.set(dut.s_data, data)
        await ctx.tick()             # push: fill 0 → 1
        ctx.set(dut.s_valid, 0)
        # Sample BEFORE the next tick pops the element.
        # After the push tick, m_valid=1, m_data=mem[0]=data, fill=1.
        if ctx.get(dut.m_valid) and ctx.get(dut.m_ready):
            result.append((ctx.get(dut.m_data), ctx.get(dut.fill)))
        await ctx.tick()             # pop

    sim.add_testbench(tb)
    sim.run()
    return result[0] if result else (None, None)


def sim_fill_and_drain(depth: int = 16) -> dict:
    """
    Fill the FIFO to capacity then drain completely.

    Uses "sample-before-tick" so that m_data is read while rd_ptr still
    points at the element being presented (Amaranth post-edge read model).
    """
    dut = StreamFIFO(depth=depth)
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    log = {}

    async def tb(ctx):
        ctx.set(dut.m_ready, 0)
        await ctx.tick().repeat(2)

        for i in range(depth):
            ctx.set(dut.s_valid, 1)
            ctx.set(dut.s_data, i)
            await ctx.tick()
        ctx.set(dut.s_valid, 0)
        await ctx.tick()             # one settling tick

        log["fill_after_push"]   = ctx.get(dut.fill)
        log["s_ready_when_full"] = ctx.get(dut.s_ready)

        received = []
        ctx.set(dut.m_ready, 1)
        # Sample BEFORE each tick: m_data = mem[rd_ptr] (pre-pop value).
        for _ in range(depth + 2):
            if ctx.get(dut.m_valid) and ctx.get(dut.m_ready):
                received.append(ctx.get(dut.m_data))
            await ctx.tick()         # pops element, rd_ptr advances
        log["received"] = received

    sim.add_testbench(tb)
    sim.run()
    return log


def elaborate_to_verilog(outfile: str = None) -> str:
    """Elaborate StreamFIFO to Verilog; optionally write to file."""
    from amaranth.back.verilog import convert
    dut = StreamFIFO()
    v   = convert(dut, ports=[
        dut.s_valid, dut.s_ready, dut.s_data,
        dut.m_valid, dut.m_ready, dut.m_data,
        dut.fill,
    ])
    if outfile:
        with open(outfile, "w") as f:
            f.write(v)
    return v


if __name__ == "__main__":
    waves = os.path.expanduser("~/future_prep/waves")
    dut   = StreamFIFO()
    sim   = Simulator(dut)
    sim.add_clock(1e-6)

    async def tb(ctx):
        ctx.set(dut.m_ready, 1)
        for i in range(8):
            ctx.set(dut.s_valid, 1)
            ctx.set(dut.s_data, i * 0x10)
            await ctx.tick()
        ctx.set(dut.s_valid, 0)
        await ctx.tick().repeat(12)

    sim.add_testbench(tb)
    with sim.write_vcd(f"{waves}/m05_amaranth_fifo.vcd"):
        sim.run()
    print("VCD written to waves/m05_amaranth_fifo.vcd")
