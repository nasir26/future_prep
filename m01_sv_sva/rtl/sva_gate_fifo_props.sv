// =============================================================================
// Day 4: SVA properties for gate_fifo_sv  (attached via `bind`, same pattern
// as Day 3's sva_fifo_props.sv)
// =============================================================================
`timescale 1ns/1ps
//
// Reuses every property Day 3 established for axi_stream_fifo (occupancy
// bounds, full/empty imply ready/valid, held-until-accepted on both ports)
// and adds exactly one new one: the gate itself. That new property is the
// entire reason this file exists separately from sva_fifo_props.sv rather
// than parameterizing that one — `gate_en` doesn't exist on axi_stream_fifo,
// so the checker's port list has to differ, and a checker with a signal it
// only sometimes needs is worse than two small checkers.
// =============================================================================

module gate_fifo_sv_sva #(
    parameter int DATA_W = 8,
    parameter int DEPTH  = 8
) (
    input logic                   clk,
    input logic                   rst,
    input logic                   gate_en,
    input logic                   s_axis_tvalid,
    input logic                   s_axis_tready,
    input logic [DATA_W-1:0]      s_axis_tdata,
    input logic                   s_axis_tlast,
    input logic                   m_axis_tvalid,
    input logic                   m_axis_tready,
    input logic [DATA_W-1:0]      m_axis_tdata,
    input logic                   m_axis_tlast,
    input logic [$clog2(DEPTH):0] fill_level
);

    default clocking cb @(posedge clk); endclocking

    localparam logic [$clog2(DEPTH):0] FULL_LVL = DEPTH[$clog2(DEPTH):0];

    // ── (A) DESIGN: the gate itself — the one property this file exists for ─
    ap_gate_blocks_write: assert property (disable iff (rst)
        !gate_en |-> !s_axis_tready)
        else $error("[SVA] s_axis_tready high while gate_en=0");

    // ── (A) DESIGN: occupancy never exceeds DEPTH ────────────────────────────
    ap_no_overflow: assert property (disable iff (rst)
        fill_level <= FULL_LVL)
        else $error("[SVA] fill_level=%0d exceeds DEPTH=%0d", fill_level, DEPTH);

    // ── (A) DESIGN: full or gated => writes refused ──────────────────────────
    ap_full_blocks_write: assert property (disable iff (rst)
        (fill_level == FULL_LVL) |-> !s_axis_tready)
        else $error("[SVA] tready high while FIFO full");

    // ── (A) DESIGN: empty => no data offered ─────────────────────────────────
    ap_empty_no_valid: assert property (disable iff (rst)
        (fill_level == '0) |-> !m_axis_tvalid)
        else $error("[SVA] tvalid high while FIFO empty");

    // ── (A) DESIGN: master holds VALID/DATA stable until accepted ────────────
    ap_m_valid_held: assert property (disable iff (rst)
        (m_axis_tvalid && !m_axis_tready) |=> m_axis_tvalid)
        else $error("[SVA] m_axis_tvalid dropped before handshake");

    ap_m_data_stable: assert property (disable iff (rst)
        (m_axis_tvalid && !m_axis_tready) |=> $stable(m_axis_tdata) &&
                                              $stable(m_axis_tlast))
        else $error("[SVA] m_axis_tdata/tlast changed while stalled");

    // ── (B) STIMULUS: producer holds VALID/DATA stable while offering ───────
    ap_s_valid_held: assert property (disable iff (rst)
        (s_axis_tvalid && !s_axis_tready) |=> s_axis_tvalid)
        else $error("[SVA-STIM] s_axis_tvalid dropped before handshake");

    ap_s_data_stable: assert property (disable iff (rst)
        (s_axis_tvalid && !s_axis_tready) |=> $stable(s_axis_tdata) &&
                                              $stable(s_axis_tlast))
        else $error("[SVA-STIM] s_axis_tdata/tlast changed while stalled");

    // ── COVERAGE: prove the gate itself gets exercised both ways ─────────────
    cp_gated_stall:  cover property (disable iff (rst)
                         s_axis_tvalid && !gate_en);
    cp_gate_release: cover property (disable iff (rst)
                         $rose(gate_en) ##0 s_axis_tvalid ##0 s_axis_tready);

endmodule

bind gate_fifo_sv gate_fifo_sv_sva #(
    .DATA_W(DATA_W), .DEPTH(DEPTH)
) u_sva (.*);
