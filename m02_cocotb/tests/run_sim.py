#!/usr/bin/env python3
"""
run_sim.py — M02 cocotb test runner
====================================
Wraps cocotb_tools.runner (cocotb 2.x Python runner API).
This script is called by the Makefile; you can also run it directly:

  python tests/run_sim.py            # run all suites
  python tests/run_sim.py counter    # ex01 only
  python tests/run_sim.py axis       # ex02 only
  python tests/run_sim.py rand       # ex03 only

How cocotb_tools.runner works
------------------------------
1. runner.build()  — calls iverilog to compile the DUT + cocotb VPI shim.
   The shim is a small Verilog module (cocotb_iverilog_dump) that iverilog
   adds as an extra top-level; it contains $dumpvars so wave output works.

2. runner.test()   — calls vvp to execute the compiled simulation.
   cocotb's Python side is loaded via the -m VPI switch; your @cocotb.test()
   functions run as coroutines scheduled by cocotb's internal event loop.

Wave output
-----------
- waves=True in build() → iverilog generates the dump stub
- waves=True in test()  → vvp is invoked with -fst (FST format)
- The +dumpfile_path=... plusarg redirects the wave file to ~/future_prep/waves/

Author: Nasir Ali, C-DAC Noida
"""

import sys
from pathlib import Path

from cocotb_tools.runner import get_runner

# ── Directory layout ────────────────────────────────────────────────────────
HERE      = Path(__file__).resolve().parent   # tests/
ROOT      = HERE.parent                        # m02_cocotb/
RTL_DIR   = ROOT / "rtl"
BUILD_DIR = ROOT / "build"
WAVES_DIR = Path.home() / "future_prep" / "waves"

WAVES_DIR.mkdir(parents=True, exist_ok=True)
BUILD_DIR.mkdir(parents=True, exist_ok=True)

SIM = "icarus"   # Icarus Verilog (vvp) via VPI — iverilog 12.0


# ═══════════════════════════════════════════════════════════════════════════
#  Suite runners
# ═══════════════════════════════════════════════════════════════════════════

def run_counter():
    """
    ex01 — 4-bit counter.
    Concepts: Clock, RisingEdge, ClockCycles, signal read/write.
    """
    sim_build = BUILD_DIR / "sim_counter"
    runner = get_runner(SIM)

    # Build: iverilog compiles counter.v + the cocotb VPI dump stub
    runner.build(
        verilog_sources=[RTL_DIR / "counter.v"],
        hdl_toplevel="counter",
        build_dir=sim_build,
        parameters={"WIDTH": 4},
        waves=True,         # generate cocotb_iverilog_dump stub
        always=True,        # recompile even if sources haven't changed
        timescale=("1ns", "1ps"),
    )

    # Test: vvp runs the simulation; @cocotb.test() functions execute as coroutines
    runner.test(
        hdl_toplevel="counter",
        test_module="test_counter",
        build_dir=sim_build,
        test_dir=HERE,
        waves=True,
        # +dumpfile_path redirects the FST wave file into our central waves/
        plusargs=[f"+dumpfile_path={WAVES_DIR}/m02_counter.fst"],
        results_xml=str(BUILD_DIR / "results_counter.xml"),
    )


def run_axis():
    """
    ex02 — AXI4-Stream FIFO directed tests.
    Concepts: Driver / Monitor / Scoreboard pattern, concurrent coroutines.
    """
    sim_build = BUILD_DIR / "sim_axis"
    runner = get_runner(SIM)

    runner.build(
        verilog_sources=[RTL_DIR / "axis_fifo.sv"],
        hdl_toplevel="axis_fifo",
        build_dir=sim_build,
        parameters={"DATA_W": 8, "DEPTH": 16},
        build_args=["-g2012"],   # enable SystemVerilog 2012 in iverilog
        waves=True,
        always=True,
        timescale=("1ns", "1ps"),
    )

    runner.test(
        hdl_toplevel="axis_fifo",
        test_module="test_axis_fifo",
        build_dir=sim_build,
        test_dir=HERE,
        parameters={"DATA_W": 8, "DEPTH": 16},
        waves=True,
        plusargs=[f"+dumpfile_path={WAVES_DIR}/m02_axis_fifo.fst"],
        results_xml=str(BUILD_DIR / "results_axis.xml"),
    )


def run_rand():
    """
    ex03 — AXI4-Stream FIFO constrained-random tests + coverage model.
    Concepts: background coroutines, random stimulus, Python coverage bins.
    """
    sim_build = BUILD_DIR / "sim_rand"
    runner = get_runner(SIM)

    runner.build(
        verilog_sources=[RTL_DIR / "axis_fifo.sv"],
        hdl_toplevel="axis_fifo",
        build_dir=sim_build,
        parameters={"DATA_W": 8, "DEPTH": 16},
        build_args=["-g2012"],
        waves=True,
        always=True,
        timescale=("1ns", "1ps"),
    )

    runner.test(
        hdl_toplevel="axis_fifo",
        test_module="test_axis_rand",
        build_dir=sim_build,
        test_dir=HERE,
        parameters={"DATA_W": 8, "DEPTH": 16},
        waves=True,
        plusargs=[f"+dumpfile_path={WAVES_DIR}/m02_axis_rand.fst"],
        results_xml=str(BUILD_DIR / "results_rand.xml"),
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Dispatch
# ═══════════════════════════════════════════════════════════════════════════

SUITES = {
    "counter": (run_counter, "ex01: hello cocotb (counter)"),
    "axis":    (run_axis,    "ex02: AXI-Stream FIFO directed"),
    "rand":    (run_rand,    "ex03: AXI-Stream FIFO random"),
}

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    if target == "all":
        for name, (fn, desc) in SUITES.items():
            print(f"\n{'='*60}")
            print(f"  {desc}")
            print(f"{'='*60}")
            fn()
        print("\n=== M02 cocotb: all suites complete ===")
    elif target in SUITES:
        fn, desc = SUITES[target]
        print(f"\n  {desc}")
        fn()
    else:
        print(f"Unknown suite: {target!r}. Choose from: {list(SUITES)} or 'all'")
        sys.exit(1)
