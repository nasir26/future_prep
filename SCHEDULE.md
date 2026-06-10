# 4-Week Prep Schedule

**Prep window:** 10 June – 14 August 2026 (Mon–Fri, no weekends)  
**Daily break:** 1:00 PM – 2:00 PM  
**Effective daily hours:** ~7 hrs focused work

---

## WEEK 1 — Modules 00–02: Toolchain + RTL Language + Verification

### Day 1 (Mon 10 Jun) — M00: Toolchain bootstrap
- AM: Miniforge install, `qprep` env, iverilog/Verilator/GTKWave, Python stack
- PM: Counter smoke test in all 3 simulators; VCD → VS Code Surfer workflow confirmed
- EOD milestone: `make smoke` passes, waveform visible in Surfer

### Day 2 (Tue 11 Jun) — M01: SV basics
- AM: logic/always_ff/always_comb, typedef/enum, packed structs exercises (graded ladder)
- PM: interfaces + modports, packages, parameterized modules
- EOD milestone: All SV ladder exercises passing self-test benches

### Day 3 (Wed 12 Jun) — M01: AXI4-Stream FIFO + SVA
- AM: Write AXI4-Stream FIFO in SV; understand handshake protocol deeply
- PM: Write SVA properties for VALID/READY rules; run in xsim; debug assertions
- EOD milestone: FIFO passes all SVA assertions in xsim

### Day 4 (Thu 13 Jun) — M01: AXI4-Lite regfile + gate_fifo.v port
- AM: Write AXI4-Lite slave register file in SV
- PM: Copy gate_fifo.v from ~/fpga_rtl, port to idiomatic SV + assertions
- EOD milestone: M01 DoC checklist complete; write FSM + AXI-Stream block cold

### Day 5 (Fri 14 Jun) — M02: cocotb setup + first testbench
- AM: cocotb environment check; driver/monitor/scoreboard pattern intro
- PM: Full cocotb testbench for AXI4-Stream FIFO with constrained-random stimulus
- EOD milestone: `pytest m02_cocotb/` green; coverage report generated

---

## WEEK 2 — Modules 02–03: cocotb done + RFSoC gateware

### Day 6 (Mon 17 Jun) — M02: cocotb on RTL engine
- AM: cocotb regression against cz_engine.v + fp64_sim_models.v copy
- PM: pytest integration, CI-friendly output
- EOD milestone: M02 DoC checklist complete

### Day 7 (Tue 18 Jun) — M03: DDS/NCO core
- AM: 32-bit phase accumulator + sine LUT design; AXI4-Lite control interface
- PM: Simulate DDS output; dump VCD; FFT in Python; verify spectral purity
- EOD milestone: DDS output waveform visible in Surfer; FFT spur < -50 dBc

### Day 8 (Wed 19 Jun) — M03: DDS CORDIC variant + pulse envelope
- AM: CORDIC-based DDS variant (referencing cordic_fp64.v approach)
- PM: Pulse envelope engine — square/Gaussian/Blackman BRAM tables, trigger gating
- EOD milestone: Envelope-modulated RF burst visible in waveform

### Day 9 (Thu 20 Jun) — M03: Timed sequencer (mini-tProc)
- AM: Instruction set design; BRAM instruction store; FSM implementation
- PM: wait/set-freq/fire-pulse/read-counter/branch instructions working in sim
- EOD milestone: Sequencer runs a 5-instruction program in simulation

### Day 10 (Fri 21 Jun) — M03: Photon counter + Rabi integration test
- AM: Pseudo-random Poisson PMT generator; threshold comparator; feed to sequencer
- PM: Full Rabi gateware test: sweep pulse duration, fit curve in Python, plot
- EOD milestone: Rabi curve plotted from RTL simulation data; M03 DoC complete

---

## WEEK 3 — Modules 03 wrap + 04–06

### Day 11 (Mon 24 Jun) — M03 wrap + QICK/ARTIQ source reading
- AM: Clone QICK + ARTIQ into vendor/; write source-reading map
- PM: Walk through QICK tProc source; compare to own sequencer design
- EOD milestone: Source-reading map written; can explain QICK vs own sequencer

### Day 12 (Tue 25 Jun) — M04: ARTIQ environment setup + TTL/DDS basics
- AM: ARTIQ sim/dummy install; device_db for dummy core
- PM: TTL timeline, delay, at_mu, underflow handling; first kernels running
- EOD milestone: 3 basic kernels execute cleanly in ARTIQ sim

### Day 13 (Wed 26 Jun) — M04: Photon histogram, cooling, Rabi
- AM: Photon-count histogram readout with threshold; Doppler cooling skeleton
- PM: Rabi flop scan (carrier + sideband) returning realistic data via QuTiP RPC stub
- EOD milestone: Rabi scan returns a fitted sinusoid from ARTIQ kernel

### Day 14 (Thu 27 Jun) — M04: Ramsey, sideband cooling, CoreDMA
- AM: Ramsey with phase scan; sideband cooling loop
- PM: CoreDMA recorded sequences; tight gate loop timing
- EOD milestone: All 5 mid-level kernels passing

