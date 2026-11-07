"""False notes per vowel sign on the page (correct reader): of the page's vowels written with each sign, the share
noted (any heard vowel), and what was heard instead."""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU
from nikud import parse_verse
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIGN = {'ַ': 'patah', 'ָ': 'kamats', 'ֵ': 'tsere', 'ֶ': 'segol', 'ִ': 'hiriq', 'ֹ': 'holam',
        'ֺ': 'holam', 'ֻ': 'kubutz', 'ֲ': 'hataf patah', 'ֱ': 'hataf segol', 'ֳ': 'hataf kamats',
        'ׇ': 'kamats katan', 'ּ': 'shuruk?'}
def groups(w):
    g = []
    for ch in w:
        if 'א' <= ch <= 'ת': g.append([ch, ''])
        elif g: g[-1][1] += ch
    return g
opp = collections.Counter(); hit = collections.Counter(); heard = collections.defaultdict(collections.Counter)
for r in RU.load(V, sys.argv[1] if len(sys.argv) > 1 else 'samra_bigA+samra_bigB'):
    if not r['clean']: continue
    rw = RU.raw_words(r['raw']['nikud']); pv = parse_verse(r['raw']['nikud'])
    if len(rw) != len(r['words']) or len(pv) != len(rw): continue
    N = RU.notes(r, furtive=True)
    for i, (_, L, us) in enumerate(pv):
        if r['marks'][i] == 'off': continue
        g = groups(rw[i]); nk = {d['k']: d['you'] for d in N.get(i, []) if d['src'] == 'nikud'}
        for u in us:
            if u['kind'] != 'vowel': continue
            k = u['k']; ms = g[k][1] if k < len(g) else ''
            s = next((SIGN[m] for m in ms if m in SIGN and m != 'ּ'), None)
            if s is None: s = 'shuruk' if (k < len(g) and g[k][0] == 'ו' and 'ּ' in ms) else 'mater/other:' + u['c']
            opp[s] += 1
            if k in nk: hit[s] += 1; heard[s][nk[k]] += 1
for s, n in opp.most_common():
    print(f'{s:16s} {hit[s]:4d}/{n:5d} = {100*hit[s]/n:4.1f}%   heard: ' + ', '.join(f'{h} {c}' for h, c in heard[s].most_common(4)))
