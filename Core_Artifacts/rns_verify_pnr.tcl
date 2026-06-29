# Ansh-108 Core (S3) P&R -- VERIFY equality comparator rns_verify (1-stage).
set TOP        rns_verify
set PART       xc7a35tcsg324-1
set RTL        rns_verify.v
set CLK_TARGET 4.000
set OUTDIR     ./rns_verify_out
file mkdir $OUTDIR

read_verilog $RTL
synth_design -top $TOP -part $PART -flatten_hierarchy rebuilt
report_utilization -file $OUTDIR/utilization_synth.rpt

create_clock -name clk -period $CLK_TARGET [get_ports clk]
set_input_delay  -clock clk 0.000 [get_ports {rst in_valid x[*] y[*]}]
set_output_delay -clock clk 0.000 [get_ports {out_eq out_valid}]

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
# rns_verify is a single comparator -> FF, so there is NO reg-to-reg path.
# Fall back to the worst overall path (input->reg). With I/O delay = 0 this is
# the comparator logic delay + pad; NOT directly comparable to the other cores'
# reg-to-reg fmax -- labelled as such.
if {[llength $cp] == 0} {
    set cp       [get_timing_paths -delay_type max -max_paths 1 -nworst 1]
    set pathkind "input->reg (no reg-to-reg path; I/O delay=0; comparator+pad)"
} else {
    set pathkind "core reg-to-reg"
}
set wns      [get_property SLACK $cp]
set achieved [expr {$CLK_TARGET - $wns}]
set fmax     [expr {1000.0 / $achieved}]

set fh [open $OUTDIR/fmax.txt w]
puts $fh [format "core            = rns_verify (x==y -> 1-bit flag, 1-stage)"]
puts $fh [format "part            = %s" $PART]
puts $fh [format "opt_design      = %s" [expr {$OPT_OK ? "applied" : "SKIPPED"}]]
puts $fh [format "path measured   = %s" $pathkind]
puts $fh [format "WNS             = %.3f ns" $wns]
puts $fh [format "achieved_period = %.3f ns" $achieved]
puts $fh [format "implied fmax    = %.1f MHz" $fmax]
puts $fh [format "1-cycle latency = %.2f ns" $achieved]
close $fh

puts [format "  rns_verify: implied fmax = %.1f MHz (%s, period %.3f, WNS %.3f, opt %s)" \
        $fmax $pathkind $achieved $wns [expr {$OPT_OK ? "applied" : "SKIPPED"}]]
write_checkpoint -force $OUTDIR/${TOP}_routed.dcp
