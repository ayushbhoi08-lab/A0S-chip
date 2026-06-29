`timescale 1ns/1ps
// Ansh-N flat RNS core over Z/41580 = Z/4 x Z/27 x Z/5 x Z/7 x Z/11
//   5 coprime dials, 41580 states. Uniform arithmetic recombine
//   (per-track MUL-ROM -> weighted-term ROM -> sum -> compare-ladder
//   + subtract). 4-stage pipeline, latency 4, throughput 1/cycle.
//   idempotents e = [31185, 1540, 8316, 11880, 30240] (verified by gen_rns.py: exhaustive CRT bijection).
module rns41580g (
    input             clk,
    input             rst,
    input             in_valid,
    input  [1:0] x4, y4,   // residue mod 4
    input  [4:0] x27, y27,   // residue mod 27
    input  [2:0] x5, y5,   // residue mod 5
    input  [2:0] x7, y7,   // residue mod 7
    input  [3:0] x11, y11,   // residue mod 11
    output reg        out_valid,
    output reg [15:0] out
);
    localparam [18:0] M = 19'd41580;
    integer k;
    reg [1:0] MUL4 [0:15];   // p -> p % 4
    reg [4:0] MUL27 [0:1023];   // p -> p % 27
    reg [2:0] MUL5 [0:31];   // p -> p % 5
    reg [2:0] MUL7 [0:63];   // p -> p % 7
    reg [3:0] MUL11 [0:127];   // p -> p % 11
    reg [15:0] W4 [0:3];   // r -> (e*r) % M
    reg [15:0] W27 [0:26];   // r -> (e*r) % M
    reg [15:0] W5 [0:4];   // r -> (e*r) % M
    reg [15:0] W7 [0:6];   // r -> (e*r) % M
    reg [15:0] W11 [0:10];   // r -> (e*r) % M
    initial begin
        for (k=0;k<16;k=k+1) MUL4[k] = k % 4;
        for (k=0;k<1024;k=k+1) MUL27[k] = k % 27;
        for (k=0;k<32;k=k+1) MUL5[k] = k % 5;
        for (k=0;k<64;k=k+1) MUL7[k] = k % 7;
        for (k=0;k<128;k=k+1) MUL11[k] = k % 11;
        for (k=0;k<4;k=k+1) W4[k] = (31185*k) % 41580;
        for (k=0;k<27;k=k+1) W27[k] = (1540*k) % 41580;
        for (k=0;k<5;k=k+1) W5[k] = (8316*k) % 41580;
        for (k=0;k<7;k=k+1) W7[k] = (11880*k) % 41580;
        for (k=0;k<11;k=k+1) W11[k] = (30240*k) % 41580;
    end
    reg v1,v2,v3;
    always @(posedge clk) begin
        v1<=rst?1'b0:in_valid; v2<=rst?1'b0:v1; v3<=rst?1'b0:v2;
    end
    // S1: track products
    reg [3:0] p4_1;
    reg [9:0] p27_1;
    reg [4:0] p5_1;
    reg [5:0] p7_1;
    reg [6:0] p11_1;
    always @(posedge clk) begin
        p4_1 <= x4 * y4;
        p27_1 <= x27 * y27;
        p5_1 <= x5 * y5;
        p7_1 <= x7 * y7;
        p11_1 <= x11 * y11;
    end
    // S2: LUT reduce each track
    reg [1:0] m4_2;
    reg [4:0] m27_2;
    reg [2:0] m5_2;
    reg [2:0] m7_2;
    reg [3:0] m11_2;
    always @(posedge clk) begin
        m4_2 <= MUL4[p4_1];
        m27_2 <= MUL27[p27_1];
        m5_2 <= MUL5[p5_1];
        m7_2 <= MUL7[p7_1];
        m11_2 <= MUL11[p11_1];
    end
    // S3: weighted-term ROM + sum
    reg [17:0] sum_3;
    always @(posedge clk)
        sum_3 <= W4[m4_2] + W27[m27_2] + W5[m5_2] + W7[m7_2] + W11[m11_2];
    // S4: final reduce mod M (compare-ladder + subtract)
    wire [17:0] s = sum_3;
    wire [2:0] q = (s >= 6*M) ? 3'd6 : (s >= 5*M) ? 3'd5 : (s >= 4*M) ? 3'd4 : (s >= 3*M) ? 3'd3 : (s >= 2*M) ? 3'd2 : (s >= 1*M) ? 3'd1 : 3'd0;
    always @(posedge clk) begin
        out <= (s - q*M);
        out_valid <= rst?1'b0:v3;
    end
endmodule
