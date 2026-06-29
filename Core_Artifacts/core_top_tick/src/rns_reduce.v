`timescale 1ns/1ps
// ============================================================================
// Ansh-108 Core (S4) : REDUCE (opcode 3) -- thin wrapper around the S3-proven
//   Barrett reducer barrett28.  out = data mod 12289 for the full 28-bit foot.
//   Barrett mu = floor(2^28/q) = 21843 (the SAME constant as ntt_mul12289 and
//   fold_hash); ONE conditional subtract is exact for every a < 2^28 -- proven
//   EXHAUSTIVELY over all 2^28 inputs in the S3 Python leg (the modulo-reference
//   SMT wall means full numeric correctness is owned by that exhaustive proof,
//   per the arc precedent). All multiplies are by CONSTANTS. Branch-free.
//   1-stage pipeline: latency = 1 cycle, throughput = 1 reduce/cycle.
// ============================================================================
module rns_reduce (
    input             clk,
    input             rst,
    input             in_valid,
    input      [27:0] data,         // the 28-bit foot / wide value {Y,X}
    output reg        out_valid,
    output reg [13:0] out           // data mod 12289, in [0,q)
);
    localparam [13:0] Q  = 14'd12289;
    localparam [14:0] MU = 15'd21843;   // floor(2^28 / 12289)

    // Barrett reduce of any a < 2^28 -> a mod Q, one conditional subtract.
    function [13:0] barrett28(input [27:0] a);
        reg [42:0] am;      // a*MU, up to 28+15 = 43 bits
        reg [14:0] qest;    // floor(a*MU / 2^28) = estimate of floor(a/Q)
        reg [29:0] r;       // a - qest*Q, lands in [0, 2Q)
        begin
            am   = a * MU;
            qest = am[42:28];
            r    = a - qest * Q;
            barrett28 = (r >= Q) ? (r - Q) : r[13:0];
        end
    endfunction

    always @(posedge clk) begin
        out       <= barrett28(data);
        out_valid <= rst ? 1'b0 : in_valid;
    end
endmodule
