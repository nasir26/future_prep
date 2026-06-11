// =============================================================================
// Ex05: Interface + modport
// =============================================================================
//
// CONCEPT: interface
//   - A named bundle of signals shared between modules.
//   - Without interfaces: connecting two modules requires matching every port
//     by name — if you add a signal, every module's port list changes.
//   - With an interface: add the signal once in the interface definition;
//     all modules using it automatically see the new signal.
//   - AXI4-Stream has 5+ signals (VALID, READY, DATA, LAST, KEEP…).
//     An interface keeps the port lists short and consistent.
//
// CONCEPT: modport
//   - Constrains WHO can drive which signals in the interface.
//   - Without modport: all signals are inout — any module can accidentally
//     drive a signal it should only read. No compile-time check.
//   - With modport: 'producer.src' can only drive valid/data, not ready.
//     'consumer.dst' can only drive ready, not valid/data.
//   - Misconnections (e.g. a consumer accidentally driving valid) are caught
//     at compile time, not discovered during simulation.
//
// =============================================================================

// ─── Interface definition ────────────────────────────────────────────────────
// Models a simple 8-bit valid/ready handshake (AXI4-Stream subset).
`timescale 1ns/1ps
interface handshake_if #(
    parameter int DATA_W = 8
);
    logic              valid;    // source asserts: data is present
    logic              ready;    // sink asserts: can accept data this cycle
    logic [DATA_W-1:0] data;
    logic              last;     // marks end of a packet

    // modport for the SOURCE (producer) side
    modport src (
        output valid, data, last,
        input  ready
    );

    // modport for the SINK (consumer) side
    modport dst (
        input  valid, data, last,
        output ready
    );

    // modport for a monitor (read-only, e.g. SVA / coverage probe)
    modport mon (
        input valid, ready, data, last
    );
endinterface

// ─── Producer module ────────────────────────────────────────────────────────
// Sends a configurable number of bytes, then stops.
`timescale 1ns/1ps
module producer #(
    parameter int N_BYTES = 4,
    parameter int DATA_W  = 8    // must match handshake_if DATA_W
) (
    input  logic          clk,
    input  logic          rst,
    input  logic          start,          // pulse to begin transmission
    handshake_if.src      bus,            // interface with src modport
    output logic          done
);
    logic [DATA_W-1:0] cnt;   // wide enough to send as data payload
    logic              active;

    always_ff @(posedge clk) begin
        if (rst) begin
            cnt    <= '0;
            active <= 1'b0;
            done   <= 1'b0;
        end else begin
            // done is sticky: cleared on new start, set on packet completion
            if (start) done <= 1'b0;

            if (start && !active) begin
                active <= 1'b1;
                cnt    <= '0;
            end
            // handshake: transfer happens when both valid and ready are high
            if (active && bus.valid && bus.ready) begin
                if (cnt == DATA_W'(N_BYTES - 1)) begin
                    active <= 1'b0;
                    done   <= 1'b1;   // holds until next start pulse
                end else begin
                    cnt <= cnt + 1'b1;
                end
            end
        end
    end

    // drive interface outputs combinationally from state
    assign bus.valid = active;
    assign bus.data  = cnt;   // cnt is DATA_W wide, same as bus.data
    assign bus.last  = active && (cnt == DATA_W'(N_BYTES - 1));

endmodule

// ─── Consumer module ────────────────────────────────────────────────────────
// Accepts all data; records last received byte and packet count.
`timescale 1ns/1ps
module consumer (
    input  logic     clk,
    input  logic     rst,
    handshake_if.dst bus,           // interface with dst modport
    output logic [7:0] last_data,
    output logic       pkt_done
);
    // Always ready — simplest possible back-pressure model.
    // A realistic consumer would deassert ready when its buffer is full.
    assign bus.ready = 1'b1;

    always_ff @(posedge clk) begin
        if (rst) begin
            last_data <= '0;
            pkt_done  <= 1'b0;
        end else begin
            if (bus.valid && bus.ready) begin
                last_data <= bus.data;
                // pkt_done is sticky: holds until bus.valid goes low (new packet started)
                if (bus.last) pkt_done <= 1'b1;
            end
            // clear when a new packet begins (valid goes high on non-last beat)
            if (bus.valid && !bus.last && pkt_done) pkt_done <= 1'b0;
        end
    end

endmodule

// ─── Top-level wrapper ───────────────────────────────────────────────────────
// Instantiates the interface and wires producer to consumer.
// This is the module the testbench instantiates.
`timescale 1ns/1ps
module ex05_interface #(
    parameter int DATA_W  = 8,
    parameter int N_BYTES = 4
) (
    input  logic       clk,
    input  logic       rst,
    input  logic       start,
    output logic       prod_done,
    output logic [7:0] last_data,
    output logic       pkt_done
);

    // Instantiate the interface (like a signal bundle declaration)
    handshake_if #(.DATA_W(DATA_W)) bus ();

    producer #(.N_BYTES(N_BYTES)) u_prod (
        .clk   (clk),
        .rst   (rst),
        .start (start),
        .bus   (bus.src),   // pass the src modport view
        .done  (prod_done)
    );

    consumer u_cons (
        .clk       (clk),
        .rst       (rst),
        .bus       (bus.dst),  // pass the dst modport view
        .last_data (last_data),
        .pkt_done  (pkt_done)
    );

endmodule
