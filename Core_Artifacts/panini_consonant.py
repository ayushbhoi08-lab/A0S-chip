# Consonant sandhi + vipratiṣedha: where does the BRAIN's comparison load spike?
# Same metric as vowel sandhi (relational comparisons per junction) so the
# numbers are directly comparable to the 0.25 baseline.
#
# A "relational comparison" = a predicate that compares a feature ACROSS both
# operands (place(L)==place(R)) or compares two rule priorities (vipratiṣedha).
# Unary predicates (R is voiced? L is a stop?) are cheap lookups, NOT counted.

from collections import Counter

VEL, PAL, RETRO, DENT, LAB, GLOT = 0, 1, 2, 3, 4, 5
STOP, NASAL, SIB, SV, VOWEL, H, VIS = 'stop', 'nasal', 'sib', 'sv', 'vowel', 'h', 'vis'

# (place, voice, manner)
finals = {  # realistic pada-final inventory
    'k':(VEL,0,STOP),'ṭ':(RETRO,0,STOP),'t':(DENT,0,STOP),'p':(LAB,0,STOP),
    'ṅ':(VEL,1,NASAL),'n':(DENT,1,NASAL),'m':(LAB,1,NASAL),'ḥ':(GLOT,0,VIS),
}
inits = {   # representative following-sound inventory
    'a':(None,1,VOWEL),
    'k':(VEL,0,STOP),'c':(PAL,0,STOP),'ṭ':(RETRO,0,STOP),'t':(DENT,0,STOP),'p':(LAB,0,STOP),
    'g':(VEL,1,STOP),'j':(PAL,1,STOP),'d':(DENT,1,STOP),'b':(LAB,1,STOP),
    'n':(DENT,1,NASAL),'m':(LAB,1,NASAL),
    'y':(PAL,1,SV),'r':(RETRO,1,SV),'l':(DENT,1,SV),'v':(LAB,1,SV),
    'ś':(PAL,0,SIB),'ṣ':(RETRO,0,SIB),'s':(DENT,0,SIB),'h':(GLOT,1,H),
}
def pl(s): return s[0]
def vc(s): return s[1]
def mn(s): return s[2]

# Each rule: (sutra_no, domain(L,R)->bool, feature_modified, is_relational_domain, needs_wide_context)
def obstruent(s): return mn(s) in (STOP, SIB)
RULES = [
 # name              sutra   domain                                                              feat      REL?  wide?
 ("khari-ca",        8.455, lambda L,R: mn(L)==STOP and obstruent(R) and vc(R)==0,               "voice", False, False),
 ("jaśtva",          8.239, lambda L,R: mn(L)==STOP and vc(R)==1,                                "voice", False, False),
 ("ścutva",          8.440, lambda L,R: (pl(L)==DENT and mn(L) in (STOP,NASAL) and pl(R)==PAL),  "place", False, False),
 ("ṣṭutva",          8.441, lambda L,R: (pl(L)==DENT and pl(R)==RETRO),                          "place", False, False),
 ("anusvāra",        8.323, lambda L,R: L=='__m' ,                                               "manner",False, False),  # set below
 ("m→parasavarṇa",   8.458, lambda L,R: mn(L)==NASAL and pl(L)==LAB and mn(R)==STOP,             "place", False, False),
 ("nasal-assim",     8.445, lambda L,R: mn(L)==STOP and mn(R)==NASAL,                            "manner",False, False),
 ("savarṇa-degem",   8.465, lambda L,R: mn(L)==STOP and mn(R)==STOP and pl(L)==pl(R),            "delete",True,  False),
 ("visarga→sib",     8.434, lambda L,R: mn(L)==VIS and vc(R)==0 and mn(R) in (STOP,SIB)
                                          and pl(R) in (PAL,RETRO,DENT),                          "place", False, False),
 ("visarga→r/ctx",   8.434, lambda L,R: mn(L)==VIS and vc(R)==1,                                 "visarga",False,True),  # depends on PRECEDING vowel
 ("visarga-stays",   8.336, lambda L,R: mn(L)==VIS and vc(R)==0 and pl(R) in (VEL,LAB),          "identity",False,False),
]

junctions = [(lf, rf) for lf in finals for rf in inits]
N = len(junctions)

tot_rel = 0          # total relational comparisons evaluated
rel_junctions = 0    # junctions incurring >=1 relational comparison
multi = 0            # junctions needing ordered application of >=2 rules (asiddha cost)
conflict = 0         # junctions where >=2 rules target the SAME feature w/ different result
wide = 0             # junctions whose rule needs a >2-segment context window
applied_counts = Counter()
cells = {}           # (Lclass, Rclass) -> set of outcome-signatures, for table-size proxy

for lf, rf in junctions:
    L, R = finals[lf], inits[rf]
    fired = []
    for name, sutra, dom, feat, isrel, isw in RULES:
        ok = (lf == 'm') if name == "anusvāra" and False else dom(L, R)  # placeholder
        # special-case anusvāra: L is m and R is a consonant
        if name == "anusvāra":
            ok = (lf == 'm' and mn(R) != VOWEL)
        if ok:
            fired.append((name, sutra, feat, isrel, isw))

    # relational comparisons the brain must EVALUATE at this junction:
    #  (a) the savarṇa equality test, evaluated whenever both are stops (eligible),
    #      regardless of outcome -- mirrors how vowel sandhi counted ik+ik.
    rel_here = 0
    if mn(L) == STOP and mn(R) == STOP:
        rel_here += 1                       # place(L)==place(R) test
    #  (b) vipratiṣedha: if >=2 rules fire, brain compares sūtra order to sequence them
    if len(fired) >= 2:
        rel_here += 1                       # at least one priority comparison
        multi += 1
    if rel_here:
        rel_junctions += 1
    tot_rel += rel_here

    # true conflict = two fired rules modify the SAME feature with different intent
    feats = [f for _, _, f, _, _ in fired]
    if len(feats) != len(set(feats)) and len(set(feats)) < len(feats):
        # same feature appears twice
        conflict += 1
    if any(isw for *_, isw in fired):
        wide += 1
    applied_counts[len(fired)] += 1

    lclass = (pl(L), mn(L)); rclass = (pl(R), vc(R), mn(R))
    cells.setdefault((lclass, rclass), set()).add(tuple(sorted(n for n, *_ in fired)))

print("Junctions:", N)
print("Relational comparisons per junction: %.3f   (vowel-sandhi baseline = 0.250)"
      % (tot_rel / N))
print("Junctions incurring >=1 relational comparison: %d / %d = %.0f%%"
      % (rel_junctions, N, 100*rel_junctions/N))
print("Multi-rule junctions (need ordered/asiddha application): %d / %d = %.0f%%"
      % (multi, N, 100*multi/N))
print("True same-feature conflicts (need vipratiṣedha value-arbitration): %d" % conflict)
print("Junctions whose rule needs a >2-segment context window (visarga): %d / %d = %.0f%%"
      % (wide, N, 100*wide/N))
print("Rules-fired-per-junction distribution:", dict(sorted(applied_counts.items())))
print("Distinct feature-class routing cells used: %d   (vowel-sandhi table = 9 cells)"
      % len(cells))
mixed_cells = sum(1 for sigs in cells.values() if len(sigs) > 1)
print("Mixed routing cells (not decided by class alone): %d" % mixed_cells)
