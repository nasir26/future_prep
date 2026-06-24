"""
M02 ex01 — Hello cocotb
========================
Goal: build muscle memory for the four primitives every cocotb test uses.

Primitive           What it does
---------           ------------
@cocotb.test()      Marks an async def as a runnable test case.
Clock(sig, T, unit) Generates a periodic clock without blocking the test.
cocotb.start_soon   Schedules a coroutine concurrently (fire-and-forget).
RisingEdge(sig)     Suspends until the next rising edge on sig.
ClockCycles(sig,n)  Suspends until n rising edges have passed.
Timer(t, unit)      Suspends for a real time interval.
dut.<port>.value=x  Drive a signal.
int(dut.<port>.val) Read a signal as a Python integer.

Timing note — why Timer(1, unit="ps") after each edge
------------------------------------------------------
cocotb's VPI callback fires at the SAME simulator time as the rising edge,
but BEFORE iverilog's always @(posedge clk) blocks execute.  If you read a
register immediately after RisingEdge, you get the PRE-edge value.

Solution: advance 1 ps after the edge.  Verilog guarantees all delta cycles
at a given sim time complete before time advances, so after Timer(1, "ps")
all register updates have settled and the read is correct.

This keeps us in the "active" phase (unlike ReadOnly, which forbids driving).

DUT: counter.v  — 4-bit synchronous up-counter
  Ports: clk, rst (sync active-high), en, count[WIDTH-1:0]

Author: Nasir Ali, C-DAC Noida
"""

import logging
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles, Timer

log = logging.getLogger("cocotb.test")

# Convenience: 1 ps settle window after any posedge
SETTLE = Timer(1, unit="ps")


# ─── Shared helper ─────────────────────────────────────────────────────────
async def _reset(dut, n_cycles: int = 2) -> None:
    """Assert rst for n_cycles clock cycles then release."""
    dut.rst.value = 1
    dut.en.value  = 0
    await ClockCycles(dut.clk, n_cycles)
    await SETTLE          # let any RTL processing finish
    dut.rst.value = 0     # release: still in active phase → drive is legal


# ══════════════════════════════════════════════════════════════════════════
# Test 1 — synchronous reset drives count to 0
# ══════════════════════════════════════════════════════════════════════════
@cocotb.test()
async def test_reset(dut):
    """Synchronous reset must force count to 0 within one clock cycle."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.rst.value = 1
    dut.en.value  = 0
    await ClockCycles(dut.clk, 3)
    await SETTLE

    got = int(dut.count.value)
    assert got == 0, f"FAIL test_reset: expected count=0, got {got}"
    log.info("PASS test_reset")


# ══════════════════════════════════════════════════════════════════════════
# Test 2 — counter increments once per enabled clock edge
# ══════════════════════════════════════════════════════════════════════════
@cocotb.test()
async def test_count_up(dut):
    """With en=1 the count must increase by exactly 1 on every rising edge."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    dut.en.value = 1
    for expected in range(1, 12):
        await RisingEdge(dut.clk)
        await SETTLE           # 1 ps after posedge: register updates complete
        got = int(dut.count.value)
        assert got == expected, f"FAIL test_count_up: step {expected}: got {got}"
    log.info("PASS test_count_up")


# ══════════════════════════════════════════════════════════════════════════
# Test 3 — 4-bit rollover (15 → 0)
# ══════════════════════════════════════════════════════════════════════════
@cocotb.test()
async def test_rollover(dut):
    """A 4-bit counter must roll over from 15 back to 0 on the next enabled edge."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    dut.en.value = 1
    await ClockCycles(dut.clk, 15)
    await SETTLE
    assert int(dut.count.value) == 15, (
        f"FAIL: expected 15 before rollover, got {int(dut.count.value)}"
    )
    await RisingEdge(dut.clk)   # 15 + 1 = 16 → wraps to 0 in 4 bits
    await SETTLE
    got = int(dut.count.value)
    assert got == 0, f"FAIL test_rollover: expected 0 after rollover, got {got}"
    log.info("PASS test_rollover")


# ══════════════════════════════════════════════════════════════════════════
# Test 4 — enable gate freezes count
# ══════════════════════════════════════════════════════════════════════════
@cocotb.test()
async def test_enable_gate(dut):
    """With en=0 the count must remain frozen regardless of how many edges pass."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    dut.en.value = 1
    await ClockCycles(dut.clk, 5)
    await SETTLE
    frozen = int(dut.count.value)

    dut.en.value = 0
    await ClockCycles(dut.clk, 10)
    await SETTLE
    got = int(dut.count.value)
    assert got == frozen, (
        f"FAIL test_enable_gate: count changed from {frozen} to {got} while en=0"
    )
    log.info("PASS test_enable_gate")


# ══════════════════════════════════════════════════════════════════════════
# Test 5 — reset while running re-zeroes immediately
# ══════════════════════════════════════════════════════════════════════════
@cocotb.test()
async def test_reset_while_running(dut):
    """Asserting rst mid-count must snap count back to 0 on the next edge."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    dut.en.value = 1
    await ClockCycles(dut.clk, 7)
    await SETTLE
    assert int(dut.count.value) == 7, (
        f"Pre-check: expected 7, got {int(dut.count.value)}"
    )

    dut.rst.value = 1
    await RisingEdge(dut.clk)
    await SETTLE
    got = int(dut.count.value)
    assert got == 0, f"FAIL test_reset_while_running: expected 0, got {got}"
    log.info("PASS test_reset_while_running")
