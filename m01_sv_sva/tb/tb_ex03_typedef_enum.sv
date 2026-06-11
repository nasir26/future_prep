// Testbench: ex03_typedef_enum — typedef/enum/packed struct self-check

`timescale 1ns/1ps

// Import types from the DUT's file-scope declarations.
// In xsim, file-scope typedefs are visible within the same compilation unit.
// (In production, these would be in a package — see ex06.)

module tb_ex03_typedef_enum;

    // Redeclare the types here so the TB can construct values.
    typedef enum logic [1:0] { RED=2'b00, GREEN=2'b01, YELLOW=2'b10 } color_t;
    typedef struct packed {
        logic        valid;
        logic        last;
        logic [7:0]  id;
        logic [31:0] data;
    } axi_beat_t;

    logic      clk = 0;
    logic      rst;
    color_t    color_in,  color_out;
    axi_beat_t beat_in,   beat_out;
    logic [41:0] beat_raw_out;

    ex03_typedef_enum dut (.*);

    always #5 clk = ~clk;

    int pass_count = 0, fail_count = 0;

    task check_color(string name, color_t got, color_t exp);
        if (got === exp) begin
            $display("  PASS  %s: got=%s", name, got.name());
            pass_count++;
        end else begin
            $display("  FAIL  %s: got=%s  exp=%s", name, got.name(), exp.name());
            fail_count++;
        end
    endtask

    task check_beat(string name, axi_beat_t got, axi_beat_t exp);
        if (got === exp) begin
            $display("  PASS  %s", name);
            pass_count++;
        end else begin
            $display("  FAIL  %s: got=0x%011h  exp=0x%011h", name, got, exp);
            fail_count++;
        end
    endtask

    task tick(int n = 1);
        repeat(n) @(posedge clk); #1;
    endtask

    initial begin
        $dumpfile("../../waves/m01_ex03_typedef.vcd");
        $dumpvars(0, tb_ex03_typedef_enum);

        rst = 1; color_in = RED; beat_in = '0;
        tick(2);
        check_color("reset_color", color_out, RED);

        // Test color pipeline
        rst = 0; color_in = GREEN;
        tick(1);
        check_color("color_green", color_out, GREEN);

        color_in = YELLOW;
        tick(1);
        check_color("color_yellow", color_out, YELLOW);

        // Test beat pipeline — construct a packed struct value
        beat_in.valid = 1'b1;
        beat_in.last  = 1'b0;
        beat_in.id    = 8'h05;
        beat_in.data  = 32'hDEAD_BEEF;
        tick(1);
        check_beat("beat_passthrough", beat_out, beat_in);

        // Verify raw view matches struct — 42-bit concatenation
        // Expected: {valid, last, id, data} = {1,0, 8'h05, 32'hDEADBEEF}
        if (beat_raw_out === {beat_out.valid, beat_out.last, beat_out.id, beat_out.data}) begin
            $display("  PASS  beat_raw_matches_struct");
            pass_count++;
        end else begin
            $display("  FAIL  beat_raw_matches_struct");
            fail_count++;
        end

        $display("---");
        $display("ex03_typedef_enum: %0d PASS, %0d FAIL", pass_count, fail_count);
        if (fail_count == 0) $display("ALL PASS");
        else                 $display("FAILURES DETECTED");
        $finish;
    end

endmodule
