// =============================================================================
// Day 3: AXI4-Stream FIFO — VALID/READY handshake, parametric depth/width
// =============================================================================
`timescale 1ns/1ps
//
// WHY THIS EXISTS
//   This is the M01 "write it from scratch" deliverable. M02 re-uses an
//   AXI-Stream FIFO as a cocotb DUT; here the point is to (a) write the design
//   idiomatically in SystemVerilog and (b) attach SVA properties that *prove*
//   the protocol is obeyed (see sva_fifo_props.sv, bound to this module).
//
// CONCEPT: AXI4-Stream handshake (the one rule that matters)
//   A beat transfers on a rising clock edge iff (TVALID && TREADY) are BOTH
//   high. Two obligations follow:
//     - Source obligation: once TVALID is asserted it must stay asserted, and
//       TDATA/TLAST must stay stable, until the sink accepts (TREADY seen).
//       i.e. you may NOT "retract" an offered beat.
//     - Sink obligation: none on timing — TREADY may assert/deassert freely.
//   The FIFO is a SINK on its slave port and a SOURCE on its master port, so it
//   must honour the source obligation on m_axis_*. The producer driving the
//   slave port must honour it on s_axis_* — the SVA checks both sides.
//
// CONCEPT: storage + pointers
//   Circular buffer of DEPTH entries. Each entry packs {tlast, tdata} so the
//   end-of-packet marker travels with its byte. A separate fill_level counter
//   gives O(1) full/empty detection (simpler to assert on than the wrap-bit
//   trick used in ex07_sync_fifo.sv — both are valid; this one reads cleaner).
//
// NOTE ON RESET POLARITY
//   This module uses active-high SYNCHRONOUS reset (rst), matching ex01–ex07.
//   (M02's axis_fifo.sv uses active-low rst_n — be aware of the difference when
//    wiring the two together.)
//
// First-word-fall-through (FWFT): m_axis_tdata is driven combinationally from
//   the read pointer, so valid data is present on the same cycle tvalid rises —
//   no extra read-latency bubble. This is the common AXI-Stream FIFO style.
// =============================================================================

module axi_stream_fifo #(
    parameter int DATA_W = 8,      // TDATA width in bits
    parameter int DEPTH  = 8       // entries — MUST be a power of two
) (
    input  logic                   clk,
    input  logic                   rst,            // active-high, synchronous

    // ── Slave port (FIFO is the SINK; producer writes here) ──────────────────
    input  logic                   s_axis_tvalid,
    output logic                   s_axis_tready,
    input  logic [DATA_W-1:0]      s_axis_tdata,
    input  logic                   s_axis_tlast,

    // ── Master port (FIFO is the SOURCE; consumer reads here) ────────────────
    output logic                   m_axis_tvalid,
    input  logic                   m_axis_tready,
    output logic [DATA_W-1:0]      m_axis_tdata,
    output logic                   m_axis_tlast,

    // ── Occupancy: 0 = empty … DEPTH = full ──────────────────────────────────
    output logic [$clog2(DEPTH):0] fill_level
);

    localparam int PTR_W = $clog2(DEPTH);   // address width (e.g. 3 for DEPTH=8)

    // ── Storage: one extra bit packs tlast alongside tdata ───────────────────
    // mem[i] = { tlast, tdata[DATA_W-1:0] }
    logic [DATA_W:0]   mem [0:DEPTH-1];
    logic [PTR_W-1:0]  wr_ptr, rd_ptr;       // natural wrap at power-of-two depth

    // ── Status flags derived from occupancy ──────────────────────────────────
    logic full, empty;
    assign full  = (fill_level == DEPTH[$clog2(DEPTH):0]);
    assign empty = (fill_level == '0);

    // ── Handshake outputs ────────────────────────────────────────────────────
    // ready when there is room; valid when there is data (FWFT).
    assign s_axis_tready = ~full;
    assign m_axis_tvalid = ~empty;

    // ── Master-side data is combinational from the read pointer ──────────────
    assign m_axis_tdata = mem[rd_ptr][DATA_W-1:0];
    assign m_axis_tlast = mem[rd_ptr][DATA_W];

    // ── Completed transfers this cycle ───────────────────────────────────────
    logic do_write, do_read;
    assign do_write = s_axis_tvalid & s_axis_tready;   // accepted push
    assign do_read  = m_axis_tvalid & m_axis_tready;   // accepted pop

    // ── Sequential state ─────────────────────────────────────────────────────
    always_ff @(posedge clk) begin
        if (rst) begin
            wr_ptr     <= '0;
            rd_ptr     <= '0;
            fill_level <= '0;
        end else begin
            if (do_write) begin
                mem[wr_ptr] <= {s_axis_tlast, s_axis_tdata};
                wr_ptr      <= wr_ptr + 1'b1;
            end
            if (do_read) begin
                rd_ptr <= rd_ptr + 1'b1;
            end
            // Occupancy only moves on a push-without-pop or pop-without-push.
            // Simultaneous push+pop (2'b11) and idle (2'b00) leave it unchanged.
            unique case ({do_write, do_read})
                2'b10:   fill_level <= fill_level + 1'b1;
                2'b01:   fill_level <= fill_level - 1'b1;
                default: /* unchanged */ ;
            endcase
        end
    end

endmodule
