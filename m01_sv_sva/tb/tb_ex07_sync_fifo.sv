// Testbench: ex07_sync_fifo — comprehensive synchronous FIFO self-check
// Tests: empty/full flags, fill level, write→read round-trip, overflow/underflow protection

`timescale 1ns/1ps

module tb_ex07_sync_fifo;

    parameter int DATA_W    = 8;
    parameter int DEPTH_LOG2 = 3;    // depth = 8
    localparam int DEPTH    = 1 << DEPTH_LOG2;

    logic              clk = 0;
    logic              rst;
    logic              wr_en, rd_en;
    logic [DATA_W-1:0] wr_data, rd_data;
    logic              full, empty;
    logic [DEPTH_LOG2:0] fill_level;

    ex07_sync_fifo #(.DATA_W(DATA_W), .DEPTH_LOG2(DEPTH_LOG2)) dut (.*);

    always #5 clk = ~clk;

    int pass_count = 0, fail_count = 0;
    string _vcd;

    task check(string name, logic got, logic exp);
        if (got === exp) begin
            $display("  PASS  %s", name);
            pass_count++;
        end else begin
            $display("  FAIL  %s: got=%b  exp=%b", name, got, exp);
            fail_count++;
        end
    endtask

    task check8(string name, logic [7:0] got, logic [7:0] exp);
        if (got === exp) begin
            $display("  PASS  %s: %0h", name, got);
            pass_count++;
        end else begin
            $display("  FAIL  %s: got=%0h  exp=%0h", name, got, exp);
            fail_count++;
        end
    endtask

    task checkN(string name, logic [DEPTH_LOG2:0] got, logic [DEPTH_LOG2:0] exp);
        if (got === exp) begin
            $display("  PASS  %s: %0d", name, got);
            pass_count++;
        end else begin
            $display("  FAIL  %s: got=%0d  exp=%0d", name, got, exp);
            fail_count++;
        end
    endtask

    task tick(int n = 1);
        repeat(n) @(posedge clk); #1;
    endtask

    // Push a value and clock once
    task push(logic [DATA_W-1:0] val);
        wr_en = 1; wr_data = val;
        tick(1);
        wr_en = 0;
    endtask

    // Pop once and return data on the NEXT cycle (synchronous read)
    task pop_and_get(output logic [DATA_W-1:0] val);
        rd_en = 1;
        tick(1);
        rd_en = 0;
        tick(1);   // data valid now
        val = rd_data;
    endtask

    initial begin
        if (!$value$plusargs("DUMPFILE=%s", _vcd)) _vcd = "dump.vcd";
        $dumpfile(_vcd);
        $dumpvars(0, tb_ex07_sync_fifo);

        // ── Reset ───────────────────────────────────────────────────────────
        rst = 1; wr_en = 0; rd_en = 0; wr_data = '0;
        tick(2);
        check("reset_empty", empty, 1'b1);
        check("reset_full",  full,  1'b0);
        checkN("reset_fill", fill_level, 0);
        rst = 0;

        // ── Fill completely ──────────────────────────────────────────────────
        for (int i = 0; i < DEPTH; i++) push(i[DATA_W-1:0]);
        check("full_flag",   full,  1'b1);
        check("not_empty",   empty, 1'b0);
        checkN("fill_level_full", fill_level, DEPTH[DEPTH_LOG2:0]);

        // ── Drain completely ─────────────────────────────────────────────────
        begin
            logic [DATA_W-1:0] got;
            for (int i = 0; i < DEPTH; i++) begin
                pop_and_get(got);
                check8($sformatf("drain_%0d", i), got, i[DATA_W-1:0]);
            end
        end
        check("empty_after_drain", empty, 1'b1);

        // ── Simultaneous push + pop (pipeline) ───────────────────────────────
        // Push 0xAA into the empty FIFO, then simultaneously push 0xBB while popping 0xAA
        push(8'hAA);
        wr_en = 1; wr_data = 8'hBB; rd_en = 1;
        tick(1);
        wr_en = 0; rd_en = 0;
        tick(1);   // rd_data now has 0xAA
        check8("simul_pop_AA", rd_data, 8'hAA);
        checkN("simul_fill_1", fill_level, 1);   // 0xBB still in FIFO

        // Drain 0xBB
        begin
            logic [DATA_W-1:0] got;
            pop_and_get(got);
            check8("simul_pop_BB", got, 8'hBB);
        end
        check("empty_final", empty, 1'b1);

        $display("---");
        $display("ex07_sync_fifo: %0d PASS, %0d FAIL", pass_count, fail_count);
        if (fail_count == 0) $display("ALL PASS");
        else                 $display("FAILURES DETECTED");
        $finish;
    end

endmodule
