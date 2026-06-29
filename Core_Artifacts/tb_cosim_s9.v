`timescale 1ns/1ps
// ============================================================================
// Ansh-108 Core -- Path A, Phase 5 / S9: HOST <-> RTL CO-SIM TESTBENCH (Leg 2).
//   Reads cosim_vectors.txt (the EXACT packet stream the REAL host pipeline
//   emitted -- see cosim_s9.py), drives the REAL integrated core_top with the
//   locked protocol, and writes cosim_rtl_out.txt for check_cosim_s9.py.
//
//   Each vector line:  <pid> <rec> <pkt_hex>
//     rec 0 = FOLD foot   (streamed 1/cycle; the LAST result before the bindu of
//                          a committed maNDala is that maNDala's fingerprint)
//     rec 1 = RESET/bindu (fire-and-forget; fires exactly one bindu pulse; seals
//                          the current maNDala -- if it had folds, it COMMITS)
//     rec 2 = FLUSH       (fire-and-forget reseed)
//     rec 3 = gated op    (MUL/ADD/SUB/REDUCE/VERIFY/READ_TICK -- await out_valid)
//
//   Program = a run of equal pid. Per program we report (cosim_rtl_out.txt):
//     P <pid> <fp_hex> <bindu_count> <reset_count> <pushes> <gaps>
//     O <pid> <opidx> <opcode> <result_hex>        (one per gated op, in order)
//   fp = the last COMMITTED maNDala's pre-bindu FOLD result (seed if none),
//   exactly the rule the golden last_committed_fp applies in cosim_s9.py.
//
//   A continuous tick monitor (tick == cyc mod m_i every cycle, while real
//   packets fly) re-proves the free-running, write-protected Maha-Yuga clock for
//   this run. Latency facts are S4's: MUL 5, ADD/SUB 3, REDUCE/VERIFY/READ_TICK
//   2, FOLD 2 @ 1/cycle; the fingerprint is read before the bindu reseeds.
//   (TB references may use % / *; only the DUT must be branch-free.)
// ============================================================================
module tb;
    localparam integer Q = 12289;
    localparam [3:0] RESET = 4'd15;
    localparam integer REC_FOLD=0, REC_RESET=1, REC_FLUSH=2, REC_OP=3;

    reg clk=0, rst=1, in_valid=0, read_ack=0;
    reg [31:0] packet=0;
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] opcode_echo; wire [1:0] res_mode;
    wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;

    core_top dut(.clk(clk), .rst(rst), .in_valid(in_valid), .packet(packet),
                 .read_ack(read_ack), .out(out), .out_valid(out_valid),
                 .result_ready(result_ready), .busy(busy), .bindu(bindu),
                 .opcode_echo(opcode_echo), .res_mode(res_mode),
                 .tick0(t0), .tick1(t1), .tick2(t2));

    always #0.5 clk=~clk;

    // free-running cycle counter, locked to the tick (both advance when rst=0)
    integer cyc=0;
    always @(posedge clk) cyc <= rst ? 0 : cyc+1;

    integer errors=0;

    // ---- continuous tick monitor: tick == cyc mod m_i, ALWAYS (write-protect) //
    reg mon_en=0;
    always @(posedge clk) if (mon_en && !rst) begin
        if (t0 !== (cyc % 256) || t1 !== (cyc % 27) || t2 !== (cyc % 625)) begin
            errors=errors+1;
            if (errors<=8) $display("  TICK MON MISMATCH cyc=%0d t0=%0d t1=%0d t2=%0d",
                                    cyc, t0, t1, t2);
        end
    end

    // packet builder (FOLD foot)
    function [31:0] pk_data(input [3:0] op, input [27:0] dd);
        pk_data = {op, dd};
    endfunction

    // ---- gated op: 1-cycle in_valid pulse, await out_valid, capture ---- //
    task automatic run_op(input [31:0] pkt, output integer lat, output reg [22:0] cap);
        integer k;
        begin
            while (busy) @(posedge clk);
            @(posedge clk); in_valid=1'b1; packet=pkt;
            @(posedge clk); in_valid=1'b0;
            k=0;
            while (!out_valid && k<128) begin @(posedge clk); k=k+1; end
            lat=k; cap=out;
        end
    endtask

    // ---- fire-and-forget FLUSH (no result) ---- //
    task automatic fire_flush;
        begin
            while (busy) @(posedge clk);
            @(posedge clk); in_valid=1'b1; packet=pk_data(4'd8, 28'd0);
            @(posedge clk); in_valid=1'b0;
        end
    endtask

    // ---- fire RESET; count the bindu pulse(s) it raises (expect exactly 1) ---- //
    task automatic fire_reset(output integer got);
        integer w;
        begin
            while (busy) @(posedge clk);
            got=0;
            fork
                begin @(posedge clk); in_valid=1'b1; packet=pk_data(RESET, 28'd0);
                      @(posedge clk); in_valid=1'b0; end
                begin for (w=0; w<8; w=w+1) begin @(posedge clk); if (bindu) got=got+1; end end
            join
        end
    endtask

    // ---- stream a run of FOLD feet (1/cycle), capture last result + gaps ---- //
    reg [27:0] fbuf [0:4095];
    integer fcnt;
    task automatic drive_fold_burst(input integer count,
                                    output reg [22:0] last,
                                    output integer nvalid, output integer gaps);
        integer i; reg seenf; integer idle;
        begin
            while (busy) @(posedge clk);
            @(posedge clk);
            nvalid=0; gaps=0; last=23'b0;
            fork
                begin : DRV
                    for (i=0;i<count;i=i+1) begin
                        in_valid=1'b1; packet=pk_data(4'd4, fbuf[i]); @(posedge clk);
                    end
                    in_valid=1'b0;
                end
                begin : COL
                    seenf=0; idle=0;
                    while (nvalid<count && idle<(count+400)) begin
                        @(posedge clk);
                        if (out_valid) begin seenf=1; nvalid=nvalid+1; last=out; end
                        else if (seenf && nvalid<count) gaps=gaps+1;  // mid-stream bubble
                        idle=idle+1;
                    end
                end
            join
        end
    endtask

    // ---- vector storage ---- //
    integer NMAX;
    integer vpid [0:65535];
    integer vrec [0:65535];
    reg [31:0] vpkt [0:65535];
    integer fd, ofd, code, n, i;
    integer a, b; reg [31:0] c;

    // ---- per-program accumulators ---- //
    integer cur_pid, nprog, total_pkts;
    reg [22:0] prog_fp;
    integer pushes, reset_count, bindu_count, gaps_tot, opidx;
    // scratch
    integer lat, got, nv, g; reg [22:0] cap, seg_last;

    task automatic finalize_program;
        begin
            $fdisplay(ofd, "P %0d %h %0d %0d %0d %0d",
                      cur_pid, prog_fp, bindu_count, reset_count, pushes, gaps_tot);
            nprog = nprog + 1;
        end
    endtask

    task automatic start_program(input integer pid);
        begin
            cur_pid = pid; prog_fp = 23'd1;       // FOLD_SEED (no committed maNDala yet)
            pushes = 0; reset_count = 0; bindu_count = 0; gaps_tot = 0; opidx = 0; fcnt = 0;
            repeat(6) @(posedge clk);             // drain between programs
        end
    endtask

    initial begin
        // reset
        repeat(6) @(posedge clk); rst<=0; @(posedge clk); @(posedge clk); mon_en<=1;
        $display("=== Ansh-108 S9 host<->RTL co-sim TB ===");

        // ---- read the host-emitted vectors ---- //
        n=0;
        fd = $fopen("cosim_vectors.txt", "r");
        if (fd==0) begin $display("  [FATAL] cannot open cosim_vectors.txt"); $finish; end
        code = $fscanf(fd, "%d %d %h", a, b, c);
        while (code==3) begin
            vpid[n]=a; vrec[n]=b; vpkt[n]=c; n=n+1;
            code = $fscanf(fd, "%d %d %h", a, b, c);
        end
        $fclose(fd);
        total_pkts = n;
        $display("  loaded %0d vector packets", n);

        ofd = $fopen("cosim_rtl_out.txt", "w");
        if (ofd==0) begin $display("  [FATAL] cannot open cosim_rtl_out.txt"); $finish; end

        // ---- drive program by program ---- //
        cur_pid = -1; nprog = 0;
        for (i=0; i<n; i=i+1) begin
            if (vpid[i] !== cur_pid) begin
                if (i>0) finalize_program();      // close previous
                start_program(vpid[i]);
            end
            case (vrec[i])
                REC_FOLD: begin
                    fbuf[fcnt] = vpkt[i][27:0]; fcnt = fcnt + 1;
                end
                REC_RESET: begin
                    if (fcnt>0) begin             // a committed maNDala: stream its feet
                        drive_fold_burst(fcnt, seg_last, nv, g);
                        pushes  = pushes + nv;
                        gaps_tot = gaps_tot + g;
                        prog_fp = seg_last;        // last committed fingerprint wins
                        fcnt = 0;
                    end
                    fire_reset(got);
                    bindu_count = bindu_count + got;
                    reset_count = reset_count + 1;
                end
                REC_FLUSH: fire_flush();
                REC_OP: begin
                    run_op(vpkt[i], lat, cap);
                    $fdisplay(ofd, "O %0d %0d %0d %h", cur_pid, opidx, vpkt[i][31:28], cap);
                    opidx = opidx + 1;
                end
            endcase
        end
        if (n>0) finalize_program();              // close the last program

        $fdisplay(ofd, "SUMMARY programs=%0d packets=%0d tick_errors=%0d",
                  nprog, total_pkts, errors);
        $fclose(ofd);

        repeat(4) @(posedge clk);
        $display("  programs=%0d packets=%0d tick_monitor_errors=%0d", nprog, total_pkts, errors);
        if (errors==0) $display(" RESULT: PASS (RTL driven, tick monitor clean)");
        else           $display(" RESULT: FAIL (tick monitor errors=%0d)", errors);
        $finish;
    end
endmodule
