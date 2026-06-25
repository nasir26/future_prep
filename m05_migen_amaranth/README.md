# M05 — Migen & Amaranth Python HDLs

**Author:** Nasir Ali, C-DAC Noida  
**Goal:** Read and write RTL gateware in Migen and Amaranth — the two Python HDLs used in ARTIQ.

---

## Why Migen / Amaranth?

ARTIQ's existing gateware (RTIO core, DDS drive, ADC/DAC bridges) is written in
**Migen**.  New ARTIQ gateware (e.g., Phaser support) is being rewritten in
**Amaranth** (formerly nMigen), Migen's successor.  A candidate must be able to:

- read Migen `Module` / `FSM` / `If` / `Array` code in `artiq/gateware/`
- extend or patch it in Migen syntax
- write new designs from scratch in Amaranth, export to Verilog, and wire them
  into an ARTIQ bitstream

---

## Tool table

| Tool | Version | Purpose |
|------|---------|---------|
| Migen | 0.9.2 | Legacy ARTIQ gateware (read + patch) |
| Amaranth | 0.5.8 | New ARTIQ gateware (write + export) |
| amaranth-yosys | — | Verilog export via Yosys/WASM |
| pytest | 9.x | White-box RTL unit tests |

---

## Exercise ladder

| File | Framework | Concept |
|------|-----------|---------|
| `rtl/ex01_migen_basics.py` | Migen | Signal, sync, comb, If/Elif, FSM |
| `rtl/ex02_amaranth_basics.py` | Amaranth | Elaboratable, m.d.sync, with m.If, with m.FSM, Verilog export |
| `rtl/ex03_migen_fifo.py` | Migen | Array, valid/ready handshake, power-of-2 FIFO |
| `rtl/ex04_amaranth_fifo.py` | Amaranth | Same FIFO in Amaranth; testbench timing model difference |
| `rtl/ex05_amaranth_dds.py` | Amaranth | Phase accumulator, Array sine LUT, spectral purity, Verilog export |

---

## Key API comparison

```
Migen                           Amaranth 0.5
────────────────────────────────────────────────────────────────────────
class Foo(Module)               class Foo(Elaboratable): def elaborate()
self.sync += sig.eq(expr)       m.d.sync += sig.eq(expr)
self.comb += sig.eq(expr)       m.d.comb += sig.eq(expr)
If(c, a).Elif(d, b).Else(e)    with m.If(c): / with m.Elif(d): / with m.Else:
self.submodules.fsm = FSM()     with m.FSM(): / with m.State("X"):
NextState("S")                  m.next = "S"
NextValue(sig, v)               m.d.sync += sig.eq(v)
Signal(max=N)                   Signal(range(N))
Array([...])                    Array([...])           ← same

Simulation
──────────────────────────────────────────────────────────────────────
Migen: generator (yield, (yield sig), yield sig.eq(v))
Amaranth: async (await ctx.tick(), ctx.get(sig), ctx.set(sig, v))

Critical timing difference
───────────────────────────
Migen `(yield sig)` reads at the RISING EDGE (pre-sync register update).
Amaranth `ctx.get(sig)` reads POST-EDGE (after sync registers update).
For combinational outputs (e.g., m_data = mem[rd_ptr]):
  Migen: read at edge → sees rd_ptr BEFORE it increments → correct element
  Amaranth: read after edge → sees rd_ptr AFTER it increments → next element
Fix: in Amaranth testbenches, sample combinational outputs BEFORE ctx.tick()
     that causes the side effect (pop, pointer advance, etc.).
```

---

## DDS design (ex05)

```
PINC → ┌─────────────┐  ACC[N-1:N-L] ┌───────┐    sine
       │ Accumulator  ├──────────────►│  LUT  ├───────►
       │  (N=16 bits) │               │ 2^L×8b│
       └──────────────┘               └───────┘
         L = 8 LUT address bits; N = 16 acc bits

Frequency resolution: f_clk / 2^16 ≈ 1.5 kHz at 100 MHz
PINC for 10 MHz: round(0.1 × 65536) = 6554
```

---

## Running tests

```bash
conda activate qprep
cd ~/future_prep/m05_migen_amaranth

make           # runs all tests + VCD dumps
make migen     # Migen tests only  (13 tests)
make amaranth  # Amaranth tests    (19 tests)
make verilog   # Verilog export    (counter_gen.v, fifo_gen.v, dds_gen.v)
```

Expected: **32 PASS** across both suites.

---

## Definition of Command (DoC)

Pass all of the following **without references** before marking M05 complete:

1. **Migen Counter** — write a Migen `Counter(Module)` with `en`/`rst`/`count` ports
   using `self.sync +=` and `If().Elif()` from memory.

2. **Amaranth Counter** — rewrite the same design as `Counter(Elaboratable)` with
   `with m.If(): m.d.sync += ...` syntax; explain why you can't write `if self.en:`
   inside `elaborate()` (Python `if` evaluates at elaboration time, not simulation time).

3. **Migen FSM** — write a two-state FSM using `self.submodules.fsm = FSM()` +
   `fsm.act("STATE", NextState(...))`. Explain `NextState` vs `NextValue`.

4. **Amaranth FSM** — write the same FSM with `with m.FSM(): / with m.State("X"): /
   m.next = "Y"`. Explain why Amaranth uses `m.next` not a signal assignment.

5. **Valid/ready handshake** — explain the rule: a beat transfers when BOTH `valid`
   AND `ready` are high on the SAME rising edge. Relate to `do_write = s_valid & s_ready`.

6. **Array vs Memory** — `Array` synthesises as a MUX tree; `Memory` uses BRAM.
   For a 16-entry×8-bit FIFO, which would you use in production? (Answer: `Memory`
   for synthesis; `Array` for simulation clarity.)

7. **Amaranth Verilog export** — call `from amaranth.back.verilog import convert;
   convert(dut, ports=[...])` and say which Python package provides Yosys.
   (Answer: `amaranth-yosys`.)

8. **Testbench timing difference** — explain why `ctx.get(dut.m_data)` in an
   Amaranth testbench gives the NEXT element after a pop, while Migen's
   `(yield dut.m_data)` gives the CURRENT element. State the fix.
   (Answer: Amaranth reads post-edge; Migen reads at-edge. Fix: sample before tick.)

9. **DDS phase accumulator** — given `f_clk = 100 MHz`, `f_out = 10 MHz`,
   `acc_bits = 16`, compute PINC.
   (Answer: `round(10/100 × 65536) = 6554`.)

10. **SFDR** — why does using only the top `L` bits of a 16-bit accumulator for
    the LUT index improve spectral purity? (Answer: the accumulator's sub-LUT-LSB
    bits cause phase truncation spurs, but these are at known frequencies and can
    be dithered or filtered; the main benefit is phase resolution >> LUT depth.)
