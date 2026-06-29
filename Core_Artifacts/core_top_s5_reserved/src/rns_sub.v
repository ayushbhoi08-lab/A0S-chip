`timescale 1ns/1ps
// ============================================================================
// Ansh-108 Core : modular SUB on the primary lane -- out = (x - y) mod 12289.
//   Operands in [0,q), q=12289 (same lane as ntt_mul12289 -> 14-bit fields).
//   BRANCH-FREE / constant-time: x-y in (-q, q). A 15-bit subtract exposes the
//   borrow in bit[14]; on borrow (x<y) add q back. SINGLE conditional add, one
//   2:1 mux selected by the borrow bit -- no divider, no loop, value-independent.
//   2-stage pipeline: latency = 2 cycles, throughput = 1 sub/cycle.
// ============================================================================
module rns_sub (
    input             clk,
    input             rst,
    input             in_valid,
    input      [13:0] x,        // operand in [0,12289)
    input      [13:0] y,
    output reg        out_valid,
    output reg [13:0] out       // (x - y) mod 12289
);
    localparam [13:0] Q = 14'd12289;

    // valid pipeline is EXACTLY as deep as the datapath (2 stages: d1 -> out),
    // so out_valid stays aligned with out (one valid reg per data register).
    reg v1;
    always @(posedge clk) v1 <= rst ? 1'b0 : in_valid;

    // S1: raw difference as 15-bit; bit[14] = borrow (set iff x < y)
    reg [14:0] d1;
    always @(posedge clk) d1 <= {1'b0, x} - {1'b0, y};

    // S2: on borrow, add q back -> result in [0,q)
    always @(posedge clk) begin
        out       <= d1[14] ? (d1[13:0] + Q) : d1[13:0];
        out_valid <= rst ? 1'b0 : v1;
    end
endmodule
