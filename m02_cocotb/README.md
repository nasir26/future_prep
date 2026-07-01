# Module 02 — cocotb

**Status:** ✅ Complete (Days 5–6, 14 & 17 Jun 2026)  
**Goal:** Write Python testbenches for RTL using cocotb — from a hello-world coroutine to a full constrained-random testbench with a functional coverage model.

---

## Schedule

| Day | Date | Focus | EOD milestone |
|-----|------|-------|---------------|
| Day 5 | Fri 14 Jun | cocotb basics + AXI-Stream FIFO directed | `pytest m02_cocotb/` green |
| Day 6 | Mon 17 Jun | Constrained-random + coverage model | M02 DoC checklist complete |

---

## Tools

| Tool | Why used here |
|------|--------------|
| iverilog 12.0 | Compiles Verilog/SV + cocotb VPI shim |
| vvp           | Executes compiled simulation with cocotb Python injected via VPI |
| cocotb 2.0.1  | Coroutine-based testbench framework |
| cocotb-bus 0.3.0 | BusDriver/Monitor/Scoreboard base classes |
| Python 3.11   | Test logic, coverage model, scoreboard |

Wave format: **FST** (iverilog native; VS Code Surfer opens `.fst` files directly).

---

## Repo layout

```
m02_cocotb/
├── Makefile
├── README.md                ← this file
├── rtl/
│   ├── counter.v            ← ex01 DUT: 4-bit synchronous up-counter
│   └── axis_fifo.sv         ← ex02/ex03 DUT: AXI4-Stream FIFO (DATA_W=8, DEPTH=16)
└── tests/
    ├── fifo_bfm.py          ← shared BFM: AxisSource, AxisSink, Scoreboard
    ├── test_counter.py      ← ex01: hello cocotb (5 tests)
    ├── test_axis_fifo.py    ← ex02: directed Driver/Monitor/Scoreboard (5 tests)
    ├── test_axis_rand.py    ← ex03: constrained-random + coverage (3 tests)
    └── run_sim.py           ← Python runner (cocotb_tools.runner)
```

Wave files land in `~/future_prep/waves/`:
- `m02_counter.fst`
- `m02_axis_fifo.fst`
- `m02_axis_rand.fst`

---

## Exercise ladder

### ex01 — hello cocotb (`test_counter.py` → `rtl/counter.v`)

Introduces the four primitives:

```
@cocotb.test()          — marks async def as a test case
Clock(sig, T, units)    — background clock generator
cocotb.start_soon(coro) — schedule a coroutine (non-blocking)
RisingEdge(sig)         — suspend until next posedge
ClockCycles(sig, n)     — suspend for n posedges
dut.<port>.value = x    — drive a signal
int(dut.<port>.value)   — read a signal
```

Tests: reset, count_up, rollover (4→0), enable gate, reset-while-running.

### ex02 — Driver / Monitor / Scoreboard (`test_axis_fifo.py` → `rtl/axis_fifo.sv`)

Introduces the DMS verification pattern:

```
Driver (AxisSource)   — drives tvalid/tdata/tlast; waits for tready handshake
Sink (AxisSink)       — drives tready; collects accepted (data, tlast) tuples
Scoreboard            — deque-based expected vs. observed checker
cocotb.start_soon     — run send and recv concurrently (essential for non-trivial DUTs)
```

Tests: single beat, packet roundtrip, fill-and-drain, back-to-back packets, simultaneous push+pop.

### ex03 — Constrained-random + coverage (`test_axis_rand.py` → `rtl/axis_fifo.sv`)

Extends ex02 with:

```
random.randint(a, b)         — constrained to [a, DEPTH] for protocol safety
Background coroutine          — _back_pressure_task toggles tready each cycle
CoverageModel                 — tracks packet-length bins; assert_coverage() at end
task.cancel()                 — clean teardown of a background coroutine
```

Tests: 50 random packets under 70% ready probability, flow-control assertion, heavy back-pressure (20% ready).

---

## Running

```bash
source ~/future_prep/scripts/activate_qprep.sh
cd ~/future_prep/m02_cocotb

make               # run all suites
make test_counter  # ex01 only
make test_axis     # ex02 only
make test_rand     # ex03 only
make clean         # remove build/
```

---

## How cocotb_tools.runner works (key mental model)

```
iverilog -g2012 -o sim_build/axis_fifo.vvp      ← compile DUT + VPI shim
          rtl/axis_fifo.sv
          sim_build/cocotb_iverilog_dump.v       ← auto-generated dump stub

vvp -M <cocotb_libs> -m vpi.vpi sim_build/axis_fifo.vvp
    +dumpfile_path=~/future_prep/waves/m02_axis_fifo.fst
    -fst                                         ← use FST format
```

On startup, vvp loads cocotb's VPI module which:
1. Discovers all `@cocotb.test()` functions in your test module.
2. Runs them as async coroutines, advancing the simulation clock via VPI callbacks.
3. Reports PASS / FAIL per test; writes `results_*.xml` for CI parsing.

---

## Definition of Command (DoC)

Pass ALL of the following **without references** before marking M02 complete:

1. **Explain cocotb's execution model**: "cocotb injects Python via VPI into the running simulator; `await RisingEdge(clk)` registers a VPI callback and yields; the simulator advances time and fires the callback which resumes the coroutine."

2. **Write a `@cocotb.test()` from scratch** that resets a DUT, drives a 10-clock count, reads the output, and asserts the result. Should take < 2 minutes.

3. **Explain `cocotb.start_soon(coro)` vs `await coro`**: "start_soon schedules coro to run concurrently with the caller; await blocks the caller until coro finishes. You need start_soon whenever send and receive must run at the same time (e.g., FIFO with back-pressure that could deadlock if serialised)."

4. **Describe the Driver/Monitor/Scoreboard pattern**: "Driver handles protocol timing; Monitor passively observes outputs; Scoreboard compares observed to expected. Separating them makes the driver reusable and the checking logic testable in isolation."

5. **Explain what `waves=True` does in the runner**: "It generates `cocotb_iverilog_dump.v` with `$dumpvars(0, top)` and passes `-fst` to vvp, producing an FST waveform file. The `+dumpfile_path=` plusarg redirects the output to our `waves/` directory."

6. **Explain the functional coverage gap**: "The coverage model checks whether all packet-length bins were exercised. A gap means the random seed never generated a packet of that length — fix by running more packets or seeding differently."

7. **Explain back-pressure and why it must be tested**: "If the consumer is slow (tready=0), the FIFO must hold data without losing it and assert tready=0 to the producer when full. Without random tready toggling in the test, you never exercise the full/stall path, which is where FIFO bugs hide."

8. **Cold write**: given a new 8-bit DUT with a `valid`/`ready`/`data` output, write a Monitor class that collects accepted beats into a list, without referencing the existing code.
