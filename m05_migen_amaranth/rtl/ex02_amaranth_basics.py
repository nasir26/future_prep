"""
M05 ex02 — Amaranth 0.5: Elaboratable, m.d.sync, with m.If(), FSM
==================================================================
Amaranth (formerly nMigen) is Migen's successor.  It has a cleaner Python
API and better type safety, but the core concepts are identical.

Key differences from Migen
--------------------------
Migen                        Amaranth 0.5
─────────────────────────────────────────────────────────────────
class X(Module)              class X(Elaboratable): def elaborate()→Module
self.sync += [...]           m.d.sync += [...] inside elaborate()
If(cond, ...).Elif(...)      with m.If(cond): / with m.Elif(cond):
self.submodules.fsm = FSM()  m.submodules.fsm = FSM()   (same pattern)
yield sig                    ctx.get(sig)          in testbench
yield sig.eq(v)              ctx.set(sig, v)       in testbench
(yield) / for _ in range(n): yield    await ctx.tick() / .repeat(n)

Why Amaranth for new code
--------------------------
1. Better Python syntax (context managers not nested function calls)
2. Type-level shape system (signed/unsigned widths)
3. Structured modules via the lib.* hierarchy
4. Active development (ARTIQ Migen gateware is legacy; new RTL uses Amaranth)

Author: Nasir Ali, C-DAC Noida
"""

from amaranth import *
from amaranth.sim import Simulator


# ═══════════════════════════════════════════════════════════════════════════
#  Design 1 — Same counter as ex01 in Amaranth syntax
# ═══════════════════════════════════════════════════════════════════════════

class Counter(Elaboratable):
    """
    WIDTH-bit synchronous counter; direct Amaranth translation of ex01.

    Comparison with Migen
    ---------------------
    Migen: self.sync += If(self.rst, self.count.eq(0)).Elif(...)
    Amaranth: with m.If(self.rst): m.d.sync += self.count.eq(0)
    """

    def __init__(self, width: int = 8):
        self.en    = Signal()
        self.rst   = Signal()
        self.count = Signal(width)

    def elaborate(self, platform):
        m = Module()
        # Context-manager If/Elif/Else — note: 'm.If', not 'if'
        with m.If(self.rst):
            m.d.sync += self.count.eq(0)
        with m.Elif(self.en):
            m.d.sync += self.count.eq(self.count + 1)
        return m


# ═══════════════════════════════════════════════════════════════════════════
#  Design 2 — Same ToggleFSM in Amaranth
# ═══════════════════════════════════════════════════════════════════════════

class ToggleFSM(Elaboratable):
    """
    Toggle output each time trigger pulses.

    Amaranth FSM
    ------------
    from amaranth.lib.fsm import FSM  ← Amaranth 0.4
    In 0.5, FSM is integrated into Module:
      with m.FSM() as fsm:
          with m.State("IDLE"):
              with m.If(self.trigger):
                  m.next = "WAIT_RELEASE"  ← state transition keyword
    """

    def __init__(self):
        self.trigger = Signal()
        self.out     = Signal()

    def elaborate(self, platform):
        m = Module()
        with m.FSM() as fsm:
            with m.State("IDLE"):
                with m.If(self.trigger):
                    m.d.sync += self.out.eq(~self.out)
                    m.next = "WAIT_RELEASE"
            with m.State("WAIT_RELEASE"):
                with m.If(~self.trigger):
                    m.next = "IDLE"
        return m


# ═══════════════════════════════════════════════════════════════════════════
#  Amaranth simulation helpers
# ═══════════════════════════════════════════════════════════════════════════

def sim_counter(n_cycles: int = 16, width: int = 8) -> list:
    """Run counter; return list of (rst, en, count) per cycle."""
    dut = Counter(width)
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    log = []

    async def tb(ctx):
        # Reset
        ctx.set(dut.rst, 1)
        for _ in range(2):
            await ctx.tick()
            log.append((1, 0, ctx.get(dut.count)))
        ctx.set(dut.rst, 0)
        ctx.set(dut.en, 1)
        for _ in range(n_cycles - 2):
            await ctx.tick()
            log.append((0, 1, ctx.get(dut.count)))

    sim.add_testbench(tb)
    sim.run()
    return log


def sim_toggle_fsm() -> list:
    """Run toggle FSM; return (trigger, out) per cycle."""
    dut = ToggleFSM()
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    log = []

    async def tb(ctx):
        for trig, n in [(0, 2), (1, 2), (0, 2), (1, 2), (0, 2)]:
            ctx.set(dut.trigger, trig)
            for _ in range(n):
                await ctx.tick()
                log.append((ctx.get(dut.trigger), ctx.get(dut.out)))

    sim.add_testbench(tb)
    sim.run()
    return log


def elaborate_to_verilog(outfile: str = None) -> str:
    """
    Convert Counter to Verilog via Amaranth → RTLIL → Yosys.

    Returns the Verilog string.  If outfile given, also writes to disk.
    """
    from amaranth.back.verilog import convert
    dut = Counter()
    v   = convert(dut, ports=[dut.en, dut.rst, dut.count])
    if outfile:
        with open(outfile, "w") as f:
            f.write(v)
    return v


if __name__ == "__main__":
    import os
    waves = os.path.expanduser("~/future_prep/waves")
    dut = Counter()
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    async def tb(ctx):
        ctx.set(dut.rst, 1)
        await ctx.tick()
        await ctx.tick()
        ctx.set(dut.rst, 0)
        ctx.set(dut.en, 1)
        await ctx.tick().repeat(20)

    sim.add_testbench(tb)
    with sim.write_vcd(f"{waves}/m05_amaranth_counter.vcd"):
        sim.run()
    print("VCD written to waves/m05_amaranth_counter.vcd")
