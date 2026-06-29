// =============================================================================
// Testbench: axi_stream_fifo  (directed + randomized, self-checking)
// =============================================================================
`timescale 1ns/1ps
//
// Verifies functional behaviour with a scoreboard, and — when compiled with a
// simulator that supports SVA (xsim, or Verilator with --assert) — the bound
// checker in sva_fifo_props.sv runs concurrently and flags any protocol break.
//
// The randomized driver is deliberately AXI-LEGAL: once it offers a beat it
// holds TVALID and TDATA/TLAST stable until the FIFO accepts it. That keeps the
// "(B) STIMULUS" assertions green and proves they only fire on real bugs.
// =============================================================================

module tb_axi_stream_fifo;

    localparam int DATA_W = 8;
    localparam int DEPTH  = 4;     // small depth → easy to reach "full"

    logic                    clk = 0;
    logic                    rst;
    logic                    s_tvalid, s_tready, s_tlast;
    logic [DATA_W-1:0]       s_tdata;
    logic                    m_tvalid, m_tready, m_tlast;
    logic [DATA_W-1:0]       m_tdata;
    logic [$clog2(DEPTH):0]  fill;

    // ── DUT ──────────────────────────────────────────────────────────────────
    axi_stream_fifo #(.DATA_W(DATA_W), .DEPTH(DEPTH)) dut (
        .clk(clk), .rst(rst),
        .s_axis_tvalid(s_tvalid), .s_axis_tready(s_tready),
        .s_axis_tdata(s_tdata),   .s_axis_tlast(s_tlast),
        .m_axis_tvalid(m_tvalid), .m_axis_tready(m_tready),
        .m_axis_tdata(m_tdata),   .m_axis_tlast(m_tlast),
        .fill_level(fill)
    );

    always #5 clk = ~clk;          // 10 ns period

    // ── Scoreboard + counters ────────────────────────────────────────────────
    logic [DATA_W:0] model [$];    // reference FIFO of {tlast, tdata}
    int pass_count = 0, fail_count = 0;

    task automatic check(string name, logic cond);
        if (cond) begin pass_count++; $display("  PASS  %s", name); end
        else      begin fail_count++; $display("  FAIL  %s", name); end
    endtask

    task automatic step(int n = 1);
        repeat (n) @(posedge clk);
        #1;                        // settle combinational outputs after the edge
    endtask

    // ── Reset ─────────────────────────────────────────────────────────────────
    task automatic do_reset();
        rst = 1; s_tvalid = 0; s_tdata = '0; s_tlast = 0; m_tready = 0;
        step(2);
        rst = 0; step(1);
    endtask

    // ── Test 1: reset state ────────────────────────────────────────────────────
    task automatic t_reset_state();
        $display("-- T1: reset state --");
        check("empty_after_reset",  m_tvalid === 1'b0);
        check("ready_after_reset",   s_tready === 1'b1);
        check("fill_zero",           fill === '0);
    endtask

    // ── Test 2: single-beat round trip (incl. tlast) ───────────────────────────
    task automatic t_single_beat();
        $display("-- T2: single beat --");
        // push one beat with tlast=1
        s_tdata = 8'hA5; s_tlast = 1; s_tvalid = 1;
        step(1);                       // accepted (not full)
        s_tvalid = 0;
        check("not_empty_after_push", m_tvalid === 1'b1);
        check("fill_is_one",          fill === 3'd1);
        check("data_presented",       m_tdata === 8'hA5);
        check("tlast_presented",      m_tlast === 1'b1);
        // pop it
        m_tready = 1; step(1); m_tready = 0;
        check("empty_after_pop",      m_tvalid === 1'b0);
        check("fill_zero_again",      fill === '0);
    endtask

    // ── Test 3+4: fill to full, then drain in order ────────────────────────────
    task automatic t_fill_drain();
        logic [DATA_W-1:0] exp;
        $display("-- T3/T4: fill to full + ordered drain --");
        // push DEPTH beats: 0x10,0x11,0x12,0x13 (last one tlast=1)
        for (int i = 0; i < DEPTH; i++) begin
            s_tdata  = 8'h10 + i[7:0];
            s_tlast  = (i == DEPTH-1);
            s_tvalid = 1;
            step(1);
        end
        s_tvalid = 0;
        check("full_flag_ready_low",  s_tready === 1'b0);     // ap_full_blocks_write
        check("fill_eq_depth",        fill === DEPTH[$clog2(DEPTH):0]);
        // drain and check ordering
        m_tready = 1;
        for (int i = 0; i < DEPTH; i++) begin
            exp = 8'h10 + i[7:0];
            check($sformatf("drain_order_%0d", i), m_tdata === exp);
            if (i == DEPTH-1) check("drain_tlast", m_tlast === 1'b1);
            step(1);
        end
        m_tready = 0;
        check("empty_after_drain",    m_tvalid === 1'b0);
    endtask

    // ── Test 5: randomized stream with back-pressure + scoreboard ──────────────
    // Legal driver: holds a beat until accepted; never retracts an offer.
    task automatic t_random_stream(int n_beats = 200);
        int sent = 0;
        logic offering = 0;
        logic [DATA_W-1:0] cur_data = '0;
        logic cur_last = 0;
        logic [DATA_W:0] expv;
        logic do_w, do_r;          // handshakes sampled AT the edge (pre-update)
        $display("-- T5: randomized stream (%0d beats) --", n_beats);

        while (sent < n_beats || model.size() != 0 || offering) begin
            // ---- decide slave-side stimulus (legal: hold while back-pressured)
            if (!offering && sent < n_beats) begin
                if ($urandom_range(0, 2) != 0) begin   // ~2/3 chance to offer
                    offering = 1;
                    cur_data = sent[7:0];
                    cur_last = ($urandom_range(0, 3) == 0);
                end
            end
            s_tvalid = offering;
            s_tdata  = cur_data;
            s_tlast  = cur_last;

            // ---- decide master-side ready (free to toggle)
            m_tready = ($urandom_range(0, 1) == 1);

            // ---- sample handshakes NOW: these are the values the DUT sees at
            //      the upcoming edge. (Reading s_tready AFTER the edge is wrong —
            //      a simultaneous pop frees a slot and raises tready post-edge,
            //      which would falsely look like our stalled beat was accepted.)
            do_w = s_tvalid && s_tready;
            do_r = m_tvalid && m_tready;

            if (do_w) model.push_back({s_tlast, s_tdata});
            if (do_r) begin
                expv = model.pop_front();
                check("stream_data", {m_tlast, m_tdata} === expv);
            end

            @(posedge clk); #1;

            // ---- bookkeeping uses the PRE-edge handshake, not the new tready
            if (do_w) begin
                offering = 0;
                sent++;
            end
        end
        s_tvalid = 0; m_tready = 0;
        check("stream_drained", (model.size() == 0) && (fill === '0));
    endtask

    // ── Run ────────────────────────────────────────────────────────────────────
    initial begin
        $dumpfile("../../waves/m01_axi_stream_fifo.vcd");
        $dumpvars(0, tb_axi_stream_fifo);

        do_reset();
        t_reset_state();
        t_single_beat();
        t_fill_drain();
        t_random_stream(200);

        $display("---");
        $display("axi_stream_fifo: %0d PASS, %0d FAIL", pass_count, fail_count);
        if (fail_count == 0) $display("ALL PASS");
        else                 $display("FAILURES DETECTED");
        $finish;
    end

endmodule
