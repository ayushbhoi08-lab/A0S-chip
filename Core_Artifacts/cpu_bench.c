// CPU head-to-head for the chip's primitive: modular multiply (x*y) % q.
// q=41580 = the 5-dial chip's modulus; q=12289 = a real NTT crypto prime
// (lattice crypto / homomorphic encryption inner loop). Constant q lets gcc
// compile the % into a Barrett-style multiply-shift (no runtime divide) -- the
// fair, optimized CPU path. Measures: single-op LATENCY (dependent chain),
// single-core THROUGHPUT (independent ops), and all-core THROUGHPUT (OpenMP).
#include <stdio.h>
#include <stdint.h>
#include <windows.h>
#ifdef _OPENMP
#include <omp.h>
#endif

static double now_s(void){
    LARGE_INTEGER f,c; QueryPerformanceFrequency(&f); QueryPerformanceCounter(&c);
    return (double)c.QuadPart/(double)f.QuadPart;
}

#define N 8192
static uint32_t XS[N], YS[N];

#define MAKE_BENCH(Q)                                                         \
static uint64_t thru_##Q(int64_t iters){                                      \
    uint64_t a0=0,a1=0,a2=0,a3=0;                                             \
    for(int64_t it=0; it<iters; it+=4){                                       \
        a0 += ((uint64_t)XS[(it  )&(N-1)]*YS[(it  )&(N-1)]) % (Q);            \
        a1 += ((uint64_t)XS[(it+1)&(N-1)]*YS[(it+1)&(N-1)]) % (Q);            \
        a2 += ((uint64_t)XS[(it+2)&(N-1)]*YS[(it+2)&(N-1)]) % (Q);            \
        a3 += ((uint64_t)XS[(it+3)&(N-1)]*YS[(it+3)&(N-1)]) % (Q);            \
    }                                                                         \
    return a0+a1+a2+a3;                                                       \
}                                                                             \
static uint64_t lat_##Q(int64_t iters){                                       \
    uint32_t x=12345u % (Q), y=6789u % (Q);                                   \
    for(int64_t it=0; it<iters; it++){                                        \
        x = ((uint64_t)x*y) % (Q);   /* each op depends on previous */        \
        y = x + 1u;                                                           \
    }                                                                         \
    return x;                                                                 \
}                                                                             \
static uint64_t mt_##Q(int64_t iters){                                        \
    uint64_t total=0;                                                         \
    _Pragma("omp parallel reduction(+:total)")                               \
    {                                                                         \
        uint64_t a=0;                                                         \
        _Pragma("omp for")                                                    \
        for(int64_t it=0; it<iters; it++)                                     \
            a += ((uint64_t)XS[it&(N-1)]*YS[it&(N-1)]) % (Q);                 \
        total += a;                                                           \
    }                                                                         \
    return total;                                                            \
}

MAKE_BENCH(41580)
MAKE_BENCH(12289)

static uint64_t splitmix(uint64_t *s){
    uint64_t z=(*s+=0x9E3779B97F4A7C15ull);
    z=(z^(z>>30))*0xBF58476D1CE4E5B9ull; z=(z^(z>>27))*0x94D049BB133111EBull;
    return z^(z>>31);
}

int main(void){
    uint64_t s=1;
    for(int i=0;i<N;i++){ XS[i]=splitmix(&s)%41580u; YS[i]=splitmix(&s)%41580u; }

    int nthreads=1;
#ifdef _OPENMP
    #pragma omp parallel
    {
        #pragma omp single
        nthreads=omp_get_num_threads();
    }
#endif

    const int64_t TI=2000000000LL;   // throughput iters
    const int64_t LI= 300000000LL;   // latency iters

    printf("=== CPU modular-multiply benchmark (gcc -O3 -march=native) ===\n");
    printf("threads available: %d\n\n", nthreads);

    double t; uint64_t r; volatile uint64_t sink;

    #define RUN(Q) do {                                                        \
        t=now_s(); r=lat_##Q(LI);  t=now_s()-t; sink=r;                        \
        double lat_ns = t/(double)LI*1e9;                                      \
        t=now_s(); r=thru_##Q(TI); t=now_s()-t; sink=r;                        \
        double thr_1 = (double)TI/t;                                           \
        t=now_s(); r=mt_##Q(TI);   t=now_s()-t; sink=r;                        \
        double thr_n = (double)TI/t;                                           \
        printf("q=%-6d  latency/op = %6.2f ns   1-core thru = %6.0f M/s   "    \
               "%d-core thru = %7.0f M/s\n", (Q), lat_ns, thr_1/1e6,           \
               nthreads, thr_n/1e6);                                          \
    } while(0)

    RUN(41580);
    RUN(12289);
    (void)sink;
    return 0;
}
