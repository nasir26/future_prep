# Progress Tracker

Updated: 2026-07-01 (M09) — all 10 modules complete

## Module Status

| Module | Status | Completed | Notes |
|--------|--------|-----------|-------|
| M00 Toolchain bootstrap | ✅ Complete | 2026-06-10 | All 3 sims passing; VCDs in waves/ |
| M01 SV + SVA | ✅ Complete | 2026-06-24 | ex01–ex07 + axi_stream + axi_lite all PASS (314 total); DoC confirmed |
| M02 cocotb | ✅ Complete | 2026-06-24 | 13/13 PASS: ex01(5) ex02(5) ex03(3) |
| M03 RFSoC RTL | ✅ Complete | 2026-06-24 | 18/18 PASS: ex01(5) DDS, ex02(4) envelope, ex03(5) sequencer, ex04(4) Rabi |
| M04 ARTIQ kernels | ✅ Complete | 2026-06-25 | 45 PASS 1 SKIP: ex01(6) TTL, ex02(4) photon, ex03(6) DDS, ex04(5) cooling, ex05(4) Rabi, ex06(5) Ramsey/DMA, ex07(4) SBC, ex08(4) MS, ex09(8) MCM+herald |
| M05 Migen/Amaranth | ✅ Complete | 2026-06-25 | 32/32 PASS: Migen(13) Counter/FSM/FIFO, Amaranth(19) Counter/FSM/FIFO/DDS + Verilog export |
| M06 iontrap_emu | ✅ Complete | 2026-06-25 | 61/61 PASS: single-ion(10) cooling(8) readout(13) noise(16) ms_gate(7) server(7) |
| M07 Capstone | ✅ Complete | 2026-06-29 | 34/34 PASS: backend(6) compiler(7) scheduler(6) calibration(8) distributed(7) |
| M08 Infrastructure | ✅ Complete | 2026-07-01 | Docker image + compose demo + GH Actions CI (`act`-verified green) + pre-commit |
| M09 UVM + VHDL | ✅ Complete | 2026-07-01 | UVM env (8+160 beats matched, 0 mismatches) + VHDL UART mixed-language (12/12 PASS) |

## M09 Checklist (UVM + VHDL)

- [x] axis_if.sv: shared AXI-Stream interface + `mon_cb` clocking block
- [x] axis_seq_item/sequencer/driver.sv: one item + one driver, mode-configured for both DUT ports
- [x] axis_monitor/agent.sv: passive observer + agent bundling driver/sequencer/monitor
- [x] axis_scoreboard/env.sv: order-preserving comparison via two `uvm_analysis_imp_decl` exports
- [x] axis_sequences/tests.sv: axis_smoke_test (8 beats) + axis_random_test (160 beats, randomized backpressure)
- [x] tb_top.sv: DUT compiled straight from `m01_sv_sva/rtl/axi_stream_fifo.sv` (no copy)
- [x] uart_tx.vhd / uart_rx.vhd: minimal 8-N-1 UART pair
- [x] tb_uart_mixed.sv: SV testbench, VHDL DUT, loopback, 12/12 PASS
- [x] README.md with 8-item DoC

Key lessons:
- xsim's design-wide timescale check needs `xelab --timescale 1ns/1ps` when
  linking `-L uvm` — Xilinx's precompiled UVM library modules carry no
  timescale of their own, and mixing explicit-timescale user files with it
  otherwise throws `XSIM 43-4100`.
- The monitor's first version (`@(posedge vif.clk); if (tvalid && tready)`)
  raced the driver's blocking assignment in the same delta cycle — 0/8
  producer-side beats detected. Fixed with a clocking block (`#1step`
  input skew samples in the Preponed region, before this edge's Active
  region runs) — the textbook reason UVM environments use clocking blocks
  instead of raw signal access.
- A fixed post-sequence drain delay (`#200ns`) is a guess at worst-case
  randomized backpressure and will eventually under-run; waiting on the
  scoreboard's own "anything still outstanding?" state
  (`env.sb.expected_q.size() == 0`), guarded by a `fork...join_any`
  timeout as a hang safety net, is correct regardless of the random seed.
- UVM seeds sequence-item randomization from the object's name
  (`get_full_name()`), not from `-sv_seed` — identical "random" output
  across different seeds is expected UVM behavior when child sequences are
  named deterministically (`pkt_0`, `pkt_1`, ...).
