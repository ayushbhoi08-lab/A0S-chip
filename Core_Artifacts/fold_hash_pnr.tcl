# Ansh-108 Core (S3) P&R -- Horner fold accumulator fold_hash (1-stage, feedback).
# Critical path is the combinational Horner step (const-mult 108 + two Barrett
# reducers + modular add) closing back on the h register -- expect a lower fmax
# than the bare add/sub lanes; logged honestly. opt_design wrapped in catch.
set TOP        fold_hash
set PART       xc7a35tcsg324-1
set RTL        fold_hash.v
set CLK_TARGET 6.000
set OUTDIR     ./fold_hash_out
file mkdir $OUTDIR

read_verilog $RTL
synth_design -top $TOP -part $PART -flatten_hierarchy rebuilt
report_utilization -file $OUTDIR/utilization_synth.rpt

create_clock -name clk -period $CLK_TARGET [get_ports clk]
set_input_delay  -clock clk 0.000 [get_ports {rst flush fold_en data[*]}]
set_output_delay -clock clk 0.000 [get_ports {h[*] out_valid}]

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
if {[llength $cp] == 0} { set cp [get_timing_paths -delay_type max -max_paths 1 -nworst 1] }
set wns      [get_property SLACK $cp]
set achieved [expr {$CLK_TARGET - $wns}]
set fmax     [expr {1000.0 / $achieved}]

set fh [open $OUTDIR/fmax.txt w]
puts $fh [format "core            = fold_hash (h<-(h*108+data) mod 12289, 1-stage)"]
puts $fh [format "part            = %s" $PART]
puts $fh [format "opt_design      = %s" [expr {$OPT_OK ? "applied" : "SKIPPED"}]]
puts $fh [format "target_period   = %.3f ns  (%.1f MHz probe)" $CLK_TARGET [expr {1000.0/$CLK_TARGET}]]
puts $fh [format "WNS (core setup)= %.3f ns" $wns]
puts $fh [format "achieved_period = %.3f ns" $achieved]
puts $fh [format "ROUTED FMAX     = %.1f MHz" $fmax]
puts $fh [format "1-cycle latency = %.2f ns" $achieved]
close $fh

puts [format "  fold_hash: ROUTED FMAX = %.1f MHz (period %.3f, WNS %.3f, opt %s)" \
        $fmax $achieved $wns [expr {$OPT_OK ? "applied" : "SKIPPED"}]]
write_checkpoint -force $OUTDIR/${TOP}_routed.dcp
