"""Planted words NOT told on clean takes: what the ear heard in the planted slots (the page's planted vowel X, the
reader's real Y). usage: missed.py <exam> <X> <Y>"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU, vowel_rules as VR
from nikud import parse_verse
import json
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IDX = json.load(open(os.path.join(os.path.dirname(V), 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))['perakim']
nm, X, Y = sys.argv[1], sys.argv[2], sys.argv[3]
c = collections.Counter(); ex = []
for r in RU.load(V, nm):
    if not r['clean']: continue
    pv = parse_verse(r['raw']['nikud']); P = set(r.get('planted') or [])
    po = parse_verse(IDX[str(r['per'])]['pesukim'][r['ps']]['nikud'])
    if len(pv) != len(r['words']) or len(po) != len(pv): continue
    N = RU.notes(r, furtive=True)
    for i in P:
        if i in N or r['marks'][i] == 'off': continue
        us = pv[i][2]; uo = po[i][2]
        if len(us) != len(uo): continue
        ks = [u['k'] for u, o in zip(us, uo) if u['kind'] == 'vowel' and u['c'] == X and o['c'] != X]   # the planted ones only
        sl = VR.slots(r['raw']['tw'][i])
        for k in ks:
            got = [s for s in sl if s['k'] == k]
            if not got: c['no slot there'] += 1; continue
            s = got[0]; tot = sum(s['mass'].values()) or 1e-9
            c[f"heard {s['heard']}" + (' (unclear)' if not RU.vowels.clear(s, 2.0) else '')] += 1
            if len(ex) < 12: ex.append((r['per'], r['ps'] + 1, r['words'][i], k, s['heard'], {a: round(b / tot, 2) for a, b in s['mass'].items() if b / tot > .03}))
print(nm, 'missed planted vowels on clean takes:', dict(c))
for e in ex: print('  ', e)
