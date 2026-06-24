"""
M02 ex03 — Constrained-Random Stimulus + Functional Coverage Model
===================================================================
What this adds over ex02
-------------------------
  * Random packet lengths (1–DEPTH) and random data (0–255)
  * Random back-pressure on the consumer (m_axis_tready toggling)
  * Python functional coverage model with packet-length bins
  * assert_coverage() fails the test if any bin was never exercised

Why constrained-random?
  Directed tests verify the scenarios you thought of.
  Constrained-random finds the ones you didn't.

Coverage bins
  len_1    — single-beat packets
  len_2_8  — short packets
  len_9_15 — medium packets
  len_16   — max-size (fills FIFO completely)

Author: Nasir Ali, C-DAC Noida
"""

import logging
import cocotb
import random
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, ClockCycles, Timer

from fifo_bfm import AxisSource, AxisSink, Scoreboard

log    = logging.getLogger("cocotb.test")
SETTLE = Timer(1, unit="ps")


# ═══════════════════════════════════════════════════════════════════════════
#  Functional coverage model
# ═══════════════════════════════════════════════════════════════════════════

class CoverageModel:
    _BINS = {
        "len_1":    lambda n: n == 1,
        "len_2_8":  lambda n: 2 <= n <= 8,
        "len_9_15": lambda n: 9 <= n <= 15,
        "len_16":   lambda n: n == 16,
    }

    def __init__(self):
        self._hits       = {k: 0 for k in self._BINS}
        self.total_beats = 0

    def record_packet(self, length: int) -> None:
        self.total_beats += length
        for name, pred in self._BINS.items():
            if pred(length):
                self._hits[name] += 1

    def report(self) -> None:
        log.info(f"Coverage — total beats: {self.total_beats}")
        for name, count in self._hits.items():
            status = "OK" if count > 0 else "MISS"
            log.info(f"  [{status}] {name}: {count} packet(s)")

    def assert_coverage(self) -> None:
        misses = [name for name, count in self._hits.items() if count == 0]
        assert not misses, f"Coverage gaps: {misses}"


# ═══════════════════════════════════════════════════════════════════════════
#  Back-pressure background task
# ═══════════════════════════════════════════════════════════════════════════

async def _back_pressure_task(dut, prob_ready: float = 0.7) -> None:
    """
    Randomly toggles m_axis_tready each cycle to simulate a slow consumer.
    Lower prob_ready = heavier back-pressure.
    Cancel with task.cancel() when done.

    Drives tready at the FALLING edge (mid-cycle) so the new value is stable
    for the full second half of the cycle before recv_beat() samples it at the
    next rising edge.  This avoids a coroutine-ordering race: if we drove
    tready at the rising edge, this task (registered first via start_soon)
    would update tready before recv_beat() reads it in the same timestep.
    """
    while True:
        await FallingEdge(dut.clk)
        dut.m_axis_tready.value = int(random.random() < prob_ready)


# ─── Shared helpers ─────────────────────────────────────────────────────────
async def _reset(dut, n: int = 4) -> None:
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, n)
    await SETTLE
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await SETTLE


# ═══════════════════════════════════════════════════════════════════════════
#  Test 1 — many random packets under random back-pressure
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_random_packets(dut):
    """
    50 packets of random length (1–16) and data (0–255).
    Consumer has 70% ready probability.
    All bytes must arrive in-order. Coverage bins must all be hit.
    """
    random.seed(42)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    DEPTH    = 16
    NUM_PKTS = 50

    src = AxisSource(dut)
    snk = AxisSink(dut, always_ready=False)
    sb  = Scoreboard(log)
    cov = CoverageModel()

    bp = cocotb.start_soon(_back_pressure_task(dut, prob_ready=0.7))

    for _ in range(NUM_PKTS):
        pkt_len = random.randint(1, DEPTH)
        payload = [random.randint(0, 0xFF) for _ in range(pkt_len)]
        cov.record_packet(pkt_len)

        for i, byte in enumerate(payload):
            sb.expect(byte, last=(i == pkt_len - 1))

        send = cocotb.start_soon(src.send_packet(payload))
        received = []
        while True:
            beat = await snk.recv_beat()
            received.append(beat)
            if beat[1]:
                break
        await send

        for data, last in received:
            sb.check(data, last)

    sb.assert_done()
    cov.report()
    cov.assert_coverage()
    bp.cancel()
    log.info("PASS test_random_packets")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 2 — flow control (tready de-asserts on full, re-asserts when drained)
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_flow_control(dut):
    """Block reads, fill FIFO, confirm tready=0; drain, confirm tready=1."""
    random.seed(7)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    DEPTH = 16
    src   = AxisSource(dut)

    dut.m_axis_tready.value = 0

    for i in range(DEPTH):
        await src.send(i & 0xFF, last=(i == DEPTH - 1))

    await RisingEdge(dut.clk)
    await SETTLE
    assert int(dut.s_axis_tready.value) == 0, "FAIL: tready should be 0 (FIFO full)"
    assert int(dut.fill_level.value)    == DEPTH, (
        f"FAIL: fill_level={int(dut.fill_level.value)}, expected {DEPTH}"
    )

    dut.m_axis_tready.value = 1
    snk = AxisSink(dut, always_ready=True)
    for _ in range(DEPTH):
        await snk.recv_beat()

    await RisingEdge(dut.clk)
    await SETTLE
    assert int(dut.s_axis_tready.value) == 1, "FAIL: tready should be 1 (FIFO empty)"
    assert int(dut.fill_level.value)    == 0, (
        f"FAIL: fill_level={int(dut.fill_level.value)}, expected 0"
    )
    log.info("PASS test_flow_control")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 3 — heavy back-pressure (20% ready)
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_heavy_back_pressure(dut):
    """20 short packets (1–4 bytes) with 20% consumer readiness. All must arrive."""
    random.seed(123)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    src = AxisSource(dut)
    snk = AxisSink(dut, always_ready=False)
    sb  = Scoreboard(log)

    bp = cocotb.start_soon(_back_pressure_task(dut, prob_ready=0.20))

    for _ in range(20):
        pkt_len = random.randint(1, 4)
        payload = [random.randint(0, 0xFF) for _ in range(pkt_len)]
        for i, b in enumerate(payload):
            sb.expect(b, last=(i == pkt_len - 1))

        send = cocotb.start_soon(src.send_packet(payload))
        while True:
            beat = await snk.recv_beat()
            sb.check(beat[0], beat[1])
            if beat[1]:
                break
        await send

    sb.assert_done()
    bp.cancel()
    log.info("PASS test_heavy_back_pressure")
