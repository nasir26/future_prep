// axis_fifo.sv — M02 ex02/ex03 DUT
// Parameterized AXI4-Stream FIFO.
//
// Protocol rules implemented here (relevant for the SVA you write in ex02):
//   1. tvalid must not deassert without a completed handshake (tready=1 same edge)
//   2. s_axis_tready deasserts one cycle after the FIFO reaches DEPTH entries
//   3. m_axis_tvalid deasserts one cycle after the FIFO is drained to 0 entries
//   4. Simultaneous push+pop (do_write & do_read) is legal and fill_level stays constant
//
// Constraints:
//   - DEPTH must be a power of two; pointer arithmetic relies on natural bit-width wrap
//   - rst_n is synchronous active-low (consistent with the rest of this repo)
//
// Author: Nasir Ali, C-DAC Noida

`timescale 1ns/1ps
module axis_fifo #(
    parameter DATA_W = 8,          // TDATA width in bits
    parameter DEPTH  = 16          // FIFO depth — MUST be a power of two
)(
    input  logic                        clk,
    input  logic                        rst_n,

    // Slave port (input side — producer writes here)
    input  logic                        s_axis_tvalid,
    output logic                        s_axis_tready,
    input  logic [DATA_W-1:0]           s_axis_tdata,
    input  logic                        s_axis_tlast,

    // Master port (output side — consumer reads here)
    output logic                        m_axis_tvalid,
    input  logic                        m_axis_tready,
    output logic [DATA_W-1:0]           m_axis_tdata,
    output logic                        m_axis_tlast,

    // Fill level: 0 = empty, DEPTH = full
    output logic [$clog2(DEPTH):0]      fill_level
);
    // --- Local parameters ---
    localparam PTR_W = $clog2(DEPTH);   // pointer width (e.g., 4 bits for DEPTH=16)

    // --- Storage: one extra bit for tlast flag packed alongside tdata ---
    // mem[i] = {tlast[0], tdata[DATA_W-1:0]}
    logic [DATA_W:0] mem [0:DEPTH-1];

    // --- Read/write pointers (PTR_W bits — natural overflow = wrap around) ---
    logic [PTR_W-1:0] wr_ptr, rd_ptr;

    // --- Status flags (derived combinationally from fill_level) ---
    logic full, empty;
    assign full  = (fill_level == DEPTH[$clog2(DEPTH):0]);
    assign empty = (fill_level == '0);

    // --- Handshake signals ---
    logic do_write, do_read;
    assign do_write = s_axis_tvalid & s_axis_tready;
    assign do_read  = m_axis_tvalid & m_axis_tready;

    // --- Back-pressure: ready when not full; valid when not empty ---
    assign s_axis_tready = ~full;
    assign m_axis_tvalid = ~empty;

    // --- Read data (registered address → combinational output) ---
    assign m_axis_tdata = mem[rd_ptr][DATA_W-1:0];
    assign m_axis_tlast = mem[rd_ptr][DATA_W];

    // --- Sequential: update pointers and fill_level ---
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            wr_ptr     <= '0;
            rd_ptr     <= '0;
            fill_level <= '0;
        end else begin
            // Write side
            if (do_write) begin
                mem[wr_ptr] <= {s_axis_tlast, s_axis_tdata};
                wr_ptr      <= wr_ptr + 1'b1;
            end
            // Read side (combinational outputs already mux rd_ptr)
            if (do_read)
                rd_ptr <= rd_ptr + 1'b1;
            // Fill level: only changes on push-without-pop or pop-without-push
            unique case ({do_write, do_read})
                2'b10:   fill_level <= fill_level + 1'b1;
                2'b01:   fill_level <= fill_level - 1'b1;
                default: ;   // 2'b00 and 2'b11 → level unchanged
            endcase
        end
    end

endmodule
