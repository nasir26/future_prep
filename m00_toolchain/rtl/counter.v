 // counter.v — 8-bit free-running counter, smoke-test DUT
//
// Purpose: the simplest possible RTL that still exercises the full simulation
// flow: clock + reset, sequential logic, output observable in a waveform.
// This module is intentionally Verilog-2001 so it works in ALL three simulators
// without any special flags (iverilog, xsim, Verilator).

`timescale 1ns/1ps

module counter #(
    parameter WIDTH = 8          // counter bit-width, override in TB if desired
) (
    input  wire             clk,
    input  wire             rst_n,   // active-low synchronous reset
    input  wire             en,      // count-enable
    output reg  [WIDTH-1:0] count,   // current count value
    output wire             wrap     // pulses high for ONE cycle when count rolls over
);

    // Next-count value, purely combinational
    wire [WIDTH-1:0] count_next = count + 1'b1;

    // Assign wrap: fires when about to roll from max → 0
    assign wrap = en & (count == {WIDTH{1'b1}});

    // Sequential block — only place state changes happen
    always @(posedge clk) begin
        if (!rst_n)
            count <= {WIDTH{1'b0}};
        else if (en)
            count <= count_next;
        // en == 0: hold value
    end

endmodule
