// Testbench: ex06_pkg — package types + FIFO self-check

`timescale 1ns/1ps

import fifo_pkg::*;

module tb_ex06_pkg;

    parameter int DATA_W     = 8;
    parameter int DEPTH_LOG2 = 2;   // depth = 4
    localparam int DEPTH     = 1 << DEPTH_LOG2;

    logic              clk = 0;
    logic              rst;
    logic              push, pop;
    logic [DATA_W-1:0] din, dout;
    fifo_status_t      status;
    logic [2:0]        idx_in;
    logic [7:0]        one_hot_out;

    ex06_top #(.DATA_W(DATA_W), .DEPTH_LOG2(DEPTH_LOG2)) dut (.*);

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

    task tick(int n = 1);
        repeat(n) @(posedge clk); #1;
    endtask

    initial begin
        if (!$value$plusargs("DUMPFILE=%s", _vcd)) _vcd = "dump.vcd";
        $dumpfile(_vcd);
        $dumpvars(0, tb_ex06_pkg);

        rst = 1; push = 0; pop = 0; din = '0; idx_in = 0;
        tick(2);
        check("reset_empty", status.empty, 1'b1);
        check("reset_full",  status.full,  1'b0);
        rst = 0;

        // Push 4 values (fills DEPTH=4 FIFO)
        push = 1;
        din = 8'hAA; tick(1);
        din = 8'hBB; tick(1);
        din = 8'hCC; tick(1);
        din = 8'hDD; tick(1);
        push = 0;
        check("full_after_4", status.full,  1'b1);
        check("not_empty",    status.empty, 1'b0);

        // Pop and verify: read data appears one cycle after pop
        pop = 1; tick(1); pop = 0;
        tick(1);  // data registers one cycle later
        check8("pop_AA", dout, 8'hAA);

        pop = 1; tick(1); pop = 0;
        tick(1);
        check8("pop_BB", dout, 8'hBB);

        // Verify one_hot function from package
        idx_in = 3'd0; tick(1); check8("one_hot_0", one_hot_out, 8'b00000001);
        idx_in = 3'd3; tick(1); check8("one_hot_3", one_hot_out, 8'b00001000);
        idx_in = 3'd7; tick(1); check8("one_hot_7", one_hot_out, 8'b10000000);

        $display("---");
        $display("ex06_pkg: %0d PASS, %0d FAIL", pass_count, fail_count);
        if (fail_count == 0) $display("ALL PASS");
        else                 $display("FAILURES DETECTED");
        $finish;
    end

endmodule
