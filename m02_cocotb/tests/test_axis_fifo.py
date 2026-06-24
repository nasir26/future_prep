"""
M02 ex02 — AXI4-Stream FIFO: directed Driver / Monitor / Scoreboard tests
==========================================================================
What you learn here
-------------------
  * Why the Driver / Monitor / Scoreboard (DMS) pattern exists and how
    each layer maps to AXI4-Stream concepts.
  * How cocotb.start_soon() lets you run concurrent coroutines — crucial
    for back-pressure scenarios where send and receive must happen at the
    same time.
  * How a Scoreboard decouples "what I sent" from "when I check it."

Timing: same Timer(1, "ps") settle pattern as test_counter.py (see that
file's docstring for the explanation).

DUT: axis_fifo.sv  (DATA_W=8, DEPTH=16)

Author: Nasir Ali, C-DAC Noida
"""

import logging
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles, Timer

from fifo_bfm import AxisSource, AxisSink, Scoreboard

log    = logging.getLogger("cocotb.test")
SETTLE = Timer(1, unit="ps")


# ─── Shared helpers ─────────────────────────────────────────────────────────
async def _reset(dut, n: int = 4) -> None:
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, n)
    await SETTLE
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await SETTLE


async def _start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())


# ══════════════════════════════════════════════════════════════════════════
# Test 1 — single beat roundtrip
# ══════════════════════════════════════════════════════════════════════════
@cocotb.test()
async def test_single_beat(dut):
    """Write one byte with tlast=1, read it back; verify data and framing."""
    await _start_clock(dut)
    await _reset(dut)

    src = AxisSource(dut)
    snk = AxisSink(dut, always_ready=True)
    sb  = Scoreboard(log)

    sb.expect(0xAB, last=True)

    send = cocotb.start_soon(src.send(0xAB, last=True))
    data, last = await snk.recv_beat()
    await send

    sb.check(data, last)
    sb.assert_done()
    log.info("PASS test_single_beat")


# ══════════════════════════════════════════════════════════════════════════
# Test 2 — multi-byte packet roundtrip
# ══════════════════════════════════════════════════════════════════════════
@cocotb.test()
async def test_packet_roundtrip(dut):
    """Send a 6-byte packet; verify all bytes arrive in order with correct tlast."""
    await _start_clock(dut)
    await _reset(dut)

    src = AxisSource(dut)
    snk = AxisSink(dut, always_ready=True)
    sb  = Scoreboard(log)

    payload = [0x10, 0x20, 0x30, 0x40, 0x50, 0x60]
    for i, byte in enumerate(payload):
        sb.expect(byte, last=(i == len(payload) - 1))

    send = cocotb.start_soon(src.send_packet(payload))
    packet = await snk.recv_packet()
    await send

    for data, last in packet:
        sb.check(data, last)
    sb.assert_done()
    log.info("PASS test_packet_roundtrip")


# ══════════════════════════════════════════════════════════════════════════
# Test 3 — fill to capacity then drain
# ══════════════════════════════════════════════════════════════════════════
@cocotb.test()
async def test_fill_and_drain(dut):
    """
    Write DEPTH=16 beats with tready=0, then drain all at once.
    Verifies tready de-asserts on full and fill_level reaches DEPTH.
    """
    await _start_clock(dut)
    await _reset(dut)

    DEPTH = 16
    src = AxisSource(dut)
    sb  = Scoreboard(log)

    dut.m_axis_tready.value = 0

    for i in range(DEPTH):
        is_last = (i == DEPTH - 1)
        sb.expect(i, last=is_last)
        await src.send(i, last=is_last)

    await RisingEdge(dut.clk)
    await SETTLE
    assert int(dut.s_axis_tready.value) == 0, "FAIL: FIFO full but tready=1"
    assert int(dut.fill_level.value) == DEPTH, (
        f"FAIL: fill_level should be {DEPTH}, got {int(dut.fill_level.value)}"
    )

    # Now drain
    snk = AxisSink(dut, always_ready=True)
    for _ in range(DEPTH):
        data, last = await snk.recv_beat()
        sb.check(data, last)

    sb.assert_done()
    log.info("PASS test_fill_and_drain")


# ══════════════════════════════════════════════════════════════════════════
# Test 4 — back-to-back packets (tlast delineation)
# ══════════════════════════════════════════════════════════════════════════
@cocotb.test()
async def test_back_to_back_packets(dut):
    """
    Two packets back-to-back; verify tlast correctly delineates packet boundaries.
    AXI4-S does not require an idle cycle between packets.
    """
    await _start_clock(dut)
    await _reset(dut)

    src = AxisSource(dut)
    snk = AxisSink(dut, always_ready=True)
    sb  = Scoreboard(log)

    pkts = [[0xAA, 0xBB, 0xCC], [0x11, 0x22]]
    for pkt in pkts:
        for i, b in enumerate(pkt):
            sb.expect(b, last=(i == len(pkt) - 1))

    async def _send_all():
        for pkt in pkts:
            await src.send_packet(pkt)

    send_all = cocotb.start_soon(_send_all())
    pkt1 = await snk.recv_packet()
    pkt2 = await snk.recv_packet()
    await send_all

    for data, last in pkt1 + pkt2:
        sb.check(data, last)
    sb.assert_done()
    log.info("PASS test_back_to_back_packets")


# ══════════════════════════════════════════════════════════════════════════
# Test 5 — simultaneous push and pop (fill_level stable)
# ══════════════════════════════════════════════════════════════════════════
@cocotb.test()
async def test_simultaneous_push_pop(dut):
    """
    When write and read complete on the same edge, fill_level must stay constant.
    Tests the 2'b11 case of the case statement in axis_fifo.sv.
    """
    await _start_clock(dut)
    await _reset(dut)

    src = AxisSource(dut)

    # Pre-fill with 8 beats
    dut.m_axis_tready.value = 0
    for i in range(8):
        await src.send(i, last=(i == 7))

    await RisingEdge(dut.clk)
    await SETTLE
    mid_level = int(dut.fill_level.value)
    assert mid_level == 8, f"Pre-fill failed: fill_level={mid_level}"

    # Simultaneously push and pop for 4 cycles
    dut.m_axis_tready.value = 1
    for i in range(4):
        dut.s_axis_tvalid.value = 1
        dut.s_axis_tdata.value  = 0xFF - i
        dut.s_axis_tlast.value  = 0

        await RisingEdge(dut.clk)
        await SETTLE
        lvl = int(dut.fill_level.value)
        assert lvl == 8, (
            f"Cycle {i}: fill_level={lvl}, expected 8 during simultaneous push+pop"
        )

    dut.s_axis_tvalid.value = 0
    log.info("PASS test_simultaneous_push_pop")
