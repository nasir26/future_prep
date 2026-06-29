// Testbench: ex05_interface — interface/modport producer→consumer self-check
// Verifies: N_BYTES packets transferred, pkt_done fires, last_data correct

`timescale 1ns/1ps

module tb_ex05_interface;

    parameter int N_BYTES = 4;

    logic      clk = 0;
    logic      rst;
    logic      start;
    logic      prod_done;
    logic [7:0] last_data;
    logic      pkt_done;

    ex05_interface #(.N_BYTES(N_BYTES)) dut (.*);

    always #5 clk = ~clk;

    int pass_count = 0, fail_count = 0;
    string _vcd;

    task check8(string name, logic [7:0] got, logic [7:0] exp);
        if (got === exp) begin
            $display("  PASS  %s: got=%0h", name, got);
            pass_count++;
        end else begin
            $display("  FAIL  %s: got=%0h  exp=%0h", name, got, exp);
            fail_count++;
        end
    endtask

    task check1(string name, logic got, logic exp);
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

    initial begin
        if (!$value$plusargs("DUMPFILE=%s", _vcd)) _vcd = "dump.vcd";
        $dumpfile(_vcd);
        $dumpvars(0, tb_ex05_interface);

        rst = 1; start = 0;
        tick(2);
        rst = 0;
        tick(1);

        // Kick off the producer
        start = 1;
        tick(1);
        start = 0;

        // Wait for producer to signal done (max N_BYTES + 5 cycles)
        begin
            automatic int timeout = 0;
            while (!prod_done && timeout < N_BYTES + 10) begin
                tick(1);
                timeout++;
            end
        end

        // One extra cycle for consumer to process last beat
        tick(2);

        check1("prod_done",  prod_done, 1'b1);
        check1("pkt_done",   pkt_done,  1'b1);
        // Producer sends byte indices 0, 1, 2, ..., N_BYTES-1; last = N_BYTES-1
        check8("last_data",  last_data, N_BYTES - 1);

        $display("---");
        $display("ex05_interface: %0d PASS, %0d FAIL", pass_count, fail_count);
        if (fail_count == 0) $display("ALL PASS");
        else                 $display("FAILURES DETECTED");
        $finish;
    end

endmodule
