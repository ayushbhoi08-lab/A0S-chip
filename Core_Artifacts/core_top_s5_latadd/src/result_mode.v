`timescale 1ns/1ps
// ============================================================================
// Ansh-108 Core (S4 / Phase 2) : result_mode -- the adaptable result FSM.
//   Speaks the four result-mode contracts of the locked opcode map:
//     * CRITICAL  (MUL/ADD/SUB/REDUCE): hold the result, raise out_valid, then
//                 keep result_ready set until the host reads it (await-read).
//     * STREAM    (FOLD): push each fold result the cycle it completes.
//     * HANDSHAKE (VERIFY/READ_TICK): hold a 1-bit / tick result, await query.
//     * FIRE-FORGET (FLUSH/RESET/SEED): no result; RESET also fires the bindu.
//
//   Single in-flight interlock for the gated (critical/handshake) ops: `busy`
//   is set on accept and cleared when that op's result returns -- core_top blocks
//   a new gated dispatch while busy, so multi-latency ops (MUL=4 .. VERIFY=1)
//   never reorder/collide at the shared result port. FOLD streams freely (it is
//   not gated). The output stage is REGISTERED, so the core latency of any op is
//   its datapath latency + 1 (one output-pipeline cycle) -- documented, and the
//   value the formal `latency exactness` properties assert against.
//
//   `bindu` is a 1-cycle pulse, registered from accept_reset -> it fires EXACTLY
//   once per RESET packet ("sequence complete, apply final policy").
// ============================================================================
module result_mode (
    input             clk,
    input             rst,
    input             accept_gated,   // a gated (critical/handshake) op started this cycle
    input             gated_done,     // the in-flight gated op's result is valid this cycle
    input             fold_done,      // a stream (FOLD) result is valid this cycle
    input             accept_reset,   // a RESET/bindu packet was accepted this cycle
    input             read_ack,       // host has read the held result
    input      [22:0] res_in,         // the result value to latch (gated or fold)
    output reg        busy,           // a gated op is in flight (interlock)
    output reg [22:0] out,            // held result (live with out_valid; stays for late read)
    output reg        out_valid,      // 1-cycle strobe: a result was produced this cycle
    output reg        result_ready,   // sticky: a result is held awaiting read
    output reg        bindu           // 1-cycle pulse: RESET sequence-complete
);
    wire any_done = gated_done | fold_done;

    always @(posedge clk) begin
        if (rst) begin
            busy         <= 1'b0;
            out          <= 23'b0;
            out_valid    <= 1'b0;
            result_ready <= 1'b0;
            bindu        <= 1'b0;
        end else begin
            // busy interlock: set on accept, clear when its result returns.
            // (core_top guarantees accept_gated only when ~busy, so these are
            //  mutually exclusive for the same transaction.)
            if (accept_gated)    busy <= 1'b1;
            else if (gated_done) busy <= 1'b0;

            // registered output stage (adds the documented +1 latency cycle)
            out_valid <= any_done;
            if (any_done) out <= res_in;

            // sticky "result waiting" flag for the await-read contract
            if (any_done)                     result_ready <= 1'b1;
            else if (read_ack | accept_gated) result_ready <= 1'b0;

            // bindu fires exactly one cycle after a RESET packet is accepted
            bindu <= accept_reset;
        end
    end
endmodule
