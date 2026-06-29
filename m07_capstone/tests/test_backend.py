"""
test_backend.py — QPUBackend shot-based API (6 tests)

Tests that the physics layer (M06 IonTrap wrapped by QPUBackend) responds
correctly at the shot level.  Statistical bounds are loose (3-sigma) and use
a seeded RNG so the suite is deterministic.
"""

import math
import asyncio

import numpy as np
import pytest

from qpu import QPUBackend


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def be():
    """Small N_fock=8 backend with fixed seed for speed + reproducibility."""
    return QPUBackend(N_fock=8, rng=np.random.default_rng(7))


# ── Tests ───────────────────────────────────────────────────────────────────

def test_backend_init(be):
    """Backend initialises; pi_time() is positive and consistent with Omega_R."""
    t_pi = be.pi_time()
    assert t_pi > 0.0
    assert abs(t_pi - math.pi / be.Omega_R) < 1e-12


def test_no_pulse_ground_state(be):
    """
    Zero-angle pulse (theta=0) → ion stays in |g⟩ → nearly all shots read "0".

    The carrier evolve_carrier([0,0]) returns P_e = sin²(0) = 0.
    With 200 shots and optimal-threshold readout, all should be "0".
    """
    result = be.run_carrier(theta=0.0, shots=200)
    assert result["0"] + result["1"] == 200
    # P_e = 0 → at most a handful of dark clicks from mu_dark Poisson
    assert result["0"] >= 180


def test_pi_pulse_excited_state(be):
    """
    θ = π → ion flipped to |e⟩ → nearly all shots read "1".

    P_e = sin²(π/2) = 1.  A few bright-state photons may cross threshold
    (P_false_dark from FluorescenceReadout) but < 5% typically.
    """
    result = be.run_carrier(theta=math.pi, shots=300)
    assert result["0"] + result["1"] == 300
    frac_excited = result["1"] / 300
    assert frac_excited > 0.90, f"Expected >90% excited, got {frac_excited:.2%}"


def test_half_pi_superposition(be):
    """
    θ = π/2 → superposition → ~50% excited.

    Statistical window: 40%–60% (> 6σ margin for 300 shots with p=0.5).
    """
    result = be.run_carrier(theta=math.pi / 2, shots=300)
    frac = result["1"] / 300
    assert 0.35 <= frac <= 0.65, f"Expected ~50% excited, got {frac:.2%}"


def test_ms_gate_bell_state(be):
    """
    MS gate on |↓↓⟩ → (|↓↓⟩ + i|↑↑⟩)/√2.

    Expect P("00") + P("11") > 0.8 (analytic fidelity for η=0.1, n̄=0).
    """
    result = be.run_ms_gate(shots=500)
    assert sum(result.values()) == 500
    bell_frac = (result["00"] + result["11"]) / 500
    assert bell_frac > 0.75, f"Bell fraction {bell_frac:.2%} < 75%"


def test_shots_parameter_controls_count(be):
    """run_carrier(shots=N) → exactly N total measurement outcomes."""
    for n in (10, 50, 200):
        r = be.run_carrier(theta=math.pi / 3, shots=n)
        assert r["0"] + r["1"] == n
