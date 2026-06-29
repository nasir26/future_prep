"""
test_calibration.py — automated calibration routines (7 tests)

Tests freq_scan, rabi_pi_time, ramsey_track, recal_daemon, and ParamStore.
All calibration coroutines run via asyncio.run() so they can be called from
synchronous pytest without any async plugin.
"""

import asyncio
import math

import numpy as np
import pytest

from qpu import ParamStore
from qpu.calibration import freq_scan, rabi_pi_time, ramsey_track, recal_daemon
from qpu import QPUBackend


@pytest.fixture(scope="module")
def be():
    return QPUBackend(N_fock=8, rng=np.random.default_rng(3))


# ── ParamStore ──────────────────────────────────────────────────────────────

def test_param_store_set_get():
    """ParamStore stores and retrieves float values."""
    ps = ParamStore()
    ps.set("omega_0", 3.14)
    assert abs(ps.get("omega_0") - 3.14) < 1e-9
    assert ps.get("missing", default=99.0) == 99.0


# ── freq_scan ───────────────────────────────────────────────────────────────

def test_freq_scan_returns_float(be):
    """freq_scan completes and returns a float (detuning at P_e maximum)."""
    result = asyncio.run(freq_scan(be))
    assert isinstance(result, float)


def test_freq_scan_near_resonance(be):
    """
    For an on-resonance backend, the peak P_e should be at δ ≈ 0.

    We scan ±Ω_R in 21 steps; the closest grid point to 0 is 0 itself
    (symmetric grid).  Tolerance = one grid step.
    """
    omega_offsets = np.linspace(-be.Omega_R, be.Omega_R, 21)
    result = asyncio.run(freq_scan(be, omega_offsets=omega_offsets))
    step = omega_offsets[1] - omega_offsets[0]
    assert abs(result) <= step + 1e-6


# ── rabi_pi_time ────────────────────────────────────────────────────────────

def test_rabi_pi_time_returns_float(be):
    """rabi_pi_time returns a positive float."""
    t_pi = asyncio.run(rabi_pi_time(be))
    assert isinstance(t_pi, float)
    assert t_pi > 0.0


def test_rabi_pi_time_accuracy(be):
    """Fitted t_pi within 2% of analytical ion.pi_time()."""
    t_pi_true = be.pi_time()
    t_pi_fit  = asyncio.run(rabi_pi_time(be))
    rel_err = abs(t_pi_fit - t_pi_true) / t_pi_true
    assert rel_err < 0.02, f"Fitted t_pi={t_pi_fit:.3e}, true={t_pi_true:.3e}, err={rel_err:.1%}"


# ── ramsey_track ────────────────────────────────────────────────────────────

def test_ramsey_track_returns_float(be):
    """ramsey_track returns a float (detuning in rad/s)."""
    d_omega = asyncio.run(ramsey_track(be))
    assert isinstance(d_omega, float)


# ── recal_daemon ────────────────────────────────────────────────────────────

def test_recal_daemon_returns_list(be):
    """recal_daemon(n_rounds=4) returns a list of length 4."""
    history = asyncio.run(recal_daemon(be, n_rounds=4, interval_s=0.0))
    assert isinstance(history, list)
    assert len(history) == 4
    assert all(isinstance(x, float) for x in history)


def test_recal_daemon_stores_params(be):
    """recal_daemon updates ParamStore with delta_omega after each round."""
    ps = ParamStore()
    asyncio.run(recal_daemon(be, store=ps, n_rounds=2, interval_s=0.0))
    assert "delta_omega" in ps.all()
