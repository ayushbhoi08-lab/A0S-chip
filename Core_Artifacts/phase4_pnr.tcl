# ============================================================================
# Ansh-108 Core -- Phase 4 : Vivado Place & Route + Timing Closure
# Run:  vivado -mode batch -source phase4_pnr.tcl
# Produces the ABSOLUTE routed fmax for the RNS-108 transform on Artix-7,
# and converts it to the hard 4-cycle serial-latency nanosecond figure.
# Free Vivado WebPACK (Standard Edition) supports all Artix-7 parts -- no
# paid licence needed.
# ============================================================================

# ---------------- user knobs ----------------
set TOP        rns108
set PART       xc7a35tcsg324-1        ;# Arty A7-35T : a common consumer Artix-7, -1 speed grade
set RTL        rns108.v               ;# the Phase-2 RTL (already verified, 0 errors)
set CLK_PORT   clk
set CLK_TARGET 4.000                  ;# ns target (250 MHz). fmax is DERIVED from slack,
                                      ;# so this is just a probe -- any value works.
set OUTDIR     ./phase4_out
file mkdir $OUTDIR

# ---------------- 1. read + synthesize ----------------
read_verilog $RTL
synth_design -top $TOP -part $PART -flatten_hierarchy rebuilt

# ---------------- 2. clock + I/O constraints (self-contained, no board XDC) ----------------
create_clock -name clk -period $CLK_TARGET [get_ports $CLK_PORT]
# constrain the non-clock I/O so they are timed (explicit lists; avoids
# remove_from_collection which isn't available in this Tcl context)
set_input_delay  -clock clk 0.000 [get_ports {rst in_valid x[*] y[*]}]
set_output_delay -clock clk 0.000 [get_ports {out[*] out_valid}]

# ---------------- 3. implementation : opt -> place -> route ----------------
opt_design
place_design
route_design

# ---------------- 4. strict timing + utilization reports ----------------
report_timing_summary -delay_type max -max_paths 10 -file $OUTDIR/timing_summary.rpt
report_utilization                                  -file $OUTDIR/utilization.rpt
report_timing -setup -max_paths 1 -nworst 1         -file $OUTDIR/worst_path.rpt

# ---------------- 5. extract routed fmax from the CORE reg-to-reg worst slack ----------------
# isolate the true core critical path (FF -> FF), not unconstrained I/O paths
set core_path [get_timing_paths -from [all_registers -edge_triggered] \
                                -to   [all_registers -edge_triggered] \
                                -delay_type max -max_paths 1 -nworst 1]
set wns      [get_property SLACK $core_path]
set achieved [expr {$CLK_TARGET - $wns}]     ;# ns  (wns<0 => slower than target, wns>0 => room to spare)
set fmax     [expr {1000.0 / $achieved}]     ;# MHz
set lat4     [expr {4.0 * $achieved}]        ;# ns  -- the 4-cycle serial (asiddha) latency

# ---------------- 6. report the verdict ----------------
set fh [open $OUTDIR/fmax.txt w]
puts $fh [format "part            = %s" $PART]
puts $fh [format "target_period   = %.3f ns  (%.1f MHz probe)" $CLK_TARGET [expr {1000.0/$CLK_TARGET}]]
puts $fh [format "WNS (core setup)= %.3f ns" $wns]
puts $fh [format "achieved_period = %.3f ns" $achieved]
puts $fh [format "ROUTED FMAX     = %.1f MHz" $fmax]
puts $fh [format "4-cycle latency = %.2f ns" $lat4]
close $fh

puts "==================================================="
puts [format "  ROUTED FMAX      = %.1f MHz"        $fmax]
puts [format "  achieved period  = %.3f ns (WNS %.3f)" $achieved $wns]
puts [format "  4-cycle latency  = %.2f ns"         $lat4]
puts "==================================================="

write_checkpoint -force $OUTDIR/${TOP}_routed.dcp
# To use the Yosys netlist instead of re-synthesizing, replace the read_verilog +
# synth_design lines with:  read_edif rns108.edif ; link_design -part $PART -top $TOP
