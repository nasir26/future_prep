"""
M03 ex01 — DDS LUT testbench
=============================
What this verifies
------------------
  test_reset_state     — after reset, outputs are zero and valid=0
  test_pinc_readback   — AXI4-Lite write/read of PINC register
  test_phase_acc_step  — with known PINC, phase advances by exact increment
  test_iq_quadrature   — cosine leads sine by exactly 90° (quarter-LUT offset)
  test_spectral_purity — FFT of 1024 samples: peak at correct bin, max spur < -50 dBc

Timing note
-----------
dds_lut has 1 clock pipeline stage: dds_sine/dds_cos/dds_valid appear one
cycle after the phase accumulator updates.  All output reads use
Timer(1ps) settle (registered outputs), while AXI4-Lite ready signals
are sampled at RisingEdge (combinational, pre-RTL-execute).

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

# AXI4-Lite register addresses
REG_CTRL = 0x00
REG_PINC = 0x04
REG_POFF = 0x08

# DDS parameters (must match RTL parameters)
LUT_BITS = 10
PHASE_W  = 32
DATA_W   = 16
LUT_DEPTH = 1 << LUT_BITS
FULL_SCALE = (1 << (DATA_W - 1)) - 1   # 32767


# ─── Shared helpers ─────────────────────────────────────────────────────────

async def _reset(dut, n: int = 4) -> None:
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, n)
    await SETTLE
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await SETTLE


async def _collect_samples(dut, n: int):
    """Capture n (sine, cos) pairs after dds_valid goes high."""
    sins, coss = [], []
    count = 0
    while count < n:
        await RisingEdge(dut.clk)
        await SETTLE
        if int(dut.dds_valid.value) == 1:
            sins.append(int(dut.dds_sine.value.signed_integer))
            coss.append(int(dut.dds_cos.value.signed_integer))
            count += 1
    return sins, coss


# ═══════════════════════════════════════════════════════════════════════════
#  Test 1 — reset state
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_reset_state(dut):
    """After reset: dds_valid=0, dds_sine=0, dds_cos=0."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    assert int(dut.dds_valid.value) == 0, "dds_valid should be 0 after reset"
    assert int(dut.dds_sine.value)  == 0, "dds_sine should be 0 after reset"
    assert int(dut.dds_cos.value)   == 0, "dds_cos should be 0 after reset"
    log.info("PASS test_reset_state")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 2 — AXI4-Lite register read-back
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_pinc_readback(dut):
    """Write PINC and POFF via AXI4-Lite; read back; values must match."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil = AxilMaster(dut, dut.clk)

    PINC_VAL = 0x1999_999A  # ~10% of full scale → Fo ≈ 10 MHz at 100 MHz clk
    POFF_VAL = 0x4000_0000  # quarter-turn phase offset

    await axil.write(REG_PINC, PINC_VAL)
    await axil.write(REG_POFF, POFF_VAL)

    got_pinc = await axil.read(REG_PINC)
    got_poff = await axil.read(REG_POFF)

    assert got_pinc == PINC_VAL, f"PINC readback: got 0x{got_pinc:08X}, expected 0x{PINC_VAL:08X}"
    assert got_poff == POFF_VAL, f"POFF readback: got 0x{got_poff:08X}, expected 0x{POFF_VAL:08X}"
    log.info("PASS test_pinc_readback")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 3 — phase accumulator advances by PINC each cycle
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_phase_acc_step(dut):
    """
    With PINC = LUT_DEPTH, the DDS completes exactly one LUT cycle per
    2^(PHASE_W - LUT_BITS) = 2^22 = 4_194_304 clock cycles.  For a quick
    check we use PINC = 2^(PHASE_W - LUT_BITS) so that the LUT address
    advances by exactly 1 per clock — 1024 clocks = exactly one sine period.
    We verify that sample[1024] == sample[0] (period closure).
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil = AxilMaster(dut, dut.clk)
    # PINC to advance LUT address by 1 every clock: 2^(PHASE_W - LUT_BITS)
    one_lut_step = 1 << (PHASE_W - LUT_BITS)   # = 4_194_304
    await axil.write(REG_PINC, one_lut_step)
    await axil.write(REG_CTRL, 0x1)             # enable

    # Collect one full period + 1 extra sample
    sins, _ = await _collect_samples(dut, LUT_DEPTH + 1)

    assert sins[0] == sins[LUT_DEPTH], (
        f"Period closure failed: sins[0]={sins[0]}, sins[{LUT_DEPTH}]={sins[LUT_DEPTH]}"
    )
    log.info(f"PASS test_phase_acc_step  (period check: sins[0]=sins[1024]={sins[0]})")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 4 — I/Q quadrature: cosine leads sine by 90°
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_iq_quadrature(dut):
    """
    cos(θ) = sin(θ + π/2).  With PINC = one_lut_step, LUT address increments
    by 1 per clock.  Quarter-period offset = LUT_DEPTH // 4 = 256 samples.
    Verify: coss[0] == sins[LUT_DEPTH//4] within ±1 LSB (rounding).
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil = AxilMaster(dut, dut.clk)
    one_lut_step = 1 << (PHASE_W - LUT_BITS)
    await axil.write(REG_PINC, one_lut_step)
    await axil.write(REG_CTRL, 0x1)

    sins, coss = await _collect_samples(dut, LUT_DEPTH + LUT_DEPTH // 4)

    # cos[0] should equal sin[LUT_DEPTH//4]  (quarter-period ahead)
    quarter = LUT_DEPTH // 4
    for i in range(8):  # spot-check 8 points
        expected_cos = sins[i + quarter]
        got_cos      = coss[i]
        diff = abs(got_cos - expected_cos)
        assert diff <= 1, (
            f"I/Q quadrature error at sample {i}: cos={got_cos}, "
            f"expected≈{expected_cos}, diff={diff}"
        )
    log.info("PASS test_iq_quadrature")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 5 — spectral purity: peak at correct bin, all spurs < -50 dBc
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_spectral_purity(dut):
    """
    Coherent spectral purity check — all spurs < -50 dBc.

    Coherent sampling: choose Fo so exactly an integer number of sine cycles
    fits in the N-point FFT window → zero spectral leakage, no window needed.
      N = 1024, peak_bin = 100 → Fo = Fclk * 100 / 1024 = 9_765_625 Hz
      PINC = 100 * 2^32 // 1024 = 419_430_400  (exact, no rounding error)

    With coherent sampling any spur above the noise floor is due to LUT
    quantisation only.  A 10-bit, 1024-entry LUT gives SFDR ≈ 62 dBc
    (6 dB/bit rule).  The -50 dBc limit allows 12 dB margin.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil  = AxilMaster(dut, dut.clk)
    N         = 1024
    PEAK_BIN  = 100
    Fclk      = 100e6
    # Exact coherent PINC: advances LUT address by PEAK_BIN per sample
    pinc = PEAK_BIN * (1 << PHASE_W) // N   # = 419_430_400
    await axil.write(REG_PINC, pinc)
    await axil.write(REG_CTRL, 0x1)

    sins, _ = await _collect_samples(dut, N)

    # No window needed: coherent sampling means integer cycles → zero leakage
    spectrum = np.abs(np.fft.rfft(np.array(sins, dtype=float)))

    peak_bin = int(np.argmax(spectrum))
    assert peak_bin == PEAK_BIN, (
        f"Peak at bin {peak_bin}, expected {PEAK_BIN}"
    )

    peak_power = spectrum[PEAK_BIN] ** 2
    for b, amp in enumerate(spectrum):
        if abs(b - PEAK_BIN) <= 1:
            continue
        spur_dBc = 10 * math.log10((amp ** 2) / peak_power + 1e-20)
        assert spur_dBc < -50, (
            f"Spur at bin {b}: {spur_dBc:.1f} dBc (limit -50 dBc)"
        )

    log.info(
        f"PASS test_spectral_purity  peak_bin={peak_bin}  "
        f"Fo={Fclk * PEAK_BIN / N / 1e6:.4f} MHz  PINC={pinc}"
    )
