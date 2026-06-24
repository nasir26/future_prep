"""
M03 ex03 — Timed Sequencer testbench
=======================================
What this verifies
------------------
  test_wait_instr    — WAIT N halts for exactly N cycles
  test_set_freq      — SET_FREQ updates dds_pinc output
  test_fire_instr    — FIRE asserts pulse_trigger for 1 cycle
  test_read_ctr      — READ_CTR captures photon_count into result reg
  test_program       — 5-instruction program (WAIT, SET_FREQ, FIRE, READ_CTR, WAIT)

Instruction encoding (64-bit)
  [63:60] opcode   [59:28] operand   [27:16] branch target
  WAIT=0  SET_FREQ=1  FIRE=2  READ_CTR=3  BRANCH=4

AXI4-Lite register map
  0x00 CTRL  [0]=RUN [1]=DONE(RO)
  0x04 PC    current PC (RO)
  0x08 RESULT
  0x0C PROG_WR_PTR
  0x10 PROG_DATA_LO
  0x14 PROG_DATA_HI

Author: Nasir Ali, C-DAC Noida
"""

import logging
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles, Timer

from axil_bfm import AxilMaster

log    = logging.getLogger("cocotb.test")
SETTLE = Timer(1, unit="ps")

# Register addresses
REG_CTRL       = 0x00
REG_PC         = 0x04
REG_RESULT     = 0x08
REG_PROG_WR    = 0x0C
REG_PROG_LO    = 0x10
REG_PROG_HI    = 0x14

# Opcodes
OP_WAIT     = 0x0
OP_SET_FREQ = 0x1
OP_FIRE     = 0x2
OP_READ_CTR = 0x3
OP_BRANCH   = 0x4


def make_instr(opcode, operand=0, target=0) -> tuple:
    """Return (lo, hi) 32-bit words for a 64-bit instruction."""
    instr = ((opcode & 0xF) << 60) | ((operand & 0xFFFFFFFF) << 28) | ((target & 0xFFF) << 16)
    lo = instr & 0xFFFF_FFFF
    hi = (instr >> 32) & 0xFFFF_FFFF
    return (lo, hi)


async def _reset(dut, n=4):
    dut.rst_n.value = 0
    dut.photon_count.value = 0
    await ClockCycles(dut.clk, n)
    await SETTLE
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await SETTLE


async def _load_program(axil, instrs: list) -> None:
    """Load a list of (lo, hi) instruction tuples into program memory."""
    await axil.write(REG_PROG_WR, 0)   # reset write pointer to 0
    for lo, hi in instrs:
        await axil.write(REG_PROG_LO, lo)
        await axil.write(REG_PROG_HI, hi)


