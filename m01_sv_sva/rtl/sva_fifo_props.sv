// =============================================================================
// Day 3: SVA properties for axi_stream_fifo  (attached via `bind`)
// =============================================================================
`timescale 1ns/1ps
//
// CONCEPT: why a separate checker + `bind`
//   The design under test (axi_stream_fifo.sv) contains ZERO assertions — it
//   stays synthesis-clean and readable. All verification lives here. The
//   `bind` directive at the bottom of this file injects an instance of this
//   checker *inside* every axi_stream_fifo instance, wiring matching signal
//   names automatically (.*). This is the idiomatic, non-intrusive way to add
//   assertions: you never edit the RTL to verify it, and the same checker can
//   be reused across many instances/projects.
//
// CONCEPT: concurrent assertions (assert property)
//   Each property samples on @(posedge clk) (set once via `default clocking`)
//   and is ignored during reset via `disable iff (rst)`. Operators used:
//     |->   overlapping implication (consequent checked the SAME cycle)
//     |=>   non-overlapping implication (consequent checked NEXT cycle)
//     $stable(x) — x unchanged since the previous sampled cycle
//     $past(x)   — value of x one cycle ago
//
// CONCEPT: two flavours of property
//   (A) DESIGN properties — guarantees the FIFO must provide. A failure = bug.
//   (B) STIMULUS properties — obligations the producer driving the slave port
//       must obey to be AXI-legal. A failure = illegal testbench, not a DUT bug.
//
// NOTE: uses explicit `disable iff (rst)` per property (xsim and Verilator both
//   accept this; `default disable iff` is xsim-only, so avoided here).
// =============================================================================

module axi_stream_fifo_sva #(
    parameter int DATA_W = 8,
    parameter int DEPTH  = 8
) (
    input logic                   clk,
    input logic                   rst,
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

    // Sample every property on the rising clock edge.
    default clocking cb @(posedge clk); endclocking

    localparam logic [$clog2(DEPTH):0] FULL_LVL = DEPTH[$clog2(DEPTH):0];

    // ── (A) DESIGN: occupancy never exceeds DEPTH ────────────────────────────
    ap_no_overflow: assert property (disable iff (rst)
        fill_level <= FULL_LVL)
        else $error("[SVA] fill_level=%0d exceeds DEPTH=%0d", fill_level, DEPTH);

    // ── (A) DESIGN: when full, writes are refused (ready low) ────────────────
    ap_full_blocks_write: assert property (disable iff (rst)
        (fill_level == FULL_LVL) |-> !s_axis_tready)
        else $error("[SVA] tready high while FIFO full");

    // ── (A) DESIGN: when empty, no data is offered (valid low) ───────────────
    ap_empty_no_valid: assert property (disable iff (rst)
        (fill_level == '0) |-> !m_axis_tvalid)
        else $error("[SVA] tvalid high while FIFO empty");

    // ── (A) DESIGN: master holds VALID until accepted (no retracted offer) ───
    ap_m_valid_held: assert property (disable iff (rst)
        (m_axis_tvalid && !m_axis_tready) |=> m_axis_tvalid)
        else $error("[SVA] m_axis_tvalid dropped before handshake");

    // ── (A) DESIGN: master holds DATA/LAST stable while stalled ──────────────
    ap_m_data_stable: assert property (disable iff (rst)
        (m_axis_tvalid && !m_axis_tready) |=> $stable(m_axis_tdata) &&
                                              $stable(m_axis_tlast))
        else $error("[SVA] m_axis_tdata/tlast changed while stalled");

    // ── (B) STIMULUS: producer holds VALID until accepted ────────────────────
    ap_s_valid_held: assert property (disable iff (rst)
        (s_axis_tvalid && !s_axis_tready) |=> s_axis_tvalid)
        else $error("[SVA-STIM] s_axis_tvalid dropped before handshake");

    // ── (B) STIMULUS: producer holds DATA/LAST stable while back-pressured ───
    ap_s_data_stable: assert property (disable iff (rst)
        (s_axis_tvalid && !s_axis_tready) |=> $stable(s_axis_tdata) &&
                                              $stable(s_axis_tlast))
        else $error("[SVA-STIM] s_axis_tdata/tlast changed while stalled");

    // ── (A) DESIGN: occupancy bookkeeping matches the handshakes ─────────────
    ap_fill_push: assert property (disable iff (rst)
        ( s_axis_tvalid &&  s_axis_tready && !(m_axis_tvalid && m_axis_tready))
            |=> fill_level == $past(fill_level) + 1)
        else $error("[SVA] fill_level wrong after push-only");

    ap_fill_pop: assert property (disable iff (rst)
        (!(s_axis_tvalid && s_axis_tready) && m_axis_tvalid && m_axis_tready)
            |=> fill_level == $past(fill_level) - 1)
        else $error("[SVA] fill_level wrong after pop-only");

    // ── COVERAGE: prove the interesting corners get exercised ────────────────
    // (cover, not assert — these "pass" by being hit at least once.)
    cp_full:   cover property (disable iff (rst) fill_level == FULL_LVL);
    cp_sim_rw: cover property (disable iff (rst)
                   s_axis_tvalid && s_axis_tready &&
                   m_axis_tvalid && m_axis_tready);          // simultaneous push+pop
    cp_tlast:  cover property (disable iff (rst)
                   m_axis_tvalid && m_axis_tready && m_axis_tlast);

endmodule

// ── Attach the checker to every axi_stream_fifo instance, non-intrusively ────
// `.*` connects checker ports to DUT signals of the same name (incl. params).
bind axi_stream_fifo axi_stream_fifo_sva #(
    .DATA_W(DATA_W), .DEPTH(DEPTH)
) u_sva (.*);
