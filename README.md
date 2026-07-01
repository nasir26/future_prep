# QCore Prep — One-Month Ion-Trap QC Stack

**Role:** Software Engineer, Quantum Systems @ QubitCore (OIST Okinawa)  
**Start date:** ~15 August 2026  
**Prep window:** 10 June – 14 August 2026 (weekdays only)

## What this repo is

A fully simulated/emulated quantum computing software stack — no real ion trap,
no RFSoC, no pulse hardware required. Everything runs on CPU/RTL simulation.

## Toolchain

| Tool | Version | Install |
|------|---------|---------|
| Vivado/xsim | 2023.2 | `/tools/Xilinx/Vivado/2023.2/` |
| Miniforge3/mamba | see `conda list` | `~/miniforge3` |
| conda env | `qprep` (Python 3.11) | `~/miniforge3/envs/qprep` |
| Icarus Verilog | conda-forge | `iverilog` |
| Verilator | conda-forge | `verilator` |
| GTKWave | conda-forge | `gtkwave` (headless: VCD → VS Code Surfer) |

Source Vivado for any session: `source ~/future_prep/scripts/setup_vivado.sh`

## Modules — Progress Checklist

- [x] **M00** Toolchain bootstrap — smoke test counter in iverilog + xsim + Verilator, VCD → Surfer
- [x] **M01** SystemVerilog + SVA — AXI4-Stream FIFO + AXI4-Lite regfile with SVA assertions
- [x] **M02** cocotb verification — Python testbenches + coverage against M01 blocks + RTL engine
- [x] **M03** RFSoC pulse gateware emulation — DDS, envelope engine, timed sequencer, Rabi in RTL
- [x] **M04** ARTIQ kernel mastery — full kernel ladder, dummy/sim backend, QuTiP-backed scans
- [x] **M05** Migen/Amaranth literacy — DDS in Amaranth, elaborate → sim, read ARTIQ gateware
- [x] **M06** Ion-trap physics emulator (QuTiP) — `iontrap_emu/` asyncio server
- [x] **M07** CAPSTONE — QASM3 → compiler → sequencer → physics → fitted results
- [x] **M08** Infrastructure — Docker, GitHub Actions CI, pre-commit, green from fresh clone
- [x] **M09** UVM + VHDL literacy — toy UVM TB, mixed-language xsim

## Quick-start

```bash
# activate environment
source ~/miniforge3/etc/profile.d/conda.sh
conda activate qprep

# source Vivado
source ~/future_prep/scripts/setup_vivado.sh

# run any module's smoke test
cd ~/future_prep/m00_toolchain
make smoke
```

## Repository layout

```
future_prep/
├── m00_toolchain/       # Module 00: toolchain bootstrap
├── m01_sv_sva/          # Module 01: SystemVerilog + SVA
├── m02_cocotb/          # Module 02: cocotb verification
├── m03_rfsoc_rtl/       # Module 03: RFSoC pulse gateware (RTL)
├── m04_artiq/           # Module 04: ARTIQ kernel ladder
├── m05_migen_amaranth/  # Module 05: Migen/Amaranth
├── m06_iontrap_emu/     # Module 06: QuTiP physics emulator
├── m07_capstone/        # Module 07: end-to-end control stack
├── m08_infra/           # Module 08: Docker, CI, pre-commit
├── m09_uvm_vhdl/        # Module 09: UVM + VHDL literacy
├── scripts/             # setup_vivado.sh, etc.
├── vendor/              # git-cloned reference repos (QICK, ARTIQ)
├── waves/               # VCD/FST waveform dumps (not committed)
├── SCHEDULE.md          # 4-week daily plan
├── PROGRESS.md          # live progress tracker
└── README.md
```

---

## Citation

If you use this work in your research, please cite:

```bibtex
@misc{nasirali_future_prep,
  author    = {Nasir Ali},
  title     = {future prep},
  year      = {2026},
  publisher = {GitHub},
  url       = {https://github.com/nasir26/future_prep},
  note      = {Centre for Development of Advanced Computing (C-DAC), Noida, India}
}
```

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.\
© 2026 Nasir Ali, C-DAC Noida. All rights reserved.
