#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parameterized generator for the Ansh-N flat RNS core (fmax-vs-dials study).
Given any prefix of the coprime moduli, it (a) verifies the CRT bijection
exhaustively, (b) computes idempotents, and (c) emits an architecturally
IDENTICAL flat 4-stage core + testbench + formal harness + sby + synth.ys +
pnr.tcl. Every dial-count point on the curve uses the same arithmetic recombine
(uniform MUL-ROM per track -> sum -> compare-ladder + subtract), so the only
variable is the NUMBER OF DIALS.

Usage:  python gen_rns.py <name> <m0> <m1> ...
        python gen_rns.py rns540 4 27 5
"""
import sys
from math import gcd
from functools import reduce

def bitlen(n):
    return max(1, n.bit_length())

def emit(name, mods):
    k = len(mods)
    M = reduce(lambda a, b: a * b, mods)
    # pairwise coprime
    for i in range(k):
        for j in range(i + 1, k):
            assert gcd(mods[i], mods[j]) == 1, f"{mods[i]},{mods[j]} not coprime"
    # idempotents
    idem = []
    for m_i in mods:
        Mi = M // m_i
        e_i = (Mi * pow(Mi % m_i, -1, m_i)) % M
        assert e_i % m_i == 1 and all(e_i % m_j == 0 for m_j in mods if m_j != m_i)
        idem.append(e_i)
    # exhaustive bijection check
    seen = set()
    for x in range(M):
        t = tuple(x % m for m in mods)
        assert t not in seen and sum(e * r for e, r in zip(idem, t)) % M == x
        seen.add(t)
    assert len(seen) == M

    in_w   = [bitlen(m - 1) for m in mods]
    prod_w = [bitlen((m - 1) * (m - 1)) for m in mods]
    out_w  = bitlen(M - 1)
    sum_max = k * (M - 1)
    sum_w  = bitlen(sum_max)
    max_q  = (2**sum_w - 1) // M

    def ports():
        L = []
        for i, m in enumerate(mods):
            L.append(f"    input  [{in_w[i]-1}:0] x{m}, y{m},   // residue mod {m}")
        return "\n".join(L)

    # ---- core ----
    v = []
    v.append("`timescale 1ns/1ps")
    v.append(f"// Ansh-N flat RNS core over Z/{M} = " + " x ".join(f"Z/{m}" for m in mods))
    v.append(f"//   {k} coprime dials, {M} states. Uniform arithmetic recombine")
    v.append("//   (per-track MUL-ROM -> weighted-term ROM -> sum -> compare-ladder")
    v.append("//   + subtract). 4-stage pipeline, latency 4, throughput 1/cycle.")
    v.append(f"//   idempotents e = {idem} (verified by gen_rns.py: exhaustive CRT bijection).")
    v.append(f"module {name} (")
    v.append("    input             clk,")
    v.append("    input             rst,")
    v.append("    input             in_valid,")
    v.append(ports())
    v.append("    output reg        out_valid,")
    v.append(f"    output reg [{out_w-1}:0] out")
    v.append(");")
    v.append(f"    localparam [{sum_w}:0] M = {sum_w+1}'d{M};")
    v.append("    integer k;")
    # ROMs
    for i, m in enumerate(mods):
        depth = 2**prod_w[i]
        v.append(f"    reg [{in_w[i]-1}:0] MUL{m} [0:{depth-1}];   // p -> p % {m}")
    for i, m in enumerate(mods):
        v.append(f"    reg [{out_w-1}:0] W{m} [0:{m-1}];   // r -> (e*r) % M")
    v.append("    initial begin")
    for i, m in enumerate(mods):
        depth = 2**prod_w[i]
        v.append(f"        for (k=0;k<{depth};k=k+1) MUL{m}[k] = k % {m};")
    for i, m in enumerate(mods):
        v.append(f"        for (k=0;k<{m};k=k+1) W{m}[k] = ({idem[i]}*k) % {M};")
    v.append("    end")
    # valid chain (4-stage)
    v.append("    reg v1,v2,v3;")
    v.append("    always @(posedge clk) begin")
    v.append("        v1<=rst?1'b0:in_valid; v2<=rst?1'b0:v1; v3<=rst?1'b0:v2;")
    v.append("    end")
    # S1 products
    v.append("    // S1: track products")
    for i, m in enumerate(mods):
        v.append(f"    reg [{prod_w[i]-1}:0] p{m}_1;")
    v.append("    always @(posedge clk) begin")
    for m in mods:
        v.append(f"        p{m}_1 <= x{m} * y{m};")
    v.append("    end")
    # S2 reduce
    v.append("    // S2: LUT reduce each track")
    for i, m in enumerate(mods):
        v.append(f"    reg [{in_w[i]-1}:0] m{m}_2;")
    v.append("    always @(posedge clk) begin")
    for m in mods:
        v.append(f"        m{m}_2 <= MUL{m}[p{m}_1];")
    v.append("    end")
    # S3 weighted sum
    v.append("    // S3: weighted-term ROM + sum")
    v.append(f"    reg [{sum_w-1}:0] sum_3;")
    v.append("    always @(posedge clk)")
    v.append("        sum_3 <= " + " + ".join(f"W{m}[m{m}_2]" for m in mods) + ";")
    # S4 reduce
    v.append("    // S4: final reduce mod M (compare-ladder + subtract)")
    v.append(f"    wire [{sum_w-1}:0] s = sum_3;")
    ladder = "    wire [%d:0] q =" % (bitlen(max_q) - 1)
    rungs = []
    for q in range(max_q, 0, -1):
        rungs.append(f"(s >= {q}*M) ? {bitlen(max_q)}'d{q} :")
    ladder += " " + " ".join(rungs) + f" {bitlen(max_q)}'d0;"
    v.append(ladder)
    v.append("    always @(posedge clk) begin")
    v.append(f"        out <= (s - q*M);")
    v.append("        out_valid <= rst?1'b0:v3;")
    v.append("    end")
    v.append("endmodule")
    core = "\n".join(v) + "\n"

    # ---- formal harness ----
    f = []
    f.append(f"// Formal harness for {name}: per-track residue correctness (CRT-complete),")
    f.append("// no wide multiply reaches the solver. P1 out<M, P2 4-cycle latency,")
    f.append(f"// P3 out===(x_i*y_i) mod m_i for all {k} dials.")
    f.append(f"module {name}_formal (")
    f.append("    input clk, input rst, input in_valid,")
    f.append("\n".join(f"    input  [{in_w[i]-1}:0] x{m}, y{m}," for i, m in enumerate(mods)))
    f.append("    output dummy);")
    f.append("    wire out_valid;")
    f.append(f"    wire [{out_w-1}:0] out;")
    f.append("    assign dummy = 1'b0;")
    f.append(f"    {name} dut(.clk(clk),.rst(rst),.in_valid(in_valid),")
    f.append("        " + ", ".join(f".x{m}(x{m}),.y{m}(y{m})" for m in mods) + ",")
    f.append("        .out_valid(out_valid),.out(out));")
    f.append("    always @(posedge clk) begin")
    for m in mods:
        f.append(f"        assume(x{m}<{m}); assume(y{m}<{m});")
    f.append("    end")
    f.append("    initial assume(rst);")
    f.append("    reg started=1'b0; always @(posedge clk) started<=1'b1;")
    f.append(f"    always @(posedge clk) if (started) assert (out < {M});")
    f.append("    reg v1,v2,v3,v4;")
    f.append("    always @(posedge clk) begin")
    f.append("        v1<=rst?1'b0:in_valid; v2<=rst?1'b0:v1; v3<=rst?1'b0:v2; v4<=rst?1'b0:v3;")
    f.append("    end")
    f.append("    always @(posedge clk) if (started) assert (out_valid == v4);")
    # expected residues
    for i, m in enumerate(mods):
        ew = bitlen((m - 1) * (m - 1))
        f.append(f"    wire [{ew-1}:0] e{m} = (x{m}*y{m}) % {m};")
    for i, m in enumerate(mods):
        ew = bitlen((m - 1) * (m - 1))
        f.append(f"    reg [{ew-1}:0] e{m}_1,e{m}_2,e{m}_3,e{m}_4;")
    f.append("    always @(posedge clk) begin")
    for m in mods:
        f.append(f"        e{m}_1<=e{m}; e{m}_2<=e{m}_1; e{m}_3<=e{m}_2; e{m}_4<=e{m}_3;")
    f.append("    end")
    f.append("    always @(posedge clk) if (started && v4) begin")
    for m in mods:
        f.append(f"        assert ((out % {m}) == e{m}_4);")
    f.append("    end")
    f.append("endmodule")
    formal = "\n".join(f) + "\n"

    # ---- testbench ----
    drives = "\n".join(
        f"            x{m} <= xi % {m}; y{m} <= yi % {m};" for m in mods)
    tb = f"""`timescale 1ns/1ps
// Self-checking TB for {name} ({k}-dial, Z/{M}). Random integer operands ->
// residue tuples; checks reconstructed product vs true (x*y) mod {M}.
module tb;
    localparam integer M = {M};
    localparam integer NTEST = 200000;
    reg clk=0, rst=1, in_valid=0;
{chr(10).join(f"    reg [{in_w[i]-1}:0] x{m}, y{m};" for i,m in enumerate(mods))}
    wire out_valid; wire [{out_w-1}:0] out;
    {name} dut(.clk(clk),.rst(rst),.in_valid(in_valid),
        {", ".join(f".x{m}(x{m}),.y{m}(y{m})" for m in mods)},
        .out_valid(out_valid),.out(out));
    always #0.5 clk=~clk;
    reg [31:0] cx=0, cy=0;
    function [{out_w-1}:0] goldp(input [31:0] xx, input [31:0] yy); goldp=(xx*yy)%M; endfunction
    reg [{out_w-1}:0] e1,e2,e3,e4; reg ev1,ev2,ev3,ev4;
    always @(posedge clk) begin
        e1<=goldp(cx,cy); ev1<=rst?1'b0:in_valid;
        e2<=e1; ev2<=rst?1'b0:ev1; e3<=e2; ev3<=rst?1'b0:ev2; e4<=e3; ev4<=rst?1'b0:ev3;
    end
    integer cyc=0; always @(posedge clk) cyc=cyc+1;
    integer n=0, errors=0, first_in=-1, first_out=-1;
    always @(posedge clk) begin
        if (in_valid && first_in<0) first_in=cyc;
        if (out_valid && first_out<0) first_out=cyc;
        if (out_valid) begin
            n=n+1;
            if (out!==e4) begin errors=errors+1;
                if (errors<=5) $display("  MISMATCH n=%0d out=%0d exp=%0d", n, out, e4); end
        end
    end
    task drive(input [31:0] xi, input [31:0] yi);
        begin
            @(posedge clk); in_valid<=1; cx<=xi; cy<=yi;
{drives}
        end
    endtask
    integer i; reg [31:0] rx, ry;
    initial begin
        repeat(4) @(posedge clk); rst<=0; @(posedge clk);
        drive(0,0); drive(1,1); drive(M-1,M-1); drive(M-1,2); drive(M/2,M/3); drive(M-1,0);
        for (i=0;i<NTEST;i=i+1) begin rx=$random; ry=$random; rx=rx%M; ry=ry%M; drive(rx,ry); end
        @(posedge clk); in_valid<=0; repeat(8) @(posedge clk);
        $display("=== {name}  [{k} dials, Z/{M}] ===");
        $display(" checked=%0d  mismatches=%0d  latency=%0d cyc", n, errors, first_out-first_in);
        $finish;
    end
endmodule
"""

    sby = f"""[options]
mode bmc
depth 12

[engines]
smtbmc boolector

[script]
read_verilog -formal {name}.v {name}_formal.v
prep -top {name}_formal

[files]
{name}.v
{name}_formal.v
"""

    ys = f"read_verilog {name}.v\nsynth_xilinx -family xc7 -top {name}\nstat\nltp\n"

    portlist = " ".join(f"x{m}[*] y{m}[*]" for m in mods)
    pnr = f"""# P&R for {name} ({k}-dial Z/{M}); same flow/part/probe as the rest of the curve.
set TOP {name}
set PART xc7a35tcsg324-1
set RTL {name}.v
set CLK_TARGET 4.000
set OUTDIR ./{name}_out
file mkdir $OUTDIR
read_verilog $RTL
synth_design -top $TOP -part $PART -flatten_hierarchy rebuilt
create_clock -name clk -period $CLK_TARGET [get_ports clk]
set_input_delay  -clock clk 0.000 [get_ports {{rst in_valid {portlist}}}]
set_output_delay -clock clk 0.000 [get_ports {{out[*] out_valid}}]
if {{[catch {{opt_design}} em]}} {{ puts "WARN opt_design: $em" }}
place_design
route_design
report_utilization -file $OUTDIR/utilization.rpt
set cp [get_timing_paths -from [all_registers -edge_triggered] -to [all_registers -edge_triggered] -delay_type max -max_paths 1 -nworst 1]
set wns [get_property SLACK $cp]
set ach [expr {{$CLK_TARGET - $wns}}]
set fmax [expr {{1000.0/$ach}}]
set fh [open $OUTDIR/fmax.txt w]
puts $fh [format "core            = {name} ({k} dials, Z/{M})"]
puts $fh [format "WNS (core setup)= %.3f ns" $wns]
puts $fh [format "achieved_period = %.3f ns" $ach]
puts $fh [format "ROUTED FMAX     = %.1f MHz" $fmax]
puts $fh [format "4-cycle latency = %.2f ns" [expr {{4.0*$ach}}]]
close $fh
puts [format "  {name}: ROUTED FMAX = %.1f MHz  (period %.3f ns, WNS %.3f)" $fmax $ach $wns]
"""

    base = f"C:/Users/Ayush/AppData/Local/Temp/claude/c--Users-Ayush-Desktop-Project-ansh/62155f2d-eae5-412d-a020-c8496acc14ad/scratchpad/"
    for suffix, content in [(".v", core), ("_formal.v", formal), (".sby", sby),
                            ("_tb.v", tb), (".ys_", ys), ("_pnr.tcl", pnr)]:
        pass
    out = {
        f"{name}.v": core,
        f"{name}_formal.v": formal,
        f"tb_{name}.v": tb,
        f"{name}.sby": sby,
        f"synth_{name}.ys": ys,
        f"{name}_pnr.tcl": pnr,
    }
    for fn, content in out.items():
        with open(base + fn, "w", encoding="utf-8") as fh:
            fh.write(content)
    print(f"{name}: {k} dials, M={M}, out_w={out_w}, sum_w={sum_w}, max_q={max_q}, "
          f"idem={idem}  -> wrote {len(out)} files  [bijection PASS over {M} states]")

if __name__ == "__main__":
    name = sys.argv[1]
    mods = [int(a) for a in sys.argv[2:]]
    emit(name, mods)
