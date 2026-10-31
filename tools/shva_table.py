"""Tables from shva_rows2.json: per rule, what is heard (A = e-like slot, B = any-vowel slot, and combinations).
usage: shva_table.py [rows] [perek range lo-hi]"""
import json, sys, collections
R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'shva_rows2.json', encoding='utf-8'))
if len(sys.argv) > 2: lo, hi = map(int, sys.argv[2].split('-')); R = [r for r in R if lo <= r['per'] <= hi]
def hA(r, tv=.5, tn=.05): a = r['A']; return 'vowel' if a['used'] and a['mass'] >= tv else 'none' if (not a['used'] and a['gapmax'] < tn) else 'unsure'
def hB(r, tv=.5, tn=.05): b = r['B']; return 'vowel' if b['used'] and b['mass'] >= tv else 'none' if (not b['used'] and b['gapmax'] < tn) else 'unsure'
def hC(r):   # vowel by A (e-like), none by B (no vowel at all)
    a = hA(r); b = hB(r)
    return 'vowel' if a == 'vowel' else 'none' if b == 'none' else 'unsure'
by = collections.defaultdict(list)
for r in R:
    if r['B'] is None: continue
    by[(r['kind'], r['rule'])].append(r)
print(len(R), 'shvas,', len({(r['per'], r['ps']) for r in R}), 'pesukim')
for name, h in (('A (e-like)', hA), ('B (any vowel)', hB), ('C (vowel by A, none by B)', hC)):
    print(f"\n{name}\n{'rule':18s} {'n':>5s} {'vowel':>6s} {'none':>6s} {'unsure':>7s}")
    for (k, ru), rs in sorted(by.items(), key=lambda kv: (kv[0][0], -len(kv[1]))):
        c = collections.Counter(h(r) for r in rs); n = len(rs)
        print(f"{k + ' ' + ru:18s} {n:5d} {c['vowel'] / n:6.0%} {c['none'] / n:6.0%} {c['unsure'] / n:7.0%}")
