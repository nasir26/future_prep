"""
M04 test configuration — shared fixtures for ARTIQ kernel tests.

Each fixture returns a freshly built experiment instance with a clean
Core event log.  Tests call exp.prepare(); exp.run(); exp.analyze()
in sequence (mirrors how artiq_client would drive a real ARTIQ experiment).

Author: Nasir Ali, C-DAC Noida
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from artiq_sim.environment import make_experiment

# Import all experiment classes
from kernels.ex01_ttl_basics       import TTLBasics
from kernels.ex02_photon_counting  import PhotonCounting
from kernels.ex03_dds_control      import DDSControl
from kernels.ex04_doppler_cooling  import DopplerCooling
from kernels.ex05_rabi_scan        import RabiScan
from kernels.ex06_ramsey           import Ramsey
from kernels.ex07_sideband_cooling import SidebandCooling
from kernels.ex08_ms_gate          import MSGate
from kernels.ex09_mid_circuit      import MidCircuitMeasure, HeraldedEntanglement


@pytest.fixture
def ttl_basics():
    exp = make_experiment(TTLBasics)
    exp.prepare()
    return exp


@pytest.fixture
def photon_counting():
    exp = make_experiment(PhotonCounting)
    exp.prepare()
    return exp


@pytest.fixture
def dds_ctrl():
    exp = make_experiment(DDSControl)
    exp.prepare()
    return exp


@pytest.fixture
def doppler():
    exp = make_experiment(DopplerCooling, n_reps=20)
    exp.prepare()
    return exp


@pytest.fixture
def rabi(request):
    kwargs = getattr(request, "param", {})
    exp = make_experiment(RabiScan, **kwargs)
    exp.n_shots = 30    # fewer shots for fast tests
    exp.prepare()
    return exp


@pytest.fixture
def ramsey():
    exp = make_experiment(Ramsey)
    exp.n_shots = 20
    exp.prepare()
    return exp


@pytest.fixture
def sbc():
    exp = make_experiment(SidebandCooling)
    exp.n_shots = 30
    exp.prepare()
    return exp


@pytest.fixture
def ms_gate():
    exp = make_experiment(MSGate)
    exp.n_shots = 30
    exp.prepare()
    return exp


@pytest.fixture
def mcm():
    exp = make_experiment(MidCircuitMeasure)
    exp.n_shots = 50
    exp.prepare()
    return exp


@pytest.fixture
def heralded():
    exp = make_experiment(HeraldedEntanglement)
    exp.n_experiments = 30
    exp.prepare()
    return exp
