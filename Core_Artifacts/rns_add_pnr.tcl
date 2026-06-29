# Ansh-108 Core (S2) P&R -- modular adder rns_add (mod 12289, 2-stage).
# Same flow/part/probe as ntt_mul12289_pnr.tcl so fmax is directly comparable
# to the 12289 multiply lane (109.3 MHz). opt_design wrapped in catch (Vivado
# 2026.1 has flaked on opt_design before on this arc).
set TOP        rns_add
set PART       xc7a35tcsg324-1
set RTL        rns_add.v
set CLK_TARGET 4.000
set OUTDIR     ./rns_add_out
file mkdir $OUTDIR

read_verilog $RTL
synth_design -top $TOP -part $PART -flatten_hierarchy rebuilt
report_utilization -file $OUTDIR/utilization_synth.rpt

create_clock -name clk -period $CLK_TARGET [get_ports clk]
set_input_delay  -clock clk 0.000 [get_ports {rst in_valid x[*] y[*]}]
set_output_delay -clock clk 0.000 [get_ports {out[*] out_valid}]

set OPT_OK 1
if {[catch {opt_design} em]} {
    set OPT_OK 0
    puts "WARN: opt_design failed (\"$em\") -- continuing on post-synth netlist"
}

place_design
route_design

report_timing_summary -delay_type max -max_paths 10 -file $OUTDIR/timing_summary.rpt
report_utilization                                  -file $OUTDIR/utilization.rpt
report_timing -setup -max_paths 1 -nworst 1         -file $OUTDIR/worst_path.rpt

set cp [get_timing_paths -from [all_registers -edge_triggered] \
                         -to   [all_registers -edge_triggered] \
                         -delay_type max -max_paths 1 -nworst 1]
set wns      [get_property SLACK $cp]
set achieved [expr {$CLK_TARGET - $wns}]
set fmax     [expr {1000.0 / $achieved}]
set lat2     [expr {2.0 * $achieved}]

set fh [open $OUTDIR/fmax.txt w]
puts $fh [format "core            = rns_add ((x+y) mod 12289, branch-free, 2-stage)"]
puts $fh [format "part            = %s" $PART]
puts $fh [format "opt_design      = %s" [expr {$OPT_OK ? "applied" : "SKIPPED"}]]
puts $fh [format "target_period   = %.3f ns  (%.1f MHz probe)" $CLK_TARGET [expr {1000.0/$CLK_TARGET}]]
puts $fh [format "WNS (core setup)= %.3f ns" $wns]
puts $fh [format "achieved_period = %.3f ns" $achieved]
puts $fh [format "ROUTED FMAX     = %.1f MHz" $fmax]
puts $fh [format "2-cycle latency = %.2f ns" $lat2]
close $fh

puts "==================================================="
puts [format "  rns_add: opt_design = %s"            [expr {$OPT_OK ? "applied" : "SKIPPED"}]]
puts [format "  rns_add: ROUTED FMAX = %.1f MHz"     $fmax]
puts [format "  achieved period = %.3f ns (WNS %.3f)" $achieved $wns]
puts "==================================================="

write_checkpoint -force $OUTDIR/${TOP}_routed.dcp
