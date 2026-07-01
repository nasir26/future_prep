// =============================================================================
// M09 ex02 — axis_agent: bundles sequencer+driver+monitor, owns the config
// =============================================================================
//
// WHY THE AGENT (NOT THE ENV) SETS mode AND vif
//   The env (axis_env.sv) knows it needs "a producer" and "a consumer" —
//   it should not need to know that "producer" means DRIVE_PRODUCER on a
//   shared driver class, or which virtual-interface handle goes where.
//   Pushing `mode`/`vif` down through the agent's own build_phase (using
//   uvm_config_db with `get_full_name()` as scope) keeps that wiring local
//   to the agent, so the env's build_phase stays a two-line "new the two
//   agents" — the standard UVM information-hiding split between agent and
//   env.
//
class axis_agent extends uvm_agent;
    `uvm_component_utils(axis_agent)

    axis_dir_e     mode;
    virtual axis_if vif;

    axis_sequencer sqr;
    axis_driver    drv;
    axis_monitor   mon;

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);

        if (!uvm_config_db#(axis_dir_e)::get(this, "", "mode", mode))
            `uvm_fatal("NOMODE", "axis_agent: no axis_dir_e mode set for this component")
        if (!uvm_config_db#(virtual axis_if)::get(this, "", "vif", vif))
            `uvm_fatal("NOVIF", "axis_agent: no virtual interface set for this component")

        // Push mode/vif down to whichever children get built below — scoped
        // to this agent's own hierarchy so two agent instances never clash.
        uvm_config_db#(axis_dir_e)::set(this, "*", "mode", mode);
        uvm_config_db#(virtual axis_if)::set(this, "*", "vif", vif);

        mon = axis_monitor::type_id::create("mon", this);
        if (is_active == UVM_ACTIVE) begin
            sqr = axis_sequencer::type_id::create("sqr", this);
            drv = axis_driver::type_id::create("drv", this);
        end
    endfunction

    function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);
        if (is_active == UVM_ACTIVE)
            drv.seq_item_port.connect(sqr.seq_item_export);
    endfunction
endclass
