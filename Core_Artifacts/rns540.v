`timescale 1ns/1ps
// Ansh-N flat RNS core over Z/540 = Z/4 x Z/27 x Z/5
//   3 coprime dials, 540 states. Uniform arithmetic recombine
//   (per-track MUL-ROM -> weighted-term ROM -> sum -> compare-ladder
//   + subtract). 4-stage pipeline, latency 4, throughput 1/cycle.
//   idempotents e = [405, 460, 216] (verified by gen_rns.py: exhaustive CRT bijection).
module rns540 (
    input             clk,
    input             rst,
    input             in_valid,
    input  [1:0] x4, y4,   // residue mod 4
    input  [4:0] x27, y27,   // residue mod 27
    input  [2:0] x5, y5,   // residue mod 5
    output reg        out_valid,
    output reg [9:0] out
);
    localparam [11:0] M = 12'd540;
    integer k;
    reg [1:0] MUL4 [0:15];   // p -> p % 4
    reg [4:0] MUL27 [0:1023];   // p -> p % 27
    reg [2:0] MUL5 [0:31];   // p -> p % 5
    reg [9:0] W4 [0:3];   // r -> (e*r) % M
    reg [9:0] W27 [0:26];   // r -> (e*r) % M
    reg [9:0] W5 [0:4];   // r -> (e*r) % M
    initial begin
        for (k=0;k<16;k=k+1) MUL4[k] = k % 4;
        for (k=0;k<1024;k=k+1) MUL27[k] = k % 27;
        for (k=0;k<32;k=k+1) MUL5[k] = k % 5;
        for (k=0;k<4;k=k+1) W4[k] = (405*k) % 540;
        for (k=0;k<27;k=k+1) W27[k] = (460*k) % 540;
        for (k=0;k<5;k=k+1) W5[k] = (216*k) % 540;
    end
    reg v1,v2,v3;
    always @(posedge clk) begin
        v1<=rst?1'b0:in_valid; v2<=rst?1'b0:v1; v3<=rst?1'b0:v2;
    end
    // S1: track products
    reg [3:0] p4_1;
    reg [9:0] p27_1;
    reg [4:0] p5_1;
    always @(posedge clk) begin
        p4_1 <= x4 * y4;
        p27_1 <= x27 * y27;
        p5_1 <= x5 * y5;
    end
    // S2: LUT reduce each track
    reg [1:0] m4_2;
    reg [4:0] m27_2;
    reg [2:0] m5_2;
    always @(posedge clk) begin
        m4_2 <= MUL4[p4_1];
        m27_2 <= MUL27[p27_1];
        m5_2 <= MUL5[p5_1];
    end
    // S3: weighted-term ROM + sum
    reg [10:0] sum_3;
    always @(posedge clk)
        sum_3 <= W4[m4_2] + W27[m27_2] + W5[m5_2];
    // S4: final reduce mod M (compare-ladder + subtract)
    wire [10:0] s = sum_3;
    wire [1:0] q = (s >= 3*M) ? 2'd3 : (s >= 2*M) ? 2'd2 : (s >= 1*M) ? 2'd1 : 2'd0;
    always @(posedge clk) begin
        out <= (s - q*M);
        out_valid <= rst?1'b0:v3;
    end
endmodule
