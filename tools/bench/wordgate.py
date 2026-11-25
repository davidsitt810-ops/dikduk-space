"""A vowel gate per word. Today the vowel notes are all-or-nothing per take (rule.vclean_of: the letter head's median
on the line, and the line gap); a take under the gate shows no vowel note at all, also on the words that were heard
well. This asks, on the takes the gate shuts: if the notes were shown on the words that pass a test of their own,
how many of those words would get a false note (the reader's correct reading), and how many planted mistakes would
be told (tools/plant.py, one planted word per pasuk, replayed offline: bench/replay.py).

The tests tried, per word: the letter head's score on the word (hskel), the vowel head's own letter score on it
(vskel), both, with the word's mark ✓ or not red, and with a floor on the take's letter-head median.
For comparison, the same words-with-a-note rates on the takes the gate already opens (the live rule).

usage: wordgate.py <exam name> [...]          DK_LAB_V: where the exams are
       GATES=h.7,v.8,hv.75,...                the tests to list (default: a sweep); FLOOR=.45 (the take's median at least)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as RP
rule = RP.rule; pct = RP.pct
KINDS = ('EI', 'EA', 'IE', 'OU', 'UO')
FLOOR = float(os.environ['FLOOR']) if os.environ.get('FLOOR') else None

def word_ok(spec, tw, mark):
    """spec: h<T> (hskel >= T), v<T> (vskel >= T), hv<T> (both), m<T> (their mean); a leading '+' = the word's mark must be ✓"""
    need_ok = spec.startswith('+'); spec = spec.lstrip('+')
    if mark == 'off' or (need_ok and mark != 'ok'): return False
    h = tw.get('hskel'); v = tw.get('vskel')
    if spec.startswith('hv'): T = float(spec[2:]); return h is not None and v is not None and h >= T and v >= T
    if spec.startswith('h'): return h is not None and h >= float(spec[1:])
    if spec.startswith('v'): return v is not None and v >= float(spec[1:])
    if spec.startswith('m'): return h is not None and v is not None and (h + v) / 2 >= float(spec[1:])
    raise ValueError(spec)

def study(rows, spec):
    """on the takes the live gate shuts (and the words made out): the words the test opens, those of them with a note on
       the correct reading (false), and per planted kind the planted words told by a note"""
    c = collections.Counter()
    for r in rows:
        TW = r['raw']['rule_in']['tw']
        for kind in (None,) + KINDS:
            N = RP.notes(r, kind)
            if N is None: continue
            M = RP.marks(r, ref=kind is None); m, clean, vclean, ch, lw = M
            shut = (not vclean) and not ch and not r.get('no_speech')
            if FLOOR is not None and shut and (rule.head_median(TW) or 0) < FLOOR: shut = False; c['under_floor'] += kind is None
            nt = RP.noted(N); P = set(N['planted'])
            if kind is None:
                c['takes'] += 1; c['shut'] += shut
                for i in range(len(m)):
                    if not m[i]: continue
                    if shut:
                        c['W_shut'] += 1
                        if word_ok(spec, TW[i], m[i]): c['W_open'] += 1; c['false'] += i in nt
                    elif vclean and not ch and not r.get('no_speech'):
                        c['W_live'] += 1; c['false_live'] += (i in nt and m[i] != 'off')
            else:
                for i in P:
                    if shut:
                        c[f'P_{kind}'] += 1; c['P'] += 1
                        if word_ok(spec, TW[i], m[i]) and i in nt: c[f'told_{kind}'] += 1; c['told'] += 1
                    elif vclean and not ch and not r.get('no_speech'):
                        c['P_live'] += 1; c['told_live'] += (i in nt and m[i] != 'off')
                if shut: c['false_planted_runs'] += sum(1 for i in nt - P if word_ok(spec, TW[i], m[i])); c['W_planted_runs'] += sum(1 for i in range(len(m)) if i not in P and word_ok(spec, TW[i], m[i]))
    return c

if __name__ == '__main__':
    specs = os.environ['GATES'].split(',') if os.environ.get('GATES') else [f'{a}{t}' for a in ('h', 'v', 'hv', '+hv') for t in ('.6', '.7', '.75', '.8', '.85', '.9')]
    for name in sys.argv[1:]:
        rows = RP.load(name)
        if rows and 'vskel' not in rows[0]['raw']['rule_in']['tw'][0]: print(f'{name}: no vskel in the rows (an exam from before v6.0)'); continue
        c = study(rows, specs[0])
        print(f'== {name}: {c["takes"]} takes; the live gate shuts {c["shut"]} of them ({c["W_shut"]} words made out)' + (f', {c["under_floor"]} more under the floor {FLOOR}' if FLOOR is not None else ''))
        print(f'   where the gate is open today: words with a false note {pct(c["false_live"], c["W_live"])}; planted mistakes told by a note {pct(c["told_live"], c["P_live"])}')
        print('   on the shut takes, the notes shown on the words that pass:')
        print('   test    | words opened            | of them a false note        | planted told (of all planted words on shut takes) | per kind EI EA IE OU UO')
        for spec in specs:
            c = study(rows, spec)
            per = ' '.join(f'{c[f"told_{k}"]}/{c[f"P_{k}"]}' for k in KINDS)
            print(f'   {spec:7s} | {pct(c["W_open"], c["W_shut"]):23s} | {pct(c["false"], c["W_open"]):27s} | {pct(c["told"], c["P"]):30s} | {per}')
