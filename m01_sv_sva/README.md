# Module 01 — SystemVerilog + SVA

**Status:** 🔄 Active (Days 2–4, 11–13 Jun 2026)  
**Goal:** Write idiomatic SystemVerilog from scratch — types, FSMs, interfaces, packages, parameterized modules — then layer on SVA assertions for protocol correctness.

---

## Schedule

| Day | Date | Focus | EOD milestone |
|-----|------|-------|---------------|
| Day 2 | Tue 11 Jun | SV basics ladder (ex01–ex07) | All ladder exercises passing self-test benches |
| Day 3 | Wed 12 Jun | AXI4-Stream FIFO + SVA | FIFO passes all SVA assertions in xsim |
| Day 4 | Thu 13 Jun | AXI4-Lite regfile + gate_fifo port | M01 DoC checklist complete |

---

## Tools

| Tool | Why used here |
|------|---------------|
| xsim (Vivado 2023.2) | Primary simulator — full SV + SVA support |
| iverilog 12.0 | Used for ex01–ex03 (basic SV, no interfaces/packages) |
| VS Code Surfer | VCD viewer — all dumps go to `../waves/` |

---

## Exercise ladder (Day 2)

| File | Concept introduced |
|------|--------------------|
| `rtl/ex01_dff.sv` | `logic` type, `always_ff`, synchronous reset |
| `rtl/ex02_shift_reg.sv` | Parameterized shift register, `$clog2` |
| `rtl/ex03_typedef_enum.sv` | `typedef`, `enum`, packed `struct` |
| `rtl/ex04_fsm.sv` | Two-always FSM (traffic light) using enum states |
| `rtl/ex05_interface.sv` | `interface`, `modport`, clean handshake wiring |
| `rtl/ex06_pkg.sv` + `rtl/ex06_top.sv` | `package`, `import`, shared typedefs across modules |
| `rtl/ex07_sync_fifo.sv` | Parameterized synchronous FIFO (circular buffer) |

## Day 3 files (AXI4-Stream FIFO + SVA)

| File | Concept |
|------|---------|
| `rtl/axi_stream_fifo.sv` | AXI4-Stream FIFO — VALID/READY handshake |
| `rtl/sva_fifo_props.sv` | SVA properties: no data loss, no overflow, handshake rules |
| `tb/tb_axi_stream_fifo.sv` | Directed + random testbench |

## Day 4 files (AXI4-Lite regfile)

| File | Concept |
|------|---------|
| `rtl/axi_lite_regfile.sv` | AXI4-Lite slave — 4 read/write registers |
| `rtl/gate_fifo_sv.sv` | gate_fifo.v ported to idiomatic SV + SVA |
| `tb/tb_axi_lite_regfile.sv` | Register read/write testbench |

---

## Makefile targets

```bash
cd ~/future_prep/m01_sv_sva
source ~/future_prep/scripts/activate_qprep.sh

make all           # run all exercises (icarus + xsim where appropriate)
make ex01          # ex01_dff only
make ex02          # ex02_shift_reg only
# ... (ex01 through ex07)
make axi_stream    # AXI4-Stream FIFO sim (xsim, with SVA)
make axi_lite      # AXI4-Lite regfile sim (xsim)
make clean         # remove build artifacts
```

---

## Key SV concepts — cheat-sheet

### logic vs wire vs reg
```systemverilog
// SV rule: use 'logic' everywhere. It unifies wire + reg.
// The compiler infers driving rules. Never use 'reg' in new SV code.
logic [7:0] count;      // can be driven by always or assign
wire        clk_buf;    // use wire only for multi-driver nets (tri-state, clock buffers)
```

### always_ff / always_comb / always_latch
```systemverilog
// always_ff: ONLY flip-flops. Compiler error if not edge-triggered.
always_ff @(posedge clk) begin
    if (rst) q <= '0;
    else     q <= d;
end

// always_comb: ONLY combinational. Compiler infers sensitivity list.
// Never write always @(*) in new SV code.
always_comb begin
    y = a & b;
end
```

### Two-always FSM style
```systemverilog
// State register in always_ff — clocked, clean reset
always_ff @(posedge clk) begin
    if (rst) state <= IDLE;
    else     state <= next_state;
end

// Next-state + output in always_comb — pure combinational
always_comb begin
    next_state = state;    // default: stay
    out = '0;              // default output
    case (state)
        IDLE: if (start) next_state = WORK;
        WORK: begin out = 1; next_state = DONE; end
        DONE: next_state = IDLE;
    endcase
end
```

### Typedef + enum
```systemverilog
// Enum: compiler enforces legal values, name appears in waveforms
typedef enum logic [1:0] {
    RED    = 2'b00,
    GREEN  = 2'b01,
    YELLOW = 2'b10
} light_t;

light_t state, next_state;
```

### Packed struct
```systemverilog
// Packed struct: single bit-vector, can be sliced
typedef struct packed {
    logic        valid;
    logic [7:0]  addr;
    logic [31:0] data;
} axi_beat_t;           // total width = 41 bits

axi_beat_t beat;
assign beat.valid = 1'b1;
assign addr_bus = beat.addr;   // slice out a field
```

### Interface + modport
```systemverilog
interface handshake_if;
    logic        valid;
    logic        ready;
    logic [7:0]  data;

    // modport constrains who can drive what
    modport src (output valid, data, input ready);
    modport dst (input  valid, data, output ready);
endinterface

module producer (handshake_if.src bus, input logic clk);
module consumer (handshake_if.dst bus, input logic clk);
```

### Package
```systemverilog
package my_pkg;
    localparam int DATA_W = 32;
    typedef logic [DATA_W-1:0] data_t;
    typedef enum logic { IDLE, BUSY } state_t;
endpackage

module my_mod
    import my_pkg::*;   // import all; or name specific items
(input my_pkg::data_t d, ...);
```

---

## Definition of Command — pass before marking M01 complete

1. **[ ]** Without references, write a two-always Moore FSM with 3 states using enum; compile and sim in xsim.
2. **[ ]** Without references, write an AXI4-Stream FIFO (VALID/READY, parametric depth/width) in SV.
3. **[ ]** Explain: why use `always_ff` instead of `always @(posedge clk)`?  
   *(answer: `always_ff` is a semantic tag — compiler rejects non-FF behavior inside it, catching latch/comb bugs at compile time)*
4. **[ ]** Explain: what does `modport` do and why is it useful?  
   *(answer: constrains port directions per module role; misconnections become compile errors, not sim mismatches)*
5. **[ ]** Explain: difference between `packed struct` and `unpacked struct`?  
   *(answer: packed = contiguous bit-vector, can be sliced and used as a port; unpacked = array-of-elements, cannot be packed into a single wire)*
6. **[ ]** Run `make axi_stream` and explain each SVA property shown in the waveform.
7. **[ ]** Explain: what is the AXI4-Stream handshake rule that SVA enforces?  
   *(answer: once VALID is asserted, it must not be deasserted until READY is seen — data must be held stable)*
8. **[ ]** Write a package with a parameterized FIFO typedef; use it in two separate modules; compile clean.
