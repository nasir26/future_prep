"""
artiq_sim.environment — EnvExperiment base class
=================================================
In real ARTIQ, every experiment inherits from artiq.experiment.EnvExperiment
and gets access to the device manager, dataset manager, and scheduler.

This simulation layer provides:
  HasEnvironment — mixin with get_device / set_dataset / get_dataset
  EnvExperiment  — base class with build() / run() / analyze() lifecycle

Usage pattern (same as real ARTIQ)
------------------------------------
    from artiq_sim import EnvExperiment, kernel, ms, ns

    class RabiScan(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("dds_qubit")
            self.setattr_argument("n_shots", NumberValue(100))

        @kernel
        def run(self):
            self.core.break_realtime()
            ...

        def analyze(self):
            ...

To run: experiment = RabiScan(devices); experiment.prepare(); experiment.run()

Author: Nasir Ali, C-DAC Noida
"""

from .core    import Core
from .devices import TTLOut, TTLIn, AD9910, CoreDMA


class HasEnvironment:
    """
    Mixin providing the ARTIQ device / dataset / argument API.

    In simulation, devices is a dict mapping device name → device object.
    You can pass pre-built device objects or let the environment create
    defaults (Core + common devices).
    """

    def __init__(self, devices: dict = None):
        self._devices  = devices or {}
        self._datasets = {}

    def get_device(self, name: str):
        if name not in self._devices:
            raise KeyError(
                f"Device '{name}' not found.  Add it to the devices dict "
                f"passed to {type(self).__name__}()."
            )
        return self._devices[name]

    def setattr_device(self, name: str) -> None:
        """Fetch device and bind it as self.<name> (mirrors real ARTIQ)."""
        setattr(self, name, self.get_device(name))

    def set_dataset(self, key: str, value, broadcast: bool = False,
                    save: bool = True, unit: str = "", scale: float = 1.0) -> None:
        self._datasets[key] = value

    def get_dataset(self, key: str, default=None):
        return self._datasets.get(key, default)

    def mutate_dataset(self, key: str, index, value) -> None:
        self._datasets[key][index] = value

    def setattr_argument(self, name: str, processor=None, group=None) -> None:
        """In simulation, arguments are set directly on the experiment instance."""
        if not hasattr(self, name):
            # provide a sensible default if not already set
            setattr(self, name, getattr(processor, "default", None))


class EnvExperiment(HasEnvironment):
    """
    Base class for ARTIQ experiments.

    Lifecycle (same as real artiq.experiment.EnvExperiment):
      1. build()   — declare devices and arguments
      2. prepare() — host-side pre-computation (optional, runs before kernel)
      3. run()     — kernel: the real-time experiment (calls self.core.* etc.)
      4. analyze() — host-side post-processing (optional, runs after kernel)

    The simulation runner calls them in order:
        exp.build(); exp.prepare(); exp.run(); exp.analyze()
    """

    def build(self):
        """Override: declare devices with setattr_device, set arguments."""

    def prepare(self):
        """Override: host-side pre-computation (no kernel calls here)."""

    def run(self):
        """Override: the @kernel method driving hardware."""

    def analyze(self):
        """Override: host-side analysis of datasets."""


# ─── Convenience factory ────────────────────────────────────────────────────

def make_experiment(cls, extra_devices: dict = None, **kwargs):
    """
    Instantiate an experiment with a standard set of simulated devices.

    Devices provided by default
    ----------------------------
      core      — Core(ref_period=8ns)
      ttl_laser — TTLOut for the cooling laser gate
      ttl_mw    — TTLOut for microwave/RF gate
      ttl_pmt   — TTLIn for photon detection
      dds_qubit — AD9910 for qubit drive
      dds_cool  — AD9910 for cooling tone
      dma       — CoreDMA for sequence recording

    Any extra_devices dict can override or extend this set.
    """
    core      = Core(ref_period=8e-9)
    ttl_pmt   = TTLIn(core, "ttl_pmt")
    dds_qubit = AD9910(core, "dds_qubit")
    dds_cool  = AD9910(core, "dds_cool")

    devices = {
        "core":      core,
        "ttl_laser": TTLOut(core, "ttl_laser"),
        "ttl_mw":    TTLOut(core, "ttl_mw"),
        "ttl_pmt":   ttl_pmt,
        "dds_qubit": dds_qubit,
        "dds_cool":  dds_cool,
        "dma":       CoreDMA(core),
    }
    if extra_devices:
        devices.update(extra_devices)

    exp = cls(devices=devices)
    # Apply any kwargs as attributes (simulate argument values)
    for k, v in kwargs.items():
        setattr(exp, k, v)
    exp.build()
    return exp
