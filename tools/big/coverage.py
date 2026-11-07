"""How often the ear places a vowel slot where the nikud has a vowel: per expected vowel on clean takes, is there a
slot at that letter (or a compatible neighbour, vowels.compat) in the student's path, and in the hazzan's (Rabbi
Alouf's) on the same pasuk? By vowel class, and for the planted vowels the exam missed.
usage: coverage.py <exam with the hazzan (raw rw)> [<planted exam> ...]"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
vowels, VR = RU.vowels, RU.VR

def covered(slots, k, L):
    return any(vowels.compat(s['k'], k, L) for s in slots)

def per_row(r):
    raw = r['raw']; pv = RU.parse_verse(raw['nikud'])
    if not r['clean'] or len(pv) != len(r['words']): return None
    exp = RU.expected(pv, True, RU.raw_words(raw['nikud']))
    stu = {i: VR.slots(w) for i, w in enumerate(raw['tw'])}
    haz = {i: VR.slots(w) for i, w in enumerate(raw['rw'])} if raw.get('rw') else None
    L = {i: l for i, (_, l, _) in enumerate(pv)}
    return exp, stu, haz, L

if __name__ == '__main__':
    base = sys.argv[1]; c = collections.Counter()
    for r in RU.load(V, base):
        x = per_row(r)
        if not x: continue
        exp, stu, haz, L = x
        for i, es in exp.items():
            for e in es:
                v = e['heard']
                if v not in 'AEIOU': continue
                s_ok = covered(stu.get(i, []), e['k'], L[i]); h_ok = covered(haz.get(i, []), e['k'], L[i]) if haz else None
                c[(v, 'n')] += 1; c[(v, 'stu')] += s_ok; c[(v, 'haz')] += bool(h_ok); c[(v, 'stu no, haz yes')] += (not s_ok) and bool(h_ok)
                c[(v, 'both no')] += (not s_ok) and (h_ok is False)
    print(f'{base}: expected vowels with a slot in the path (clean takes)')
    print(f'  {"vowel":5s} {"n":>6s} {"student":>9s} {"hazzan":>9s} {"student no, hazzan yes":>23s} {"neither":>8s}')
    for v in 'AEIOU':
        n = c[(v, 'n')]
        if n: print(f'  {v:5s} {n:6d} {100*c[(v,"stu")]/n:8.1f}% {100*c[(v,"haz")]/n:8.1f}% {100*c[(v,"stu no, haz yes")]/n:22.1f}% {100*c[(v,"both no")]/n:7.1f}%')
    for pl in sys.argv[2:]:
        m = collections.Counter()
        for r in RU.load(V, pl):
            x = per_row(r)
            if not x or not r.get('planted'): continue
            exp, stu, haz, L = x; g = RU.noted(r, furtive=True)
            for i in r['planted']:
                told = i in g or r['marks'][i] == 'off'
                # the planted vowel(s): where the planted page differs from the original (the exam row keeps both nikuds?)
                m['planted'] += 1; m['told'] += told
                if not told:
                    m['missed'] += 1
                    m['missed: a slot for every expected vowel' if all(covered(stu.get(i, []), e['k'], L[i]) for e in exp[i] if e['heard'] in 'AEIOU') else 'missed: some vowel without a slot'] += 1
        print(f'{pl}:', dict(m))
