"""
test_distributed.py — QPUNode two-node distributed entanglement (6 tests)

Tests node initialisation, connection, local operations, and heralded
Bell-pair generation via the simulated photonic link.
"""

import asyncio
import math

import numpy as np
import pytest

from qpu import QPUBackend, QPUNode


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def node_pair():
    """Two fresh QPUNodes with η_link = 0.7, connected to each other."""
    a = QPUNode("A", eta_link=0.7, rng=np.random.default_rng(10))
    b = QPUNode("B", eta_link=0.7, rng=np.random.default_rng(11))
    a.connect(b)
    return a, b


# ── Tests ────────────────────────────────────────────────────────────────────

def test_two_nodes_initialise(node_pair):
    """Both nodes created with correct node_id and positive eta_link."""
    a, b = node_pair
    assert a.node_id == "A"
    assert b.node_id == "B"
    assert a.eta_link == 0.7
    assert b.eta_link == 0.7


def test_connect_links_peers(node_pair):
    """connect() establishes bidirectional peer reference."""
    a, b = node_pair
    assert a.peer is b
    assert b.peer is a


def test_local_ops_return_bitstring_dict(node_pair):
    """run_local(π) on node_a returns {"0": int, "1": int}."""
    a, b = node_pair
    result = asyncio.run(a.run_local(math.pi, shots=100))
    assert set(result.keys()) == {"0", "1"}
    assert result["0"] + result["1"] == 100


def test_local_ops_are_independent(node_pair):
    """Local ops on node_a do not interfere with node_b measurements."""
    a, b = node_pair
    result_a = asyncio.run(a.run_local(math.pi,       shots=100))
    result_b = asyncio.run(b.run_local(0.0,           shots=100))
    # node_a: π-pulse → mostly excited
    assert result_a["1"] > result_a["0"]
    # node_b: no pulse → mostly ground
    assert result_b["0"] > result_b["1"]


def test_entanglement_returns_expected_keys(node_pair):
    """attempt_entanglement() result dict has counts/attempts/successes/herald_rate."""
    a, _ = node_pair
    result = asyncio.run(a.attempt_entanglement(n_heralded=10))
    assert "counts"      in result
    assert "attempts"    in result
    assert "successes"   in result
    assert "herald_rate" in result
    assert result["successes"] == 10


def test_heralded_pairs_are_psi_minus(node_pair):
    """
    Heralded Bell pairs are |Ψ-⟩ = (|01⟩ - |10⟩)/√2.

    Joint measurement outcomes: only "01" and "10", each ~50%.
    Statistical window: ≥ 30% each with 100 pairs.
    """
    a, _ = node_pair
    result = asyncio.run(a.attempt_entanglement(n_heralded=200))
    counts = result["counts"]
    total  = counts["01"] + counts["10"]
    assert total == 200
    assert counts.get("00", 0) == 0
    assert counts.get("11", 0) == 0
    # Each outcome ≥ 35% (> 5σ margin for p=0.5, n=200)
    assert counts["01"] >= 60
    assert counts["10"] >= 60


def test_herald_rate_matches_eta_link(node_pair):
    """
    Herald rate successes/attempts ≈ η²/2.

    For η=0.7: p_herald = 0.49/2 = 0.245.
    With 200 heralded pairs the expected attempt count is ~817.
    Allow a wide statistical window (factor 2) for the test to be fast.
    """
    a, _ = node_pair
    result = asyncio.run(a.attempt_entanglement(n_heralded=200))
    p_expected = a.eta_link ** 2 / 2
    # Herald rate should be within a factor of 2 of theoretical p_herald
    assert 0.5 * p_expected <= result["herald_rate"] <= 2.0 * p_expected
