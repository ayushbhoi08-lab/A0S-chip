# ============================================================================
# Ansh-N Core (Phase 5) : Vivado Place & Route + Timing Closure
# Run:  vivado -mode batch -source phase5_pnr.tcl
# Measures the ABSOLUTE routed fmax for the 5-modulus RNS transform over
# Z/41580 on the SAME Artix-7 part as the 108-core, for a direct comparison.
# Free Vivado WebPACK supports all Artix-7 parts -- no paid licence needed.
# (Leave XILINXD_LICENSE_FILE UNSET so free-mode fallback engages.)
# ============================================================================

set TOP        rns41580
set PART       xc7a35tcsg324-1
set RTL        rns41580.v
set CLK_PORT   clk
set CLK_TARGET 4.000                  ;# ns probe; fmax is DERIVED from slack
set OUTDIR     ./phase5_out
file mkdir $OUTDIR

read_verilog $RTL
synth_design -top $TOP -part $PART -flatten_hierarchy rebuilt

create_clock -name clk -period $CLK_TARGET [get_ports $CLK_PORT]
set_input_delay  -clock clk 0.000 [get_ports {rst in_valid \
    x4[*] y4[*] x27[*] y27[*] x5[*] y5[*] x7[*] y7[*] x11[*] y11[*]}]
set_output_delay -clock clk 0.000 [get_ports {out[*] out_valid}]

opt_design
place_design
route_design

report_timing_summary -delay_type max -max_paths 10 -file $OUTDIR/timing_summary.rpt
report_utilization                                  -file $OUTDIR/utilization.rpt
report_timing -setup -max_paths 1 -nworst 1         -file $OUTDIR/worst_path.rpt

# routed fmax from the CORE reg-to-reg worst slack (ignore unconstrained I/O)
set core_path [get_timing_paths -from [all_registers -edge_triggered] \
                                -to   [all_registers -edge_triggered] \
                                -delay_type max -max_paths 1 -nworst 1]
set wns      [get_property SLACK $core_path]
set achieved [expr {$CLK_TARGET - $wns}]
set fmax     [expr {1000.0 / $achieved}]
set lat4     [expr {4.0 * $achieved}]

set fh [open $OUTDIR/fmax.txt w]
puts $fh [format "part            = %s" $PART]
puts $fh [format "target_period   = %.3f ns  (%.1f MHz probe)" $CLK_TARGET [expr {1000.0/$CLK_TARGET}]]
puts $fh [format "WNS (core setup)= %.3f ns" $wns]
puts $fh [format "achieved_period = %.3f ns" $achieved]
puts $fh [format "ROUTED FMAX     = %.1f MHz" $fmax]
puts $fh [format "4-cycle latency = %.2f ns" $lat4]
close $fh

puts "==================================================="
puts [format "  ROUTED FMAX      = %.1f MHz"            $fmax]
puts [format "  achieved period  = %.3f ns (WNS %.3f)"  $achieved $wns]
puts [format "  4-cycle latency  = %.2f ns"             $lat4]
puts "==================================================="

write_checkpoint -force $OUTDIR/${TOP}_routed.dcp
