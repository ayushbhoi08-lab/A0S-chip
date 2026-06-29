`timescale 1ns/1ps
// ============================================================================
// Ansh-108 Core (S4 / plan amendment v2) : tick_counter -- the "Yuga clock".
//   A free-running, carry-free RNS counter. Three pairwise-coprime dials
//   {256, 27, 625} = {2^8, 3^3, 5^4}; each dial increments mod m_i with NO carry
//   between dials. Period = 256*27*625 = 4,320,000 ticks = one Maha Yuga; wrap
//   = Pralaya. The combined value (host-side CRT recombine of the residues) is a
//   monotonic 0..M-1 ramp -- proven as a bijection EXHAUSTIVELY over all 4.32M
//   states in golden_model.check_crt_bijection.
//
//   "CAN'T LIE" by construction: there is NO data port and NO opcode path into
//   this module -- only clk and the power-on rst. No packet can set, rewind, or
//   forge the tick (write-protected; the S4 formal proves the dials evolve
//   independent of any packet). It exposes RESIDUES only; CRT reconstruction to
//   an absolute count is a positional/magnitude op and lives host-side (Path A
//   fence). READ_TICK in core_top returns these residues.
//
//   Honesty firewall (carry-forward): this is a perfect CYCLE counter; cycles ->
//   calendar seconds needs a disciplined oscillator at board level (Phase 7+).
// ============================================================================
module tick_counter (
    input            clk,
    input            rst,        // power-on / genesis only (NOT an opcode)
    output reg [7:0] c0,         // dial 0: mod 256 (2^8 wraps naturally)
    output reg [4:0] c1,         // dial 1: mod 27  (0..26)
    output reg [9:0] c2          // dial 2: mod 625 (0..624)
);
    always @(posedge clk) begin
        if (rst) begin
            c0 <= 8'd0;
            c1 <= 5'd0;
            c2 <= 10'd0;
        end else begin
            c0 <= c0 + 8'd1;                              // mod 256 by overflow
            c1 <= (c1 == 5'd26)  ? 5'd0  : c1 + 5'd1;     // mod 27
            c2 <= (c2 == 10'd624)? 10'd0 : c2 + 10'd1;    // mod 625
        end
    end
endmodule
