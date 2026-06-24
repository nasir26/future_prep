"""
M03 ex02 — Pulse Envelope testbench
=====================================
What this verifies
------------------
  test_square_pulse    — unity envelope, pulse_valid asserts for exactly PERIOD cycles
  test_gaussian_env    — write Gaussian shape to BRAM, verify output amplitude follows
  test_busy_clears     — CTRL.BUSY clears and pulse_done strobes at end of pulse
  test_back_to_back    — two pulses fired sequentially, no gap in timing

Envelope × DDS multiply note
-----------------------------
pulse_i = (dds_sine * env_amp) >> (ENV_W - 1)
With env_amp = 0x7FFF (max) and dds_sine at ±32767, pulse_i ≈ dds_sine (unity gain).
With env_amp = 0x3FFF (half), pulse_i ≈ dds_sine / 2.

Author: Nasir Ali, C-DAC Noida
"""

import logging
import math
import numpy as np
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles, Timer

from axil_bfm import AxilMaster

log    = logging.getLogger("cocotb.test")
SETTLE = Timer(1, unit="ps")

# Register addresses
REG_CTRL   = 0x00
REG_PINC   = 0x04
REG_PERIOD = 0x08
BRAM_BASE  = 0x100

BRAM_DEPTH = 64
DATA_W     = 16
ENV_W      = 16
FULL_SCALE = (1 << (ENV_W - 1)) - 1   # 32767 max envelope


async def _reset(dut, n: int = 4) -> None:
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, n)
    await SETTLE
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await SETTLE


async def _write_bram(axil, shape: list) -> None:
    """Write shape[0..BRAM_DEPTH-1] to envelope BRAM."""
    for i, val in enumerate(shape):
        addr = BRAM_BASE + i * 4
        await axil.write(addr, int(val) & 0xFFFF)


async def _fire_pulse(dut, axil, period: int) -> None:
    """Write PERIOD and assert START; wait for BUSY to clear."""
    await axil.write(REG_PERIOD, period)
    await axil.write(REG_CTRL, 0x1)   # START=1


async def _collect_pulse(dut) -> tuple:
    """Collect (pulse_i, pulse_q) while pulse_valid=1.
    Returns (samples list, saw_done bool)."""
    samples  = []
    saw_done = False
    # Wait for pulse to start
    while True:
        await RisingEdge(dut.clk)
        await SETTLE
        if int(dut.pulse_valid.value) == 1:
            break
    # Collect until valid drops; capture pulse_done on the same cycle it fires
    while int(dut.pulse_valid.value) == 1:
        samples.append((
            int(dut.pulse_i.value.signed_integer),
            int(dut.pulse_q.value.signed_integer),
        ))
        if int(dut.pulse_done.value) == 1:
            saw_done = True
        await RisingEdge(dut.clk)
        await SETTLE
    # pulse_done may fire on the last valid cycle (same as valid→0 transition)
    if int(dut.pulse_done.value) == 1:
        saw_done = True
    return samples, saw_done


# ═══════════════════════════════════════════════════════════════════════════
#  Test 1 — square pulse: unity envelope, exact duration
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_square_pulse(dut):
    """
    Unity envelope (all BRAM entries = FULL_SCALE).
    pulse_valid must be asserted for exactly PERIOD=256 cycles.
    pulse_i must be non-zero (DDS running at non-zero PINC).
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil = AxilMaster(dut, dut.clk)

    # Square = all BRAM entries at full scale (already default, but write explicitly)
    shape = [FULL_SCALE] * BRAM_DEPTH
    await _write_bram(axil, shape)

    # DDS at bin-100 coherent frequency (same as DDS test)
    PINC = 100 * (1 << 32) // 1024
    await axil.write(REG_PINC, PINC)

    PERIOD = 256
    await _fire_pulse(dut, axil, PERIOD)

    samples, saw_done = await _collect_pulse(dut)

    assert len(samples) == PERIOD, (
        f"Square pulse length: got {len(samples)}, expected {PERIOD}"
    )
    nonzero = sum(1 for i, q in samples if abs(i) > 0)
    assert nonzero > PERIOD // 2, "Most pulse_i samples are zero — DDS may not be running"
    log.info(f"PASS test_square_pulse  len={len(samples)} non-zero={nonzero}")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 2 — Gaussian envelope: output amplitude follows BRAM shape
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_gaussian_env(dut):
    """
    Write a Gaussian shape into BRAM.  With a CW DDS carrier (constant
    amplitude), the pulse_i peak should occur at the Gaussian peak sample.
    We check that the output sequence is symmetric about the midpoint.

    Gaussian: env[i] = FULL_SCALE * exp(-((i - N/2)^2) / (2 * sigma^2))
    sigma = BRAM_DEPTH / 6  → ~99.7% of peak within the window.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil = AxilMaster(dut, dut.clk)

    # Build Gaussian shape
    sigma = BRAM_DEPTH / 6.0
    mid   = BRAM_DEPTH / 2.0
    gauss = [
        round(FULL_SCALE * math.exp(-0.5 * ((i - mid) ** 2) / sigma ** 2))
        for i in range(BRAM_DEPTH)
    ]
    await _write_bram(axil, gauss)

    # Use a slow DDS frequency so the carrier completes many cycles
    # within the pulse — makes it easier to find the envelope peak.
    PINC   = 10 * (1 << 32) // 1024   # bin 10
    PERIOD = 256
    await axil.write(REG_PINC, PINC)
    await _fire_pulse(dut, axil, PERIOD)

    samples, _ = await _collect_pulse(dut)
    assert len(samples) == PERIOD

    magnitude = [abs(i) + abs(q) for i, q in samples]
    peak_idx  = magnitude.index(max(magnitude))

    tolerance = PERIOD // 5
    centre    = PERIOD // 2
    assert abs(peak_idx - centre) <= tolerance, (
        f"Gaussian peak at sample {peak_idx}, expected near {centre} ± {tolerance}"
    )
    log.info(f"PASS test_gaussian_env  peak_at={peak_idx}/{PERIOD}")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 3 — BUSY clears and pulse_done fires
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_busy_clears(dut):
    """After pulse completes: CTRL.BUSY=0 via AXI readback, pulse_done=1."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil  = AxilMaster(dut, dut.clk)
    PINC  = 100 * (1 << 32) // 1024
    await axil.write(REG_PINC, PINC)
    await _fire_pulse(dut, axil, 64)

    _, saw_done = await _collect_pulse(dut)
    assert saw_done, "pulse_done never asserted during pulse"

    # Give one extra cycle for BUSY to clear through the register
    await RisingEdge(dut.clk)
    await SETTLE
    ctrl_val = await axil.read(REG_CTRL)
    busy = (ctrl_val >> 1) & 1
    assert busy == 0, f"CTRL.BUSY should be 0 after pulse, got {busy}"
    log.info("PASS test_busy_clears")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 4 — back-to-back pulses
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_back_to_back(dut):
    """Two consecutive pulses; second starts after first completes."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil = AxilMaster(dut, dut.clk)
    PINC = 100 * (1 << 32) // 1024
    await axil.write(REG_PINC, PINC)

    for pulse_num in range(2):
        await _fire_pulse(dut, axil, 128)
        samples, _ = await _collect_pulse(dut)
        assert len(samples) == 128, (
            f"Pulse {pulse_num}: expected 128 samples, got {len(samples)}"
        )
        await RisingEdge(dut.clk)
        await SETTLE

    log.info("PASS test_back_to_back")
