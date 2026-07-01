// Testbench: ex02_shift_reg — parameterized shift register self-check
// Tests: reset clears, data propagates through DEPTH stages, enable gating

`timescale 1ns/1ps

module tb_ex02_shift_reg;

    parameter int DEPTH = 4;
    parameter int WIDTH = 8;

    logic             clk = 0;
    logic             rst;
    logic             en;
    logic [WIDTH-1:0] d_in;
    logic [WIDTH-1:0] d_out;
    logic [DEPTH-1:0] tap;

    ex02_shift_reg #(.DEPTH(DEPTH), .WIDTH(WIDTH)) dut (.*);

    always #5 clk = ~clk;

    int pass_count = 0, fail_count = 0;

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
        repeat(n) @(posedge clk); #1;
    endtask

    initial begin
        $dumpfile("../waves/m01_ex02_shift_reg.vcd");
        $dumpvars(0, tb_ex02_shift_reg);

        rst = 1; en = 0; d_in = '0;
        tick(2);
        check("reset_out", d_out, 8'h00);

        // Push value 8'hA1 into the shift register.
        // It must take exactly DEPTH clocks to appear at d_out.
        rst = 0; en = 1; d_in = 8'hA1;
        tick(1);  d_in = 8'h00;   // only one beat of data

        // After 1 clock: A1 is in stage[0] but not at d_out yet
        // After DEPTH-1 more clocks: A1 arrives at d_out
        tick(DEPTH - 1);
        check("propagation", d_out, 8'hA1);

        // Enable gating: freeze the shift register for 2 cycles, then resume
        en = 0;
        d_in = 8'hBB;
        tick(2);
        check("hold_during_disable", d_out, 8'hA1);  // d_out must not change

        en = 1;
        tick(DEPTH);
        check("propagation_after_enable", d_out, 8'hBB);

        $display("---");
        $display("ex02_shift_reg: %0d PASS, %0d FAIL", pass_count, fail_count);
        if (fail_count == 0) $display("ALL PASS");
        else                 $display("FAILURES DETECTED");
        $finish;
    end

endmodule
