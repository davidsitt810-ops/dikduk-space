"""Vowel notes replayed offline from an exam's kept rows (tools/exam_voice.py with RAW=1), with this checkout's own
code (vowels.vowel_notes, rule.py) — no server, seconds instead of hours.

Why it works: the take's vowel slots come from the audio and the line's letters alone (app.analyse); the nikud only
says which vowel each slot should be. So ONE run of the server per kind of recording (as recorded, on a phone, with
noise), with the hazzan, holds everything for
  - the reader's correct reading: every note is false (kind "right", with the hazzan's cross-checks as on the site)
  - each planted mistake (tools/plant.py: EI EA IE OU UO, one planted word per pasuk, no hazzan — he says the vowel
    right, as the reader does, and the cross-check would hide the planted word): what `exam_voice.py PLANT=<kind>
    PLANT_ONE=1 NO_REF=1` gives through the server, take for take (--check compares the two)
  - any gate on top: the take's own (rule.vclean_of), or a rule per word (bench/wordgate.py)

usage: replay.py <exam name> [...]                 the correct reading and the five planted kinds under the live gate
       replay.py --check <exam name> <planted exam name> <kind>     the replay against a planted run of the server
env:   DK_LAB_V = the folder with exam_<name>.json / .jsonl (default: tools/)"""
import sys, os, json, math, random, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(HERE))
import rule, vowels as VW, nikud as NK
from plant import planter, KINDS
V = os.environ.get('DK_LAB_V') or os.path.dirname(HERE)
PLANT = {k: planter(k) for k in KINDS}

def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0, c - h), 100 * min(1, c + h))
def pct(k, n):
    lo, hi = wilson(k, n); return f'{k}/{n} = {100 * k / max(1, n):.1f}% ({lo:.1f}–{hi:.1f})'

def load(name):
    """an exam's rows that carry the raw slots and the word rule's inputs (finished .json, or the .jsonl of a run still going)"""
    p = os.path.join(V, f'exam_{name}.json')
    if os.path.exists(p): rows = json.load(open(p, encoding='utf-8'))
    else: rows = [json.loads(l) for l in open(os.path.join(V, f'exam_{name}.jsonl'), encoding='utf-8') if l.strip()]
    return [r for r in rows if 'err' not in r and 'raw' in r and 'rule_in' in r['raw']]

def slots_of(lst):
    return {i: [{'k': k, 'heard': h, 'mass': m, 'p': p} for k, h, m, p in w] for i, w in enumerate(lst or [])}

def notes(r, kind=None, ref=None):
    """the take's vowel notes as app.run_check makes them. kind None: the page's own nikud (the correct reading);
       a planted kind: the nikud with one word rewritten (seeded by perek and pasuk, as exam_voice.py PLANT_ONE=1).
       ref: with the hazzan's slots (default: yes for the correct reading, no for a planted kind).
       -> {'vh': against the hazzan {word: [..]}, 'vn': against the nikud, 'planted': [word indices], 'nik': the line}
       or None when the nikud's words do not match the line's (the server gives no nikud notes then)"""
    raw = r['raw']; nik = raw['nikud']; planted = []
    if ref is None: ref = kind is None
    if kind:
        assert 'planted' not in r, 'replay a planted kind from a run of the correct reading'
        nik, planted, _ = PLANT[kind](nik, random.Random(r['per'] * 1000 + r['ps']))
    pv = NK.parse_verse(nik)
    if len(pv) != len(r['words']): return None
    ctx = VW.vowel_context(pv); exp = {i: VW.expected_vowels(us, ctx['stress'][i]) for i, (_, _, us) in enumerate(pv)}
    haz = slots_of(raw['rw']) if (ref and raw.get('rw')) else None
    vh, vn = VW.vowel_notes(slots_of(raw['tw']), haz, exp, {i: l for i, (_, l, _) in enumerate(pv)}, ctx)
    return {'vh': vh or {}, 'vn': vn or {}, 'planted': planted, 'nik': nik}

