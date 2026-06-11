// =============================================================================
// Ex04: Two-always FSM — Traffic Light Controller
// =============================================================================
//
// CONCEPT: Two-always FSM style (Moore machine)
//   A Moore machine's outputs depend ONLY on the current state (not inputs).
//   Two-always style separates concerns cleanly:
//
//     1. State register (always_ff) — clocked; only updates on clock edge.
//        Contains ONLY: state <= next_state (plus reset).
//
//     2. Next-state + output logic (always_comb) — combinational; no clock.
//        Contains: all case/if logic that decides next_state and drives outputs.
//
//   WHY separate? Mixing clocked and combinational logic in one always block
//   is legal but makes synthesis and lint tools work harder and makes it easier
//   to accidentally infer latches. Two-always is the industry-standard idiom.
//
// CONCEPT: Default assignment in always_comb
//   Always assign defaults at the TOP of the combinational block before the
//   case statement. This prevents unintentional latches for signals not assigned
//   in every branch. Missing default = latch inferred = synthesis mismatch.
//
// DESIGN: Simple 3-state traffic light.
//   RED    →(timer==0) GREEN
//   GREEN  →(timer==0) YELLOW
//   YELLOW →(timer==0) RED
//   Each state holds for a programmable number of cycles (HOLD_CYCLES).
//
// =============================================================================

module ex04_fsm #(
    parameter int HOLD_CYCLES = 4   // cycles each light stays on (sim-friendly)
) (
    input  logic clk,
    input  logic rst,
    // outputs: one-hot LED encoding (red, yellow, green)
    output logic led_red,
    output logic led_yellow,
    output logic led_green,
    // current state exposed for testbench checking
    output logic [1:0] state_out
);

    // ─── Type ──────────────────────────────────────────────────────────────
    typedef enum logic [1:0] {
        ST_RED    = 2'b00,
        ST_GREEN  = 2'b01,
        ST_YELLOW = 2'b10
    } light_t;

    // ─── State and timer registers ─────────────────────────────────────────
    light_t                          state, next_state;
    logic [$clog2(HOLD_CYCLES)-1:0]  timer;
    logic                            timer_done;

    // ─── 1. State register ─────────────────────────────────────────────────
    always_ff @(posedge clk) begin
        if (rst) begin
            state <= ST_RED;
            timer <= HOLD_CYCLES[($clog2(HOLD_CYCLES)-1):0] - 1'b1;
        end else begin
            state <= next_state;
            if (timer_done)
                timer <= HOLD_CYCLES[($clog2(HOLD_CYCLES)-1):0] - 1'b1;
            else
                timer <= timer - 1'b1;
        end
    end

    // ─── 2. Combinational next-state + output logic ────────────────────────
    always_comb begin
        // --- defaults: prevent latches ---
        next_state = state;   // stay in current state by default
        led_red    = 1'b0;
        led_yellow = 1'b0;
        led_green  = 1'b0;
        timer_done = (timer == '0);

        case (state)
            ST_RED: begin
                led_red = 1'b1;
                if (timer_done) next_state = ST_GREEN;
            end

            ST_GREEN: begin
                led_green = 1'b1;
                if (timer_done) next_state = ST_YELLOW;
            end

            ST_YELLOW: begin
                led_yellow = 1'b1;
                if (timer_done) next_state = ST_RED;
            end

            // default: unreachable in a 3-state enum, but avoids lint warnings
            default: next_state = ST_RED;
        endcase
    end

    // Expose raw state encoding for waveform/testbench
    assign state_out = state;

endmodule
