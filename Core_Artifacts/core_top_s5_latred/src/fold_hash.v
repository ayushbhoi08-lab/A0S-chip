`timescale 1ns/1ps
// ============================================================================
// Ansh-108 Core : FOLD -- Horner / polynomial whole-pattern fingerprint.
//   h <- (h*B + data) mod q,  q=12289, B=108 (chip's own number, coprime to q),
//   seed h0 = 1 (blank-wax start; Horner form can't collapse to zero).
//   `data` is the full 28-bit "foot" (the chant pada). Matches golden_model FOLD.
//
//   BRANCH-FREE construction (no divider). Reduce the two summands SEPARATELY
//   with the proven Barrett reducer, then modular-add:
//       h_next = ( (h*B mod q) + (data mod q) ) mod q  ==  (h*B + data) mod q
//   Barrett mu = floor(2^28/q) = 21843 (same constant as ntt_mul12289). ONE
//   correction is exact for every input < 2^28 (error term < 1) -- h*B < 2^21
//   and data < 2^28 both qualify; the exhaustive Python leg proves the reducer
//   over all 2^28 inputs. All multiplies here are by CONSTANTS (108, 21843).
//
//   1-stage accumulator: latency = 1 cycle, throughput = 1 fold/cycle (the
//   feedback uses the current registered h combinationally, so back-to-back
//   folds chain correctly). rst and flush both reload the seed (FLUSH/RESET in
//   the opcode map); neither touches any time counter (that fence is elsewhere).
// ============================================================================
module fold_hash #(
    parameter [13:0] Q    = 14'd12289,
    parameter [13:0] B    = 14'd108,
    parameter [13:0] SEED = 14'd1
) (
    input             clk,
    input             rst,
    input             flush,    // synchronous reseed to SEED (no result)
    input             fold_en,  // incorporate `data` into the running hash
    input      [27:0] data,     // the 28-bit foot
    output reg        out_valid,
    output reg [13:0] h         // running fold hash, always in [0,Q)
);
    localparam [14:0] MU = 15'd21843;   // floor(2^28 / 12289)

    // Barrett reduce of any a < 2^28  ->  a mod Q, one conditional subtract.
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

    // combinational next-hash (Horner step)
    wire [27:0] hB     = h * B;                 // h*108 < 2^21, fits 28 bits
    wire [13:0] pr     = barrett28(hB);         // (h*108) mod Q
    wire [13:0] dr     = barrett28(data);       // data    mod Q
    wire [14:0] s      = pr + dr;               // < 2Q
    wire [13:0] next_h = (s >= Q) ? (s - Q) : s[13:0];

    always @(posedge clk) begin
        if (rst || flush)      h <= SEED;       // reseed wins over fold
        else if (fold_en)      h <= next_h;
        out_valid <= rst ? 1'b0 : (fold_en & ~flush);
    end
endmodule
