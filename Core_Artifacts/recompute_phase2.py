# Recompute the utilization curve with MEASURED hardware E (RTL) vs host S,c.
# Host costs = x86 measurements from the C kernel (the brain IS the host CPU),
# best-case (min over runs; S,c are a few cycles each so jitter run-to-run).
S      = 0.79    # ns, indexed rule select (measured C, min-of-runs)
c      = 0.57    # ns, one rule-domain check (measured C, min-of-runs)
E_x86  = 9.69    # ns, software RNS transform, x86 div-bound (measured C, min-of-runs)
LAT    = 4       # cycles, RTL serial latency (measured iverilog)
THRU   = 1       # cycle,  RTL throughput  (measured iverilog)

print("MEASURED RTL: latency = %d cycles, throughput = %d transform/cycle\n" % (LAT, THRU))
print("SERIAL (asiddha) regime -- chip pays full %d-cycle latency, no overlap:" % LAT)
print("  clock      E_serial   util=E/(S+E)   N*=E/c")
for f in (250, 500, 1000, 2000, 3000):
    p = 1000.0 / f          # ns/cycle
    E = LAT * p
    print("  %4d MHz   %6.2f ns    %5.1f%%        %5.2f rules" %
          (f, E, 100*E/(S+E), E/c))
print("  x86 sw     %6.2f ns    %5.1f%%        %5.2f rules   (division-bound baseline)" %
      (E_x86, 100*E_x86/(S+E_x86), E_x86/c))

print("\nPARALLELIZABLE regime -- chip pipelines at 1 transform/cycle (independent ops):")
for f in (1000, 2000):
    p = 1000.0 / f
    bound = "HOST-bound (host slower than chip throughput)" if S > p else "chip-bound"
    print("  %4d MHz   chip throughput = %.2f ns/op   host S = %.2f ns -> %s" % (f, p, S, bound))

print("\nDelta from removing the divider (LUT mod-27):")
for f in (1000, 2000):
    p = 1000.0 / f; E = LAT * p
    print("  @%d MHz: muscle %.2f ns -> %.2f ns  (%.2fx faster); util %.0f%% -> %.0f%%; N* %.1f -> %.1f"
          % (f, E_x86, E, E_x86/E, 100*E_x86/(S+E_x86), 100*E/(S+E), E_x86/c, E/c))
