/* Ansh-108 RNS kernel microbenchmark.
 * Measures the REAL per-op costs the model only assumed:
 *   E = RNS transform (mod-4 & mod-27 residue ops + CRT recombine 81a+28b mod108)
 *   c = one rule-domain predicate check
 *   S = indexed rule selection (pointer advance + one domain check)
 * then derives the measured crossover N* = E/c and util = E/(S+E).
 *
 * Methodology: __rdtsc(), calibrated to ns via QueryPerformanceCounter.
 * Every loop carries a data dependency so the work is serial (the asiddha
 * case) and cannot be optimized away; results are summed into volatile sinks.
 */
#include <stdio.h>
#include <stdint.h>
#include <x86intrin.h>
#include <windows.h>

volatile unsigned g_sink = 0;   /* defeats dead-code elimination */

/* --- the muscle: one RNS transform over Z/108Z (108 = 4*27) --- */
static inline unsigned rns_transform(unsigned x, unsigned y) {
    unsigned a1 = x & 3u,  b1 = x % 27u;      /* decompose: mod4 free, mod27 real */
    unsigned a2 = y & 3u,  b2 = y % 27u;
    unsigned a  = (a1 * a2) & 3u;             /* track A (parallel in real HW) */
    unsigned b  = (b1 * b2) % 27u;            /* track B */
    return (81u * a + 28u * b) % 108u;        /* CRT recombine */
}

/* --- the brain: a rule domain predicate (3 feature comparisons) --- */
typedef struct { int lman, rvoice, rplace; } Rule;   /* -1 = wildcard */
static inline int domain_check(const Rule *r, int lman, int rvoice, int rplace) {
    return (r->lman   < 0 || r->lman   == lman)
        && (r->rvoice < 0 || r->rvoice == rvoice)
        && (r->rplace < 0 || r->rplace == rplace);
}

static double g_tsc_hz;
static double ns(uint64_t ticks) { return (double)ticks * 1e9 / g_tsc_hz; }

static void calibrate_tsc(void) {
    LARGE_INTEGER f, q0, q1; QueryPerformanceFrequency(&f);
    uint64_t t0 = __rdtsc(); QueryPerformanceCounter(&q0);
    do { QueryPerformanceCounter(&q1); }
    while ((double)(q1.QuadPart - q0.QuadPart) / f.QuadPart < 0.25);
    uint64_t t1 = __rdtsc();
    double secs = (double)(q1.QuadPart - q0.QuadPart) / f.QuadPart;
    g_tsc_hz = (double)(t1 - t0) / secs;
}

int main(void) {
    calibrate_tsc();
    printf("TSC calibrated: %.3f GHz  (1 tick = %.4f ns)\n\n", g_tsc_hz/1e9, ns(1));

    const uint64_t NE = 200000000ULL;   /* transform iters  */
    const uint64_t NC = 400000000ULL;   /* domain-check iters */

    /* ---- E: RNS transform (serial dependency: x feeds next x) ---- */
    unsigned x = 12345u % 108u, acc = 0;
    uint64_t s = __rdtsc();
    for (uint64_t i = 0; i < NE; i++) { x = rns_transform(x, x + 7u); acc += x; }
    uint64_t e = __rdtsc();
    g_sink += acc;
    double E = (double)(e - s) / NE;

    /* ---- c: one domain check ---- */
    Rule r = { 0, 1, -1 };          /* L=stop, R=voiced, any place */
    int sink = 0;
    s = __rdtsc();
    for (uint64_t i = 0; i < NC; i++)
        sink += domain_check(&r, (int)(i & 1), (int)((i>>1)&1), (int)(i%5));
    e = __rdtsc();
    g_sink += (unsigned)sink;
    double c = (double)(e - s) / NC;

    /* ---- S: indexed select (pointer advance + one check) ---- */
    enum { TBL = 4096 };
    static Rule tbl[TBL];
    for (int k = 0; k < TBL; k++) { tbl[k].lman = 2; tbl[k].rvoice = 2; tbl[k].rplace = 9; } /* none match */
    unsigned p = 0; sink = 0;
    const uint64_t NS = 200000000ULL;
    s = __rdtsc();
    for (uint64_t i = 0; i < NS; i++) {
        const Rule *rr = &tbl[p];
        sink += domain_check(rr, (int)(i&1), (int)((i>>1)&1), (int)(i%5));
        p = (p + 1) & (TBL - 1);
    }
    e = __rdtsc();
    g_sink += (unsigned)sink;
    double S = (double)(e - s) / NS;

    /* ---- scan: O(N) over a rule table (none match -> full scan = N*c) ---- */
    printf("MEASURED per-op (serial latency):\n");
    printf("  E  (RNS transform)      = %.3f ns  (%.2f ticks)\n", E*1e9/g_tsc_hz, E);
    printf("  c  (one domain check)   = %.3f ns  (%.2f ticks)\n", c*1e9/g_tsc_hz, c);
    printf("  S  (indexed select)     = %.3f ns  (%.2f ticks)\n", S*1e9/g_tsc_hz, S);

    double Ens = ns((uint64_t)(E*1000))/1000.0, cns = ns((uint64_t)(c*1000))/1000.0,
           Sns = ns((uint64_t)(S*1000))/1000.0;
    /* use float ns directly to avoid truncation */
    Ens = E*1e9/g_tsc_hz; cns = c*1e9/g_tsc_hz; Sns = S*1e9/g_tsc_hz;

    printf("\nDERIVED (measured):\n");
    printf("  Crossover N* = E/c              = %.2f rules/step\n", E/c);
    printf("  Chip util (indexed) = E/(S+E)   = %.1f%%\n", 100.0*E/(S+E));

    printf("\nSCAN sweep (full scan, latency per junction = N*c):\n");
    int Ns[] = {16, 256, 4096};
    for (int t = 0; t < 3; t++) {
        int N = Ns[t];
        unsigned q = 0; sink = 0;
        uint64_t OUTER = 2000000ULL;
        uint64_t ss = __rdtsc();
        for (uint64_t i = 0; i < OUTER; i++) {
            int hit = 0;
            for (int j = 0; j < N; j++)
                hit += domain_check(&tbl[j], (int)(i&1), (int)((i>>1)&1), (int)(i%5));
            sink += hit; q ^= (unsigned)i;
        }
        uint64_t ee = __rdtsc();
        g_sink += (unsigned)sink + q;
        double per = (double)(ee - ss) / OUTER;
        printf("  N=%-5d  per-junction = %8.1f ns   chip-util = %.4f%%\n",
               N, per*1e9/g_tsc_hz, 100.0*E/(per+E));
    }

    /* ---- depth-5 asiddha chain with MEASURED constants ---- */
    printf("\nDEPTH-5 ASIDDHA CHAIN (measured indexed S, E):\n");
    double per_step = Sns + Ens;
    printf("  per-step (S+E) = %.3f ns   depth-5 latency = %.3f ns   chip-util = %.1f%%\n",
           per_step, 5*per_step, 100.0*Ens/per_step);
    printf("  vs full-scan N=4096 depth-5 latency = %.1f ns\n", 5*(4096*cns + Ens));

    printf("\n[sink=%u]\n", g_sink);
    return 0;
}