### Day 15 (Fri 28 Jun) — M04: MS gate + mid-circuit measurement + entanglement
- AM: MS gate pulse skeleton; mid-circuit measurement with conditional branch
- PM: Ion–photon entanglement attempt/herald/retry loop
- EOD milestone: M04 DoC complete; all 10 kernel types implemented

### Day 16 (Mon 1 Jul) — M05: Migen/Amaranth intro + blinker → FIFO
- AM: Amaranth syntax; blinker; AXI-Stream-ish stream FIFO in Amaranth
- PM: Elaborate to Verilog; simulate with Icarus; view waveforms
- EOD milestone: Amaranth FIFO generates Verilog and passes sim

### Day 17 (Tue 2 Jul) — M05: DDS in Amaranth + ARTIQ gateware reading
- AM: Small DDS core in Amaranth; elaborate + simulate
- PM: Walk ARTIQ Migen gateware — rtio core, phys; guided reading map
- EOD milestone: M05 DoC complete; can read ARTIQ rtio Migen unaided

### Day 18 (Wed 3 Jul) — M06: Single-ion QuTiP emulator
- AM: Two-level + harmonic mode; carrier/RSB/BSB Rabi dynamics; thermal states
- PM: Doppler + sideband cooling rate models; test all single-ion scenarios
- EOD milestone: Single-ion Rabi curves match analytical expectations

### Day 19 (Thu 4 Jul) — M06: Readout model + two-ion MS gate
- AM: State-dependent fluorescence; Poisson photon counts; threshold fidelity
- PM: Two-ion MS gate dynamics; detuning/gate-time/phase-space sweep
- EOD milestone: MS gate fidelity vs detuning curve plotted

### Day 20 (Fri 5 Jul) — M06: Photonic link + noise + asyncio server
- AM: Photonic link model; heralded Bell measurement; attempt-rate/fidelity tradeoff
- PM: Noise knobs (laser noise, heating, B-field drift); asyncio TCP/JSON server
- EOD milestone: M06 DoC complete; iontrap_emu server accepts connections

---

## WEEK 4 — Capstone + Infrastructure + UVM/VHDL

### Day 21 (Mon 8 Jul) — M07: Stack wiring + experiment scheduler
- AM: asyncio experiment scheduler; CLI interface; instruction compiler sketch
- PM: Wire to ARTIQ-sim backend OR cocotb/Verilator co-sim sequencer
- EOD milestone: Single-qubit gate experiment runs end-to-end in the stack

### Day 22 (Tue 9 Jul) — M07: Calibration routines
- AM: Frequency scan → fit → parameter store; Rabi → π-time
- PM: Ramsey → qubit frequency tracking; closed-loop recalibration daemon
- EOD milestone: All 4 calibration routines automated

### Day 23 (Wed 10 Jul) — M07: OpenQASM 3 front end
- AM: Parse QASM3 circuit with qiskit/openqasm3; compile to pulse instructions
- PM: Run Bell-state circuit through full stack; return counts
- EOD milestone: `run_qasm3.py bell.qasm` returns |00⟩+|11⟩ distribution

### Day 24 (Thu 11 Jul) — M07: Multi-node distributed entanglement
- AM: Two emulator instances on loopback; orchestration layer
- PM: Heralded remote-entanglement experiment across two "QPU nodes"
- EOD milestone: M07 DoC complete — one command, Bell circuit, fitted results

### Day 25 (Fri 12 Jul) — M08: Infrastructure
- AM: Dockerfile(s) for qprep env; docker-compose for capstone services
- PM: GitHub Actions YAML (lint + pytest + Icarus); pre-commit hooks (ruff, verible)
- EOD milestone: `act` runs CI locally green

### Day 26 (Mon 15 Jul) — M09: UVM testbench
- AM: UVM env/agent/driver/monitor/scoreboard for AXI-Stream FIFO (xsim UVM 1.2)
- PM: Debug and annotate heavily; run all UVM sequences
- EOD milestone: UVM TB passes; all classes annotated as learning artifact

### Day 27 (Tue 16 Jul) — M09: VHDL + mixed-language
- AM: Small open-source VHDL UART; compile with xvhdl
- PM: Mixed-language xsim run (Verilog TB + VHDL DUT); VHDL↔Verilog cheat-sheet
- EOD milestone: M09 DoC complete; all 10 modules checked off PROGRESS.md

### Days 28–35 (Wed 17 Jul – Fri 25 Jul) — Buffer + polish
- Revisit weakest modules; deepen any DoC gaps
- Write up interview prep notes in each module README
- Full capstone demo run-through; timing; clean up any rough edges

### Days 36–45 (Mon 28 Jul – Fri 8 Aug) — Interview prep + QubitCore deep-dive
- Study QubitCore's published papers / patents on photonic interconnects
- Practice explaining every layer of the stack verbally
- Mock interviews; whiteboard pulse sequence design
- Final: `make smoke` passes everywhere from a fresh shell

### Days 46-49 (Mon 11 Aug – Thu 14 Aug) — Final run-through
- End-to-end capstone demo; document lessons learned
- Archive and push to private GitHub

---

*Schedule is a target, not a contract — adjust based on actual pace.*
