# Ansh-N Core (Phase 5b) P&R -- DEEP-PIPELINED 5-dial core rns41580p.
# Same flow/part/probe as phase5_pnr_v2.tcl so the fmax is directly comparable
# to the flat rns41580 (118.7 MHz) and the 108-core (157.9 MHz). opt_design
# wrapped in catch (Vivado 2026.1 flaked once on the flat core).
set TOP        rns41580p
set PART       xc7a35tcsg324-1
set RTL        rns41580p.v
set CLK_PORT   clk
set CLK_TARGET 4.000
set OUTDIR     ./phase5p_out
file mkdir $OUTDIR

read_verilog $RTL
synth_design -top $TOP -part $PART -flatten_hierarchy rebuilt
report_utilization -file $OUTDIR/utilization_synth.rpt

create_clock -name clk -period $CLK_TARGET [get_ports $CLK_PORT]
set_input_delay  -clock clk 0.000 [get_ports {rst in_valid \
    x4[*] y4[*] x27[*] y27[*] x5[*] y5[*] x7[*] y7[*] x11[*] y11[*]}]
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

set core_path [get_timing_paths -from [all_registers -edge_triggered] \
                                -to   [all_registers -edge_triggered] \
                                -delay_type max -max_paths 1 -nworst 1]
set wns      [get_property SLACK $core_path]
set achieved [expr {$CLK_TARGET - $wns}]
set fmax     [expr {1000.0 / $achieved}]
set lat6     [expr {6.0 * $achieved}]

set fh [open $OUTDIR/fmax.txt w]
puts $fh [format "part            = %s" $PART]
puts $fh [format "opt_design      = %s" [expr {$OPT_OK ? "applied" : "SKIPPED"}]]
puts $fh [format "target_period   = %.3f ns  (%.1f MHz probe)" $CLK_TARGET [expr {1000.0/$CLK_TARGET}]]
puts $fh [format "WNS (core setup)= %.3f ns" $wns]
puts $fh [format "achieved_period = %.3f ns" $achieved]
puts $fh [format "ROUTED FMAX     = %.1f MHz" $fmax]
puts $fh [format "6-cycle latency = %.2f ns" $lat6]
close $fh

puts "==================================================="
puts [format "  opt_design       = %s" [expr {$OPT_OK ? "applied" : "SKIPPED"}]]
puts [format "  ROUTED FMAX      = %.1f MHz"            $fmax]
puts [format "  achieved period  = %.3f ns (WNS %.3f)"  $achieved $wns]
puts [format "  6-cycle latency  = %.2f ns"             $lat6]
puts "==================================================="

write_checkpoint -force $OUTDIR/${TOP}_routed.dcp
