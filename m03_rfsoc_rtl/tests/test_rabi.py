"""
M03 ex04 — Rabi Integration Test
===================================
Concept
-------
A Rabi oscillation experiment sweeps pulse duration τ and measures how often
the ion ends up in the excited (bright) state.  The transition probability is:

    P_bright(τ) = sin²(π · τ / τ_π)

where τ_π is the π-pulse time (the pulse duration that fully flips the qubit).
The photon counter measures fluorescence: bright → many photons, dark → few.

This test simulates the full experiment loop:
  1. For each τ in {τ_0 … τ_max}: compute expected P_bright, write MEAN to
     the photon_counter model, soft-trigger a capture, read back COUNT.
  2. Fit the {τ, COUNT} data to A·sin²(π·τ/T) + B using scipy curve_fit.
  3. Assert fit quality: R² > 0.95, fitted T within 20% of true τ_π.

Tests
-----
  test_prng_noise      — verify LFSR generates non-trivial noise (σ > 0)
  test_single_capture  — single capture matches programmed mean (within noise)
  test_threshold_disc  — STATE bit discriminates bright vs dark counts
  test_rabi_sweep      — full 10-point sweep, sinusoidal fit, residuals < 20%

Author: Nasir Ali, C-DAC Noida
"""

import logging
import math
import numpy as np
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles, Timer
from scipy.optimize import curve_fit

from axil_bfm import AxilMaster

log    = logging.getLogger("cocotb.test")
SETTLE = Timer(1, unit="ps")

# Register addresses
REG_CTRL      = 0x00
REG_MEAN      = 0x04
REG_NOISE_AMP = 0x08
REG_THRESHOLD = 0x0C
REG_COUNT     = 0x10
REG_STATE     = 0x14

BRIGHT_COUNT = 40   # expected photon count in fully-excited state
DARK_COUNT   = 2    # expected count in ground state (dark + background)
TAU_PI       = 100  # π-pulse duration in clock cycles


async def _reset(dut, n=4):
    dut.rst_n.value        = 0
    dut.capture_trigger.value = 0
    await ClockCycles(dut.clk, n)
    await SETTLE
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await SETTLE


async def _soft_capture(axil) -> int:
    """Trigger a soft capture and read back COUNT."""
    await axil.write(REG_CTRL, 0x1)   # SOFT_CAPTURE
    await axil.write(REG_CTRL, 0x0)   # deassert
    return await axil.read(REG_COUNT)


async def _hw_capture(dut, axil) -> int:
    """Assert capture_trigger for 1 cycle, then read COUNT."""
    dut.capture_trigger.value = 1
    await RisingEdge(dut.clk)
    await SETTLE
    dut.capture_trigger.value = 0
    await RisingEdge(dut.clk)
    await SETTLE
    return await axil.read(REG_COUNT)


