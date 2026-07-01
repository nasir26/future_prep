# M09 — UVM + VHDL

**Author:** Nasir Ali
**Org:** C-DAC Noida
**Goal:** Build a real UVM 1.2 verification environment for an existing
design (M01's AXI-Stream FIFO), and get comfortable reading/writing VHDL
alongside SystemVerilog in a mixed-language xsim flow — the two skills
this repo hasn't exercised yet.

---

## Tool table

| Tool | Version | Role |
|------|---------|------|
| xsim | 2023.2 (Vivado) | The only simulator here with bundled UVM 1.2 and VHDL support |
| UVM | 1.2 (Xilinx-bundled, `-L uvm`) | Verification methodology library |
| xvhdl | 2023.2 | VHDL compiler (uart_tx.vhd, uart_rx.vhd) |

M09 is xsim-only — same reason M01's SVA exercises are: UVM's `-L uvm`
library and `xvhdl` are Vivado-specific, with no iverilog/Verilator
equivalent. (This is also why M08's CI, which only has the open-source
toolchain, doesn't run M09.)

---

## Module layout

```
m09_uvm_vhdl/
├── uvm/
│   ├── axis_if.sv          ← interface + clocking block (shared by both DUT ports)
│   ├── axis_seq_item.sv    ← ex01: the one transaction class both sides share
│   ├── axis_sequencer.sv   ← ex01: uvm_sequencer#(axis_seq_item) typedef
│   ├── axis_driver.sv      ← ex01: producer/consumer drive roles, one class
│   ├── axis_monitor.sv     ← ex02: passive observer, broadcasts every beat
│   ├── axis_agent.sv       ← ex02: bundles sequencer+driver+monitor+config
│   ├── axis_scoreboard.sv  ← ex03: FIFO-order-preserving comparison
│   ├── axis_env.sv         ← ex03: wires two agents + scoreboard together
│   ├── axis_sequences.sv   ← ex04: packet/multi-packet/backpressure sequences
│   ├── axis_tests.sv       ← ex04: axis_smoke_test, axis_random_test
│   ├── axis_pkg.sv         ← compiles the above as one UVM class library
│   ├── tb_top.sv           ← DUT (../../m01_sv_sva/rtl/axi_stream_fifo.sv) + clk/rst
│   └── Makefile
├── vhdl/
│   ├── uart_tx.vhd         ← ex05: minimal 8-N-1 UART transmitter
│   ├── uart_rx.vhd         ← ex05: matching receiver (mid-bit sampling)
│   ├── tb_uart_mixed.sv    ← ex06: SV testbench driving the VHDL pair (loopback)
│   └── Makefile
├── Makefile                ← make all -> uvm/ + vhdl/
└── README.md
```

---

## Exercise ladder

### ex01 — axis_seq_item / axis_sequencer / axis_driver: one class, two roles
The DUT has two AXI-Stream ports (slave `s_axis_*`, master `m_axis_*`) that
speak the identical protocol — only who's *supposed* to drive `tvalid` vs.
`tready` differs. Rather than writing separate producer/consumer classes,
`axis_driver` takes an `axis_dir_e mode` (`DRIVE_PRODUCER`/`DRIVE_CONSUMER`)
set via `uvm_config_db`, and `axis_seq_item` carries fields for both roles
(`data`/`last` for the producer, `ready_delay` for the consumer's
backpressure) — each driver simply ignores the fields it doesn't need.

**Key concept:** this is the exact same lesson as M02's `AxisSource`/
`AxisSink` BFM split, rebuilt in UVM's driver/sequencer idiom instead of
two cocotb classes.

### ex02 — axis_monitor / axis_agent: observing without a direction
A monitor never drives — it just watches `tvalid && tready` and reports
every completed beat, and that rule is identical on both ports. One
monitor class, bound to either interface instance, serves both roles;
`axis_agent` bundles sequencer+driver+monitor and pushes `mode`/`vif` down
to its children via its own scoped `uvm_config_db` calls, keeping that
wiring out of the env.

**Key concept — the bug this shipped with:** the monitor originally
sampled with plain `@(posedge vif.clk); if (vif.tvalid && vif.tready)`.
That races the driver's blocking assignment in the same time step
whenever a beat lands in the same delta as `@(negedge rst)` unblocking —
which cost every single producer-side beat on the very first run (0
matched, 8 "arrived with nothing expected"). The fix is `axis_if`'s
`mon_cb` clocking block: default input skew (`#1step`) samples in the
Preponed region, guaranteed settled before this edge's Active-region
assignments run, so `mon_cb.tvalid` is race-free regardless of
driver/monitor process-scheduling order. See `axis_if.sv`'s header
comment for the full account — it's the one piece of this module worth
being able to explain cold.

### ex03 — axis_scoreboard / axis_env: order-preserving comparison
Two `uvm_analysis_imp_decl`'d imports (`_expected`, `_actual`) let one
scoreboard component have two independently-connectable analysis exports.
Expected (producer-side) items queue up; each actual (consumer-side) item
pops the oldest expected item and compares — catching reordering bugs a
simple in-count/out-count check would miss.

### ex04 — axis_sequences / axis_tests: reuse across tests
`axis_packet_seq`/`axis_multi_packet_seq` (producer) and
`axis_consumer_seq` (consumer, `throttle` toggles backpressure on/off)
know nothing about each other — a test class is what pairs one of each
and runs them concurrently (`fork`/`join_none` for the background consumer,
foreground `.start()` for the producer). `axis_smoke_test` (1 packet, no
backpressure) and `axis_random_test` (20 random-length packets, randomized
backpressure) reuse the identical sequence classes.

**Key concept — the second bug this shipped with:** `axis_random_test`
originally ended the run with a fixed `#200ns` drain delay after the
producer sequence finished, sized by guesswork against the *worst-case*
randomized backpressure still outstanding. It usually worked and then
failed with "1 beat never arrived" on a run where the last item happened
to draw a slow `ready_delay`. `axis_base_test::drain()` replaces the fixed
delay with `wait (env.sb.expected_q.size() == 0)` (the actual "is
everything accounted for" signal), guarded by a `fork...join_any` timeout
as a hang safety net — correct regardless of what the random seed
produces.

**Gotcha worth knowing cold:** UVM seeds sequence-item randomization from
each object's *name* (`get_full_name()`), not from `-sv_seed` — so
`axis_multi_packet_seq`'s child sequences, named deterministically
(`pkt_0`, `pkt_1`, ...), draw the *same* "random" packet lengths on every
run regardless of `-sv_seed`. This is by design (reproducibility), and it
means "my results didn't change when I changed `-sv_seed`" is expected
UVM behavior, not a broken test.

### ex05/ex06 — uart_tx.vhd / uart_rx.vhd / tb_uart_mixed.sv: mixed-language xsim
A minimal 8-N-1 UART pair in VHDL, driven and self-checked by a
SystemVerilog testbench — xvhdl and xvlog each compile their own language
into the same `work` library, and xelab links across the boundary with no
wrapper needed. `CLKS_PER_BIT` is a VHDL generic overridden from the SV
side exactly like an SV parameter (`uart_tx #(.CLKS_PER_BIT(4)) ...`).

**Key concept:** `uart_rx` samples at bit *center*, not bit *edge* — after
detecting the start-bit falling edge it waits `CLKS_PER_BIT/2` cycles
before its first sample, then `CLKS_PER_BIT` cycles between each
subsequent one. That's the one idea that makes asynchronous serial
reception work at all: every sample lands maximally far from either
neighboring bit transition.

---

## Quick start

```bash
source ~/future_prep/scripts/activate_qprep.sh
cd m09_uvm_vhdl

make all     # uvm/ (smoke + random) + vhdl/ (mixed-language UART)
```

Expected output (abridged):
```
UVM_INFO ... [SCOREBOARD] PASS — 8 beat(s) matched, 0 mismatches, 0 stuck in flight
UVM_INFO ... [SCOREBOARD] PASS — 160 beat(s) matched, 0 mismatches, 0 stuck in flight
  PASS  sent=0x00  received=0x00
  ...
tb_uart_mixed: 12 PASS, 0 FAIL
ALL PASS
```

---

## Definition of Command (DoC)

Pass ALL of the following **without references**:

1. **One driver, two roles**: Explain how `axis_driver` drives both the
   producer side (`s_axis_*`) and the consumer side (`m_axis_tready`)
   without being two classes, and why `axis_seq_item` carries fields for
   both roles instead of being split in two.

2. **The clocking-block bug**: Reproduce the argument for why
   `@(posedge vif.clk); if (vif.tvalid && vif.tready)` is a race, and why
   `axis_if`'s `mon_cb` clocking block (`#1step` input skew) fixes it
   regardless of process-scheduling order. Bonus: explain why the
   consumer-side monitor only showed a one-cycle *lag* while the
   producer-side monitor showed *zero* events, from the same root cause.

3. **Scoreboard design**: Explain why `axis_scoreboard` needs two
   `uvm_analysis_imp_decl`'d imports instead of one, and why it compares
   via a queue rather than counting beats in vs. beats out.

4. **The drain-time bug**: Explain why a fixed `#200ns` after the producer
   sequence finishes is the wrong way to end `axis_random_test`, what
   `axis_base_test::drain()` waits on instead, and why the `fork...
   join_any` timeout is still there even though the wait condition is
   "correct."

5. **UVM's name-based seeding**: Explain why `axis_random_test` produces
   the identical packet-length sequence across different `-sv_seed`
   values, and what would need to change for it not to.

6. **VHDL <-> SV cheat-sheet**: Cold, name the VHDL/SV equivalents for
   `std_logic`, `std_logic_vector`, and "generic" — and state which two
   xsim compiler invocations produce the `work` library that `tb_uart_mixed`
   links against.

7. **UART sampling**: Explain why `uart_rx` waits `CLKS_PER_BIT/2` cycles
   after detecting the start bit before its first sample, rather than
   sampling immediately.

8. **Fresh-run acid test**: From a clean `make clean && make all` in
   `m09_uvm_vhdl/`, get both UVM tests' `[SCOREBOARD] PASS` lines and
   `tb_uart_mixed: 12 PASS, 0 FAIL` / `ALL PASS` — without looking at any
   test file — and check off all 10 modules in the top-level
   `PROGRESS.md`.
