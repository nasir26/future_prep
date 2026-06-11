// =============================================================================
// Ex07: Parameterized Synchronous FIFO — Day 2 capstone
// =============================================================================
`timescale 1ns/1ps
//
// CONCEPT: Circular buffer with dual-pointer full/empty detection
//   Classic implementation: wr_ptr and rd_ptr are (DEPTH_LOG2+1)-bit counters.
//   The extra MSB is the "wrap bit" — it flips every full traversal.
//
//   Full/empty detection:
//     empty = (wr_ptr == rd_ptr)               — same value, same wrap parity
//     full  = (wr_ptr[MSB] != rd_ptr[MSB])     — same address, opposite parity
//              && (wr_ptr[MSB-1:0] == rd_ptr[MSB-1:0])
//
//   This avoids a separate counter register and removes the need for a
//   special-case around the pointer wrap point.
//
// CONCEPT: Synchronous read (registered output)
//   The read data register updates on the clock edge after a pop.
//   This means dout is valid one cycle after pop — factor into testbench.
//   A variant with asynchronous read (assign dout = mem[rd_addr]) is also
//   common but requires care in synthesis for large depths.
//
// CONCEPT: self-check $display in simulation
//   $display and $error do not affect synthesis — they disappear in the
//   netlist. Use them freely in RTL for simulation-time assertions.
//   Format: $display("time=%0t val=%0d", $time, signal);
//
// =============================================================================

module ex07_sync_fifo #(
    parameter int DATA_W    = 8,
    parameter int DEPTH_LOG2 = 3    // depth = 2^DEPTH_LOG2 (must be power of 2)
) (
    input  logic              clk,
    input  logic              rst,

    // Write port
    input  logic              wr_en,   // push request
    input  logic [DATA_W-1:0] wr_data,
    output logic              full,

    // Read port
    input  logic              rd_en,   // pop request
    output logic [DATA_W-1:0] rd_data,
    output logic              empty,

    // Optional: fill level (useful for almost-full/almost-empty thresholds)
    output logic [DEPTH_LOG2:0] fill_level
);

    localparam int DEPTH = 1 << DEPTH_LOG2;

    // ── Storage ───────────────────────────────────────────────────────────────
    logic [DATA_W-1:0] mem [0:DEPTH-1];

    // ── Pointers — one extra MSB is the wrap/parity bit ─────────────────────
    logic [DEPTH_LOG2:0] wr_ptr, rd_ptr;

    // ── Full / empty flags ────────────────────────────────────────────────────
    // empty: pointers are identical (same address, same parity)
    assign empty = (wr_ptr == rd_ptr);

    // full: same lower address, OPPOSITE parity bits
    assign full  = (wr_ptr[DEPTH_LOG2-1:0] == rd_ptr[DEPTH_LOG2-1:0])
                && (wr_ptr[DEPTH_LOG2]     != rd_ptr[DEPTH_LOG2]);

    // fill level: simply the difference; wraps naturally with (DEPTH_LOG2+1) bits
    assign fill_level = wr_ptr - rd_ptr;

    // ── Write path ────────────────────────────────────────────────────────────
    always_ff @(posedge clk) begin
        if (rst) begin
            wr_ptr <= '0;
        end else if (wr_en && !full) begin
            mem[wr_ptr[DEPTH_LOG2-1:0]] <= wr_data;
            wr_ptr <= wr_ptr + 1'b1;
        end else if (wr_en && full) begin
            // Overflow detected: flag it at simulation time (not synthesisable)
            // In a real system this would be a status register bit or an interrupt.
            $error("[ex07_sync_fifo] OVERFLOW: wr_en asserted when FIFO is full at time %0t", $time);
        end
    end

    // ── Read path (synchronous: data valid one cycle after rd_en) ─────────────
    always_ff @(posedge clk) begin
        if (rst) begin
            rd_ptr  <= '0;
            rd_data <= '0;
        end else if (rd_en && !empty) begin
            rd_data <= mem[rd_ptr[DEPTH_LOG2-1:0]];
            rd_ptr  <= rd_ptr + 1'b1;
        end else if (rd_en && empty) begin
            $error("[ex07_sync_fifo] UNDERFLOW: rd_en asserted when FIFO is empty at time %0t", $time);
        end
    end

endmodule
