"""Word-initial ע and ח for the letter checker: which combination of the three ears (letter head ratio, v2 classifier,
Arabic peak) separates Rabbi Alouf's (throat) from the Israelis' (plain) best, with few false "wrong" on Alouf.
Reads letters_rows.json."""
import sys, os, json, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, 'letters_rows.json'), encoding='utf-8'))
def F(r):
    th = r['throat']; c = r['c']; key = 'ח' if c == 'ח' else 'ע'; alt = 'כ' if c == 'ח' else 'א'
    hm = (th.get('head') or {}).get('mass') or {}; tot = hm.get(key, 0) + hm.get(alt, 0)
    ar = th.get('ar') or {}
    return {'rh': (hm.get(key, 0) / tot) if tot >= .2 else None, 'tot': tot, 'p2': th.get('p2'), 'p': th.get('p'), 'ar': ar.get('ع' if key == 'ע' else 'ح', 0), 'alef': ar.get('alef', 0), 'kh': max(ar.get('خ', 0), ar.get('ه', 0)), 'phones': [x[0] for x in r['phones'][:3]]}
def votes(f, c, arabic_plain=False, nomass_plain=False, p_hi=.6, p_lo=.3, ar_hi=.5):
    t, p = [], []
    if f['rh'] is not None:
        if f['rh'] >= .7: t.append('head')
        elif f['rh'] <= .3: p.append('head')
    elif nomass_plain: p.append('head0')
    pc = f['p2'] if f['p2'] is not None else f['p']
    if pc is not None:
        if pc >= p_hi: t.append('clf')
        elif pc <= p_lo: p.append('clf')
    if f['ar'] >= ar_hi: t.append('ar')
    elif arabic_plain and f['ar'] < .15 and (c == 'ח' and f['kh'] >= .4 or c == 'ע' and f['alef'] >= .4): p.append('ar')
    if len(t) >= 2 and not p: return 'throat'
    if len(p) >= 2 and not t: return 'plain'
    return 'unsure'
for c in 'עח':
    A = [F(r) for r in R if r['src'] == 'al' and r['c'] == c and r.get('throat')]; I = [F(r) for r in R if r['src'] == 'il' and r['c'] == c and r.get('throat')]
    print(f'\n== {c}: Alouf {len(A)} (should be throat) · Israelis {len(I)} (should be plain)')
    for name, kw in [('as the line checker (arabic plain vote)', dict(arabic_plain=True)), ('no arabic plain vote', {}), ('no arabic plain, head-no-mass = plain vote', dict(nomass_plain=True)),
                     ('…and classifier .5/.4', dict(nomass_plain=True, p_hi=.5, p_lo=.4)), ('…and arabic peak .4', dict(nomass_plain=True, p_hi=.5, p_lo=.4, ar_hi=.4)), ('no arabic plain, clf .5/.4, ar .4', dict(p_hi=.5, p_lo=.4, ar_hi=.4))]:
        va = collections.Counter(votes(f, c, **kw) for f in A); vi = collections.Counter(votes(f, c, **kw) for f in I)
        print(f"  {name:48s} Alouf right {va['throat']:3d} ({100 * va['throat'] / len(A):.0f}%) wrong {va['plain']:2d} ({100 * va['plain'] / len(A):.0f}%) unsure {va['unsure']:3d} | Israelis caught {vi['plain']:3d} ({100 * vi['plain'] / max(1, len(I)):.0f}%) called throat {vi['throat']:2d} ({100 * vi['throat'] / max(1, len(I)):.0f}%) unsure {vi['unsure']:2d}")
    print('  Alouf head-no-mass:', sum(f['rh'] is None for f in A), ' Israelis head-no-mass:', sum(f['rh'] is None for f in I))
    print('  Israeli rows called throat (any rule):', [(f['rh'], round(f['tot'], 2), f['p2'], f['ar'], f['phones']) for f in I if votes(f, c) == 'throat' or votes(f, c, nomass_plain=True, p_hi=.5, p_lo=.4, ar_hi=.4) == 'throat'])
