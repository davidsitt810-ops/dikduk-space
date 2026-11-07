"""Is a vowel note likelier on an unstressed vowel? Stress from the te'amim (Tehillim's poetic accents): the letter
that carries a stress accent (not dehi, which stands before the word, nor the geresh of revia mugrash, nor tsinnor,
which stands after it); silluq (the meteg of the pasuk's last word) when nothing else; else the last vowel.
usage: stress.py <kind like E->I> <exam>[+...] [planted]"""
import sys, os, json, collections
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.join(V, 'big'))
import rules as RU
import false_notes as FN
from nikud import parse_verse, clean_verse, NAME
NOT_STRESS = {'֭', '֝', '֮'}            # dehi, geresh muqdam, tsinnor
ACC = {chr(c) for c in range(0x0591, 0x05B0)} - NOT_STRESS
def stress_letter(word, last):
    i = -1; got = None; meteg = None
    for ch in word:
        if 'א' <= ch <= 'ת': i += 1
        elif ch in ACC and got is None: got = i
        elif ch == 'ֽ': meteg = i
    if got is None and last and meteg is not None: got = meteg
    return got
kind = sys.argv[1]; REF, YOU = kind.split('->'); rows = RU.load(V, sys.argv[2])
planted = any(r.get('planted') is not None for r in rows)
C = collections.Counter()   # (stressed?, noted?) over expected REF slots (correct) or planted REF slots (planted)
for r in rows:
    if not r['clean']: continue
    raw_words = clean_verse(r['raw']['nikud']).split(' ')
    pv = parse_verse(r['raw']['nikud'])
    if len(pv) != len(r['words']) or len(raw_words) != len(pv): continue
    P = set(r.get('planted') or [])
    notes = collections.defaultdict(set)
    for w_, ds in RU.notes(r).items():
        for n in ds:
            if (n['ref'], n['you']) == (REF, YOU): notes[w_].add(n['k'])
    for i, (w, l, us) in enumerate(pv):
        if r['marks'][i] == 'off' or NAME.search(w): continue
        if planted and i not in P: continue
        if not planted and i in P: continue
        sk = stress_letter(raw_words[i], i == len(pv) - 1)
        ev = [u for u in us if u['kind'] == 'vowel']
        if sk is None and ev: sk = ev[-1]['k']
        for u in ev:
            if u['c'] != REF: continue
            hit = any(k == u['k'] or abs(k - u['k']) == 1 for k in notes.get(i, ()))
            C[(u['k'] == sk, hit)] += 1
for s in (True, False):
    n = C[(s, True)] + C[(s, False)]
    print(f'{"stressed  " if s else "unstressed"} {REF} slots {n}: {kind} note on {C[(s, True)]} = {100 * C[(s, True)] / max(1, n):.1f}%')
