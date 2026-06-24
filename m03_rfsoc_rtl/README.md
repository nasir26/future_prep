# M03 — RFSoC RTL: Signal Generation & Experiment Control

**Author:** Nasir Ali, C-DAC Noida

## Goal

Build and verify the core RTL blocks of an RFSoC quantum-control stack:
a Direct Digital Synthesizer (DDS), a pulse envelope shaper, a timed
sequencer (mini tProc), and a photon counter — then tie them together in
a simulated Rabi oscillation experiment.

## Tool table

| Tool | Role |
|------|------|
| iverilog 12.0 | SystemVerilog simulation |
| cocotb 2.0.1 | Python test harness |
| numpy / scipy | FFT, curve fit |
| run_sim.py | cocotb_tools.runner wrapper |

## Exercise ladder

| # | File | Concept | Tests | Status |
|---|------|---------|-------|--------|
| ex01 | `rtl/dds_lut.sv` | Phase accumulator + LUT DDS + AXI4-Lite | 5 | ✅ |
| ex02 | `rtl/pulse_envelope.sv` | Envelope shaper: Gaussian, square, busy/done | 4 | ✅ |
| ex03 | `rtl/timed_sequencer.sv` | Mini tProc: WAIT/SET_FREQ/FIRE/READ_CTR/BRANCH | 5 | ✅ |
| ex04 | `rtl/photon_counter.sv` | PMT model, LFSR noise, Rabi sweep + fit | 4 | ✅ |

**Total: 18/18 PASS**

## Quick start

```bash
source ~/future_prep/scripts/activate_qprep.sh
cd ~/future_prep
make -C m03_rfsoc_rtl all
```

Or individually:
```bash
python m03_rfsoc_rtl/tests/run_sim.py dds
python m03_rfsoc_rtl/tests/run_sim.py envelope
python m03_rfsoc_rtl/tests/run_sim.py sequencer
python m03_rfsoc_rtl/tests/run_sim.py rabi
```

## Key concepts

### DDS (ex01)
- **Phase accumulator:** 32-bit register increments by `PINC` each cycle.
  Top 10 bits address a 1024-entry sine LUT.
- **Frequency tuning:** `PINC = Fo / Fclk × 2^32`
- **Coherent sampling:** for a clean FFT with no window, choose `PINC` so
  an integer number of cycles fits in the FFT window:
  `PINC = bin × 2^32 // N`
- **Spectral purity:** 10-bit LUT → ~62 dBc SFDR (6 dB/bit rule)
- **I/Q quadrature:** cosine = sine delayed by LUT_DEPTH/4 entries (+ π/2)

### Pulse envelope (ex02)
- Envelope BRAM (64 entries, 16-bit) resampled over `PERIOD` clock cycles.
- Multiplier: `pulse_i = (DDS_sine × env_amp) >> 15`
- AXI4-Lite address decode: control regs at 0x00–0x08; BRAM at 0x100–0x1FC.
  `addr[8]=1` selects BRAM; `addr[7:2]` is the entry index.
- `BUSY` bit clears and `pulse_done` strobes on the last pulse cycle.

### Timed sequencer (ex03)
- Fixed 64-bit instruction encoding: `[63:60]=opcode [59:28]=operand`.
- Program memory initialized to HALT (opcode 0xF) so falling off the end
  of written code automatically stops execution — no explicit HALT needed.
- Key design lesson: poll `seq_done` signal directly (not via AXI reads)
  when monitoring 1-cycle strobes — AXI read overhead (~3 cycles) misses
  single-cycle events.
- BRANCH checks `result_reg < THRESHOLD` for feedback-based loops.

### Photon counter / Rabi sweep (ex04)
- 16-bit Fibonacci LFSR (x^16+x^15+x^13+x^4+1, period 65535).
- `count = clip(MEAN + noise, 0, 255)` on each `capture_trigger`.
- Rabi physics model lives in Python (appropriate — Python computes
  `mean = DARK + (BRIGHT−DARK)×sin²(π×τ/τ_π)`, RTL adds Poisson noise).
- Fit `A×sin²(π×τ/T)+B` with scipy.optimize.curve_fit: R²=0.98+

## Definition of Command (DoC)

Pass all of the following **without references**:

1. Explain what `PINC = round(Fo/Fclk × 2^32)` means and why 32 bits
   gives ~0.023 Hz resolution at 100 MHz.
2. Draw the DDS pipeline: PINC → phase acc → LUT addr → sine reg → output.
3. Explain why coherent sampling eliminates the need for a window function.
4. Write the AXI4-Lite handshake sequence (AW+W channels, B response).
5. Explain why the BFM samples `tready` at `RisingEdge` (not `+1ps`):
   combinational RTL outputs must be read before delta cycles execute.
6. Write a WAIT/SET_FREQ/FIRE program for the timed sequencer from memory.
7. Explain the Fibonacci LFSR update rule and why the seed must be non-zero.
8. State the Rabi oscillation formula and explain what τ_π represents
   physically.