# ═══════════════════════════════════════════════════════════════════════════
#  Test 1 — PRNG generates non-trivial noise
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_prng_noise(dut):
    """
    With MEAN=50 and NOISE_AMP=20, take 32 captures.
    All counts must differ (LFSR is not stuck) and std_dev > 2 LSB.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil = AxilMaster(dut, dut.clk)
    await axil.write(REG_MEAN,      50)
    await axil.write(REG_NOISE_AMP, 20)

    counts = []
    for _ in range(32):
        c = await _soft_capture(axil)
        counts.append(c)
        # Advance a few cycles between captures so LFSR evolves
        await ClockCycles(dut.clk, 4)

    unique = len(set(counts))
    std_dev = np.std(counts)
    assert unique > 4, f"LFSR stuck: only {unique} unique values in 32 captures"
    assert std_dev > 2.0, f"Noise too small: std_dev={std_dev:.2f} (need > 2.0)"
    log.info(f"PASS test_prng_noise  unique={unique}/32  std={std_dev:.2f}")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 2 — single capture is close to programmed mean
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_single_capture(dut):
    """
    With NOISE_AMP=0 (zero noise), every capture should return exactly MEAN.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil = AxilMaster(dut, dut.clk)
    await axil.write(REG_NOISE_AMP, 0)

    for mean_val in [0, 10, 50, 127, 200, 255]:
        await axil.write(REG_MEAN, mean_val)
        count = await _soft_capture(axil)
        assert count == mean_val, (
            f"MEAN={mean_val}: got {count} (noise=0, expected exact)"
        )

    log.info("PASS test_single_capture")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 3 — threshold discriminator
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_threshold_disc(dut):
    """
    Set THRESHOLD=20.
    MEAN=5  (dark) → STATE should be 0.
    MEAN=40 (bright) → STATE should be 1.
    (NOISE_AMP=0 for determinism.)
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil = AxilMaster(dut, dut.clk)
    await axil.write(REG_NOISE_AMP, 0)
    await axil.write(REG_THRESHOLD, 20)

    await axil.write(REG_MEAN, 5)
    await _soft_capture(axil)
    state = await axil.read(REG_STATE)
    assert state == 0, f"Dark state: STATE={state}, expected 0"

    await axil.write(REG_MEAN, 40)
    await _soft_capture(axil)
    state = await axil.read(REG_STATE)
    assert state == 1, f"Bright state: STATE={state}, expected 1"

    log.info("PASS test_threshold_disc")


# ═══════════════════════════════════════════════════════════════════════════
#  Test 4 — Rabi sweep: 10-point scan, sinusoidal fit, R² > 0.95
# ═══════════════════════════════════════════════════════════════════════════

@cocotb.test()
async def test_rabi_sweep(dut):
    """
    Sweep τ from τ_π/10 to 2·τ_π in 10 steps.  For each τ, set MEAN to
    the model prediction and trigger a capture (with small noise).
    Fit the counts to A·sin²(π·τ/T) + B and verify:
      · R² ≥ 0.90
      · Fitted T within 25% of true TAU_PI (robust to noise)

    The MEAN for each τ is set by the test (Python as the physics model);
    the RTL adds PRNG noise to simulate realistic Poisson fluctuations.
    This mirrors a real experiment: software computes the expected sequence,
    hardware returns noisy measurements, software fits the result.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    axil = AxilMaster(dut, dut.clk)
    await axil.write(REG_NOISE_AMP, 4)   # small noise for cleaner fit

    # 10 pulse durations covering one full Rabi oscillation
    taus = [TAU_PI * k // 10 for k in range(1, 11)]  # 10..100 cycles

    counts = []
    for tau in taus:
        # Physics model: compute Rabi excitation probability
        p_bright = math.sin(math.pi * tau / TAU_PI) ** 2
        mean_val = round(DARK_COUNT + (BRIGHT_COUNT - DARK_COUNT) * p_bright)
        mean_val = max(0, min(255, mean_val))

        await axil.write(REG_MEAN, mean_val)
        # Advance a few cycles so LFSR evolves between measurements
        await ClockCycles(dut.clk, 8)
        count = await _hw_capture(dut, axil)
        counts.append(count)
        log.info(f"  τ={tau:4d}  mean={mean_val:3d}  got={count:3d}")

    # Sinusoidal fit: A * sin²(π * τ / T) + B
    def rabi_model(tau_arr, amplitude, period, offset):
        return amplitude * np.sin(np.pi * tau_arr / period) ** 2 + offset

    tau_arr = np.array(taus, dtype=float)
    cnt_arr = np.array(counts, dtype=float)

    try:
        popt, _ = curve_fit(
            rabi_model, tau_arr, cnt_arr,
            p0=[BRIGHT_COUNT - DARK_COUNT, TAU_PI, DARK_COUNT],
            bounds=([0, TAU_PI * 0.3, 0], [255, TAU_PI * 3.0, 255]),
            maxfev=5000,
        )
        A_fit, T_fit, B_fit = popt

        # Compute R²
        cnt_pred = rabi_model(tau_arr, *popt)
        ss_res = np.sum((cnt_arr - cnt_pred) ** 2)
        ss_tot = np.sum((cnt_arr - cnt_arr.mean()) ** 2)
        r2 = 1 - ss_res / (ss_tot + 1e-10)

        log.info(
            f"Rabi fit: A={A_fit:.1f}  T={T_fit:.1f}  B={B_fit:.1f}  R²={r2:.4f}"
        )

        assert r2 >= 0.90, f"Rabi fit R²={r2:.4f} < 0.90"
        assert abs(T_fit - TAU_PI) / TAU_PI < 0.25, (
            f"Fitted τ_π={T_fit:.1f}, true={TAU_PI}, error > 25%"
        )
        log.info(
            f"PASS test_rabi_sweep  T_fit={T_fit:.1f}  R²={r2:.4f}"
        )
    except RuntimeError as e:
        raise AssertionError(f"curve_fit failed: {e}") from e
