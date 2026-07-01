// tb_counter_xsim.v — xsim testbench for the counter module
//
// Almost identical to the Icarus testbench; kept separate because:
//  • xsim's $dumpfile path resolution differs (relative to the .wdb working dir)
//  • We name the output counter_xsim.vcd to distinguish dumps
//  • xsim is invoked with a different command flow (xvlog → xelab → xsim)
//
// Compile flow:
//   xvlog rtl/counter.v rtl/tb_counter_xsim.v
//   xelab tb_counter_xsim -s sim_snapshot
//   xsim sim_snapshot --runall
//
// The Makefile in this directory handles all of that.

`timescale 1ns/1ps

module tb_counter_xsim;

    reg        clk   = 0;
    reg        rst_n = 0;
    reg        en    = 0;
    wire [7:0] count;
    wire       wrap;

    always #5 clk = ~clk;

    counter #(.WIDTH(8)) dut (
        .clk   (clk),
        .rst_n (rst_n),
        .en    (en),
        .count (count),
        .wrap  (wrap)
    );

    // xsim also supports $dumpfile/$dumpvars — write VCD to waves/
    initial begin
        $dumpfile("../../../waves/counter_xsim.vcd");  // from build/xsim_work/ → future_prep/waves/
        $dumpvars(0, tb_counter_xsim);
    end

    integer errors = 0;

    initial begin
        $display("=== counter smoke test (xsim) ===");

        rst_n = 0; en = 0;
        repeat(4) @(posedge clk); #1;
        if (count !== 8'h00) begin $display("FAIL T1"); errors = errors + 1; end
        else $display("PASS T1: reset holds 0");

        @(posedge clk); #1; rst_n = 1;
        repeat(3) @(posedge clk); #1;
        if (count !== 8'h00) begin $display("FAIL T2"); errors = errors + 1; end
        else $display("PASS T2: holds without enable");

        en = 1;
        @(posedge clk); #1;
        if (count !== 8'h01) begin $display("FAIL T3 got %0d", count); errors = errors + 1; end
        else $display("PASS T3: first increment");

        repeat(253) @(posedge clk); #1;
        if (count !== 8'hFE) begin $display("FAIL T4 got 0x%02X", count); errors = errors + 1; end
        else $display("PASS T4: at 0xFE");

        @(posedge clk); #1;
        if (wrap !== 1'b1) begin $display("FAIL T5a wrap=%0b", wrap); errors = errors + 1; end
        else $display("PASS T5a: wrap=1 at 0xFF");

        @(posedge clk); #1;
        if (count !== 8'h00) begin $display("FAIL T5b got 0x%02X", count); errors = errors + 1; end
        else $display("PASS T5b: rolled to 0");

        if (wrap !== 1'b0) begin $display("FAIL T5c wrap=%0b", wrap); errors = errors + 1; end
        else $display("PASS T5c: wrap deasserts after rollover");

        en = 0;
        repeat(5) @(posedge clk); #1;
        if (count !== 8'h00) begin $display("FAIL T6 got %0d", count); errors = errors + 1; end
        else $display("PASS T6: frozen at 0");

        $display("---");
        if (errors == 0) $display("ALL TESTS PASSED");
        else             $display("FAILED: %0d error(s)", errors);
        $display("---");

        #10 $finish;
    end

endmodule
