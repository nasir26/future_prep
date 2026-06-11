// =============================================================================
// Ex06: Package — shared typedefs and constants across modules
// =============================================================================
`timescale 1ns/1ps
//
// CONCEPT: package
//   - A package is a named namespace for types, parameters, functions, and
//     tasks that multiple modules can import.
//   - Without packages: you either duplicate typedef declarations across files
//     (inconsistency hazard) or use `include to paste text (macro pollution).
//   - With packages: one authoritative definition; modules import what they need.
//
// CONCEPT: import
//   Two styles:
//     import fifo_pkg::*;         // wildcard: all names visible, no prefix needed
//     import fifo_pkg::fifo_cfg_t; // explicit: only this name, clearer dependencies
//
//   Wildcard import is fine for small packages; explicit import is cleaner in
//   large codebases where name collisions are possible.
//
// =============================================================================

package fifo_pkg;

    // ── Parameterized FIFO configuration struct ──────────────────────────────
    // Using a struct instead of scattered parameters keeps all FIFO config in
    // one place and makes instantiation more readable.
    typedef struct packed {
        logic [4:0] depth_log2;   // actual depth = 2^depth_log2
        logic [4:0] data_width;   // bits per entry
    } fifo_cfg_t;

    // ── FIFO status flags (returned as a bundle) ─────────────────────────────
    typedef struct packed {
        logic full;
        logic empty;
        logic almost_full;    // depth - 1 entries used
        logic almost_empty;   // 1 entry used
    } fifo_status_t;

    // ── Common bus widths ────────────────────────────────────────────────────
    localparam int BYTE_W    = 8;
    localparam int HALFWORD  = 16;
    localparam int WORD_W    = 32;
    localparam int DWORD_W   = 64;

    // ── Utility function: one-hot encode a 3-bit index ───────────────────────
    // Packages can contain functions — a clean way to share combinational logic.
    function automatic logic [7:0] one_hot8(input logic [2:0] idx);
        one_hot8 = 8'b0;
        one_hot8[idx] = 1'b1;
    endfunction

endpackage
