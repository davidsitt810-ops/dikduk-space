"""The letter checker's rules, measured: letters_rows.json (letters_study.py) through letters.verdict — per letter and
variant, Rabbi Alouf's word-initial letters (should be RIGHT) and Israelis reading (ע ח ק ט צ ר should be WRONG — they
say them the Israeli way; א ת should be RIGHT) — plus the numbers behind the thresholds and a small grid.
usage: letters_rules.py [rows.json] [--grid]"""
import sys, os, json, collections
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import letters as LT
HERE = os.path.dirname(os.path.abspath(__file__))
f = next((a for a in sys.argv[1:] if a.endswith('.json')), os.path.join(HERE, 'letters_rows.json'))
rows = json.load(open(f, encoding='utf-8'))
EXPECT_IL = {'ע': 'wrong', 'ח': 'wrong', 'ק': 'wrong', 'ט': 'wrong', 'צ': 'wrong', 'ר': 'wrong', 'א': 'right', 'ת': 'right'}
import re
SHEVA = '\u05b0'
def first_vowel(p):
    """the vowel under a pointed word's first letter: A E I O U, 'sheva', or '?'"""
    p = re.sub('[\u0591-\u05af\u05bd\u05bf\u05c0\u05c4\u05c5]', '', p); m = re.match(r'[\u05d0-\u05ea]([\u05b0-\u05bc\u05c1\u05c2\u05c7]*)', p); marks = m.group(1) if m else ''
    if SHEVA in marks: return 'sheva'
    for ch, cls in [('\u05b7', 'A'), ('\u05b8', 'A'), ('\u05b2', 'A'), ('\u05c7', 'O'), ('\u05b3', 'O'), ('\u05b9', 'O'), ('\u05ba', 'O'), ('\u05b6', 'E'), ('\u05b5', 'E'), ('\u05b1', 'E'), ('\u05b4', 'I'), ('\u05bb', 'U')]:
        if ch in marks: return cls
    if 'ו' in p[1:3]: return 'O'
    return '?'
def pct(n, d): return f'{100 * n / d:.0f}%' if d else '-'
def dist(vals): return f'p10/50/90 {np.percentile(vals, 10):.2f}/{np.percentile(vals, 50):.2f}/{np.percentile(vals, 90):.2f}' if len(vals) else '-'
def want_of(r):
    L = LT.BY_C.get(r['c'])
    if not L or not L.get('want'): return None
    return r.get('var')
def run(rows, label, show=True):
    print(f'\n== {label}: {len(rows)} rows')
    tot = collections.Counter()
    for L in LT.LETTERS:
        c = L['c']
        variants = [w[0] for w in L['want']] if L.get('want') else [None]
        for want in variants:
            for src in ('al', 'il'):
                R = [r for r in rows if r['src'] == src and r['c'] == c and (want is None or r.get('var') == want)]
                if src == 'al' and L['kind'] == 'emphatic': R = [r for r in R if first_vowel(r.get('pointed') or '') in ('A', 'O', 'U')]   # the checker asks for "a"
                if not R: continue
                if src == 'il' and L.get('want'): continue   # no nikud: the Israeli variant is unknown
                V = collections.Counter(LT.verdict(c, want, r)['v'] for r in R)
                n = len(R); exp = 'right' if src == 'al' else EXPECT_IL.get(c)
                s = f"  {c} {want or '':3s} {'Alouf   ' if src == 'al' else 'Israeli '} n={n:4d}  right {V['right']:4d} ({pct(V['right'], n)})  wrong {V['wrong']:4d} ({pct(V['wrong'], n)})  unsure {V['unsure'] + V['no_speech']:4d} ({pct(V['unsure'] + V['no_speech'], n)})"
                if exp: s += f"   expected {exp}" + ('  <-- miss ' + pct(V['wrong' if exp == 'right' else 'right'], n) if V['wrong' if exp == 'right' else 'right'] else '')
                if exp: tot[(src, 'n')] += n; tot[(src, 'hit')] += V[exp]; tot[(src, 'miss')] += V['wrong' if exp == 'right' else 'right']
                if show: print(s)
                if show and L['kind'] not in ('throat', 'plain', 'resh'):
                    E = LT.EV.get((c, want)) or LT.EV.get((c, None))
                    print(f"        for {dist([LT.ev_peak(r, E['for']) for r in R])}   against {dist([LT.ev_peak(r, E['against']) for r in R])}")
                if show and L['kind'] in ('throat', 'plain'):
                    vt = collections.Counter();
                    for r in R:
                        th = r.get('throat') or {}; votes = th.get('votes') or {}
                        for k in ('head', 'classifier', 'arabic'):
                            vt[(k, 'throat' if k in votes.get('throat', []) else 'plain' if k in votes.get('plain', []) else '-')] += 1
                    print('        votes:', {f'{k} {v}': n for (k, v), n in sorted(vt.items())})
    print(f"  Alouf right {tot[('al', 'hit')]}/{tot[('al', 'n')]} ({pct(tot[('al', 'hit')], tot[('al', 'n')])}), called wrong {tot[('al', 'miss')]} ({pct(tot[('al', 'miss')], tot[('al', 'n')])}) · Israelis as expected {tot[('il', 'hit')]}/{tot[('il', 'n')]} ({pct(tot[('il', 'hit')], tot[('il', 'n')])}), the opposite {tot[('il', 'miss')]} ({pct(tot[('il', 'miss')], tot[('il', 'n')])})")
    return tot
run(rows, 'the rules in letters.py')
if '--grid' in sys.argv:
    print('\n== grid over hi/lo for the peak letters (Alouf right% / Alouf wrong% / Israeli wrong% where expected)')
    for L in LT.LETTERS:
        if L['kind'] in ('throat', 'plain', 'resh'): continue
        c = L['c']; variants = [w[0] for w in L['want']] if L.get('want') else [None]
        for want in variants:
            E = LT.EV.get((c, want)) or LT.EV.get((c, None)); keep = (E['hi'], E['lo'])
            RA = [r for r in rows if r['src'] == 'al' and r['c'] == c and (want is None or r.get('var') == want)]
            RI = [r for r in rows if r['src'] == 'il' and r['c'] == c] if not L.get('want') else []
            line = []
            for hi in (.3, .4, .5, .6, .7):
                for lo in (.1, .2, .3):
                    E['hi'], E['lo'] = hi, lo
                    va = collections.Counter(LT.verdict(c, want, r)['v'] for r in RA); vi = collections.Counter(LT.verdict(c, want, r)['v'] for r in RI)
                    line.append(f"hi{hi} lo{lo}: {pct(va['right'], len(RA))}/{pct(va['wrong'], len(RA))}" + (f"/{pct(vi['wrong'], len(RI))}" if RI else ''))
            E['hi'], E['lo'] = keep
            print(f"  {c} {want or ''}: " + ' | '.join(line))
