// =============================================================================
// M09 — AXI4-Stream bus interface (shared by both DUT ports)
// =============================================================================
`timescale 1ns/1ps
//
// WHY ONE INTERFACE TYPE FOR TWO PORTS
//   The DUT (m01_sv_sva/rtl/axi_stream_fifo.sv) has two AXI-Stream ports:
//   a slave port (s_axis_*, FIFO is the sink) and a master port (m_axis_*,
//   FIFO is the source). Both speak the identical protocol — only who's
//   "supposed" to drive tvalid vs. tready differs, and that's a *driver*
//   concern, not a signal concern. So tb_top binds ONE interface type to
//   BOTH DUT ports (two separate instances, prod_if and cons_if), and the
//   UVM driver/monitor classes stay bus-agnostic: whether a given instance
//   is "the producer side" or "the consumer side" is purely a config_db
//   setting on the agent (see axis_agent.sv), never a difference in the
//   interface or monitor code. This is the same lesson as M02's
//   AxisSource/AxisSink split, rebuilt in UVM's driver/sequencer idiom.
//
interface axis_if #(
    parameter int DATA_W = 8
) (
    input logic clk,
    input logic rst        // active-high, synchronous — matches the DUT
);
    logic                 tvalid;
    logic                 tready;
    logic [DATA_W-1:0]     tdata;
    logic                 tlast;

    // WHY THE MONITOR NEEDS A CLOCKING BLOCK (this bit cost real debug time)
    //   The driver sets tvalid/tdata/tlast with plain blocking assignments,
    //   and — for the very first beat after reset — that assignment lands
    //   in the SAME simulation time step as the clock edge the monitor is
    //   also waiting on (the `@(negedge rst)` that unblocks the driver is
    //   itself triggered by that edge's reset-counter). A monitor written
    //   as `@(posedge clk); if (tvalid && tready)` is racing the driver's
    //   blocking assignment in that step — whether it sees the new value
    //   or the stale one depends on process-scheduling order, not on the
    //   protocol. It cost 8 "missing" producer-side beats to notice this.
    //   A clocking block's default input skew (#1step) samples signals in
    //   the Preponed region — guaranteed settled *before* this edge's
    //   Active-region assignments run — so `mon_cb.tvalid` is race-free
    //   by construction, regardless of what order driver/monitor processes
    //   happen to be scheduled in. Real UVM environments use clocking
    //   blocks for exactly this reason; the raw-signal version above only
    //   looked reasonable because most of its beats aren't at t=0.
    clocking mon_cb @(posedge clk);
        input tvalid, tready, tdata, tlast;
    endclocking
endinterface
