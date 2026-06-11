# Progress Tracker

Updated: 2026-06-11

## Module Status

| Module | Status | Completed | Notes |
|--------|--------|-----------|-------|
| M00 Toolchain bootstrap | ✅ Complete | 2026-06-10 | All 3 sims passing; VCDs in waves/ |
| M01 SV + SVA | 🔄 Active | — | Day 2 done: ex01–ex07 all PASS; Day 3–4 pending |
| M02 cocotb | ⏳ Pending | — | |
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
- [ ] Day 3: AXI4-Stream FIFO + SVA assertions (Wed 12 Jun)
- [ ] Day 4: AXI4-Lite regfile + gate_fifo port (Thu 13 Jun)

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
