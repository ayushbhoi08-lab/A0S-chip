`timescale 1ns/1ps
// ============================================================================
// Ansh-108 Core : RNS transform over Z/108 = Z/4 x Z/27
//   * Mod-4 track  : free (low 2 bits) -- runs in PARALLEL with...
//   * Mod-27 track : LUT-based reduction (NO divider -- bypasses x86's div)
//   * CRT recombine: out = (81*a + 28*b) mod 108, also LUT-reduced
// 4-stage pipeline: throughput = 1 transform/cycle, latency = 4 cycles.
// The % operators below run ONCE at elaboration to FILL the ROMs; in synthesis
// they become ROM contents, not runtime dividers.
// ============================================================================
module rns108 (
    input             clk,
    input             rst,
    input             in_valid,
    input      [6:0]  x,        // operand in 0..107
    input      [6:0]  y,
    output reg        out_valid,
    output reg [6:0]  out       // result in 0..107
);
    // ---- precomputed ROMs (no division at runtime) ----
    reg [4:0] MOD27  [0:1023];  // v -> v % 27   (v up to 676)
    reg [6:0] MOD108 [0:1023];  // s -> s % 108  (s up to 971)
    integer k;
    initial begin
        for (k = 0; k < 1024; k = k + 1) MOD27[k]  = k % 27;
        for (k = 0; k < 1024; k = k + 1) MOD108[k] = k % 108;
    end

    // ---- Stage 1: decompose (mod-4 = bits, mod-27 = LUT) -- PARALLEL ----
    reg [1:0] a1, a2;
    reg [4:0] b1, b2;
    reg       v1;
    always @(posedge clk) begin
        a1 <= x[1:0];      b1 <= MOD27[x];     // track A | track B  (parallel)
        a2 <= y[1:0];      b2 <= MOD27[y];
        v1 <= rst ? 1'b0 : in_valid;
    end

    // ---- Stage 2: multiply on each track (still parallel, no cross-talk) ----
    reg [1:0] a2r;
    reg [9:0] p2;          // raw product b1*b2, up to 676
    reg       v2;
    always @(posedge clk) begin
        a2r <= (a1 * a2) & 2'b11;   // mod-4 track: product mod 4 = low bits
        p2  <= b1 * b2;             // mod-27 track: raw product (reduce next)
        v2  <= rst ? 1'b0 : v1;
    end

    // ---- Stage 3: reduce the mod-27 track via LUT ----
    reg [1:0] a3;
    reg [4:0] b3;
    reg       v3;
    always @(posedge clk) begin
        a3 <= a2r;
        b3 <= MOD27[p2];            // LUT reduce -- the division-free step
        v3 <= rst ? 1'b0 : v2;
    end

    // ---- Stage 4: CRT recombine (81a + 28b) then mod-108 LUT ----
    always @(posedge clk) begin
        out       <= MOD108[81*a3 + 28*b3];
        out_valid <= rst ? 1'b0 : v3;
    end
endmodule
