// tb_counter_icarus.v — Icarus Verilog testbench for the counter module
//
// Icarus-specific notes:
//  • Uses $dumpfile/$dumpvars for VCD generation — the primary waveform format
//    for Icarus. Output goes to ../../waves/counter_icarus.vcd
//  • Simulation ends with $finish; no need for timeout guards in a simple bench
//  • This testbench is also valid Verilog-2001 — NOT SystemVerilog — so it
//    compiles identically with: iverilog, xvlog (with -sv flag), and Verilator
//    (though Verilator has its own TB wrapper; see tb_counter_verilator.cpp)
//
// Tested behaviors:
//  1. reset holds count at 0
//  2. enable=1 causes count to increment each cycle
//  3. enable=0 holds count
//  4. wrap signal fires exactly one cycle when count rolls over from 255→0
//  5. count reaches 255 (8-bit max) and wraps back to 0 cleanly

`timescale 1ns/1ps

module tb_counter_icarus;

    // ------------------------------------------------------------------ //
    //  DUT signals
    // ------------------------------------------------------------------ //
    reg        clk   = 0;
    reg        rst_n = 0;
    reg        en    = 0;
    wire [7:0] count;
    wire       wrap;

    // ------------------------------------------------------------------ //
    //  Clock: 10 ns period (100 MHz)
    // ------------------------------------------------------------------ //
    always #5 clk = ~clk;

    // ------------------------------------------------------------------ //
    //  DUT instantiation
    // ------------------------------------------------------------------ //
    counter #(.WIDTH(8)) dut (
        .clk   (clk),
        .rst_n (rst_n),
        .en    (en),
        .count (count),
        .wrap  (wrap)
    );

    // ------------------------------------------------------------------ //
    //  VCD dump — lands in waves/ relative to where sim is invoked
    // ------------------------------------------------------------------ //
    initial begin
        $dumpfile("../waves/counter_icarus.vcd");   // relative to m00_toolchain/ → future_prep/waves/
        $dumpvars(0, tb_counter_icarus);   // 0 = dump all hierarchy levels
    end

    // ------------------------------------------------------------------ //
    //  Stimulus + checking
    // ------------------------------------------------------------------ //
    integer i;
    integer errors = 0;

    initial begin
        $display("=== counter smoke test (Icarus) ===");

        // --- Test 1: reset holds count at 0 ---
        rst_n = 0; en = 0;
        repeat(4) @(posedge clk); #1;
        if (count !== 8'h00) begin
            $display("FAIL T1: reset, expected 0 got %0d", count);
            errors = errors + 1;
        end else
            $display("PASS T1: reset holds count at 0");

        // --- Test 2: release reset, count stays 0 when en=0 ---
        @(posedge clk); #1;
        rst_n = 1;
        repeat(3) @(posedge clk); #1;
        if (count !== 8'h00) begin
            $display("FAIL T2: count changed without enable, got %0d", count);
            errors = errors + 1;
        end else
            $display("PASS T2: count holds when en=0");

        // --- Test 3: enable=1, count increments ---
        en = 1;
        @(posedge clk); #1;   // count goes to 1
        if (count !== 8'h01) begin
            $display("FAIL T3: expected 1 got %0d", count);
            errors = errors + 1;
        end else
            $display("PASS T3: first increment to 1");

        // --- Test 4: run to near-overflow, check wrap ---
        // Jump to count = 254 by resetting and re-counting
        // (simpler: just count 253 more cycles)
        repeat(253) @(posedge clk); #1;   // count should now be 254
        if (count !== 8'hFE) begin
            $display("FAIL T4: expected 0xFE got 0x%02X", count);
            errors = errors + 1;
        end else
            $display("PASS T4: count at 0xFE before wrap");

        // One more clock: count goes to 0xFF, wrap fires on NEXT edge
        @(posedge clk); #1;   // count = 0xFF, wrap = 1 (because en=1 & count=0xFF)
        if (wrap !== 1'b1) begin
            $display("FAIL T5a: wrap should be 1 when count=0xFF en=1, got %0b", wrap);
            errors = errors + 1;
        end else
            $display("PASS T5a: wrap=1 when count=0xFF");

        @(posedge clk); #1;   // count rolls to 0x00, wrap goes back to 0
        if (count !== 8'h00) begin
            $display("FAIL T5b: expected rollover to 0 got 0x%02X", count);
            errors = errors + 1;
        end else
            $display("PASS T5b: count rolled over to 0");

        if (wrap !== 1'b0) begin
            $display("FAIL T5c: wrap should be 0 after rollover, got %0b", wrap);
            errors = errors + 1;
        end else
            $display("PASS T5c: wrap=0 after rollover");

        // --- Test 5: en=0 freezes count ---
        en = 0;
        repeat(5) @(posedge clk); #1;
        if (count !== 8'h00) begin
            $display("FAIL T6: count moved while en=0, got %0d", count);
            errors = errors + 1;
        end else
            $display("PASS T6: en=0 freezes count at 0");

        // ---------------------------------------------------------------
        $display("---");
        if (errors == 0)
            $display("ALL TESTS PASSED");
        else
            $display("FAILED: %0d error(s)", errors);
        $display("---");

        #10 $finish;
    end

endmodule
