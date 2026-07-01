// =============================================================================
// M09 ex04 — test classes: pair a producer sequence with a consumer sequence
// =============================================================================
//
// WHY axis_base_test EXISTS SEPARATELY FROM ITS TWO CHILDREN
//   Every test needs the same env built and the same vif config_db wiring;
//   only "which sequences run, and with what knobs" differs between the
//   smoke test and the random test. Factoring that shared setup into
//   axis_base_test means axis_smoke_test/axis_random_test are each just a
//   run_phase — the part that actually differs.
//
class axis_base_test extends uvm_test;
    `uvm_component_utils(axis_base_test)

    axis_env env;

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        env = axis_env::type_id::create("env", this);
    endfunction

    // WHY THIS IS A WAIT-FOR-CONDITION, NOT A FIXED #delay
    //   A fixed drain time has to be sized for the *worst-case* remaining
    //   backpressure across every item still in flight when the producer
    //   sequence finishes — with per-item ready_delay randomized up to 4
    //   cycles, that worst case isn't obvious, and getting it wrong reads
    //   as a scoreboard "beat never arrived" failure that looks like a DUT
    //   bug but is really just an impatient testbench (this is exactly
    //   what happened while bringing this test up: a fixed #200ns dropped
    //   the objection one beat before the last, slowly-throttled item
    //   drained). Waiting on the scoreboard's own expected_q — the actual
    //   "is everything accounted for" signal — is correct regardless of
    //   how much backpressure the random seed happens to generate; the
    //   fork/join_any timeout is only a safety net against a real hang.
    task drain(int unsigned timeout_ns = 5000);
        fork
            wait (env.sb.expected_q.size() == 0);
            begin
                #(timeout_ns * 1ns);
                `uvm_error("DRAIN_TIMEOUT",
                    $sformatf("%0d beat(s) still unaccounted for after %0dns",
                              env.sb.expected_q.size(), timeout_ns))
            end
        join_any
        disable fork;
        #20ns;   // let the last beat's monitor sample land
    endtask
endclass

// ── ex04a: directed smoke test — one packet, consumer always ready ─────────
class axis_smoke_test extends axis_base_test;
    `uvm_component_utils(axis_smoke_test)

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    task run_phase(uvm_phase phase);
        axis_packet_seq   prod_seq;
        axis_consumer_seq cons_seq;

        phase.raise_objection(this);

        cons_seq = axis_consumer_seq::type_id::create("cons_seq");
        cons_seq.num_items = 50;
        cons_seq.throttle  = 0;
        fork
            cons_seq.start(env.consumer_agent.sqr);
        join_none

        prod_seq = axis_packet_seq::type_id::create("prod_seq");
        prod_seq.num_beats = 8;
        prod_seq.start(env.producer_agent.sqr);

        drain();
        phase.drop_objection(this);
    endtask
endclass

// ── ex04b: random regression — many packets, randomized backpressure ───────
class axis_random_test extends axis_base_test;
    `uvm_component_utils(axis_random_test)

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    task run_phase(uvm_phase phase);
        axis_multi_packet_seq prod_seq;
        axis_consumer_seq     cons_seq;

        phase.raise_objection(this);

        cons_seq = axis_consumer_seq::type_id::create("cons_seq");
        cons_seq.num_items = 500;
        cons_seq.throttle  = 1;
        fork
            cons_seq.start(env.consumer_agent.sqr);
        join_none

        prod_seq = axis_multi_packet_seq::type_id::create("prod_seq");
        prod_seq.num_packets = 20;
        prod_seq.max_beats   = 16;
        prod_seq.start(env.producer_agent.sqr);

        drain();
        phase.drop_objection(this);
    endtask
endclass
