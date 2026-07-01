// =============================================================================
// M09 ex04 — sequence library: what to send, decoupled from how to send it
// =============================================================================
//
// WHY producer/consumer SEQUENCES DON'T KNOW ABOUT EACH OTHER
//   axis_packet_seq only knows "send N beats, tlast on the last one" — it
//   has no idea whether the consumer side is throttling or wide open.
//   axis_consumer_seq only knows "accept N beats with these delays" — it
//   has no idea how many packets the producer is sending or how long they
//   are. A test class (axis_tests.sv) is what pairs one producer sequence
//   with one consumer sequence and runs them concurrently. This
//   separation is *the* reason UVM sequences exist instead of just writing
//   one big directed task per test: the same axis_packet_seq gets reused
//   by both the smoke test and the random test, only the consumer side
//   (throttled vs. not) changes.
//
class axis_packet_seq extends uvm_sequence #(axis_seq_item);
    `uvm_object_utils(axis_packet_seq)

    int unsigned num_beats = 8;   // set by the test before start()

    function new(string name = "axis_packet_seq");
        super.new(name);
    endfunction

    task body();
        axis_seq_item item;
        for (int i = 0; i < num_beats; i++) begin
            item = axis_seq_item::type_id::create($sformatf("item_%0d", i));
            start_item(item);
            item.randomize() with {
                last == (i == num_beats - 1);
            };
            finish_item(item);
        end
    endtask
endclass

// Repeats axis_packet_seq num_packets times, each with a randomized length
// in [1:max_beats] — this is what gives the random test packet-boundary
// coverage that a single fixed-length packet can't.
class axis_multi_packet_seq extends uvm_sequence #(axis_seq_item);
    `uvm_object_utils(axis_multi_packet_seq)

    int unsigned num_packets = 10;
    int unsigned max_beats   = 16;

    function new(string name = "axis_multi_packet_seq");
        super.new(name);
    endfunction

    task body();
        axis_packet_seq pkt;
        for (int p = 0; p < num_packets; p++) begin
            pkt = axis_packet_seq::type_id::create($sformatf("pkt_%0d", p));
            if (!pkt.randomize() with { num_beats inside {[1:max_beats]}; })
                `uvm_fatal("RANDFAIL", "axis_multi_packet_seq: pkt.randomize failed")
            pkt.start(m_sequencer, this);
        end
    endtask
endclass

// Consumer-side sequence: `throttle=0` gives an "always ready" driver
// (ready_delay forced to 0 every item) for directed/smoke tests where
// backpressure isn't the thing under test; `throttle=1` randomizes
// ready_delay per item for the random-backpressure regression.
class axis_consumer_seq extends uvm_sequence #(axis_seq_item);
    `uvm_object_utils(axis_consumer_seq)

    int unsigned num_items = 500;   // sized generously; extra items just
                                    // block harmlessly until the phase ends
    bit          throttle  = 1;

    function new(string name = "axis_consumer_seq");
        super.new(name);
    endfunction

    task body();
        axis_seq_item item;
        for (int i = 0; i < num_items; i++) begin
            item = axis_seq_item::type_id::create($sformatf("cons_%0d", i));
            start_item(item);
            if (throttle) item.randomize();
            else          item.ready_delay = 0;
            finish_item(item);
        end
    endtask
endclass
