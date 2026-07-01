// =============================================================================
// M09 ex01 — axis_sequencer: no new behavior, just the item-type binding
// =============================================================================
//
// A sequencer's whole job is arbitrating which sequence's next item reaches
// the driver — `uvm_sequencer#(T)` already implements that. There's nothing
// to override here; the typedef exists only so the rest of the code has a
// named class to instantiate/reference instead of the raw parameterized
// type everywhere.
typedef uvm_sequencer #(axis_seq_item) axis_sequencer;