def marks(r, ref=True):
    """the page's word marks from the kept inputs -> (marks, clean, vclean, cant_hear, line_wrong); ref False: as a run
       with no hazzan gives them (no fit)"""
    ri = r['raw']['rule_in']; TW = ri['tw']; F = ([({'fit': x} if x is not None else None) for x in ri['fit']] or None) if ref else None
    clean = rule.clean_of(TW); m, why, lw, ch = rule.marks_of(TW, F, r['gap'], clean, r['rival'])
    if r.get('no_speech'): m = ['unsure' if x else x for x in m]; lw = False; ch = False
    return m, clean, rule.vclean_of(TW, r['gap'], clean, True), ch, lw

def noted(N):
    """the words with a note, against the hazzan or the nikud (the page shows both, one line per word)"""
    return set(N['vh']) | set(N['vn'])

def shown_live(r, N, M):
    """the words whose vowel notes the page shows today: the take's gate (rule.summarize)"""
    m, clean, vclean, ch, lw = M
    if not vclean or ch or r.get('no_speech'): return set()
    return {i for i in noted(N) if m[i] != 'off'}

def tally(rows, kind, shown=shown_live):
    """-> Counter: takes n, vclean; for the correct reading the words W and those noted (all false); for a planted kind
       the planted words P, told (a note on it, or red), and the other words W with a note"""
    c = collections.Counter()
    for r in rows:
        N = notes(r, kind)
        if N is None: c['skipped'] += 1; continue
        M = marks(r, ref=kind is None); S = shown(r, N, M); P = set(N['planted'])
        c['n'] += 1; c['vclean'] += bool(M[2] and not M[3] and not r.get('no_speech'))
        if kind and not P: c['no_plant'] += 1; continue
        c['P'] += len(P); c['told'] += sum(1 for i in P if i in S or M[0][i] == 'off'); c['noted_p'] += sum(1 for i in P if i in S)
        c['W'] += len(M[0]) - len(P); c['noted'] += len(S - P)
    return c

def check(name, planted_name, kind):
    """the replay of a planted kind against the server's own run of it (exam_voice.py PLANT=<kind> PLANT_ONE=1 NO_REF=1)"""
    A = {(r['per'], r['ps']): r for r in load(name)}; n = bad = 0
    for q in load(planted_name):
        r = A.get((q['per'], q['ps']))
        if r is None: continue
        N = notes(r, kind); n += 1
        want = {int(i): [(d['k'], d['you'], d['ref']) for d in ds] for i, ds in (q['raw'].get('svn') or {}).items()}
        got = {i: [(d['k'], d['you'], d['ref']) for d in ds] for i, ds in N['vn'].items()}
        M = marks(r, ref=False)
        same = N['nik'] == q['raw']['nikud'] and N['planted'] == q['planted'] and want == got and M[0] == q['marks'] and M[2] == bool(rule.vclean_of(q['raw']['rule_in']['tw'], q['gap'], q['clean'], True))
        if not same:
            bad += 1
            if bad <= 5: print(f"  differs {q['per']}:{q['ps'] + 1}: planted {q['planted']} / {N['planted']}; server notes {want}; replay {got}; marks same {M[0] == q['marks']}")
    print(f'{name} replayed as {kind} against {planted_name}: {n - bad} of {n} takes the same (the planted line, its words, the nikud notes, the marks, the gate)')
    return bad == 0 and n > 0

if __name__ == '__main__':
    if sys.argv[1] == '--check': sys.exit(0 if check(*sys.argv[2:5]) else 1)
    for name in sys.argv[1:]:
        rows = load(name); c = tally(rows, None)
        print(f'== {name}: {c["n"]} takes, vowels checked on {pct(c["vclean"], c["n"])}')
        print(f'   correct reading: words with a vowel note (all false) {pct(c["noted"], c["W"])}')
        for k in ('EI', 'EA', 'IE', 'OU', 'UO'):
            c = tally(rows, k)
            print(f'   planted {k}: told {pct(c["told"], c["P"])} (by a note {c["noted_p"]}); other words noted {pct(c["noted"], c["W"])}; pesukim with none to plant {c["no_plant"]}')
