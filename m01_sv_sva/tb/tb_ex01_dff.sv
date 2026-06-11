// Testbench: ex01_dff — D flip-flop self-check
// Tests: reset clears output, data captured on clock edge, enable gating

`timescale 1ns/1ps

module tb_ex01_dff;

    parameter int WIDTH = 8;

    logic             clk = 0;
    logic             rst;
    logic             en;
    logic [WIDTH-1:0] d;
    logic [WIDTH-1:0] q_basic, q_en;

    // DUT
    ex01_dff #(.WIDTH(WIDTH)) dut (.*);

    // 10 ns clock
    always #5 clk = ~clk;

    // ── Helper tasks ────────────────────────────────────────────────────────
    int pass_count = 0;
    int fail_count = 0;

    task check(string name, logic [WIDTH-1:0] got, logic [WIDTH-1:0] exp);
        if (got === exp) begin
            $display("  PASS  %s: got=%0h", name, got);
            pass_count++;
        end else begin
            $display("  FAIL  %s: got=%0h  exp=%0h", name, got, exp);
            fail_count++;
        end
    endtask

    task tick(int n = 1);
        repeat(n) @(posedge clk); #1;   // sample just after clock edge
    endtask

    // ── Test sequence ────────────────────────────────────────────────────────
    initial begin
        $dumpfile("../../waves/m01_ex01_dff.vcd");
        $dumpvars(0, tb_ex01_dff);

        rst = 1; en = 0; d = 8'hAB;
        tick(2);

        // Test 1: reset holds outputs at zero
        check("reset_basic", q_basic, 8'h00);
        check("reset_en",    q_en,    8'h00);

        // Test 2: basic DFF captures data after reset released
        rst = 0; d = 8'h42;
        tick(1);
        check("capture_basic", q_basic, 8'h42);
        check("en_blocked",    q_en,    8'h00);   // en still 0

        // Test 3: clock enable gates the DFF
        en = 1; d = 8'hFF;
        tick(1);
        check("en_capture",    q_en,    8'hFF);
        check("basic_follows", q_basic, 8'hFF);

        // Test 4: disable enable, change d — q_en must hold
        en = 0; d = 8'h12;
        tick(1);
        check("en_hold",       q_en,    8'hFF);   // must not change
        check("basic_update",  q_basic, 8'h12);   // basic always follows

        // Test 5: reset overrides enable
        en = 1; rst = 1; d = 8'hAA;
        tick(1);
        check("rst_over_en",   q_en,    8'h00);

        $display("---");
        $display("ex01_dff: %0d PASS, %0d FAIL", pass_count, fail_count);
        if (fail_count == 0) $display("ALL PASS");
        else                 $display("FAILURES DETECTED");
        $finish;
    end

endmodule
