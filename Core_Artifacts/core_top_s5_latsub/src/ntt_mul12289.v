`timescale 1ns/1ps
// ============================================================================
// NTT butterfly modular multiplier: out = (x*y) mod 12289, divider-free.
//   q=12289 is a real NTT-friendly prime (12288 = 2^12*3; supports radix-2 NTT
//   up to N=4096), the inner-loop op of lattice crypto (Kyber/Dilithium-class)
//   and FHE. Barrett reduction (constants verified EXHAUSTIVELY over all
//   12289^2 pairs in barrett_check.c): mu=floor(2^28/q)=21843, one correction.
//   3 multiplies (x*y, a*mu, t*q) -> DSP-mapped. 4-stage pipeline, 1 op/cycle.
// ============================================================================
module ntt_mul12289 (
    input             clk,
    input             rst,
    input             in_valid,
    input      [13:0] x,        // operand in [0,12289)
    input      [13:0] y,
    output reg        out_valid,
    output reg [13:0] out       // (x*y) mod 12289
);
    localparam [13:0] Q  = 14'd12289;
    localparam [14:0] MU = 15'd21843;   // floor(2^28 / 12289)

    reg v1, v2, v3;
    always @(posedge clk) begin
        v1 <= rst ? 1'b0 : in_valid;
        v2 <= rst ? 1'b0 : v1;
        v3 <= rst ? 1'b0 : v2;
    end

    // S1: a = x*y  (<= 12288^2 < 2^28)
    reg [27:0] a1;
    always @(posedge clk) a1 <= x * y;

    // S2: t = floor(a*mu / 2^28); carry a forward
    reg [27:0] a2;
    reg [14:0] t2;
    wire [42:0] am = a1 * MU;       // 28 x 15
    always @(posedge clk) begin
        a2 <= a1;
        t2 <= am[42:28];
    end

    // S3: r = a - t*q   (lies in [0, 2q); t*q < q^2 < 2^28 so 28-bit exact)
    reg [15:0] r3;
    wire [27:0] tq = t2 * Q;        // 15 x 14, value < 2^28
    always @(posedge clk) r3 <= a2 - tq;

    // S4: single conditional subtract -> result in [0, q)
    always @(posedge clk) begin
        out       <= (r3 >= Q) ? (r3 - Q) : r3[13:0];
        out_valid <= rst ? 1'b0 : v3;
    end
endmodule
