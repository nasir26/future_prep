"""
iontrap — ion-trap quantum emulator package
Author: Nasir Ali, C-DAC Noida
"""

from .ion     import IonTrap, carrier_rabi_analytic, rsb_rabi_analytic
from .cooling import SidebandCooling, sideband_cooling_analytic, doppler_equilibrium
from .readout import FluorescenceReadout, sideband_asymmetry
from .ms_gate import MSGate, ms_fidelity_analytic
from .noise   import HeatingModel, LaserPhaseNoise, BFieldDrift

__all__ = [
    "IonTrap", "carrier_rabi_analytic", "rsb_rabi_analytic",
    "SidebandCooling", "sideband_cooling_analytic", "doppler_equilibrium",
    "FluorescenceReadout", "sideband_asymmetry",
    "MSGate", "ms_fidelity_analytic",
    "HeatingModel", "LaserPhaseNoise", "BFieldDrift",
]
