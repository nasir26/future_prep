"""
M05 ex03 — Migen: AXI-Stream-like Sync FIFO
=============================================
A synchronous FIFO with a valid/ready stream interface — the same protocol
used by ARTIQ's RTIO fabric and the AXI4-Stream channels in M02.

This design uses Migen's Array primitive for the storage elements, giving
a purely register-based FIFO.  In real gateware you'd use a BRAM (Memory)
for large FIFOs, but registers are simpler to simulate and verify.

Key Migen primitives used
--------------------------
Array(...)       — indexed array of signals; synthesises as a mux
Mux(sel, a, b)   — combinational 2-to-1 mux
Signal(max=N)    — signal wide enough to represent [0, N)
self.specials += — attach non-module Migen objects (Memory, Instance, ...)

Why valid/ready?
----------------
The handshake rule: a beat is transferred when BOTH valid AND ready are high
on the SAME rising clock edge.  The sender drives valid+data; the receiver
drives ready.  This decouples producer and consumer timing.

Comparison with M01/M02
------------------------
This module is the Python/Migen equivalent of m01_sv_sva/rtl/axi_stream_fifo.sv
and the DUT tested by m02_cocotb/.  Same protocol, same fill/drain logic —
different implementation language.

Author: Nasir Ali, C-DAC Noida
"""

from migen import *
from migen.sim import run_simulation


class StreamFIFO(Module):
    """
    AXI-Stream-style synchronous FIFO.

    Parameters
    ----------
    data_width : int — data bus width in bits (default 8)
    depth      : int — FIFO depth; MUST be a power of 2 for natural wrap

    Ports
    -----
    s_valid, s_data, s_ready  — slave (write) port
    m_valid, m_data, m_ready  — master (read) port
    fill                      — current fill level (0..depth)
    """

    def __init__(self, data_width: int = 8, depth: int = 16):
        assert (depth & (depth - 1)) == 0, "depth must be a power of 2"
        ptr_bits = (depth - 1).bit_length()

        # ── Stream ports ──────────────────────────────────────────────
        self.s_valid = Signal()
        self.s_ready = Signal()
        self.s_data  = Signal(data_width)
        self.m_valid = Signal()
        self.m_ready = Signal()
        self.m_data  = Signal(data_width)
        self.fill    = Signal(max=depth + 1)

        # ── Internal storage: Array of registers ──────────────────────
        # Array is synthesised as a multiplexer, not a BRAM.
        # For synthesis of large FIFOs, replace with Memory.
        mem     = Array(Signal(data_width, name=f"cell{i}") for i in range(depth))
        wr_ptr  = Signal(ptr_bits)   # write pointer (wraps naturally at 2^ptr_bits)
        rd_ptr  = Signal(ptr_bits)   # read pointer

        # ── Derived signals ───────────────────────────────────────────
        do_write = Signal()
        do_read  = Signal()

        self.comb += [
            self.s_ready.eq(self.fill < depth),  # not full
            self.m_valid.eq(self.fill > 0),       # not empty
            self.m_data.eq(mem[rd_ptr]),           # output word (registered ptr)
            do_write.eq(self.s_valid & self.s_ready),
            do_read.eq(self.m_valid  & self.m_ready),
        ]

        # ── Synchronous state ─────────────────────────────────────────
        self.sync += [
            If(do_write,
                mem[wr_ptr].eq(self.s_data),
                wr_ptr.eq(wr_ptr + 1),
            ),
            If(do_read,
                rd_ptr.eq(rd_ptr + 1),
            ),
            If(do_write & ~do_read,
                self.fill.eq(self.fill + 1),
            ).Elif(do_read & ~do_write,
                self.fill.eq(self.fill - 1),
            ),
        ]


# ═══════════════════════════════════════════════════════════════════════════
#  Testbench helpers
# ═══════════════════════════════════════════════════════════════════════════

def _clk(n: int = 1):
    """Advance N clock cycles in a Migen generator testbench."""
    for _ in range(n):
        yield


def sim_single_beat(data: int = 0xAB) -> tuple:
    """Push one beat, pop it, return (sent, received, fill_after)."""
    dut = StreamFIFO()

    def tb():
        # Give ready to receiver
        yield dut.m_ready.eq(1)
        yield from _clk(2)
        # Push
        yield dut.s_valid.eq(1)
        yield dut.s_data.eq(data)
        yield from _clk()
        yield dut.s_valid.eq(0)
        yield from _clk(2)

    result = []
    def observer():
        for _ in range(10):
            yield
            v = yield dut.m_valid
            r = yield dut.m_ready
            d = yield dut.m_data
            f = yield dut.fill
            if v and r:
                result.append((d, f))

    from migen.sim import run_simulation as _run
    _run(dut, [tb(), observer()])
    return result[0] if result else (None, None)


def sim_fill_and_drain(depth: int = 16) -> dict:
    """Fill FIFO to capacity then drain; return fill levels sampled."""
    dut = StreamFIFO(depth=depth)
    log = {}

    def tb():
        # Block read side
        yield dut.m_ready.eq(0)
        yield from _clk(2)

        # Push depth beats
        for i in range(depth):
            yield dut.s_valid.eq(1)
            yield dut.s_data.eq(i)
            yield from _clk()
        yield dut.s_valid.eq(0)
        yield from _clk()

        # Sample fill after filling
        log["fill_after_push"] = (yield dut.fill)
        log["s_ready_when_full"] = (yield dut.s_ready)

        # Drain
        yield dut.m_ready.eq(1)
        received = []
        for _ in range(depth + 2):
            yield from _clk()
            v = yield dut.m_valid
            r = yield dut.m_ready
            d = yield dut.m_data
            f = yield dut.fill
            if v and r:
                received.append(d)

        log["received"] = received

    run_simulation(dut, tb())
    return log


if __name__ == "__main__":
    import os
    waves = os.path.expanduser("~/future_prep/waves")
    dut = StreamFIFO()

    def tb():
        yield dut.m_ready.eq(1)
        for i in range(8):
            yield dut.s_valid.eq(1)
            yield dut.s_data.eq(i * 0x10)
            yield
        yield dut.s_valid.eq(0)
        for _ in range(12):
            yield

    run_simulation(dut, tb(), vcd_name=f"{waves}/m05_migen_fifo.vcd")
    print("VCD written to waves/m05_migen_fifo.vcd")
