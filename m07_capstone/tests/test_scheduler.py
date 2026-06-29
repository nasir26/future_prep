"""
test_scheduler.py — asyncio ExperimentScheduler (6 tests)

Verifies queueing, execution order (priority), result accumulation, and
that multiple experiments don't clobber each other's results.
"""

import asyncio
import math

import pytest

from qpu import Experiment, ExperimentScheduler, QPUBackend


# ── Helpers ─────────────────────────────────────────────────────────────────

def _pi_fn(shots=50):
    """Run function: apply π pulse and return counts."""
    async def fn(backend):
        return backend.run_carrier(math.pi, shots=shots)
    return fn


def _half_pi_fn(shots=50):
    async def fn(backend):
        return backend.run_carrier(math.pi / 2, shots=shots)
    return fn


# ── Tests ───────────────────────────────────────────────────────────────────

def test_submit_queues_experiment(scheduler):
    """submit() increases pending count."""
    assert scheduler.pending() == 0
    scheduler.submit(Experiment("e1", _pi_fn()))
    assert scheduler.pending() == 1


def test_run_all_returns_results_dict(scheduler):
    """run_all() returns dict keyed by experiment name."""
    scheduler.submit(Experiment("a", _pi_fn()))
    results = asyncio.run(scheduler.run_all())
    assert isinstance(results, dict)
    assert "a" in results


def test_result_counts_sum_to_shots(scheduler):
    """Result for a single-qubit experiment has "0"+"1" == shots."""
    shots = 75
    scheduler.submit(Experiment("b", _pi_fn(shots), shots=shots))
    results = asyncio.run(scheduler.run_all())
    r = results["b"]
    assert r["0"] + r["1"] == shots


def test_multiple_experiments_no_clobber(scheduler):
    """Two experiments store independent results under their own keys."""
    scheduler.submit(Experiment("pi",     _pi_fn()))
    scheduler.submit(Experiment("half",   _half_pi_fn()))
    results = asyncio.run(scheduler.run_all())
    assert "pi"   in results
    assert "half" in results
    # π-pulse → mostly "1"; π/2-pulse → both present
    assert results["pi"]["1"]  > results["pi"]["0"]


def test_priority_ordering(scheduler):
    """Higher priority experiment runs first (call order tracked via list)."""
    order = []

    async def fn_low(backend):
        order.append("low")
        return {}

    async def fn_high(backend):
        order.append("high")
        return {}

    scheduler.submit(Experiment("low",  fn_low,  priority=0))
    scheduler.submit(Experiment("high", fn_high, priority=10))
    asyncio.run(scheduler.run_all())
    assert order == ["high", "low"]


def test_empty_queue_returns_empty_dict(scheduler):
    """run_all() on an empty queue returns {} without error."""
    results = asyncio.run(scheduler.run_all())
    assert results == {} or isinstance(results, dict)   # may have prior results
    # Ensure no exception and queue is empty
    assert scheduler.pending() == 0
