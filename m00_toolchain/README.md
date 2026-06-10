# Module 00 — Toolchain Bootstrap

**Status:** Complete  
**Goal:** Every tool in the chain works, the waveform loop is verified, you understand WHY each tool exists.

---

## What you installed

| Tool | Version | Purpose |
|------|---------|---------|
| Miniforge3 | latest | conda package manager (user-local, no sudo) |
| Python | 3.11.15 | runtime for all Python tools |
| **iverilog** | 12.0 | Icarus Verilog — open-source Verilog sim; **cocotb's preferred simulator** |
| **verilator** | 5.048 | Transpiles Verilog → C++; fastest open-source sim for big designs |
| **gtkwave** | 3.3.x | Classic waveform viewer (headless: use VS Code Surfer) |
| xsim | 2023.2 | Xilinx simulator (bundled in Vivado); needed for SVA assertions + UVM |
| qutip | 5.3.0 | QuTiP — quantum physics simulation (Module 06) |
| cocotb | 2.0.1 | Python-based RTL testbench framework (Module 02) |
| amaranth | 0.5.8 | Amaranth HDL — Python-based hardware description (Module 05) |
| migen | 0.9.2 | Migen HDL — ARTIQ's gateware language (Module 05) |
| qiskit | 2.4.1 | IBM Qiskit — used for OpenQASM 3 parsing (Module 07) |
| openqasm3 | 1.0.1 | OpenQASM 3 AST parser |
| zmq | 27.1.0 | ZeroMQ — transport for iontrap_emu server (Module 06) |
| grpc | 1.81.1 | gRPC — alternative transport |

---

## Why iverilog AND xsim AND Verilator?

**iverilog:** The go-to for open-source simulation. cocotb's xsim support is rudimentary
(no native Python callbacks); iverilog (and Verilator) are cocotb's first-class targets.
Fast iteration, no license needed.

**xsim:** Required for SystemVerilog Assertions (SVA) in Module 01 — Icarus doesn't
support SVA. Also runs UVM 1.2 natively in Module 09. Essential for the Vivado ecosystem.

**Verilator:** Compiles Verilog to C++, giving 10-100× speedup vs event-driven simulators
for large RTL. Module 07's co-simulation uses Verilator for performance.

---

## One-line environment activation

```bash
source ~/future_prep/scripts/activate_qprep.sh
```

This sources Miniforge's conda init, activates `qprep`, and adds Vivado 2023.2 to PATH.
Add it to your shell session whenever you start work on this repo.

---

## Waveform viewing — VS Code Surfer (primary, headless)

**Step 1:** Install the extension  
Open VS Code → Extensions (`Ctrl+Shift+X`) → search **"Surfer"** → Install  
(Publisher: `surfer-project`; alternatively search "WaveTrace" as a backup)

**Step 2:** Open a waveform  
- In the VS Code Explorer sidebar, right-click any `.vcd` file → **"Open With..."** → **Surfer**
- Or: `Ctrl+Shift+P` → `Surfer: Open VCD file` → navigate to `~/future_prep/waves/`

**Step 3:** Add signals  
In Surfer's left panel, expand the module hierarchy → click signal names to add them
to the waveform view.

**The three smoke-test VCDs:**
```
~/future_prep/waves/counter_icarus.vcd     ← Icarus run
~/future_prep/waves/counter_xsim.vcd       ← xsim run
~/future_prep/waves/counter_verilator.vcd  ← Verilator run
```

All three contain the same counter DUT — compare them to understand each simulator's
VCD dialect (they differ slightly in header format but show identical waveforms).

---

## GTKWave fallback (when you have X11 display)

```bash
# Via X-forwarding — add -X flag when SSH-ing in:
ssh -X abhishek@aiqtfpga

# Then on the server:
source ~/future_prep/scripts/activate_qprep.sh
gtkwave ~/future_prep/waves/counter_icarus.vcd
```

GTKWave is installed in the `qprep` env. The `-X` flag tunnels the X11 window back
to your local machine. Works from Linux/Mac desktops; on Windows use MobaXterm or
WSL2 with VcXsrv.

---

## Smoke test

```bash
cd ~/future_prep/m00_toolchain
source ~/future_prep/scripts/activate_qprep.sh
make smoke
```

Expected output: 7 PASS lines per simulator (21 total), 3 VCD files in `../waves/`.

---

## Definition of Command — pass before marking M00 complete

1. **[ ]** Run `source ~/future_prep/scripts/activate_qprep.sh` and show `xsim --version` + `iverilog -V` output
2. **[ ]** Run `python -c "import qutip, cocotb, amaranth; print('ok')"` inside the activated env
3. **[ ]** Run `cd ~/future_prep/m00_toolchain && make smoke` — all tests pass, 3 VCDs appear
4. **[ ]** Open `~/future_prep/waves/counter_icarus.vcd` in VS Code Surfer; zoom to show `clk`, `count`, `wrap` signals with the wrap pulse visible
5. **[ ]** Explain verbally: why does cocotb prefer iverilog over xsim? (answer: xsim has no native VPI callback support in cocotb; iverilog uses the standard Verilog PLI/VPI interface)
6. **[ ]** Explain verbally: what is the difference between `$dumpfile`/`$dumpvars` (Verilog standard) and xsim's `.wdb` format? (answer: VCD is a portable text format; `.wdb` is Xilinx-proprietary binary — we use VCD for portability with Surfer)

---

## What you should now understand

The full simulation–visualization loop is proven: write RTL → compile in any of three
simulators → get a VCD → open it in VS Code without ever needing a display. You know
WHY each simulator exists in the stack (iverilog for cocotb, xsim for SVA/UVM,
Verilator for speed) and you have a single activation script that sets up the complete
environment in one command.
