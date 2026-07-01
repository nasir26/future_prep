// =============================================================================
// M09 ex02 — axis_monitor: passively observes handshakes, broadcasts beats
// =============================================================================
//
// WHY THE MONITOR NEEDS NO axis_dir_e
//   Unlike the driver, a monitor never drives anything — it just watches
//   tvalid/tready/tdata/tlast and reports every completed beat (the AXI
//   rule: a beat transfers iff tvalid && tready on the same clock edge).
//   That rule is identical on both DUT ports, so one monitor class, bound
//   to either interface instance, does the job for both the "what went
//   in" side and the "what came out" side. The scoreboard is what gives
//   those two streams different meaning (see axis_scoreboard.sv).
//
class axis_monitor extends uvm_monitor;
    `uvm_component_utils(axis_monitor)

    virtual axis_if                    vif;
    uvm_analysis_port #(axis_seq_item) ap;

    function new(string name, uvm_component parent);
        super.new(name, parent);
        ap = new("ap", this);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual axis_if)::get(this, "", "vif", vif))
            `uvm_fatal("NOVIF", "axis_monitor: no virtual interface set for this component")
    endfunction

    task run_phase(uvm_phase phase);
        axis_seq_item item;
        forever begin
            @(vif.mon_cb);
            if (vif.mon_cb.tvalid && vif.mon_cb.tready) begin
                item      = axis_seq_item::type_id::create("item");
                item.data = vif.mon_cb.tdata;
                item.last = vif.mon_cb.tlast;
                ap.write(item);
            end
        end
    endtask
endclass
