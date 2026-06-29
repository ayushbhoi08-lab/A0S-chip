`timescale 1ns/1ps
// ============================================================================
// Ansh-N Core (Phase 5) : RNS transform over Z/41580 = Z/4 x Z/27 x Z/5 x Z/7 x Z/11
//   5 coprime tracks, all parallel, NO carry between dials, NO runtime divider.
//   Inputs are residue tuples (the subject of the "carry-free scaling" claim);
//   integer->residue decomposition is a separate shared front-end, excluded here.
//   CRT recombine: out = (sum e_i*r_i) mod 41580, idempotents from verify_crt_5mod.py
//     e = [31185(mod4), 1540(mod27), 8316(mod5), 11880(mod7), 30240(mod11)]
//   4-stage pipeline: throughput = 1 transform/cycle, latency = 4 cycles
//   (same depth as the 108-core; this measures whether width costs fmax/area).
//   All % operators below run ONCE at elaboration to FILL ROMs -> in synthesis
//   they are ROM contents, not dividers (same trick as rns108.v).
// ============================================================================
module rns41580 (
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
    localparam [16:0] M = 17'd41580;

    // ---- precomputed reduction ROMs (filled at elaboration; no runtime div) ----
    reg [4:0] MUL27 [0:1023];  // p -> p % 27   (p = r*r up to 676)
    reg [2:0] MUL5  [0:31];    // p -> p % 5    (p up to 16)
    reg [2:0] MUL7  [0:63];    // p -> p % 7    (p up to 36)
    reg [3:0] MUL11 [0:127];   // p -> p % 11   (p up to 100)
    // weighted-term ROMs: r -> (e_i * r) % M  (each < 41580, 16-bit)
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

    // ---- Stage 1: raw track products (all parallel, no cross-talk) ----
    reg [1:0] m4_1;
    reg [9:0] p27_1;   // up to 676
    reg [4:0] p5_1;    // up to 16
    reg [5:0] p7_1;    // up to 36
    reg [6:0] p11_1;   // up to 100
    reg       v1;
    always @(posedge clk) begin
        m4_1  <= (x4 * y4) & 2'b11;     // mod-4 product = low 2 bits
        p27_1 <= x27 * y27;
        p5_1  <= x5 * y5;
        p7_1  <= x7 * y7;
        p11_1 <= x11 * y11;
        v1    <= rst ? 1'b0 : in_valid;
    end

    // ---- Stage 2: reduce each track via LUT (the division-free step) ----
    reg [1:0] m4_2;
    reg [4:0] m27_2;
    reg [2:0] m5_2;
    reg [2:0] m7_2;
    reg [3:0] m11_2;
    reg       v2;
    always @(posedge clk) begin
        m4_2  <= m4_1;
        m27_2 <= MUL27[p27_1];
        m5_2  <= MUL5[p5_1];
        m7_2  <= MUL7[p7_1];
        m11_2 <= MUL11[p11_1];
        v2    <= rst ? 1'b0 : v1;
    end

    // ---- Stage 3: CRT weighted terms + sum (each term < M, sum < 5M) ----
    reg [17:0] sum_3;   // up to 5*41579 < 207900 (18-bit)
    reg        v3;
    always @(posedge clk) begin
        sum_3 <= W4[m4_2] + W27[m27_2] + W5[m5_2] + W7[m7_2] + W11[m11_2];
        v3    <= rst ? 1'b0 : v2;
    end

    // ---- Stage 4: final reduce mod 41580 ----
    //      divider-free: count how many M's fit, subtract that multiple.
    //      Legit sum < 5M, but reduce robustly over the FULL 18-bit range
    //      (q up to 6) so out < M holds unconditionally -- even on power-on
    //      garbage before the pipeline fills (the 108-core got this free from
    //      its bounded output ROM; the arithmetic path must do it explicitly).
    wire [17:0] s = sum_3;
    wire [2:0]  q = (s >= 6*M) ? 3'd6 :
                    (s >= 5*M) ? 3'd5 :
                    (s >= 4*M) ? 3'd4 :
                    (s >= 3*M) ? 3'd3 :
                    (s >= 2*M) ? 3'd2 :
                    (s >=   M) ? 3'd1 : 3'd0;
    always @(posedge clk) begin
        out       <= s - q * M;
        out_valid <= rst ? 1'b0 : v3;
    end
endmodule
