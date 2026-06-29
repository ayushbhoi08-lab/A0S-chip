`timescale 1ns/1ps
// ============================================================================
// Ansh-108 Core : modular ADD on the primary lane -- out = (x + y) mod 12289.
//   Operands in [0,q), q=12289 (same lane as ntt_mul12289 -> 14-bit fields).
//   BRANCH-FREE / constant-time: x+y < 2q, so a SINGLE conditional subtract of q
//   reduces to [0,q). No data-dependent loop, no divider; the "?:" is a 2:1 mux
//   selected by one carry/compare bit (timing is value-independent).
//   2-stage pipeline: latency = 2 cycles, throughput = 1 add/cycle.
// ============================================================================
module rns_add (
    input             clk,
    input             rst,
    input             in_valid,
    input      [13:0] x,        // operand in [0,12289)
    input      [13:0] y,
    output reg        out_valid,
    output reg [13:0] out       // (x + y) mod 12289
);
    localparam [13:0] Q = 14'd12289;

    // valid pipeline is EXACTLY as deep as the datapath (2 stages: s1 -> out),
    // so out_valid stays aligned with out (one valid reg per data register).
    reg v1;
    always @(posedge clk) v1 <= rst ? 1'b0 : in_valid;

    // S1: raw sum (15-bit; max 12288+12288 = 24576 < 2q)
    reg [14:0] s1;
    always @(posedge clk) s1 <= x + y;

    // S2: one branch-free correction -> result in [0,q)
    always @(posedge clk) begin
        out       <= (s1 >= Q) ? (s1 - Q) : s1[13:0];
        out_valid <= rst ? 1'b0 : v1;
    end
endmodule
