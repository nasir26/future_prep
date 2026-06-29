"""
Shared pytest fixtures for M07 capstone tests.
"""

import math
import sys
import pathlib

import numpy as np
import pytest

# Make both qpu package and M06 importable from the test runner's cwd
_ROOT = pathlib.Path(__file__).parent.parent
_M06  = _ROOT.parent / "m06_iontrap_emu"

for _p in (_ROOT, str(_M06)):
    _p = str(_p)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from qpu import QPUBackend, ExperimentScheduler, QPUNode, ParamStore


@pytest.fixture(scope="module")
def backend():
    """Fast QPUBackend: N_fock=8, seeded RNG for reproducible shots."""
    return QPUBackend(N_fock=8, rng=np.random.default_rng(0))


@pytest.fixture
def scheduler(backend):
    return ExperimentScheduler(backend)


@pytest.fixture(scope="module")
def node_a(backend):
    return QPUNode("node_A", backend=backend, eta_link=0.7,
                   rng=np.random.default_rng(1))


@pytest.fixture(scope="module")
def node_b():
    return QPUNode("node_B", eta_link=0.7,
                   rng=np.random.default_rng(2))


@pytest.fixture
def store():
    return ParamStore()
