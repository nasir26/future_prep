// =============================================================================
// M09 — tb_top: DUT instantiation, clock/reset, run_test() entry point
// =============================================================================
`timescale 1ns/1ps
//
// WHY THE DUT IS ../m01_sv_sva/rtl/axi_stream_fifo.sv, NOT A COPY
//   M09's whole point is writing a UVM environment *around* a design that
//   already exists — the AXI-Stream FIFO from M01 Day 3, already proven
//   correct there via SVA (sva_fifo_props.sv) and directed/random cocotb
//   tests in M02. Copying the file would let it drift from the original;
//   compiling it in place means M09's UVM env and M01's SVA checker are
//   both, permanently, verifying the exact same source.
//
// WHY RESET LIVES HERE, NOT IN A UVM PHASE
//   Real reset-phase UVM (pre_reset/reset/post_reset domains) exists, but
//   it's a lot of machinery for "hold rst high for a few cycles at time
//   zero." Every driver already does `@(negedge vif.rst)` before driving
//   anything (see axis_driver.sv), so a plain initial block here is the
//   simplest thing that is still correct — keep the UVM env focused on
//   the part of the testbench that's actually about UVM.
//
module tb_top;
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    import axis_pkg::*;

    localparam int DATA_W = 8;
    localparam int DEPTH  = 8;

    logic clk = 0;
    logic rst = 1;
    always #5 clk = ~clk;   // 10ns period

    initial begin
        repeat (4) @(posedge clk);
        rst = 0;
    end

    // ── One interface instance per DUT port (see axis_if.sv for why) ───────
    axis_if #(.DATA_W(DATA_W)) prod_if (.clk(clk), .rst(rst));   // s_axis_*
    axis_if #(.DATA_W(DATA_W)) cons_if (.clk(clk), .rst(rst));   // m_axis_*

    logic [$clog2(DEPTH):0] fill_level;

    axi_stream_fifo #(.DATA_W(DATA_W), .DEPTH(DEPTH)) dut (
        .clk(clk), .rst(rst),
        .s_axis_tvalid(prod_if.tvalid), .s_axis_tready(prod_if.tready),
        .s_axis_tdata(prod_if.tdata),   .s_axis_tlast(prod_if.tlast),
        .m_axis_tvalid(cons_if.tvalid), .m_axis_tready(cons_if.tready),
        .m_axis_tdata(cons_if.tdata),   .m_axis_tlast(cons_if.tlast),
        .fill_level(fill_level)
    );

    // ── VCD: same DUMPFILE-plusarg convention as every other xsim TB here ───
    string _vcd;
    initial begin
        if (!$value$plusargs("DUMPFILE=%s", _vcd)) _vcd = "dump.vcd";
        $dumpfile(_vcd);
        $dumpvars(0, tb_top);
    end

    // ── Hand the two vifs to the env before run_test() builds it ────────────
    initial begin
        uvm_config_db#(virtual axis_if)::set(null, "uvm_test_top.env", "prod_vif", prod_if);
        uvm_config_db#(virtual axis_if)::set(null, "uvm_test_top.env", "cons_vif", cons_if);
        run_test();
    end
endmodule
