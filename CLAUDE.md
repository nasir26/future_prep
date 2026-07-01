# CLAUDE.md — future_prep repo

**Owner:** Nasir Ali  
**Goal:** 10-module (M00–M09) one-month interview-prep repo for a quantum-computing hardware/software stack role.

---

## ALWAYS DO FIRST

1. Read `PROGRESS.md` — know which modules are done and which are active.
2. Read `SCHEDULE.md` — know what today's target is (daily hour breakdown, EOD milestones).
3. Read the active module's README (e.g., `m01_sv_sva/README.md`) if one exists.

Then act. Never skip these reads.

---

## Repo layout

```
future_prep/
├── CLAUDE.md          ← this file
├── PROGRESS.md        ← module completion tracker (update on EOD)
├── SCHEDULE.md        ← day-by-day plan
├── README.md          ← high-level overview
├── scripts/
│   ├── activate_qprep.sh   ← ONE-LINE env activation (always use this)
│   ├── eod_commit.sh
│   └── setup_vivado.sh
├── waves/             ← ALL VCD dumps go here (every module)
├── vendor/            ← cloned repos (QICK, ARTIQ) go here
├── m00_toolchain/     ← COMPLETE
├── m01_sv_sva/        ← COMPLETE
├── m02_cocotb/
├── m03_rfsoc_rtl/
├── m04_artiq/
├── m05_migen_amaranth/
├── m06_iontrap_emu/
├── m07_capstone/
├── m08_infra/
└── m09_uvm_vhdl/
```

---

## Environment

```bash
source ~/future_prep/scripts/activate_qprep.sh
```

This activates the `qprep` conda env (Python 3.11, iverilog 12.0, Verilator 5.048, GTKWave) and sources Vivado 2023.2 (xsim). Run this at the start of every session before any `make` target.

**Simulators in this repo:**
| Simulator | When to use |
|-----------|-------------|
| iverilog  | Verilog-2001/2005, cocotb (Module 02+) |
| xsim      | SystemVerilog, SVA assertions, UVM (Module 01, 09) |
| Verilator | Large designs, co-sim speed (Module 07) |

---

## Module conventions (EVERY module must follow these)

1. **Graded exercise ladder** — start from simplest concept, add one concept per file.  
2. **Heavily commented educational code** — comments explain the WHY, not the what. Every non-obvious design decision commented. Beginners must be able to learn from the source alone.  
3. **Makefile targets** — every module has a `Makefile` with at minimum: `make all`, `make clean`. Self-test benches print `PASS` / `FAIL` per test.  
4. **VCD dumps to `waves/`** — every simulation writes a `.vcd` (or `.vcd`-equivalent) to `~/future_prep/waves/<module_prefix>_<name>.vcd`.  
5. **Per-module README** — includes: Goal, tool table, exercise list, and a **Definition of Command** (DoC) checklist — the verbal/hands-on tests you must pass cold before marking the module complete.

---

## Module status quick-ref

(Kept in sync with PROGRESS.md, the source of truth — check there for
per-module test counts and lessons learned.)

| Module | Status |
|--------|--------|
| M00 Toolchain bootstrap | ✅ Complete (2026-06-10) |
| M01 SV + SVA | ✅ Complete (2026-06-24) |
| M02 cocotb | ✅ Complete (2026-06-24) |
| M03 RFSoC RTL | ✅ Complete (2026-06-24) |
| M04 ARTIQ kernels | ✅ Complete (2026-06-25) |
| M05 Migen/Amaranth | ✅ Complete (2026-06-25) |
| M06 iontrap_emu | ✅ Complete (2026-06-25) |
| M07 Capstone | ✅ Complete (2026-06-29) |
| M08 Infrastructure | ✅ Complete (2026-07-01) |
| M09 UVM + VHDL | ✅ Complete (2026-07-01) |

---

## Original module brief pattern

Each module follows this structure:
- **Goal** — one sentence, what capability you will have at the end.
- **Exercises** — numbered, increasing difficulty. Each is a self-contained `.sv`/`.py` file with a self-test bench or pytest.
- **Makefile** — `make all` runs all exercises; `make clean` removes build artifacts.
- **VCD output** — every RTL exercise dumps a VCD to `waves/`.
- **README** — tool table, exercise list, heavily annotated code walkthrough, DoC checklist.
- **Definition of Command** — 5–8 items you must demonstrate cold (no references) before marking done.
