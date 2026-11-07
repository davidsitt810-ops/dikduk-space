"""Kamats katan (U+05C7) on the page: what Faraj and Rabbi Alouf are heard saying there, by what follows it."""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU, vowel_rules as VR
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QQ, HQ, SH, MET = 'ׇ', 'ֳ', 'ְ', 'ֽ'
def letters(w):
    g = []
    for ch in w:
        if 'א' <= ch <= 'ת': g.append([ch, ''])
        elif g: g[-1][1] += ch
    return g
def kind(g, k):
    nxt = g[k + 1] if k + 1 < len(g) else None
    if nxt is None: return 'word-final'
    if HQ in nxt[1]: return 'before hataf kamats (אׇהֳלֶךָ)'
    if MET in g[k][1]: return 'with a meteg (שׇֽׁמְרֵנִי)'
    if SH in nxt[1] and k + 2 < len(g): return 'before a shva (שׇׁמְרֵנִי)'
    return 'other (כׇּל, חׇכְמָה…)'
tab = collections.defaultdict(collections.Counter); ex = collections.defaultdict(list)
for r in RU.load(V, 'samra_bigA+samra_bigB'):
    if not r['clean']: continue
    rw = RU.raw_words(r['raw']['nikud'])
    if len(rw) != len(r['words']): continue
    for i, w in enumerate(rw):
        g = letters(w)
        for k, (c, ms) in enumerate(g):
            if QQ not in ms: continue
            kd = kind(g, k)
            for who, src in (('Faraj', r['raw']['tw']), ('Alouf', r['raw']['rw'])):
                if not src or i >= len(src): continue
                sl = [s for s in VR.slots(src[i]) if s['k'] == k]
                h = sl[0]['heard'] if sl else '-'
                tab[(kd, who)][h] += 1
                if who == 'Faraj' and h == 'A': ex[kd].append(re.sub('[֑-ֽ֯׀׃]', '', w))
for kd in sorted({k for k, _ in tab}):
    for who in ('Faraj', 'Alouf'):
        c = tab[(kd, who)]; n = sum(c.values())
        print(f'{kd:34s} {who:6s} n={n:3d}  ' + '  '.join(f'{h} {100*v/n:.0f}%' for h, v in c.most_common()))
    print('     Faraj "a":', ' '.join(sorted(set(ex[kd]))[:20]))
