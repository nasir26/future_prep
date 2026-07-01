// =============================================================================
// M09 — tb_uart_mixed: SystemVerilog TB driving a VHDL DUT pair (mixed-language)
// =============================================================================
`timescale 1ns/1ps
//
// WHY THIS FILE EXISTS
//   Everything else in this repo is SystemVerilog. Real interview-relevant
//   codebases are rarely 100% one HDL — legacy IP, vendor cores, and
//   third-party blocks show up in VHDL constantly, and xsim (like every
//   commercial simulator) elaborates mixed-language designs by compiling
//   each language with its own compiler (xvlog for SV, xvhdl for VHDL)
//   into the SAME work library, then letting xelab resolve instances
//   across the boundary. The DUT here (uart_tx.vhd + uart_rx.vhd) is
//   genuinely VHDL; this file is genuinely SystemVerilog; nothing bridges
//   them except the shared library and matching port names/widths.
//
// VHDL <-> SystemVerilog cheat-sheet (the parts that bit me writing this):
//   - std_logic          <-> logic              (both single-bit 4-state)
//   - std_logic_vector   <-> logic [N-1:0]       (VHDL is NOT auto-indexed;
//                                                  watch downto vs [N-1:0])
//   - VHDL generic       <-> SV parameter        (#(.NAME(value)) works
//                                                  identically from the SV
//                                                  instantiation side)
//   - VHDL has no `always`/procedural blocks outside a `process` — but
//     from the SV side, a VHDL entity looks exactly like a normal module:
//     port list, instantiate, connect. No `import`/wrapper needed.
//
module tb_uart_mixed;

    localparam int CLKS_PER_BIT = 4;   // small: fast, still-readable waveform

    logic       clk = 0;
    logic       rst = 1;
    always #5 clk = ~clk;   // 10ns period

    logic [7:0] tx_data;
    logic       tx_dv;
    logic       tx_active;
    logic       tx_serial;
    logic       tx_done;

    logic       rx_dv;
    logic [7:0] rx_byte;

    // ── DUT: VHDL uart_tx, wired straight into VHDL uart_rx ─────────────────
    // (loopback: no physical UART line here, just tx_serial === rx_serial)
    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) dut_tx (
        .clk(clk), .rst(rst),
        .i_data(tx_data), .i_dv(tx_dv),
        .o_tx_active(tx_active), .o_tx_serial(tx_serial), .o_tx_done(tx_done)
    );

    uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) dut_rx (
        .clk(clk), .rst(rst),
        .i_rx_serial(tx_serial),
        .o_rx_dv(rx_dv), .o_rx_byte(rx_byte)
    );

    // ── VCD: same DUMPFILE-plusarg convention as every other xsim TB here ───
    string _vcd;
    initial begin
        if (!$value$plusargs("DUMPFILE=%s", _vcd)) _vcd = "dump.vcd";
        $dumpfile(_vcd);
        $dumpvars(0, tb_uart_mixed);
    end

    // ── One byte, round-trip, self-checked ──────────────────────────────────
    int pass_count = 0;
    int fail_count = 0;

    task automatic send_and_check(input logic [7:0] byte_in);
        @(posedge clk);
        tx_data <= byte_in;
        tx_dv   <= 1;
        @(posedge clk);
        tx_dv   <= 0;

        wait (tx_done === 1);
        @(posedge clk);
        wait (rx_dv === 1);
        @(posedge clk);

        if (rx_byte === byte_in) begin
            $display("  PASS  sent=0x%02h  received=0x%02h", byte_in, rx_byte);
            pass_count++;
        end else begin
            $display("  FAIL  sent=0x%02h  received=0x%02h", byte_in, rx_byte);
            fail_count++;
        end
    endtask

    initial begin
        tx_data = '0;
        tx_dv   = 0;
        repeat (4) @(posedge clk);
        rst = 0;
        @(posedge clk);

        // Directed edge cases: all-zeros, all-ones, alternating patterns.
        send_and_check(8'h00);
        send_and_check(8'hFF);
        send_and_check(8'hA5);
        send_and_check(8'h5A);

        // A handful of random bytes for broader coverage.
        for (int i = 0; i < 8; i++) begin
            send_and_check($urandom_range(0, 255));
        end

        $display("");
        $display("tb_uart_mixed: %0d PASS, %0d FAIL", pass_count, fail_count);
        if (fail_count == 0) $display("ALL PASS");
        else                 $display("SOME FAILED");
        $finish;
    end

endmodule
