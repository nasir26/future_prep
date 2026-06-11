// =============================================================================
// Ex01: D Flip-Flop — logic type, always_ff, synchronous reset
// =============================================================================
//
// CONCEPT: The 'logic' type replaces both 'wire' and 'reg' in SystemVerilog.
//   - In Verilog-2001 you had to choose 'reg' (driven by always) or 'wire'
//     (driven by assign / port). This was a *structural* choice, not semantic.
//   - In SV, 'logic' is a 4-state type (0, 1, X, Z). The compiler figures out
//     whether it's a flip-flop or a wire based on HOW you drive it.
//   - Exception: multi-driver nets (tri-state buses) still need 'wire'.
//
// CONCEPT: always_ff vs always @(posedge clk)
//   - 'always_ff' is a *semantic annotation*: "this block infers registers."
//   - The compiler ENFORCES that every variable assigned inside always_ff is
//     flip-flop-inferred. If you accidentally write combinational logic here,
//     you get a compile error — not a silent latch or mismatched sim/synth.
//   - Rule of thumb: always_ff → registers only, always_comb → comb only.
//
// =============================================================================

// Two flip-flop variants in one module so you can compare waveforms side-by-side.

module ex01_dff #(
    parameter int WIDTH = 8   // data path width; default 8 bits
) (
    input  logic             clk,
    input  logic             rst,   // synchronous active-high reset
    input  logic             en,    // clock enable
    input  logic [WIDTH-1:0] d,
    output logic [WIDTH-1:0] q_basic,   // plain DFF (no enable)
    output logic [WIDTH-1:0] q_en       // DFF with clock enable
);

    // -------------------------------------------------------------------------
    // Variant A: plain D flip-flop
    // -------------------------------------------------------------------------
    // Synchronous reset: reset takes effect on the rising edge, NOT asynchronously.
    // Why synchronous? Simpler timing analysis; reset path is just another data path.
    // Why asynchronous? Device powers up in known state even without a clock.
    // This course uses synchronous reset throughout for simplicity.
    always_ff @(posedge clk) begin
        if (rst) q_basic <= '0;   // '0 is a "fill with zeros" literal — width-agnostic
        else     q_basic <= d;
    end

    // -------------------------------------------------------------------------
    // Variant B: DFF with clock enable
    // -------------------------------------------------------------------------
    // Clock enable: hold the register value when en=0.
    // DO NOT gate the clock signal itself — that creates glitches in RTL.
    // Instead, mux the input: if enable, accept new data; else keep old data.
    always_ff @(posedge clk) begin
        if (rst)    q_en <= '0;
        else if (en) q_en <= d;
        // implicit else: q_en keeps its value (synthesises as enable on the FF)
    end

endmodule
