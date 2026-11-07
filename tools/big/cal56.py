"""Two heads on the same takes under v5.6 as a whole: the furtive patah AND the drop bar at 20. Each exam's marks are
replayed from its stored rule inputs at drop 20 (drops.marks; checked first against a v5.6 server run, which must be
reproduced word for word), or taken as stored when the name ends in '@' (a v5.6 server run). Notes with the furtive
fix, never on a red word. Paired by take (perek, pasuk).
Correct readers: words with a vowel note, words red. Planted: planted words told (noted or red), other words noted / red.
usage: cal56.py <base exam>[@] <new exam>[@] [lo-hi]"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU, drops as D
V = D.V; pct = D.pct

def rows(spec, lo, hi):
    name = spec.rstrip('@'); as_is = spec.endswith('@'); out = {}
    for r in RU.load(V, name, lo, hi):
        if not as_is:
            if 'rule_in' not in r['raw']: sys.exit(f'{name}: a row without rule inputs ({r["per"]}:{r["ps"]}); run it through v5.6 and pass it with @')
            r = dict(r, marks=D.marks(r, drop=20))
        out[(r['per'], r['ps'])] = r
    return out

def selfcheck(name='samra_v56B'):
    """drops.marks at drop 20 must give the v5.6 server's own marks on every take of a v5.6 run"""
    bad = n = 0
    for r in RU.load(V, name):
        if 'rule_in' not in r['raw']: continue
        n += 1; bad += D.marks(r, drop=20) != r['marks']
    return n, bad

if __name__ == '__main__':
    n, bad = selfcheck(); print(f'self-check: the drop-20 replay of samra_v56B reproduces the v5.6 server on {n - bad} of {n} takes')
    a_spec, b_spec = sys.argv[1], sys.argv[2]; lo, hi = (int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else '1-150').split('-'))
    A, B = rows(a_spec, lo, hi), rows(b_spec, lo, hi); keys = sorted(set(A) & set(B))
    planted = any(A[k].get('planted') is not None for k in keys)
    t = {'a': [0] * 6, 'b': [0] * 6}; only_a = only_b = 0; skipped = 0
    for k in keys:
        ra, rb = A[k], B[k]
        if len(ra['words']) != len(rb['words']): skipped += 1; continue
        P = set(ra.get('planted') or []); ga, gb = RU.noted(ra, furtive=True), RU.noted(rb, furtive=True)
        for nm, r, g in (('a', ra, ga), ('b', rb, gb)):
            x = t[nm]
            x[0] += sum(1 for i in P if i in g or r['marks'][i] == 'off'); x[1] += len(P)
            x[2] += len(g - P); x[3] += len(r['words']) - len(P)
            x[4] += sum(1 for i, m in enumerate(r['marks']) if m == 'off' and i not in P)
            x[5] += sum(1 for i in P if r['marks'][i] == 'off')
        if planted:
            for i in P:
                ta = i in ga or ra['marks'][i] == 'off'; tb = i in gb or rb['marks'][i] == 'off'
                only_a += ta and not tb; only_b += tb and not ta
        else:
            only_a += len((ga - gb) - P); only_b += len((gb - ga) - P)
    a, b = t['a'], t['b']
    print(f'{a_spec} vs {b_spec}, perakim {lo}-{hi}: {len(keys)} takes in common ({len(A)} / {len(B)}), {skipped} left out (word counts differ)')
    if planted:
        print(f'   planted told {pct(a[0], a[1])} -> {pct(b[0], b[1])}   (told only by the base {only_a}, only by the new {only_b}; of them red {a[5]} / {b[5]})')
        print(f'   other words noted {pct(a[2], a[3])} -> {pct(b[2], b[3])}')
    else:
        print(f'   words with a vowel note {pct(a[2], a[3])} -> {pct(b[2], b[3])}   (noted only under the base {only_a}, only under the new {only_b})')
    print(f'   other words red {a[4]} -> {b[4]}')
