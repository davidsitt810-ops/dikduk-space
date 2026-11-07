"""E->I notes by context: is the page's e followed by a bare yod (tsere/segol male, "ey"), stressed, word-final?"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU
from nikud import parse_verse
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def ctx_of(us, k, L):
    """the page's vowel at letter k (the e) -> (a mater yod after it — the parser keeps no unit for it —, word-final)"""
    if not any(u['kind'] == 'vowel' and u['k'] == k for u in us): return None
    ck = {u['k'] for u in us if u['kind'] == 'cons'}
    mater = k + 1 < len(L) and L[k + 1] == 'י' and (k + 1) not in ck
    last = all(kk <= k for kk in ck) and not (k + 1 < len(L) and (k + 1) in ck)
    return ('yod after' if mater else 'no yod', 'word-final' if (last or (mater and k + 2 >= len(L))) else 'inside')
def run(name, want, planted):
    rows = RU.load(V, name); c = collections.Counter(); base = collections.Counter()
    for r in rows:
        if not r['clean']: continue
        pv = parse_verse(r['raw']['nikud']); P = set(r.get('planted') or [])
        N = RU.notes(r, furtive=True)
        for i, (_, L, us) in enumerate(pv):
            if planted and i not in P: continue
            if not planted and i in P: continue
            # every page-E vowel (the base) and the ones noted "I"
            for u in us:
                if u['kind'] == 'vowel' and u['c'] == 'E':
                    x = ctx_of(us, u['k'], L)
                    if x: base[x] += 1
            for d in N.get(i, []):
                if d['ref'] == 'E' and d['you'] == 'I':
                    x = ctx_of(us, d['k'], L)
                    if x is None and d['k'] > 0: x = ctx_of(us, d['k'] - 1, L)
                    c[x] += 1
    print(f'== {name} ({"planted words" if planted else "correct words"}): E->I notes by context (of the page-E vowels there)')
    for x in sorted(base): print(f'   {str(x):28s} {c[x]:4d} of {base[x]:5d} = {100*c[x]/max(1,base[x]):.1f}%')
    print('   unplaced', c[None])
run('samra_bigA+samra_bigB', 'EI', False)
run('samra_oneie', 'EI', True)
