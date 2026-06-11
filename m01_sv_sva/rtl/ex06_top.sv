// =============================================================================
// Ex06: Package consumer — demonstrates import and use of fifo_pkg types
// =============================================================================
`timescale 1ns/1ps

// Import the package — 'import' must appear before the module header.
// Use '::*' (wildcard) here for brevity; production code often uses explicit imports.

import fifo_pkg::*;

module ex06_top #(
    parameter int DATA_W    = 8,
    parameter int DEPTH_LOG2 = 3    // depth = 2^3 = 8 entries
) (
    input  logic              clk,
    input  logic              rst,
    // simple push/pop interface (no handshake for clarity in this exercise)
    input  logic              push,
    input  logic              pop,
    input  logic [DATA_W-1:0] din,
    output logic [DATA_W-1:0] dout,
    // status bundle — using the package type
    output fifo_status_t      status,
    // demonstrate the package function
    input  logic [2:0]        idx_in,
    output logic [7:0]        one_hot_out
);

    // ── Internal storage ─────────────────────────────────────────────────────
    localparam int DEPTH = 1 << DEPTH_LOG2;   // 2^DEPTH_LOG2

    logic [DATA_W-1:0]  mem [0:DEPTH-1];
    logic [DEPTH_LOG2:0] wr_ptr, rd_ptr;   // one extra bit for full/empty distinguish

    // ── Push / pop logic ─────────────────────────────────────────────────────
    always_ff @(posedge clk) begin
        if (rst) begin
            wr_ptr <= '0;
            rd_ptr <= '0;
            dout   <= '0;
        end else begin
            if (push && !status.full) begin
                mem[wr_ptr[DEPTH_LOG2-1:0]] <= din;
                wr_ptr <= wr_ptr + 1'b1;
            end
            if (pop && !status.empty) begin
                // synchronous read: capture current head, then advance pointer
                dout   <= mem[rd_ptr[DEPTH_LOG2-1:0]];
                rd_ptr <= rd_ptr + 1'b1;
            end
        end
    end

    // ── Status flags using the package struct ────────────────────────────────
    logic [DEPTH_LOG2:0] count;
    assign count = wr_ptr - rd_ptr;   // wraps correctly with the extra MSB trick

    always_comb begin
        status.empty        = (count == 0);
        status.full         = (count == DEPTH[DEPTH_LOG2:0]);
        status.almost_empty = (count == 1);
        status.almost_full  = (count == DEPTH[DEPTH_LOG2:0] - 1);
    end

    // ── Package function usage ───────────────────────────────────────────────
    assign one_hot_out = one_hot8(idx_in);

endmodule
