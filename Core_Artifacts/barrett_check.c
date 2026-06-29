// Exhaustively verify a divider-free Barrett modular multiply for the NTT prime
// q=12289, over ALL x,y in [0,q)^2 (~151M pairs). Fixes the hardware constants
// (mu, shift, #corrections) so ntt_mul12289.v can mirror this exact arithmetic.
//   x,y < q  ->  a = x*y < q^2 < 2^28
//   mu = floor(2^K / q),  t = (a*mu) >> K,  r = a - t*q,  then <=C corrections.
#include <stdio.h>
#include <stdint.h>

int main(void){
    const uint32_t q = 12289;
    const int K = 28;                       // a < q^2 = 150994944 < 2^28
    const uint64_t mu = ((uint64_t)1 << K) / q;
    printf("q=%u  K=%d  mu=%llu  (q^2=%llu, fits %d bits)\n",
           q, K, (unsigned long long)mu, (unsigned long long)q*q, 28);

    // first: how many corrections are ever needed? (sweep, track max)
    int max_corr = 0;
    uint64_t bad = 0, checked = 0;
    for(uint32_t x=0; x<q; x++){
        for(uint32_t y=0; y<=x; y++){           // symmetric: x*y==y*x, halve work
            uint64_t a = (uint64_t)x*y;
            uint64_t t = (a * mu) >> K;
            int64_t  r = (int64_t)a - (int64_t)t*q;
            int corr = 0;
            while(r >= (int64_t)q){ r -= q; corr++; }
            if(r < 0){ bad++; }                  // would indicate t too large
            if(corr > max_corr) max_corr = corr;
            if((uint64_t)r != a % q) bad++;
            checked++;
        }
    }
    printf("checked %llu distinct pairs (x>=y); mismatches=%llu; max_corrections=%d\n",
           (unsigned long long)checked, (unsigned long long)bad, max_corr);
    printf(max_corr<=2 && bad==0 ?
           "RESULT: PASS -- mu=%llu, K=%d, %d conditional subtractions suffice for ALL inputs\n"
         : "RESULT: FAIL\n", (unsigned long long)mu, K, max_corr);
    return bad!=0;
}
