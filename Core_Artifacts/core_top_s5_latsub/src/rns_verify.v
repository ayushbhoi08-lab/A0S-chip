`timescale 1ns/1ps
// ============================================================================
// Ansh-108 Core : VERIFY -- residue-native equality test, 1-bit pass/fail flag.
//   On the primary mod-12289 lane an operand is a single dial, so "equal" is a
//   direct x==y comparator. In a multi-dial RNS this generalises to the AND of
//   per-dial equalities (equal iff ALL dials match) -- the cheap-in-residue
//   property that makes VERIFY free of any CRT reconstruction. Branch-free.
//   1-stage pipeline: latency = 1 cycle, throughput = 1 compare/cycle.
// ============================================================================
module rns_verify (
    input             clk,
    input             rst,
    input             in_valid,
    input      [13:0] x,        // operand in [0,12289)
    input      [13:0] y,
    output reg        out_valid,
    output reg        out_eq    // 1 iff x == y, else 0
);
    always @(posedge clk) begin
        out_eq    <= (x == y);                 // AND-reduce of a single dial
        out_valid <= rst ? 1'b0 : in_valid;
    end
endmodule
