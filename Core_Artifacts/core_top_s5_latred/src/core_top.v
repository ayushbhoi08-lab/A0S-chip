`timescale 1ns/1ps
// ============================================================================
// Ansh-108 Core (S4 / Phase 2) : core_top -- the integrated Path-A core.
//   decode (opcode_decode) + the residue datapath (REUSED, already 5-leg proven:
//   ntt_mul12289, rns_add, rns_sub, rns_verify, fold_hash) + REDUCE (rns_reduce)
//   + the free-running tick_counter + the result FSM (result_mode). One clock.
//
//   Protocol: assert in_valid with a 32-bit packet to dispatch it.
//     - gated ops (MUL/ADD/SUB/REDUCE/VERIFY/READ_TICK) are accepted only when
//       ~busy (single in-flight; host awaits out_valid/result_ready before the
//       next gated op). Latencies (datapath + 1 output reg):
//         MUL 4+1=5 | ADD/SUB 2+1=3 | REDUCE/VERIFY/READ_TICK 1+1=2.
//     - FOLD streams 1/cycle (not gated): latency 1+1=2, throughput 1/cycle.
//     - FLUSH/RESET reseed the fold accumulator (fire-and-forget). RESET also
//       raises the bindu pulse. NEITHER touches the tick (write-protected).
//     - SEED_FROM_TICK (opcode 7) is decoded but, per the lock "off by default",
//       has no on-chip datapath effect in this build (the proven fold_hash takes
//       a fixed seed; arbitrary seed-load is deferred and not rebuilt here).
//     - reserved opcodes 9..14 (host-side cmp/bitwise) decode to no select ->
//       no accept, no effect.
//
//   Result bus `out` [22:0]: arithmetic/REDUCE in [13:0]; VERIFY equality in
//   bit[0]; READ_TICK = packed tick residues {c0[7:0],c1[4:0],c2[9:0]} (the host
//   CRT-recombines them -- positional op, Path-A fence). tick residues are also
//   exposed directly for the host / for the write-protect formal property.
// ============================================================================
module core_top (
    input         clk,
    input         rst,
    input         in_valid,        // dispatch the packet this cycle
    input  [31:0] packet,
    input         read_ack,        // host acknowledges reading the held result
    output [22:0] out,
    output        out_valid,       // 1-cycle strobe when a result is produced
    output        result_ready,    // sticky: a result is held awaiting read
    output        busy,            // a gated op is in flight
    output        bindu,           // 1-cycle pulse: RESET/bindu sequence-complete
    output [3:0]  opcode_echo,
    output [1:0]  res_mode,        // result-mode class of the current opcode
    output [7:0]  tick0,           // tick residues (host CRT-recombines)
    output [4:0]  tick1,
    output [9:0]  tick2
);
    localparam [3:0] MUL=4'd0, ADD=4'd1, SUB=4'd2, REDUCE=4'd3,
                     VERIFY=4'd5, READ_TICK=4'd6;

    // ---------------- decode ---------------------------------------------- //
    wire [3:0]  opcode;
    wire [13:0] x, y;
    wire [27:0] data28;
    wire sel_mul, sel_add, sel_sub, sel_reduce, sel_fold,
         sel_verify, sel_read_tick, sel_seed_tick, sel_flush, sel_reset;
    wire is_bindu, gated;
    wire [1:0] rmode;

    opcode_decode u_dec (
        .packet(packet), .opcode(opcode), .x(x), .y(y), .data28(data28),
        .sel_mul(sel_mul), .sel_add(sel_add), .sel_sub(sel_sub), .sel_reduce(sel_reduce),
        .sel_fold(sel_fold), .sel_verify(sel_verify), .sel_read_tick(sel_read_tick),
        .sel_seed_tick(sel_seed_tick), .sel_flush(sel_flush), .sel_reset(sel_reset),
        .is_bindu(is_bindu), .gated(gated), .result_mode(rmode)
    );
    assign opcode_echo = opcode;
    assign res_mode    = rmode;

    // ---------------- dispatch / accept ----------------------------------- //
    wire busy_w;
    wire accept_gated  = in_valid & gated & ~busy_w;                 // single in-flight
    wire accept_stream = in_valid & sel_fold;                        // FOLD streams freely
    wire accept_ff     = in_valid & (sel_flush | sel_reset | sel_seed_tick);

    // ---------------- residue datapath (REUSED, already proven) ----------- //
    wire        ntt_ov; wire [13:0] ntt_out;
    ntt_mul12289 u_mul (.clk(clk), .rst(rst), .in_valid(accept_gated & sel_mul),
                        .x(x), .y(y), .out_valid(ntt_ov), .out(ntt_out));

    wire        add_ov; wire [13:0] add_out;
    rns_add u_add (.clk(clk), .rst(rst), .in_valid(accept_gated & sel_add),
                   .x(x), .y(y), .out_valid(add_ov), .out(add_out));

    wire        sub_ov; wire [13:0] sub_out;
    rns_sub u_sub (.clk(clk), .rst(rst), .in_valid(accept_gated & sel_sub),
                   .x(x), .y(y), .out_valid(sub_ov), .out(sub_out));

    wire        red_ov; wire [13:0] red_out;
    rns_reduce u_red (.clk(clk), .rst(rst), .in_valid(accept_gated & sel_reduce),
                      .data(data28), .out_valid(red_ov), .out(red_out));

    wire        ver_ov, ver_eq;
    rns_verify u_ver (.clk(clk), .rst(rst), .in_valid(accept_gated & sel_verify),
                      .x(x), .y(y), .out_valid(ver_ov), .out_eq(ver_eq));

    // FOLD: flush wins (FLUSH or RESET), else fold on a streamed packet.
    wire        fold_ov; wire [13:0] fold_h;
    fold_hash u_fold (.clk(clk), .rst(rst),
                      .flush(accept_ff & (sel_flush | sel_reset)),
                      .fold_en(accept_stream),
                      .data(data28), .out_valid(fold_ov), .h(fold_h));

    // ---------------- tick counter (free-running, write-protected) -------- //
    wire [7:0] c0; wire [4:0] c1; wire [9:0] c2;
    tick_counter u_tick (.clk(clk), .rst(rst), .c0(c0), .c1(c1), .c2(c2));
    assign tick0 = c0; assign tick1 = c1; assign tick2 = c2;

    // READ_TICK is a 1-cycle "op": capture residues at accept, valid next cycle.
    reg        rt_ov;
    reg [22:0] rt_cap;
    always @(posedge clk) begin
        rt_ov <= rst ? 1'b0 : (accept_gated & sel_read_tick);
        if (accept_gated & sel_read_tick) rt_cap <= {c0, c1, c2};
    end

    // ---------------- in-flight result MUX (gated ops) -------------------- //
    reg [3:0] inflight;
    always @(posedge clk) begin
        if (rst)               inflight <= 4'hF;     // none
        else if (accept_gated) inflight <= opcode;
    end

    wire dp_valid_gated =
        (inflight == MUL)       ? ntt_ov :
        (inflight == ADD)       ? add_ov :
        (inflight == SUB)       ? sub_ov :
        (inflight == REDUCE)    ? red_ov :
        (inflight == VERIFY)    ? ver_ov :
        (inflight == READ_TICK) ? rt_ov  : 1'b0;

    wire [22:0] dp_out_gated =
        (inflight == MUL)       ? {9'b0, ntt_out} :
        (inflight == ADD)       ? {9'b0, add_out} :
        (inflight == SUB)       ? {9'b0, sub_out} :
        (inflight == REDUCE)    ? {9'b0, red_out} :
        (inflight == VERIFY)    ? {22'b0, ver_eq} :
        (inflight == READ_TICK) ? rt_cap          : 23'b0;

    wire        gated_done = busy_w & dp_valid_gated;
    wire        fold_done  = fold_ov;
    wire [22:0] res_in     = gated_done ? dp_out_gated : {9'b0, fold_h};

    // ---------------- result FSM ------------------------------------------ //
    result_mode u_fsm (
        .clk(clk), .rst(rst),
        .accept_gated(accept_gated),
        .gated_done(gated_done),
        .fold_done(fold_done),
        .accept_reset(accept_ff & sel_reset),
        .read_ack(read_ack),
        .res_in(res_in),
        .busy(busy_w),
        .out(out),
        .out_valid(out_valid),
        .result_ready(result_ready),
        .bindu(bindu)
    );
    assign busy = busy_w;
endmodule
