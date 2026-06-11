// =============================================================================
// Ex02: Parameterized Shift Register
// =============================================================================
//
// CONCEPT: parameters + localparam
//   - 'parameter' is a module-level constant overridable at instantiation:
//       ex02_shift_reg #(.DEPTH(16), .WIDTH(4)) u_sr (...);
//   - 'localparam' is derived and NOT overridable — use for internal constants.
//
// CONCEPT: $clog2
//   - Built-in function: ceiling log2.
//   - $clog2(8)=3, $clog2(9)=4, $clog2(1)=0.
//   - Canonical idiom to size a pointer/counter for a buffer of depth N:
//       logic [$clog2(DEPTH)-1:0] ptr;
//   - Warning: $clog2(1) = 0, giving a 0-width signal. Guard with max(1,…)
//     if DEPTH=1 is a legal instantiation.
//
// CONCEPT: generate for loop
//   - Unrolls at elaboration time — generates N instances of identical logic.
//   - genvar is a compile-time integer, not a signal.
//
// =============================================================================

module ex02_shift_reg #(
    parameter int DEPTH = 8,   // number of pipeline stages
    parameter int WIDTH = 8    // data width per stage
) (
    input  logic             clk,
    input  logic             rst,
    input  logic             en,          // shift enable
    input  logic [WIDTH-1:0] d_in,
    output logic [WIDTH-1:0] d_out,       // data from the last stage
    output logic [DEPTH-1:0] tap          // each bit: serial content of stage i
);
    // DEPTH pipeline stages
    logic [WIDTH-1:0] stage [0:DEPTH-1];  // unpacked array of WIDTH-bit logic

    // Stage 0: receive new data
    always_ff @(posedge clk) begin
        if (rst)    stage[0] <= '0;
        else if (en) stage[0] <= d_in;
    end

    // Stages 1..DEPTH-1: shift along the chain
    genvar i;
    generate
        for (i = 1; i < DEPTH; i++) begin : g_stages
            always_ff @(posedge clk) begin
                if (rst)    stage[i] <= '0;
                else if (en) stage[i] <= stage[i-1];
            end
        end
    endgenerate

    // Outputs
    assign d_out = stage[DEPTH-1];

    // Tap: expose bit[0] of each stage as a 1-bit serial view
    // Useful for visualising the shift in a waveform.
    generate
        for (i = 0; i < DEPTH; i++) begin : g_taps
            assign tap[i] = stage[i][0];
        end
    endgenerate

endmodule
