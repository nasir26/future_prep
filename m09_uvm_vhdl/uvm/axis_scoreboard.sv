// =============================================================================
// M09 ex03 — axis_scoreboard: FIFO order-preserving comparison
// =============================================================================
//
// WHY TWO uvm_analysis_imp_decl'S INSTEAD OF ONE
//   A uvm_component can only have one `write()` method per base analysis-imp
//   type — but this scoreboard needs to tell "a beat arrived on the input
//   side" apart from "a beat arrived on the output side" (both are
//   axis_seq_item). `uvm_analysis_imp_decl(_expected)` /
//   `uvm_analysis_imp_decl(_actual)` mint two distinct imp classes
//   (uvm_analysis_imp_expected#(...), uvm_analysis_imp_actual#(...)), each
//   routing to its own named write method below. This is the standard UVM
//   idiom for "one component, two independently-connectable analysis
//   ports."
//
// WHY A QUEUE, NOT A COUNT
//   The FIFO is a strict in-order pipe: the Nth beat that comes OUT must
//   equal the Nth beat that went IN. A queue of "expected" items lets
//   write_actual() pop-and-compare against the oldest still-unmatched
//   expected item — catching reordering bugs a simple "count in == count
//   out" check would miss entirely.
//
`uvm_analysis_imp_decl(_expected)
`uvm_analysis_imp_decl(_actual)

class axis_scoreboard extends uvm_scoreboard;
    `uvm_component_utils(axis_scoreboard)

    uvm_analysis_imp_expected #(axis_seq_item, axis_scoreboard) expected_export;
    uvm_analysis_imp_actual   #(axis_seq_item, axis_scoreboard) actual_export;

    axis_seq_item expected_q[$];
    int unsigned  match_count;
    int unsigned  mismatch_count;

    function new(string name, uvm_component parent);
        super.new(name, parent);
        expected_export = new("expected_export", this);
        actual_export   = new("actual_export", this);
    endfunction

    function void write_expected(axis_seq_item item);
        expected_q.push_back(item);
    endfunction

    function void write_actual(axis_seq_item item);
        axis_seq_item exp;
        if (expected_q.size() == 0) begin
            `uvm_error("SCOREBOARD",
                $sformatf("beat arrived on output with nothing expected: data=0x%0h last=%0b",
                          item.data, item.last))
            mismatch_count++;
            return;
        end
        exp = expected_q.pop_front();
        if (exp.data !== item.data || exp.last !== item.last) begin
            `uvm_error("SCOREBOARD",
                $sformatf("MISMATCH — expected data=0x%0h last=%0b, got data=0x%0h last=%0b",
                          exp.data, exp.last, item.data, item.last))
            mismatch_count++;
        end else begin
            match_count++;
        end
    endfunction

    function void report_phase(uvm_phase phase);
        super.report_phase(phase);
        if (mismatch_count == 0 && expected_q.size() == 0 && match_count > 0)
            `uvm_info("SCOREBOARD",
                $sformatf("PASS — %0d beat(s) matched, 0 mismatches, 0 stuck in flight",
                          match_count), UVM_NONE)
        else
            `uvm_error("SCOREBOARD",
                $sformatf("FAIL — %0d matched, %0d mismatched, %0d never arrived",
                          match_count, mismatch_count, expected_q.size()))
    endfunction
endclass
