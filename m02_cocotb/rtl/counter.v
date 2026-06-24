// counter.v — M02 ex01 DUT
// Parameterized synchronous up-counter with enable and synchronous reset.
// Plain Verilog (no SV) so both iverilog and xsim handle it identically.
//
// Author: Nasir Ali, C-DAC Noida

`timescale 1ns/1ps
module counter #(
    parameter WIDTH = 4         // bit width; default gives 0–15 range
)(
    input  wire             clk,
    input  wire             rst,    // synchronous active-high reset
    input  wire             en,     // count enable: hold when 0
    output reg  [WIDTH-1:0] count
);
    always @(posedge clk) begin
        if (rst)
            count <= {WIDTH{1'b0}};
        else if (en)
            count <= count + 1'b1;
        // implicit else: count holds — no latch because always_ff block
    end
endmodule
