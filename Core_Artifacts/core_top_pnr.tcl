# Ansh-108 Core (S4) P&R -- integrated core_top on xc7a35tcsg324-1 (Vivado 2026.1).
# Same flow/part/probe as the per-op P&R scripts so the integrated fmax is directly
# comparable to the bare datapath lanes. opt_design wrapped in catch (Vivado 2026.1
# has flaked on opt_design before on this arc). The reg-to-reg critical path is
# expected to be the fold_hash Horner feedback (the S3 limiter, ~41 MHz) since the
# integration adds only decode/mux/control around the already-proven datapath.
set TOP        core_top
set PART       xc7a35tcsg324-1
set RTL        {core_top.v opcode_decode.v result_mode.v rns_reduce.v tick_counter.v \
                ntt_mul12289.v rns_add.v rns_sub.v rns_verify.v fold_hash.v}
set CLK_TARGET 8.000
set OUTDIR     ./core_top_out
file mkdir $OUTDIR

read_verilog $RTL
synth_design -top $TOP -part $PART -flatten_hierarchy rebuilt
report_utilization -file $OUTDIR/utilization_synth.rpt

create_clock -name clk -period $CLK_TARGET [get_ports clk]
set_input_delay  -clock clk 0.000 [get_ports {rst in_valid read_ack packet[*]}]
set_output_delay -clock clk 0.000 [get_ports {out[*] out_valid result_ready busy bindu \
                                              opcode_echo[*] res_mode[*] tick0[*] tick1[*] tick2[*]}]

set OPT_OK 1
if {[catch {opt_design} em]} {
    set OPT_OK 0
    puts "WARN: opt_design failed (\"$em\") -- continuing on post-synth netlist"
}

place_design
route_design

report_timing_summary -delay_type max -max_paths 10 -file $OUTDIR/timing_summary.rpt
report_utilization                                  -file $OUTDIR/utilization.rpt
report_timing -setup -max_paths 5 -nworst 5         -file $OUTDIR/worst_path.rpt

set cp [get_timing_paths -from [all_registers -edge_triggered] \
                         -to   [all_registers -edge_triggered] \
                         -delay_type max -max_paths 1 -nworst 1]
if {[llength $cp] == 0} { set cp [get_timing_paths -delay_type max -max_paths 1 -nworst 1] }
set wns      [get_property SLACK $cp]
set achieved [expr {$CLK_TARGET - $wns}]
set fmax     [expr {1000.0 / $achieved}]

set fh [open $OUTDIR/fmax.txt w]
puts $fh [format "core            = core_top (integrated Path-A: decode+datapath+FSM+tick)"]
puts $fh [format "part            = %s" $PART]
puts $fh [format "opt_design      = %s" [expr {$OPT_OK ? "applied" : "SKIPPED"}]]
puts $fh [format "target_period   = %.3f ns  (%.1f MHz probe)" $CLK_TARGET [expr {1000.0/$CLK_TARGET}]]
puts $fh [format "WNS (core setup)= %.3f ns" $wns]
puts $fh [format "achieved_period = %.3f ns" $achieved]
puts $fh [format "ROUTED FMAX     = %.1f MHz" $fmax]
close $fh

puts "==================================================="
puts [format "  core_top: opt_design = %s"           [expr {$OPT_OK ? "applied" : "SKIPPED"}]]
puts [format "  core_top: ROUTED FMAX = %.1f MHz"     $fmax]
puts [format "  achieved period = %.3f ns (WNS %.3f)" $achieved $wns]
puts "==================================================="

write_checkpoint -force $OUTDIR/${TOP}_routed.dcp
