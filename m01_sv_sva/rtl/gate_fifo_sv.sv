// =============================================================================
// Day 4: gate_fifo_sv — AXI4-Stream FIFO with a control-plane write gate
// =============================================================================
`timescale 1ns/1ps
//
// WHAT "PORTED" MEANS HERE
//   The Day 4 brief is to port an existing gate_fifo.v to idiomatic SV.
//   No such file exists in this environment (no ~/fpga_rtl checkout to pull
//   from) — so this is an original implementation of what that name
//   describes: a FIFO whose write side is gated by a control register
//   rather than being open all the time. In this repo's world, that's
//   exactly the shape of a real block: a pulse-sequencer or DDS write
//   port that should only accept new words while an AXI-Lite "enable" bit
//   says the datapath is armed (see axi_lite_regfile.sv's REG0 bit 0,
//   wired to `gate_en` in tb_axi_lite_regfile.sv).
//
// CONCEPT: gating is a THIRD condition on tready, not a separate FSM
//   Everything here is identical to Day 3's axi_stream_fifo.sv (circular
//   buffer, FWFT read, occupancy counter) with exactly one change:
//   `s_axis_tready = ~full && gate_en`. That's the whole feature. Bolting
//   a control-plane enable onto a datapath FIFO doesn't need new states —
//   it needs one more AND term on the existing "can I accept a write"
//   signal. Reaching for a bigger change than that here would be solving
//   a problem this design doesn't have.
//
module gate_fifo_sv #(
    parameter int DATA_W = 8,
    parameter int DEPTH  = 8       // entries — MUST be a power of two
) (
    input  logic                   clk,
    input  logic                   rst,            // active-high, synchronous
    input  logic                   gate_en,        // 0 = refuse all writes

    // ── Slave port (sink; producer writes here) ──────────────────────────────
    input  logic                   s_axis_tvalid,
    output logic                   s_axis_tready,
    input  logic [DATA_W-1:0]      s_axis_tdata,
    input  logic                   s_axis_tlast,

    // ── Master port (source; consumer reads here) ────────────────────────────
    output logic                   m_axis_tvalid,
    input  logic                   m_axis_tready,
    output logic [DATA_W-1:0]      m_axis_tdata,
    output logic                   m_axis_tlast,

    // ── Occupancy: 0 = empty … DEPTH = full ──────────────────────────────────
    output logic [$clog2(DEPTH):0] fill_level
);

    localparam int PTR_W = $clog2(DEPTH);

    logic [DATA_W:0]   mem [0:DEPTH-1];   // {tlast, tdata} per entry
    logic [PTR_W-1:0]  wr_ptr, rd_ptr;

    logic full, empty;
    assign full  = (fill_level == DEPTH[$clog2(DEPTH):0]);
    assign empty = (fill_level == '0);

    // The one line this whole exercise is about: gate_en is a THIRD reason
    // (alongside "not full") that the write side can refuse a beat.
    assign s_axis_tready = ~full && gate_en;
    assign m_axis_tvalid = ~empty;

    assign m_axis_tdata = mem[rd_ptr][DATA_W-1:0];
    assign m_axis_tlast = mem[rd_ptr][DATA_W];

    logic do_write, do_read;
    assign do_write = s_axis_tvalid & s_axis_tready;
    assign do_read  = m_axis_tvalid & m_axis_tready;

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
            unique case ({do_write, do_read})
                2'b10:   fill_level <= fill_level + 1'b1;
                2'b01:   fill_level <= fill_level - 1'b1;
                default: /* unchanged */ ;
            endcase
        end
    end

endmodule
