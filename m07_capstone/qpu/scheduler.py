"""
M07 — Experiment Scheduler
============================
asyncio-based scheduler that queues, prioritises, and executes quantum
experiments on a QPUBackend, then stores results by experiment name.

Design notes
------------
- Experiments are submitted synchronously; execution is async (run_all).
- Priority is an integer: higher value → runs first.
- Results are accumulated in an internal store and queryable after run_all().
- run_fn is an async callable `(backend: QPUBackend) -> dict[str, int]`.
  This makes experiments composable — a calibration routine, a QASM3 circuit
  execution, or a distributed entanglement attempt can all be wrapped as
  run_fns and treated uniformly.

Author: Nasir Ali, C-DAC Noida
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable


@dataclass
class Experiment:
    """
    A single quantum experiment.

    Parameters
    ----------
    name     : str      — unique identifier; used as key in results dict
    run_fn   : async callable (backend) → dict  — the experiment logic
    shots    : int      — number of measurement shots (passed by run_fn or meta)
    priority : int      — scheduling priority (higher = earlier)
    """
    name: str
    run_fn: Callable[..., Awaitable[dict]]
    shots: int = 200
    priority: int = 0


class ExperimentScheduler:
    """
    Queue-based asyncio scheduler for QPU experiments.

    Usage
    -----
    >>> sched = ExperimentScheduler(backend)
    >>> sched.submit(Experiment("rabi", my_rabi_fn, shots=500))
    >>> results = asyncio.run(sched.run_all())
    >>> results["rabi"]   # {"0": ..., "1": ...}
    """

    def __init__(self, backend) -> None:
        self._backend = backend
        self._queue: list[Experiment] = []
        self._results: dict[str, dict] = {}

    # ── Queue management ────────────────────────────────────────────────────

    def submit(self, experiment: Experiment) -> "ExperimentScheduler":
        """Add an experiment to the pending queue.  Returns self for chaining."""
        self._queue.append(experiment)
        return self

    def pending(self) -> int:
        """Number of experiments waiting to run."""
        return len(self._queue)

    # ── Execution ───────────────────────────────────────────────────────────

    async def run_all(self) -> dict[str, dict]:
        """
        Execute all queued experiments in priority order (high first).

        Clears the queue after completion.  Accumulated results persist in
        self._results and can be read with self.results().
        """
        ordered = sorted(self._queue, key=lambda e: -e.priority)
        for exp in ordered:
            self._results[exp.name] = await exp.run_fn(self._backend)
        self._queue.clear()
        return dict(self._results)

    def results(self) -> dict[str, dict]:
        """Return a copy of all accumulated results."""
        return dict(self._results)
