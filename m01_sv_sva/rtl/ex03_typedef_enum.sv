// =============================================================================
// Ex03: typedef, enum, and packed struct
// =============================================================================
//
// CONCEPT: typedef
//   - Creates a named alias for a type. Same as C typedef.
//   - Benefits: self-documenting ports, single point of change if width changes.
//     typedef logic [31:0] word_t;  →  word_t data_a, data_b;
//
// CONCEPT: enum
//   - Restricts a variable to named legal values.
//   - Without enum: a logic [1:0] state could be assigned 2'b11 (illegal in
//     a 3-state FSM) with no compile warning. With enum: illegal assignment
//     = compile error.
//   - The underlying base type (logic [1:0]) is explicit — matches your state
//     register width to the number of states.
//   - Simulator shows the NAME (e.g. "GREEN") in waveforms, not the raw bits.
//
// CONCEPT: packed struct
//   - Groups named fields into a single contiguous bit-vector.
//   - 'packed': all fields laid out MSB→LSB, can be assigned/sliced as a whole.
//   - 'unpacked': fields may have padding (like C structs); cannot be used as
//     a port or packed into a signal.
//   - Use packed structs for AXI beats, instruction words, register maps —
//     anywhere you need to both name fields AND treat the whole thing as a bus.
//
// =============================================================================

// ─── Type declarations (normally these would live in a package — see ex06) ───

// Enum: three named colours with explicit binary encoding.
// The base type logic [1:0] gives us 4 possible values; only 3 are named.
// Assigning 2'b11 to a color_t variable is a compile-time error.
typedef enum logic [1:0] {
    RED    = 2'b00,
    GREEN  = 2'b01,
    YELLOW = 2'b10
} color_t;

// Packed struct: models a simplified AXI4-Stream beat header.
// Total width = 1 + 1 + 8 + 32 = 42 bits.
// Fields are ordered MSB first in the declaration.
typedef struct packed {
    logic        valid;       // bit 41
    logic        last;        // bit 40 — last beat in a packet
    logic [7:0]  id;          // bits 39:32 — stream identifier
    logic [31:0] data;        // bits 31:0
} axi_beat_t;

// ─── Module: demonstrates both types in a trivial circuit ────────────────────

module ex03_typedef_enum (
    input  logic      clk,
    input  logic      rst,
    // color input/output
    input  color_t    color_in,
    output color_t    color_out,
    // AXI beat pass-through (registered)
    input  axi_beat_t beat_in,
    output axi_beat_t beat_out,
    // raw-bus view of the beat (42 bits) — for waveform inspection
    output logic [41:0] beat_raw_out
);

    // Register the color input — one cycle delay
    always_ff @(posedge clk) begin
        if (rst) color_out <= RED;       // reset to a named value, not 2'b00
        else     color_out <= color_in;
    end

    // Register the full AXI beat struct — works because it's packed (single wire)
    always_ff @(posedge clk) begin
        if (rst) beat_out <= '0;         // zero-init clears all fields
        else     beat_out <= beat_in;
    end

    // Expose raw bits for waveform: cast the struct to its underlying bit-vector
    // This is a zero-cost operation — purely a view renaming for the simulator.
    assign beat_raw_out = beat_out;

endmodule
