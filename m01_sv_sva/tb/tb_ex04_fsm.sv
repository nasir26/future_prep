// Testbench: ex04_fsm — traffic-light FSM self-check
// Verifies: correct state sequence, LED encoding, hold timing

`timescale 1ns/1ps

module tb_ex04_fsm;

    parameter int HOLD = 4;

    logic       clk = 0;
    logic       rst;
    logic       led_red, led_yellow, led_green;
    logic [1:0] state_out;

    ex04_fsm #(.HOLD_CYCLES(HOLD)) dut (.*);

    always #5 clk = ~clk;

    int pass_count = 0, fail_count = 0;

    task check(string name, logic got, logic exp);
        if (got === exp) begin
            $display("  PASS  %s", name);
            pass_count++;
        end else begin
            $display("  FAIL  %s: got=%b  exp=%b", name, got, exp);
            fail_count++;
        end
    endtask

    task tick(int n = 1);
        repeat(n) @(posedge clk); #1;
    endtask

    // Verify exactly one LED is on
    task automatic check_one_hot_leds(string phase);
        int active;
        active = led_red + led_yellow + led_green;  // evaluate when called, not at time-0
        if (active == 1) begin
            $display("  PASS  one_hot_led [%s]", phase);
            pass_count++;
        end else begin
            $display("  FAIL  one_hot_led [%s]: r=%b y=%b g=%b", phase, led_red, led_yellow, led_green);
            fail_count++;
        end
    endtask

    initial begin
        $dumpfile("../../waves/m01_ex04_fsm.vcd");
        $dumpvars(0, tb_ex04_fsm);

        rst = 1;
        tick(2);
        check("reset_red",     led_red,    1'b1);
        check("reset_no_grn",  led_green,  1'b0);
        check("reset_no_yel",  led_yellow, 1'b0);

        rst = 0;

        // ── RED phase: should hold for HOLD cycles ───────────────────────────
        repeat(HOLD) begin
            check_one_hot_leds("RED");
            check("red_led_on", led_red, 1'b1);
            tick(1);
        end

        // ── GREEN phase ──────────────────────────────────────────────────────
        repeat(HOLD) begin
            check_one_hot_leds("GREEN");
            check("green_led_on", led_green, 1'b1);
            tick(1);
        end

        // ── YELLOW phase ─────────────────────────────────────────────────────
        repeat(HOLD) begin
            check_one_hot_leds("YELLOW");
            check("yel_led_on", led_yellow, 1'b1);
            tick(1);
        end

        // ── Back to RED ───────────────────────────────────────────────────────
        check("cycle_back_red", led_red, 1'b1);

        $display("---");
        $display("ex04_fsm: %0d PASS, %0d FAIL", pass_count, fail_count);
        if (fail_count == 0) $display("ALL PASS");
        else                 $display("FAILURES DETECTED");
        $finish;
    end

endmodule