- Mixed-language xsim needs no wrapper: `xvhdl` and `xvlog` each compile
  their own language into the same `work` library, and `xelab` links
  across the boundary as if everything were one language.

## M08 Checklist (Infrastructure — Docker, CI, pre-commit)

- [x] Dockerfile: open-source qprep image (`condaforge/miniforge3` + `environment.yml`), Vivado/xsim deliberately excluded (proprietary/licensed)
- [x] docker-compose.yml: `iontrap-server` (M06 asyncio TCP/JSON server) + `client` (demo_client.py) — real two-container network demo
- [x] .github/workflows/ci.yml: ruff + verible-verilog-lint + M01(ex01-04)/M02/M03/M04/M05/M06/M07 — one job, `conda-incubator/setup-miniconda` from the same `environment.yml`
- [x] .pre-commit-config.yaml + ruff.toml + .rules.verible_lint at repo root (tool-discovery constraints force this; documented in m08_infra/README.md)
- [x] `act push -W .github/workflows/ci.yml` runs the whole pipeline green locally
- [x] `make demo` → two-container compose run prints real `rabi_scan`/`ms_gate` results over the network
- [x] README.md with 8-item DoC

Key lessons:
- Adding real CI immediately surfaced two pre-existing bugs invisible on this workstation:
  1. M01's ex01-04 testbenches hardcoded `$dumpfile("../../waves/...")` — one directory too far up. It "worked" locally only because a stray `~/waves/` directory (outside the repo) had been silently absorbing VCDs since 2026-06-11. Fixed to `../waves/` to match the Makefile's `WAVES_DIR` and the repo's actual convention.
  2. `amaranth-yosys` (needed for M05's `.convert()` Verilog-export tests) was pip-installed locally but never added to `environment.yml` — undeclared environment drift. Added to the pip section.
- `docker run` doesn't source a login shell, so `conda activate` no-ops across Docker layers — use `mamba run -n qprep` instead (both `SHELL` and `ENTRYPOINT` in the Dockerfile do this).
- M07's `QPUNode.connect()` links two peers in-process (`self._peer = other`) — no network protocol exists to run it across containers. M06's `iontrap.server` (asyncio TCP/JSON) is the one real network service in the repo, so it's what the compose demo actually runs.
- Introducing a repo-wide linter after 7 modules already exist means choosing: retrofit everything, or scope the gate. Waived `ruff`/`verible` rules narrowly per-module (documented in `ruff.toml`/`.rules.verible_lint`) rather than editing already-complete, DoC-confirmed RTL/Python; fixed the two genuinely trivial one-line lint issues (M02/M03) directly since risk was zero.

## M07 Checklist (Capstone — full-stack quantum control)

- [x] backend.py: QPUBackend wrapping M06 IonTrap + FluorescenceReadout + MS gate (6 tests)
- [x] compiler.py: QASM3 regex parser — h/x/rz/cx/measure → CarrierPulse/VirtualZ/EntangleGate/MeasureOp (7 tests)
- [x] scheduler.py: asyncio ExperimentScheduler — submit/priority/run_all (6 tests)
- [x] calibration.py: ParamStore + freq_scan/rabi_pi_time/ramsey_track/recal_daemon (7 tests)
- [x] node.py: QPUNode — local ops + heralded entanglement via photonic link (8 tests)
- [x] circuits/bell.qasm: H + CX + measure → Bell state
- [x] circuits/rabi.qasm: X + measure → π-pulse demo
- [x] run_qasm3.py: CLI — QASM3 → compile → execute → ASCII bar chart
- [x] README.md with 7-item DoC

Key lessons:
- Virtual Z (rz) is zero-cost on trapped-ion hardware: DDS phase offset, no pulse
- t_pulse = θ / Ω_R — rotation angle → physical duration via Rabi frequency
- MS gate fidelity: F = 1 − 2η²(n̄ + ½) — two noise sources: thermal + Lamb-Dicke
- Ramsey ×N more sensitive than Rabi for same total interrogation time T
- Herald rate ∝ η²: doubling collection efficiency → 4× faster entanglement rate
- asyncio.sleep(0) inside calibration coroutines yields to event loop without delay
- Bell circuit: 5 compiled instructions (not 6 — header/declaration lines are skipped)

## M01 Checklist (Day 2 — SV basics ladder)

- [x] ex01: D flip-flop — logic, always_ff, synchronous reset (iverilog, 9 PASS)
- [x] ex02: Parameterized shift register — parameter, $clog2, generate (iverilog, 4 PASS)
- [x] ex03: typedef / enum / packed struct — axi_beat_t (iverilog, 5 PASS)
- [x] ex04: Two-always FSM — traffic light, Moore machine (iverilog, 28 PASS)
- [x] ex05: Interface + modport — producer/consumer handshake (xsim, 3 PASS)
- [x] ex06: Package — fifo_pkg types + function (xsim, 9 PASS)
- [x] ex07: Parameterized sync FIFO — circular buffer, dual-pointer (xsim, 19 PASS)
- [x] Day 3: AXI4-Stream FIFO + SVA assertions (218 PASS incl. 200-beat random stream)
- [x] Day 4: AXI4-Lite regfile + gate_fifo_sv + SVA (19 PASS) — see m01_sv_sva/README.md
      for why `gate_fifo_sv.sv` is an original implementation, not a literal port
      (no `~/fpga_rtl/gate_fifo.v` source exists on this machine)

Day 4 key lessons:
- The AXI-Stream STIMULUS property (once TVALID asserts, it must hold until
  TREADY is seen) applies to test *stimulus*, not just the DUT — a first
  version of `tb_axi_lite_regfile.sv`'s gate test asserted `s_tvalid` to
  probe that the gated FIFO refuses it, then unconditionally cleared it,
  which is itself an illegal retracted offer. Fix: hold the offer and let
  the *next* test pick it up once the gate opens, rather than drop-and-reoffer.
- Corollary: once that held offer's `tready` goes high mid-way through a
  concurrent AXI-Lite write's own response handshake, it must be cleared by
  a process racing that write (`fork ... join`), not sequentially after —
  otherwise the DUT (correctly) accepts several more beats of the same
  now-unwanted held data before the test notices.
- AXI4-Lite's AW/W channels are independent — a legal master may assert
  either one first — so `axi_lite_regfile.sv`'s write FSM needs
  `W_WAIT_DATA`/`W_WAIT_ADDR` states to latch whichever arrives first.

## M04 Checklist (ARTIQ kernels — artiq_sim + pytest)

- [x] artiq_sim/core.py: Core device, timeline cursor, mu conversion, RTIOUnderflow
- [x] artiq_sim/devices.py: TTLOut, TTLIn (Poisson counts), AD9910 FTW/POW/ASF, CoreDMA
- [x] artiq_sim/environment.py: EnvExperiment, HasEnvironment, make_experiment()
- [x] ex01 TTL basics: break_realtime, delay, at_mu, burst, underflow demo (6 tests)
- [x] ex02 Photon counting: gate_rising_mu, count, histogram, discrimination fidelity (4 tests)
- [x] ex03 DDS: set, set_mu, phase, RF switch, freq ramp (6 tests)
- [x] ex04 Doppler cooling: cool_and_pump(), detect() subroutines (5 tests)
- [x] ex05 Rabi scan: P=sin²(π f_Rabi τ) [NOT sin²(πτ/τ_π)], scipy fit, τ_π ±30% (4 tests)
- [x] ex06 Ramsey: phase scan, CoreDMA trace recording/playback, contrast fit (5 tests)
- [x] ex07 Sideband cooling: r^N model, sideband asymmetry n̄ extraction (3+1skip)
- [x] ex08 MS gate: bichromatic pulse, N_MODCYCLES, fidelity=1−2η²(n̄+½) (4 tests)
- [x] ex09 Mid-circuit + heralded: MCM+conditional X; geometric herald loop (8 tests)

Key lessons:
- ARTIQ is Nix-only; artiq_sim matches the real API 1:1 for portable kernel code
- Rabi formula: P = sin²(π × f_Rabi × τ) — at τ_π = 1/(2f_Rabi), P=1 NOT 0
- Underflow demo: go back >SLACK_MU (2ms), not exactly =SLACK_MU (1ms = boundary, no raise)
- SBC asymmetry: n̄/(n̄+1) ratio unmeasurable with 30 shots when n̄ < 0.1 (Poisson noise)
- CoreDMA: record once, playback N times — key for tight shot loops

## M03 Checklist (RFSoC RTL — iverilog + cocotb)

- [x] ex01 dds_lut: 5 tests (reset, pinc_readback, phase_acc_step, iq_quadrature, spectral_purity) — 5/5 PASS
- [x] ex02 pulse_envelope: 4 tests (square, gaussian, busy_clears, back_to_back) — 4/4 PASS
- [x] ex03 timed_sequencer: 5 tests (wait, set_freq, fire, read_ctr, 5-instr program) — 5/5 PASS
- [x] ex04 photon_counter: 4 tests (prng_noise, single_capture, threshold, rabi_sweep R²=0.99) — 4/4 PASS
- [x] axil_bfm.py: reusable AXI4-Lite master BFM for all tests
- [x] run_sim.py: LUT pre-generation + cocotb_tools.runner for all 4 targets
- [x] README.md with 8-item DoC

Key lessons:
- Coherent sampling (integer cycles in FFT window) eliminates spectral leakage
- AXI addr decode: use bit-field check (addr[8]) not constant compare for BRAM regions
- prog_mem init to HALT opcode (0xF) so PC falling off end auto-terminates sequencer
- Fibonacci LFSR: 16-bit polynomial x^16+x^15+x^13+x^4+1 is clean + maximal-length

## M02 Checklist (cocotb 2.0.1 + iverilog)

- [x] ex01 counter: 5 tests (reset, count_up, rollover, enable_gate, reset_while_running) — 5/5 PASS
- [x] ex02 axis_fifo directed: 5 tests (single_beat, packet_roundtrip, fill_and_drain, back_to_back, sim_push_pop) — 5/5 PASS
- [x] ex03 axis_fifo random: 3 tests (random_packets 50pkt/70% bp, flow_control, heavy_back_pressure 20% bp) — 3/3 PASS
- [x] BFM (fifo_bfm.py): AxisSource, AxisSink, Scoreboard with correct handshake timing
- [x] Coverage model: 4 packet-length bins, all hit in test_random_packets
- [x] Wave dumps: m02_counter.fst, m02_axis_fifo.fst, m02_axis_rand.fst in waves/
- [x] run_sim.py: cocotb_tools.runner wrapper for all three targets
- [x] README.md with DoC checklist

Key timing lesson: BFM handshake signals (tready, tvalid — combinational RTL outputs) must
be sampled at RisingEdge (pre-delta), NOT at RisingEdge+Timer(1ps).  The Timer is only
needed in test code to read registered outputs (fill_level, count) after an edge.

## M00 Checklist

- [x] Miniforge3 installed at `~/miniforge3`
- [x] `qprep` conda env created with Python 3.11.15
- [x] `iverilog` 12.0 installed and on PATH in qprep
- [x] `verilator` 5.048 installed and on PATH in qprep
- [x] `gtkwave` installed in qprep (headless: VCD via VS Code Surfer)
- [x] Python stack: numpy 2.4.6, scipy 1.17.1, matplotlib 3.10.9, qutip 5.3.0, cocotb 2.0.1, pytest, migen 0.9.2, amaranth 0.5.8, qiskit 2.4.1, openqasm3 1.0.1, zmq 27.1.0, grpcio 1.81.1
- [x] Vivado 2023.2 / xsim sourced and verified: `setup_vivado.sh`
- [x] Smoke test: counter.v simulates in **iverilog** → VCD `waves/counter_icarus.vcd`
- [x] Smoke test: counter.v simulates in **xsim** → VCD `waves/counter_xsim.vcd`
- [x] Smoke test: counter.v simulates in **Verilator** → VCD `waves/counter_verilator.vcd`
- [x] Waveform viewing: VS Code Surfer extension documented in m00_toolchain/README.md
- [x] `make smoke` in m00_toolchain/ exits 0 — 9 PASS-ish lines (8 tests + 1 summary) × 3 simulators = 27 total

## M00 Definition of Command

Pass ALL of the following **without references**:
1. Type `source ~/future_prep/scripts/setup_vivado.sh` and show `xsim --version` output
2. Type `conda activate qprep` and show `python -c "import qutip, cocotb, amaranth; print('ok')"`
3. Explain the difference between iverilog and xsim for cocotb (why cocotb prefers iverilog)
4. Open `waves/counter_icarus.vcd` in VS Code Surfer without any extra commands
5. Explain GTKWave X-forwarding fallback (`ssh -X`)

## Lessons Learned

*(fill in as you work)*