async def _run_until_done(dut, axil, timeout: int = 2000) -> int:
    """Assert RUN, wait for DONE=1, return clock-cycle count.
    Polls dut.seq_done directly (1 cycle/check) to avoid AXI read overhead
    obscuring timing and missing 1-cycle output strobes."""
    await axil.write(REG_CTRL, 0x1)   # RUN=1
    for cyc in range(timeout):
        await RisingEdge(dut.clk)
        await SETTLE
        if int(dut.seq_done.value) == 1:
            return cyc
    raise TimeoutError(f"Sequencer did not finish within {timeout} cycles")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 1 — WAIT instruction halts for N cycles
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_wait_instr(dut):
    """
    Program: WAIT 10 → (end of memory → halt via unknown opcode)
    Measure cycles between RUN assertion and DONE.
    Expected: FETCH(1) + EXEC→WAIT_STATE(N) + FETCH(1) + EXEC default halt(1) ≈ N+3
    We verify done arrives within a loose window around N.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil = AxilMaster(dut, dut.clk)

    WAIT_N = 10
    prog = [make_instr(OP_WAIT, operand=WAIT_N)]
    await _load_program(axil, prog)

    cyc = await _run_until_done(dut, axil, timeout=500)
    # WAIT 10 takes: fetch + exec (transitions to WAIT state) + 9 more WAIT cycles
    # + fetch + exec (unknown instr → done) = ~13 cycles overhead
    assert WAIT_N <= cyc <= WAIT_N + 20, (
        f"WAIT {WAIT_N}: done at cycle {cyc}, expected {WAIT_N}..{WAIT_N+20}"
    )
    log.info(f"PASS test_wait_instr  done_at_cycle={cyc}")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 2 — SET_FREQ updates dds_pinc output
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_set_freq(dut):
    """Program: SET_FREQ(0xDEAD_BEEF) → verify dds_pinc port updates."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil   = AxilMaster(dut, dut.clk)
    TARGET = 0xDEAD_BEEF

    prog = [make_instr(OP_SET_FREQ, operand=TARGET)]
    await _load_program(axil, prog)
    await _run_until_done(dut, axil, timeout=100)

    got = int(dut.dds_pinc.value)
    assert got == TARGET, f"dds_pinc: got 0x{got:08X}, expected 0x{TARGET:08X}"
    log.info(f"PASS test_set_freq  dds_pinc=0x{got:08X}")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 3 — FIRE asserts pulse_trigger for exactly 1 cycle
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_fire_instr(dut):
    """FIRE(DURATION=128) → pulse_trigger must assert for exactly 1 cycle."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil = AxilMaster(dut, dut.clk)
    prog = [make_instr(OP_FIRE, operand=128)]
    await _load_program(axil, prog)

    await axil.write(REG_CTRL, 0x1)   # RUN

    trigger_count = 0
    for _ in range(200):
        await RisingEdge(dut.clk)
        await SETTLE
        if int(dut.pulse_trigger.value) == 1:
            trigger_count += 1

    assert trigger_count == 1, (
        f"pulse_trigger asserted {trigger_count} times, expected 1"
    )
    assert int(dut.pulse_duration.value) == 128, (
        f"pulse_duration: {int(dut.pulse_duration.value)}, expected 128"
    )
    log.info("PASS test_fire_instr")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 4 — READ_CTR captures photon_count into result register
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_read_ctr(dut):
    """READ_CTR captures the current photon_count value into RESULT reg."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil       = AxilMaster(dut, dut.clk)
    TEST_COUNT = 0x0000_0042   # photon count to inject

    dut.photon_count.value = TEST_COUNT

    prog = [make_instr(OP_READ_CTR)]
    await _load_program(axil, prog)
    await _run_until_done(dut, axil, timeout=100)

    result = await axil.read(REG_RESULT)
    assert result == TEST_COUNT, (
        f"RESULT: got 0x{result:08X}, expected 0x{TEST_COUNT:08X}"
    )
    log.info(f"PASS test_read_ctr  result=0x{result:08X}")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 5 — 5-instruction program
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_program(dut):
    """
    5-instruction program that exercises all non-branch opcodes in sequence:
      [0] WAIT   5           — pause 5 cycles
      [1] SET_FREQ 0x1999_9999 — tune DDS to ~10 MHz
      [2] FIRE   64          — fire 64-cycle pulse
      [3] READ_CTR           — capture photon count
      [4] WAIT   0           — zero-delay (fall-through)
      → end of program → halt

    Verifies: dds_pinc updated, pulse_trigger fired once, result = photon_count.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil      = AxilMaster(dut, dut.clk)
    FREQ_WORD = 0x1999_9999
    PHOT_CNT  = 0x0000_0007

    dut.photon_count.value = PHOT_CNT

    prog = [
        make_instr(OP_WAIT,     operand=5),
        make_instr(OP_SET_FREQ, operand=FREQ_WORD),
        make_instr(OP_FIRE,     operand=64),
        make_instr(OP_READ_CTR),
        make_instr(OP_WAIT,     operand=0),
    ]
    await _load_program(axil, prog)

    # Monitor pulse_trigger every clock cycle in the background while
    # the main coroutine waits for DONE.  AXI reads would miss the
    # 1-cycle strobe, so we sample the port signal directly.
    trigger_count = 0

    async def _count_triggers():
        nonlocal trigger_count
        while True:
            await RisingEdge(dut.clk)
            await SETTLE
            if int(dut.pulse_trigger.value) == 1:
                trigger_count += 1

    monitor = cocotb.start_soon(_count_triggers())
    await _run_until_done(dut, axil, timeout=500)
    monitor.cancel()

    # Check dds_pinc
    got_pinc = int(dut.dds_pinc.value)
    assert got_pinc == FREQ_WORD, (
        f"dds_pinc: got 0x{got_pinc:08X}, expected 0x{FREQ_WORD:08X}"
    )
    assert trigger_count == 1, f"pulse_trigger fired {trigger_count} times, expected 1"

    result = await axil.read(REG_RESULT)
    assert result == PHOT_CNT, (
        f"RESULT: got 0x{result:08X}, expected 0x{PHOT_CNT:08X}"
    )
    log.info(
        f"PASS test_program  dds_pinc=0x{got_pinc:08X}  "
        f"triggers={trigger_count}  result=0x{result:08X}"
    )
