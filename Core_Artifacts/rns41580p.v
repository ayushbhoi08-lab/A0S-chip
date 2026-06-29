`timescale 1ns/1ps
// ============================================================================
// Ansh-N Core (Phase 5b) : DEEP-PIPELINED 5-dial RNS over Z/41580.
//   Same transform as rns41580.v, same divider-free ROMs, but the CRT recombine
//   ("glue") is split across separate pipeline stages instead of one fat cycle,
//   to recover the fmax the flat 4-stage version lost in stage-4.
//   Z/41580 = Z/4 x Z/27 x Z/5 x Z/7 x Z/11, idempotents from verify_crt_5mod.py
//   6-stage pipeline: throughput = 1 transform/cycle, latency = 6 cycles.
//     S1 track products | S2 LUT reduce | S3 W-ROM weighted terms
//     S4 5-way sum       | S5 reduce-quotient ladder | S6 final subtract
//   The two heavy blocks of the flat core (5-add and ladder+subtract) are each
//   given their own cycle, halving the critical path.
// ============================================================================
module rns41580p (
    input             clk,
    input             rst,
    input             in_valid,
    input      [1:0]  x4,  y4,    // residue mod 4   (0..3)
    input      [4:0]  x27, y27,   // residue mod 27  (0..26)
    input      [2:0]  x5,  y5,    // residue mod 5   (0..4)
    input      [2:0]  x7,  y7,    // residue mod 7   (0..6)
    input      [3:0]  x11, y11,   // residue mod 11  (0..10)
    output reg        out_valid,
    output reg [15:0] out         // result in 0..41579
);
    localparam [17:0] M = 18'd41580;

    // ---- precomputed reduction ROMs (filled at elaboration; no runtime div) ----
    reg [4:0] MUL27 [0:1023];
    reg [2:0] MUL5  [0:31];
    reg [2:0] MUL7  [0:63];
    reg [3:0] MUL11 [0:127];
    reg [15:0] W4  [0:3];
    reg [15:0] W27 [0:26];
    reg [15:0] W5  [0:4];
    reg [15:0] W7  [0:6];
    reg [15:0] W11 [0:10];
    integer k;
    initial begin
        for (k = 0; k < 1024; k = k + 1) MUL27[k] = k % 27;
        for (k = 0; k < 32;   k = k + 1) MUL5[k]  = k % 5;
        for (k = 0; k < 64;   k = k + 1) MUL7[k]  = k % 7;
        for (k = 0; k < 128;  k = k + 1) MUL11[k] = k % 11;
        for (k = 0; k < 4;    k = k + 1) W4[k]  = (31185 * k) % 41580;
        for (k = 0; k < 27;   k = k + 1) W27[k] = (1540  * k) % 41580;
        for (k = 0; k < 5;    k = k + 1) W5[k]  = (8316  * k) % 41580;
        for (k = 0; k < 7;    k = k + 1) W7[k]  = (11880 * k) % 41580;
        for (k = 0; k < 11;   k = k + 1) W11[k] = (30240 * k) % 41580;
    end

    // valid shift register (6 deep -> out_valid 6 cycles behind in_valid)
    reg v1, v2, v3, v4, v5;
    always @(posedge clk) begin
        v1 <= rst ? 1'b0 : in_valid;
        v2 <= rst ? 1'b0 : v1;
        v3 <= rst ? 1'b0 : v2;
        v4 <= rst ? 1'b0 : v3;
        v5 <= rst ? 1'b0 : v4;
    end

    // ---- S1: raw track products (all parallel) ----
    reg [1:0] m4_1;
    reg [9:0] p27_1;
    reg [4:0] p5_1;
    reg [5:0] p7_1;
    reg [6:0] p11_1;
    always @(posedge clk) begin
        m4_1  <= (x4 * y4) & 2'b11;
        p27_1 <= x27 * y27;
        p5_1  <= x5 * y5;
        p7_1  <= x7 * y7;
        p11_1 <= x11 * y11;
    end

    // ---- S2: reduce each track via LUT ----
    reg [1:0] m4_2;
    reg [4:0] m27_2;
    reg [2:0] m5_2;
    reg [2:0] m7_2;
    reg [3:0] m11_2;
    always @(posedge clk) begin
        m4_2  <= m4_1;
        m27_2 <= MUL27[p27_1];
        m5_2  <= MUL5[p5_1];
        m7_2  <= MUL7[p7_1];
        m11_2 <= MUL11[p11_1];
    end

    // ---- S3: CRT weighted-term ROM lookups (each < M, 16-bit) ----
    reg [15:0] w4_3, w27_3, w5_3, w7_3, w11_3;
    always @(posedge clk) begin
        w4_3  <= W4[m4_2];
        w27_3 <= W27[m27_2];
        w5_3  <= W5[m5_2];
        w7_3  <= W7[m7_2];
        w11_3 <= W11[m11_2];
    end

    // ---- S4: 5-way sum (its own cycle) -- up to 5*(M-1) < 5M (18-bit) ----
    reg [17:0] sum_4;
    always @(posedge clk)
        sum_4 <= w4_3 + w27_3 + w5_3 + w7_3 + w11_3;

    // ---- S5: reduce-quotient ladder (its own cycle); carry the sum along ----
    //   how many M's fit in sum -- full 18-bit range so out<M holds even on
    //   power-on garbage (legit sum<5M => q<=4; the 5/6 rungs are robustness).
    reg [17:0] sum_5;
    reg [2:0]  q_5;
    always @(posedge clk) begin
        sum_5 <= sum_4;
        q_5   <= (sum_4 >= 6*M) ? 3'd6 :
                 (sum_4 >= 5*M) ? 3'd5 :
                 (sum_4 >= 4*M) ? 3'd4 :
                 (sum_4 >= 3*M) ? 3'd3 :
                 (sum_4 >= 2*M) ? 3'd2 :
                 (sum_4 >=   M) ? 3'd1 : 3'd0;
    end

    // ---- S6: final subtract (its own cycle) ----
    wire [17:0] red = sum_5 - q_5 * M;
    always @(posedge clk) begin
        out       <= red[15:0];
        out_valid <= rst ? 1'b0 : v5;
    end
endmodule
