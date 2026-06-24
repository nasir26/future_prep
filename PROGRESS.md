# Progress Tracker

Updated: 2026-06-24

## Module Status

| Module | Status | Completed | Notes |
|--------|--------|-----------|-------|
| M00 Toolchain bootstrap | ✅ Complete | 2026-06-10 | All 3 sims passing; VCDs in waves/ |
| M01 SV + SVA | ✅ Complete | 2026-06-24 | ex01–ex07 all PASS; DoC confirmed |
| M02 cocotb | ✅ Complete | 2026-06-24 | 13/13 PASS: ex01(5) ex02(5) ex03(3) |
| M03 RFSoC RTL | ⏳ Pending | — | |
| M04 ARTIQ kernels | ⏳ Pending | — | |
| M05 Migen/Amaranth | ⏳ Pending | — | |
| M06 iontrap_emu | ⏳ Pending | — | |
| M07 Capstone | ⏳ Pending | — | |
| M08 Infrastructure | ⏳ Pending | — | |
| M09 UVM + VHDL | ⏳ Pending | — | |

## M01 Checklist (Day 2 — SV basics ladder)

- [x] ex01: D flip-flop — logic, always_ff, synchronous reset (iverilog, 9 PASS)
- [x] ex02: Parameterized shift register — parameter, $clog2, generate (iverilog, 4 PASS)
- [x] ex03: typedef / enum / packed struct — axi_beat_t (iverilog, 5 PASS)
- [x] ex04: Two-always FSM — traffic light, Moore machine (iverilog, 28 PASS)
- [x] ex05: Interface + modport — producer/consumer handshake (xsim, 3 PASS)
- [x] ex06: Package — fifo_pkg types + function (xsim, 9 PASS)
- [x] ex07: Parameterized sync FIFO — circular buffer, dual-pointer (xsim, 19 PASS)
- [x] Day 3: AXI4-Stream FIFO + SVA assertions
- [x] Day 4: AXI4-Lite regfile + gate_fifo port

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
- [x] `make smoke` in m00_toolchain/ exits 0 — 7 PASS × 3 simulators

## M00 Definition of Command

Pass ALL of the following **without references**:
1. Type `source ~/future_prep/scripts/setup_vivado.sh` and show `xsim --version` output
2. Type `conda activate qprep` and show `python -c "import qutip, cocotb, amaranth; print('ok')"`
3. Explain the difference between iverilog and xsim for cocotb (why cocotb prefers iverilog)
4. Open `waves/counter_smoke.vcd` in VS Code Surfer without any extra commands
5. Explain GTKWave X-forwarding fallback (`ssh -X`)

## Lessons Learned

*(fill in as you work)*
