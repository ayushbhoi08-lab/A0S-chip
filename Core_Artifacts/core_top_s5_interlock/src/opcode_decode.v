`timescale 1ns/1ps
// ============================================================================
// Ansh-108 Core (S4 / Phase 2) : opcode_decode -- packet front-end.
//   32-bit pada = [31:28] opcode | [27:0] data.  Hybrid unpack (per locked S2):
//     fast lane (arith)  : X = data[13:0], Y = data[27:14]  (exact fit for q=12289)
//     flexible lane      : data28 = data[27:0]  (FOLD foot, REDUCE wide value)
//   Pure combinational. Emits one-hot op selects + the result-mode class + the
//   bindu (RESET, opcode 15) marker. Reserved opcodes 9..14 (host-side cmp/bitwise
//   in Path A) decode to NO select -> core_top ignores them (no datapath effect).
//   Matches golden_model.py decode_packet + the opcode/result-mode tables.
// ============================================================================
module opcode_decode (
    input      [31:0] packet,
    output     [3:0]  opcode,
    output     [13:0] x,            // fast-lane operand X
    output     [13:0] y,            // fast-lane operand Y
    output     [27:0] data28,       // flexible-lane full foot (FOLD/REDUCE)
    output            sel_mul,
    output            sel_add,
    output            sel_sub,
    output            sel_reduce,
    output            sel_fold,
    output            sel_verify,
    output            sel_read_tick,
    output            sel_seed_tick,
    output            sel_flush,
    output            sel_reset,
    output            is_bindu,      // opcode 15 (RESET) = sequence-complete bindu
    output            gated,         // result-producing, NON-stream (busy-interlocked)
    output     [1:0]  result_mode    // 00 critical, 01 stream, 10 handshake, 11 fire-forget
);
    localparam [3:0] MUL=4'd0, ADD=4'd1, SUB=4'd2, REDUCE=4'd3, FOLD=4'd4,
                     VERIFY=4'd5, READ_TICK=4'd6, SEED_TICK=4'd7, FLUSH=4'd8, RESET=4'd15;

    assign opcode = packet[31:28];
    assign data28 = packet[27:0];
    assign x      = packet[13:0];
    assign y      = packet[27:14];

    assign sel_mul       = (opcode == MUL);
    assign sel_add       = (opcode == ADD);
    assign sel_sub       = (opcode == SUB);
    assign sel_reduce    = (opcode == REDUCE);
    assign sel_fold      = (opcode == FOLD);
    assign sel_verify    = (opcode == VERIFY);
    assign sel_read_tick = (opcode == READ_TICK);
    assign sel_seed_tick = (opcode == SEED_TICK);
    assign sel_flush     = (opcode == FLUSH);
    assign sel_reset     = (opcode == RESET);
    assign is_bindu      = (opcode == RESET);

    // gated = the multi-/single-cycle result-producing ops that use the busy
    // interlock (await-read). FOLD streams (not gated); FLUSH/RESET/SEED are
    // fire-and-forget (not gated).
    assign gated = sel_mul | sel_add | sel_sub | sel_reduce | sel_verify | sel_read_tick;

    assign result_mode =
        (sel_fold)                              ? 2'b01 :   // stream
        (sel_verify | sel_read_tick)            ? 2'b10 :   // handshake
        (sel_seed_tick | sel_flush | sel_reset) ? 2'b11 :   // fire-and-forget
                                                  2'b00 ;   // critical (MUL/ADD/SUB/REDUCE) + default
endmodule
