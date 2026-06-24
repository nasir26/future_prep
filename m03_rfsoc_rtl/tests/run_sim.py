"""
run_sim.py — M03 cocotb_tools.runner wrapper
=============================================
Usage:
    python run_sim.py dds          # ex01 DDS LUT tests
    python run_sim.py envelope     # ex02 pulse envelope tests
    python run_sim.py sequencer    # ex03 timed sequencer tests
    python run_sim.py rabi         # ex04 Rabi integration test

Author: Nasir Ali, C-DAC Noida
"""

import sys
import math
import numpy as np
from pathlib import Path
from cocotb_tools.runner import get_runner

HERE      = Path(__file__).parent
RTL_DIR   = HERE.parent / "rtl"
BUILD_DIR = HERE.parent / "build"
WAVES_DIR = Path.home() / "future_prep" / "waves"
WAVES_DIR.mkdir(parents=True, exist_ok=True)

SIM = "icarus"


# ───────────────────────────────────────────────────────────────────────────
#  LUT generation helper (called before DDS / envelope builds)
# ───────────────────────────────────────────────────────────────────────────

def gen_sine_lut(build_dir: Path, lut_bits: int = 10, data_w: int = 16) -> Path:
    """Generate signed sine LUT hex file; return path."""
    depth    = 1 << lut_bits
    full_scl = (1 << (data_w - 1)) - 1   # 32767
    vals     = np.round(full_scl * np.sin(2 * math.pi * np.arange(depth) / depth)
                        ).astype(np.int16)
    path = build_dir / "dds_sine_lut.hex"
    with open(path, "w") as f:
        for v in vals:
            f.write(f"{int(v) & 0xFFFF:04X}\n")
    print(f"[run_sim] Sine LUT written → {path}  ({depth} entries)")
    return path


# ───────────────────────────────────────────────────────────────────────────
#  ex01 — DDS LUT
# ───────────────────────────────────────────────────────────────────────────

def run_dds():
    sim_build = BUILD_DIR / "sim_dds"
    sim_build.mkdir(parents=True, exist_ok=True)
    lut_path = gen_sine_lut(sim_build)

    runner = get_runner(SIM)
    runner.build(
        sources       = [RTL_DIR / "dds_lut.sv"],
        hdl_toplevel  = "dds_lut",
        build_dir     = str(sim_build),
        build_args    = ["-g2012"],
        waves         = True,
        always        = True,
        timescale     = ("1ns", "1ps"),
    )
    runner.test(
        hdl_toplevel  = "dds_lut",
        test_module   = "test_dds",
        build_dir     = str(sim_build),
        test_dir      = str(HERE),
        waves         = True,
        plusargs      = [
            f"+lut_file={lut_path}",
            f"+dumpfile_path={WAVES_DIR}/m03_dds.fst",
        ],
        results_xml   = str(BUILD_DIR / "results_dds.xml"),
    )


# ───────────────────────────────────────────────────────────────────────────
#  ex02 — Pulse envelope
# ───────────────────────────────────────────────────────────────────────────

def run_envelope():
    sim_build = BUILD_DIR / "sim_envelope"
    sim_build.mkdir(parents=True, exist_ok=True)
    lut_path = gen_sine_lut(sim_build)

    runner = get_runner(SIM)
    runner.build(
        sources      = [RTL_DIR / "dds_lut.sv", RTL_DIR / "pulse_envelope.sv"],
        hdl_toplevel = "pulse_envelope",
        build_dir    = str(sim_build),
        build_args   = ["-g2012"],
        waves        = True,
        always       = True,
        timescale    = ("1ns", "1ps"),
    )
    runner.test(
        hdl_toplevel = "pulse_envelope",
        test_module  = "test_envelope",
        build_dir    = str(sim_build),
        test_dir     = str(HERE),
        waves        = True,
        plusargs     = [
            f"+lut_file={lut_path}",
            f"+dumpfile_path={WAVES_DIR}/m03_envelope.fst",
        ],
        results_xml  = str(BUILD_DIR / "results_envelope.xml"),
    )


# ───────────────────────────────────────────────────────────────────────────
#  ex03 — Timed sequencer
# ───────────────────────────────────────────────────────────────────────────

def run_sequencer():
    sim_build = BUILD_DIR / "sim_sequencer"
    sim_build.mkdir(parents=True, exist_ok=True)

    runner = get_runner(SIM)
    runner.build(
        sources      = [RTL_DIR / "timed_sequencer.sv"],
        hdl_toplevel = "timed_sequencer",
        build_dir    = str(sim_build),
        build_args   = ["-g2012"],
        waves        = True,
        always       = True,
        timescale    = ("1ns", "1ps"),
    )
    runner.test(
        hdl_toplevel = "timed_sequencer",
        test_module  = "test_sequencer",
        build_dir    = str(sim_build),
        test_dir     = str(HERE),
        waves        = True,
        plusargs     = [f"+dumpfile_path={WAVES_DIR}/m03_sequencer.fst"],
        results_xml  = str(BUILD_DIR / "results_sequencer.xml"),
    )


# ───────────────────────────────────────────────────────────────────────────
#  ex04 — Rabi integration (pulse_envelope + photon_counter + Python fit)
# ───────────────────────────────────────────────────────────────────────────

def run_rabi():
    sim_build = BUILD_DIR / "sim_rabi"
    sim_build.mkdir(parents=True, exist_ok=True)

    runner = get_runner(SIM)
    runner.build(
        sources      = [RTL_DIR / "photon_counter.sv"],
        hdl_toplevel = "photon_counter",
        build_dir    = str(sim_build),
        build_args   = ["-g2012"],
        waves        = True,
        always       = True,
        timescale    = ("1ns", "1ps"),
    )
    runner.test(
        hdl_toplevel = "photon_counter",
        test_module  = "test_rabi",
        build_dir    = str(sim_build),
        test_dir     = str(HERE),
        waves        = True,
        plusargs     = [f"+dumpfile_path={WAVES_DIR}/m03_rabi.fst"],
        results_xml  = str(BUILD_DIR / "results_rabi.xml"),
    )


# ───────────────────────────────────────────────────────────────────────────

TARGETS = {
    "dds":       run_dds,
    "envelope":  run_envelope,
    "sequencer": run_sequencer,
    "rabi":      run_rabi,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in TARGETS:
        print(f"Usage: python run_sim.py [{' | '.join(TARGETS)}]")
        sys.exit(1)
    TARGETS[sys.argv[1]]()
