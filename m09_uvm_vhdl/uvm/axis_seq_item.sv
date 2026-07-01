// =============================================================================
// M09 ex01 — axis_seq_item: the one transaction class both sides share
// =============================================================================
//
// WHY data/last AND ready_delay LIVE IN THE SAME CLASS
//   A UVM sequence item is "whatever a driver needs to produce one unit of
//   driving work." The producer driver needs {data, last} (what to put on
//   the bus). The consumer driver needs {ready_delay} (how long to withhold
//   tready before accepting the next beat — i.e. backpressure). Splitting
//   these into two item classes would mean two sequencer/driver/sequence
//   type parameterizations for what is conceptually "one AXI-Stream agent."
//   Instead: one item, one field set, and each driver simply ignores the
//   fields it doesn't need (the producer driver never reads ready_delay).
//
class axis_seq_item extends uvm_sequence_item;
    rand bit [7:0]        data;
    rand bit              last;
    rand int unsigned     ready_delay;   // cycles the consumer holds tready=0

    // Keep ready_delay small — this is backpressure *density*, not a timeout
    // test. Large gaps just make waveforms tedious to read without adding
    // coverage.
    constraint ready_delay_c { ready_delay inside {[0:4]}; }

    `uvm_object_utils_begin(axis_seq_item)
        `uvm_field_int(data,        UVM_ALL_ON)
        `uvm_field_int(last,        UVM_ALL_ON)
        `uvm_field_int(ready_delay, UVM_ALL_ON)
    `uvm_object_utils_end

    function new(string name = "axis_seq_item");
        super.new(name);
    endfunction
endclass
