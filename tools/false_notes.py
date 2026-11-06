"""Where the false vowel notes on a correct reader come from (rule A, the server's since v5.3): every note shown on a
correct take, by what the page says -> what the ear heard, by source (hazzan / nikud), by the slot's place in the word
and the letter it follows, and how sure the ear was (m = the winner's share of the vowel mass, p = the slot's score).
usage: false_notes.py exam.json [planted_exam.json]"""
import sys, os, json, collections
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, 'tools'))
from nikud import parse_verse
from vowels import vowel_notes, expected_vowels
import vowel_rules as VR

def notes_detail(r):
    raw = r['raw']; W = r['words']
    pv = parse_verse(raw['nikud'])
    if len(pv) != len(W) or not r['clean']: return []
    letters = {i: l for i, (_, l, _) in enumerate(pv)}
    exp = {i: expected_vowels(us) for i, (_, _, us) in enumerate(pv)}   # as the server (v5.6: a furtive patah where it is said)
    stu = {i: VR.slots(w) for i, w in enumerate(raw['tw'])}
    haz = {i: VR.slots(w) for i, w in enumerate(raw['rw'])} if raw['rw'] else {}
    vh, vn = vowel_notes(stu, haz if haz else None, exp, letters); vh = vh or {}; vn = vn or {}
    out = []
    for src, d in (('hazzan', vh), ('nikud', vn)):
        for i, ds in d.items():
            if r['marks'][int(i)] == 'off': continue
            L = letters[int(i)]; sl = stu.get(int(i), [])
            for x in ds:
                k = x['k']; pos = [s['k'] for s in sl].index(k) if k in [s['k'] for s in sl] else -1
                p = next((s['p'] for s in sl if s['k'] == k), None)
                out.append({'w': int(i), 'word': W[int(i)], 'src': src, 'ref': x['ref'], 'you': x['you'], 'm': x['m'], 'p': p,
                            'after': L[k] if 0 <= k < len(L) else '?', 'next': L[k + 1] if k + 1 < len(L) else '#',
                            'place': 'only' if len(sl) == 1 else ('first' if pos == 0 else ('last' if pos == len(sl) - 1 else 'mid'))})
    return out

def report(fn):
    rows = [r for r in json.load(open(fn, encoding='utf-8')) if 'raw' in r and 'words' in r]
    planted = any(r.get('planted') is not None for r in rows)
    allN = []
    for r in rows:
        P = set(r.get('planted') or [])
        for n in notes_detail(r):
            if n['w'] in P: continue   # a planted word: a catch, not a false note
            allN.append(n)
    words = len({(id(r), n['w']) for r in rows for n in []})
    print(f'\n== {os.path.basename(fn)}: {len(allN)} false notes (slots) on {"planted" if planted else "correct"} takes')
    C = lambda key: collections.Counter(key(n) for n in allN).most_common(12)
    print('  page -> heard:', C(lambda n: f"{n['ref']}->{n['you']}"))
    print('  source:', C(lambda n: n['src']))
    print('  place in word:', C(lambda n: n['place']))
    print('  letter before the vowel:', C(lambda n: n['after']))
    print('  letter after the vowel (# = word end):', C(lambda n: n['next']))
    ms = sorted(n['m'] for n in allN); ps = sorted(n['p'] or 0 for n in allN)
    q = lambda a, f: a[min(len(a) - 1, int(f * len(a)))] if a else None
    print(f"  ear's share for its vowel m: p10 {q(ms, .1)} p50 {q(ms, .5)} p90 {q(ms, .9)}; slot score p: p10 {q(ps, .1)} p50 {q(ps, .5)} p90 {q(ps, .9)}")
    print('  examples:', '; '.join(f"{n['word']} ({n['ref']}->{n['you']}, {n['src']}, m {n['m']}, p {n['p']})" for n in allN[:14]))
    return allN

if __name__ == '__main__':
    for fn in sys.argv[1:]: report(fn)
