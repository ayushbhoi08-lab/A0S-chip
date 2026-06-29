set TOP ntt_mul12289
set PART xc7a35tcsg324-1
set CLK_TARGET 4.000
set OUTDIR ./ntt12289_out
file mkdir $OUTDIR
read_verilog ntt_mul12289.v
synth_design -top $TOP -part $PART -flatten_hierarchy rebuilt
report_utilization -file $OUTDIR/utilization.rpt
create_clock -name clk -period $CLK_TARGET [get_ports clk]
set_input_delay  -clock clk 0.000 [get_ports {rst in_valid x[*] y[*]}]
set_output_delay -clock clk 0.000 [get_ports {out[*] out_valid}]
if {[catch {opt_design} em]} { puts "WARN opt_design: $em" }
place_design
route_design
report_utilization -file $OUTDIR/utilization.rpt
set cp [get_timing_paths -from [all_registers -edge_triggered] -to [all_registers -edge_triggered] -delay_type max -max_paths 1 -nworst 1]
set wns [get_property SLACK $cp]
set ach [expr {$CLK_TARGET - $wns}]
set fh [open $OUTDIR/fmax.txt w]
puts $fh [format "core            = ntt_mul12289 (NTT prime q=12289, Barrett)"]
puts $fh [format "WNS (core setup)= %.3f ns" $wns]
puts $fh [format "achieved_period = %.3f ns" $ach]
puts $fh [format "ROUTED FMAX     = %.1f MHz" [expr {1000.0/$ach}]]
puts $fh [format "4-cycle latency = %.2f ns" [expr {4.0*$ach}]]
close $fh
puts [format "  ntt_mul12289: ROUTED FMAX = %.1f MHz (period %.3f, WNS %.3f)" [expr {1000.0/$ach}] $ach $wns]
