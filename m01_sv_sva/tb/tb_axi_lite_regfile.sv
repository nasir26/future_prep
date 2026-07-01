// =============================================================================
// Day 4 testbench: axi_lite_regfile + gate_fifo_sv (directed, self-checking)
// =============================================================================
`timescale 1ns/1ps
//
// WHY ONE TESTBENCH FOR TWO DUTS
//   axi_lite_regfile's REG0 bit 0 is wired straight to gate_fifo_sv's
//   gate_en — that's the whole point of the two Day 4 blocks existing
//   together (see gate_fifo_sv.sv's header). Testing them separately would
//   mean inventing a fake gate_en driver for the FIFO half and a fake
//   consumer of gate_en for the regfile half; testing them wired together
//   the way they're actually meant to be used is both less code and a
//   real integration test instead of two isolated unit tests.
//
module tb_axi_lite_regfile;

    localparam int ADDR_W = 4;
    localparam int DATA_W = 8;
    localparam int DEPTH  = 8;

    logic clk = 0;
    logic rst;
    always #5 clk = ~clk;

    // ── AXI4-Lite signals ─────────────────────────────────────────────────────
    logic [ADDR_W-1:0] awaddr;
    logic              awvalid, awready;
    logic [31:0]       wdata;
    logic [3:0]        wstrb;
    logic              wvalid, wready;
    logic [1:0]        bresp;
    logic              bvalid, bready;
    logic [ADDR_W-1:0] araddr;
    logic              arvalid, arready;
    logic [31:0]       rdata;
    logic [1:0]        rresp;
    logic              rvalid, rready;
    logic              gate_en;

    axi_lite_regfile #(.ADDR_W(ADDR_W)) dut_regfile (
        .clk(clk), .rst(rst),
        .s_axil_awaddr(awaddr), .s_axil_awvalid(awvalid), .s_axil_awready(awready),
        .s_axil_wdata(wdata),   .s_axil_wstrb(wstrb),
        .s_axil_wvalid(wvalid), .s_axil_wready(wready),
        .s_axil_bresp(bresp),   .s_axil_bvalid(bvalid), .s_axil_bready(bready),
        .s_axil_araddr(araddr), .s_axil_arvalid(arvalid), .s_axil_arready(arready),
        .s_axil_rdata(rdata),   .s_axil_rresp(rresp),
        .s_axil_rvalid(rvalid), .s_axil_rready(rready),
        .gate_en_o(gate_en)
    );

    // ── gate_fifo_sv signals ──────────────────────────────────────────────────
    logic                   s_tvalid, s_tready, s_tlast;
    logic [DATA_W-1:0]      s_tdata;
    logic                   m_tvalid, m_tready, m_tlast;
    logic [DATA_W-1:0]      m_tdata;
    logic [$clog2(DEPTH):0] fill;

    gate_fifo_sv #(.DATA_W(DATA_W), .DEPTH(DEPTH)) dut_fifo (
        .clk(clk), .rst(rst), .gate_en(gate_en),
        .s_axis_tvalid(s_tvalid), .s_axis_tready(s_tready),
        .s_axis_tdata(s_tdata),   .s_axis_tlast(s_tlast),
        .m_axis_tvalid(m_tvalid), .m_axis_tready(m_tready),
        .m_axis_tdata(m_tdata),   .m_axis_tlast(m_tlast),
        .fill_level(fill)
    );

    // ── Scoreboard ────────────────────────────────────────────────────────────
    int pass_count = 0, fail_count = 0;
    string _vcd;

    task automatic check(string name, logic cond);
        if (cond) begin pass_count++; $display("  PASS  %s", name); end
        else      begin fail_count++; $display("  FAIL  %s", name); end
    endtask

    task automatic step(int n = 1);
        repeat (n) @(posedge clk);
        #1;
    endtask

    // ── AXI4-Lite driver tasks (directed, one transaction at a time) ────────
    task automatic axil_write(input logic [ADDR_W-1:0] addr,
                               input logic [31:0]       data,
                               input logic [3:0]        strb = 4'hF);
        awaddr = addr; awvalid = 1;
        wdata  = data; wstrb = strb; wvalid = 1;
        bready = 1;
        // AW and W both asserted together — hold until BOTH readies seen,
        // since the DUT may accept them on different cycles.
        do @(posedge clk); while (!(awready || wready));
        #1;
        if (awready) awvalid = 0;
        if (wready)  wvalid  = 0;
        // If only one channel was accepted this edge, wait for the other.
        while (awvalid || wvalid) begin
            @(posedge clk); #1;
            if (awready) awvalid = 0;
            if (wready)  wvalid  = 0;
        end
        // Wait for the write response.
        do @(posedge clk); while (!bvalid);
        #1;
        bready = 0;
        step(1);
    endtask

    task automatic axil_read(input logic [ADDR_W-1:0] addr, output logic [31:0] data);
        araddr = addr; arvalid = 1;
        rready = 1;
        do @(posedge clk); while (!arready);
        #1;
        arvalid = 0;
        do @(posedge clk); while (!rvalid);
        #1;
        data = rdata;
        rready = 0;
        step(1);
    endtask

    task automatic do_reset();
        rst = 1;
        awaddr = '0; awvalid = 0;
        wdata  = '0; wstrb = '0; wvalid = 0;
        bready = 0;
        araddr = '0; arvalid = 0;
        rready = 0;
        s_tvalid = 0; s_tdata = '0; s_tlast = 0; m_tready = 0;
        step(2);
        rst = 0; step(1);
    endtask

    // ── Test 1: reset defaults ────────────────────────────────────────────────
    task automatic t_reset_state();
        logic [31:0] rd;
        $display("-- T1: reset state --");
        check("bvalid_low_after_reset", bvalid === 1'b0);
        check("rvalid_low_after_reset", rvalid === 1'b0);
        check("gate_en_low_after_reset", gate_en === 1'b0);
        axil_read(4'h0, rd);
        check("reg0_reads_zero", rd === 32'h0);
    endtask

    // ── Test 2: write/read-back all 4 registers ──────────────────────────────
    task automatic t_write_readback();
        logic [31:0] rd;
        $display("-- T2: write/read-back all 4 registers --");
        axil_write(4'h4, 32'hDEAD_BEEF);
        axil_read(4'h4, rd);
        check("reg1_readback", rd === 32'hDEAD_BEEF);

        axil_write(4'h8, 32'hCAFE_F00D);
        axil_read(4'h8, rd);
        check("reg2_readback", rd === 32'hCAFE_F00D);

        axil_write(4'hC, 32'h1234_5678);
        axil_read(4'hC, rd);
        check("reg3_readback", rd === 32'h1234_5678);
    endtask

    // ── Test 3: WSTRB partial write only touches the enabled byte lanes ──────
    task automatic t_wstrb_partial();
        logic [31:0] rd;
        $display("-- T3: WSTRB partial write --");
        axil_write(4'h4, 32'hFFFF_FFFF, 4'hF);       // start from all-ones
        axil_write(4'h4, 32'h0000_00AA, 4'h1);       // touch byte lane 0 only
        axil_read(4'h4, rd);
        check("wstrb_lane0_updated",   rd[7:0]   === 8'hAA);
        check("wstrb_other_lanes_held", rd[31:8] === 24'hFFFFFF);
    endtask

    // ── Test 4: gate_en=0 refuses FIFO writes even though not full ───────────
    // AXI-Stream-legal by construction: once s_tvalid asserts, it stays
    // asserted (per the STIMULUS properties in sva_gate_fifo_props.sv) until
    // the DUT actually accepts it — so this offer is deliberately left
    // *held*, not retracted, and T5 picks it up rather than issuing a new
    // one. Dropping tvalid here (before any tready) is exactly the AXI-STIM
    // violation that bit the first version of this test.
    task automatic t_gate_blocks_write();
        $display("-- T4: gate_en=0 blocks gate_fifo writes --");
        // REG0 bit 0 is 0 from reset — confirm the FIFO refuses.
        check("gate_en_still_low", gate_en === 1'b0);
        s_tdata = 8'h5A; s_tlast = 1; s_tvalid = 1;
        step(1);
        check("tready_low_while_gated", s_tready === 1'b0);
        check("fill_still_zero",        fill === '0);
        // s_tvalid stays asserted — see header comment above.
    endtask

    // ── Test 5: raising gate_en via AXI-Lite unblocks the FIFO ───────────────
    // Picks up T4's still-pending offer (same s_tdata/s_tvalid, untouched)
    // rather than issuing a fresh one, so the sequence "offer while gated,
    // then gate opens" is exercised — the interesting corner, not just
    // "offer after the gate was already open."
    //
    // WHY fork/join, NOT axil_write() THEN a separate wait
    // gate_en is combinational off REG0, so tready can go high *during*
    // axil_write's own B-channel handshake — not only after it returns.
    // A sequential "axil_write(); do @(posedge clk); while(!s_tready);"
    // would keep s_tvalid asserted with unchanged data through however
    // many extra cycles axil_write takes to return, and the DUT — quite
    // correctly — accepts a new beat of that same held data on every one
    // of those cycles too (that's what a first version of this test did,
    // and it pushed 3-4 beats of 0x5A instead of 1). Racing a concurrent
    // watcher that drops tvalid the instant tready is first seen is what
    // actually bounds it to exactly one accepted beat.
    task automatic t_gate_release();
        $display("-- T5: gate_en=1 (via REG0 write) unblocks gate_fifo --");
        fork
            axil_write(4'h0, 32'h0000_0001);      // set bit 0, leave others clear
            begin
                do @(posedge clk); while (!s_tready);
                #1;
                s_tvalid = 0;                       // legal: tready was just seen
            end
        join
        check("gate_en_now_high", gate_en === 1'b1);
        check("push_accepted_once_gated_open", fill === 3'd1);
        check("data_visible_at_output",        m_tdata === 8'h5A);

        m_tready = 1; step(1); m_tready = 0;
        check("drained_after_pop", fill === '0);
    endtask

    // ── Test 6: lowering gate_en re-blocks writes without disturbing REG0 ────
    // Same "hold, don't retract" discipline as T4 — this offer is left
    // pending when the test ends, which is legal (nothing ever samples a
    // dropped tvalid because there's no test after this one).
    task automatic t_gate_reassert();
        logic [31:0] rd;
        $display("-- T6: gate_en=0 again re-blocks writes ---");
        axil_write(4'h0, 32'h0000_0000);      // clear bit 0
        check("gate_en_low_again", gate_en === 1'b0);
        s_tdata = 8'hFF; s_tvalid = 1;
        step(1);
        check("tready_low_after_regate", s_tready === 1'b0);
        // s_tvalid stays asserted — see header comment above.
        axil_read(4'h0, rd);
        check("reg0_readback_zero", rd === 32'h0);
    endtask

    // ── Run ────────────────────────────────────────────────────────────────────
    initial begin
        if (!$value$plusargs("DUMPFILE=%s", _vcd)) _vcd = "dump.vcd";
        $dumpfile(_vcd);
        $dumpvars(0, tb_axi_lite_regfile);

        do_reset();
        t_reset_state();
        t_write_readback();
        t_wstrb_partial();
        t_gate_blocks_write();
        t_gate_release();
        t_gate_reassert();

        $display("---");
        $display("tb_axi_lite_regfile: %0d PASS, %0d FAIL", pass_count, fail_count);
        if (fail_count == 0) $display("ALL PASS");
        else                 $display("FAILURES DETECTED");
        $finish;
    end

endmodule
