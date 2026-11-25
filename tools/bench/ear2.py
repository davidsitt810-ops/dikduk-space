"""A prototype: the PHONE ear as a vowel checker of its own. The vowel head misses about a quarter of the planted
mistakes; some of them it has no slot for at all (David's "yarbesseni", Nov 1: no vowel slot after the ב, while the
phone ear wrote r b e t e n i). Here the phone ear's vowels are lined up with the nikud's between the consonants it
placed (its own anchors), and a vowel of another class than the page's is a candidate note — with the vowel head as
ITS second opinion (it heard the page's vowel there: 'ref'; the same wrong one: 'you'; no slot there: 'none').

Measured on an exam's kept answers (bench/replay.py): the correct reading (every candidate false) and the planted
kinds (a candidate on the planted word, of the planted kind: a catch), next to what the vowel head's notes give.
Nothing here is in the product; it says whether it is worth building.

usage: ear2.py <exam name> [...]       CONF=.5,.6,.7,.8,.9 (the phone ear's confidence bars to list)"""
import sys, os, collections, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as RP
VW, NK, rule, pct = RP.VW, RP.NK, RP.rule, RP.pct
ANCHOR_P = 0.3

def phone_notes(out, nik):
    """-> {word: [{'k', 'ref', 'ph' (the phone ear's classes), 'c' (its confidence), 't', 'head' ('ref'/'you'/'other'/'none')}]}"""
    pv = NK.parse_verse(nik); TW = out['take']['words']; res = {}
    if len(pv) != len(TW): return res
    ctx = VW.vowel_context(pv); PH = [(p['t'], VW.PHONE_VOWEL[p['p']], p.get('c') or 0) for p in out['take'].get('phones') or [] if p.get('p') in VW.PHONE_VOWEL]
    for i, (w, letters, us) in enumerate(pv):
        if NK.NAME.search(w): continue
        t = TW[i]
        if t.get('t0') is None: continue
        exp = VW.expected_vowels(us, ctx['stress'][i]); anc = sorted((c['k'], c['t0']) for c in (t.get('cons') or []) if c.get('t0') is not None and (c.get('p') or 0) >= ANCHOR_P)
        lo = TW[i - 1]['t1'] if i and TW[i - 1].get('t1') is not None else t['t0'] - .15; hi = TW[i + 1]['t0'] if i + 1 < len(TW) and TW[i + 1].get('t0') is not None else t['t1'] + .15
        cuts = [(-1, max(lo, t['t0'] - .15))] + anc + [(10 ** 6, min(hi, t['t1'] + .15))]
        for (ka, ta), (kb, tb) in zip(cuts, cuts[1:]):
            E = [e for e in exp if ka <= e['k'] < kb] if ka >= 0 else [e for e in exp if e['k'] < kb]
            P = [p for p in PH if ta < p[0] < tb] if ka >= 0 else [p for p in PH if ta <= p[0] < tb]
            if not E or len(E) != len(P): continue
            for e, (pt, pc, conf) in zip(E, P):
                if e['heard'] in pc: continue
                # the vowel head's opinion: its slot nearest in time
                best = None
                for s in t.get('vow') or []:
                    if s.get('t0') is None: continue
                    d = abs((s['t0'] + s['t1']) / 2 - pt)
                    if d <= VW.PHONE_NEAR and (best is None or d < best[0]): best = (d, s)
                head = 'none' if best is None else 'ref' if best[1]['heard'] == e['heard'] else 'you' if best[1]['heard'] in pc else 'other'
                res.setdefault(i, []).append({'k': e['k'], 'ref': e['heard'], 'ph': pc, 'c': conf, 't': pt, 'head': head, 'stress': e.get('stress')})
    return res

if __name__ == '__main__':
    CONF = [float(x) for x in os.environ.get('CONF', '.5,.6,.7,.8,.9').split(',')]
    for name in sys.argv[1:]:
        rows = RP.load(name); A = collections.Counter()
        cand = []   # (kind, planted word?, of the planted kind?, conf, head opinion, head note shown on the word?, mark)
        for r in rows:
            for kind in (None,) + RP.ORDER:
                out, P = RP.answer(r, kind); P = set(P); nik = r['nikud'] if kind is None else RP.planted(r, kind)[2]
                sm = rule.summarize(out); told = {v['i'] for v in sm['vowels']}; m = sm['marks']
                if sm['cant_hear'] or sm['no_speech']: continue
                N = phone_notes(out, nik)
                if kind is None:
                    A['W'] += sum(1 for x in m if x); A['head_false'] += len(told)
                    for i, ds in N.items():
                        for d in ds: cand.append(('right', False, False, d['c'], d['head'], i in told, m[i], sm['vclean']))
                else:
                    for i in P:
                        A['P'] += 1; A['head_told'] += i in told or m[i] == 'off'
                        hit = [d for d in N.get(i, []) if kind[0] in d['ph'] and d['ref'] == kind[1]]
                        if hit:
                            d = max(hit, key=lambda d: d['c']); cand.append((kind, True, True, d['c'], d['head'], i in told, m[i], sm['vclean']))
                        A['P_' + kind] += 1; A['head_' + kind] += i in told or m[i] == 'off'
        print(f'== {name}: {len(rows)} takes; the vowel head today: false notes on {pct(A["head_false"], A["W"])} of the right words, planted told {pct(A["head_told"], A["P"])}')
        for hl, hs in (('any', ('ref', 'you', 'other', 'none')), ('the head does not contradict', ('you', 'other', 'none')), ('the head has no slot there', ('none',)), ('the head agrees', ('you',))):
            print(f'   the phone ear\'s own notes, {hl}:')
            for c in CONF:
                F = [x for x in cand if x[0] == 'right' and x[3] >= c and x[4] in hs and x[6] != 'off']; newF = [x for x in F if not x[5]]
                H = [x for x in cand if x[1] and x[3] >= c and x[4] in hs and x[6] != 'off']; newH = [x for x in H if not x[5]]
                per = ' '.join(f'{k} {sum(1 for x in newH if x[0] == k)}' for k in RP.ORDER)
                print(f'     sure >= {c:.1f}: false {len(F):4d} ({100 * len(F) / max(1, A["W"]):.2f}% of right words; {len(newF)} the head does not show) | planted caught {len(H):4d} of {A["P"]}; NEW (the head does not tell them) {len(newH):3d} = +{100 * len(newH) / max(1, A["P"]):.1f} points  [{per}]')
