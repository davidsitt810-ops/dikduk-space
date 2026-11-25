"""The page's verdicts replayed offline from an exam's kept answers (tools/exam_voice.py with FULLOUT=1: the server's
whole answer for every take), with this checkout's own code — rule.summarize, vowels.vowel_notes — no server, seconds
instead of hours.

Why one run serves many exams: the take's vowel slots come from the audio and the line's letters alone (app.analyse);
the nikud only says which vowel each slot should be. So ONE run of the server per kind of recording (as recorded, on
a phone, with noise), with the hazzan, holds everything for
  - the reader's correct reading: every note is false (kind "right": the answer as it is, hazzan and all)
  - each planted mistake (tools/plant.py: EI EA IE OU UO, one planted word per pasuk, no hazzan — he says the vowel
    right, as the reader does, and the cross-check would hide the planted word): the answer rewritten as `exam_voice.py
    PLANT=<kind> PLANT_ONE=1 NO_REF=1` gets it from the server (--check compares the two, take for take)
  - any rule on top: pass another summarize() to tally(), or change rule.py and run this again

usage: replay.py <exam name> [...]                 the correct reading and the five planted kinds under rule.summarize
       replay.py --check <exam name> <planted exam name> <kind>     the replay against a planted run of the server
       replay.py --live <exam name> [...]      an exam from a server that rates its notes: the same trust here?
env:   DK_LAB_V = the folder with exam_<name>.full.jsonl[.gz] (default: tools/)
       RULESETS = 'vp=.4;vp=.5'   the same exams under other values of rule.RULE, one report each
       TRUST = <json of weights from bench/trust.py> to try them, or 'off' for the take's gate alone (v5.9)"""
import sys, os, json, gzip, math, random, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(HERE))
import rule, vowels as VW, nikud as NK
from plant import planter, KINDS
V = os.environ.get('DK_LAB_V') or os.path.dirname(HERE)
PLANT = {k: planter(k) for k in KINDS}
ORDER = ('EI', 'EA', 'IE', 'OU', 'UO')

def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0, c - h), 100 * min(1, c + h))
def pct(k, n):
    lo, hi = wilson(k, n); return f'{k}/{n} = {100 * k / max(1, n):.1f}% ({lo:.1f}–{hi:.1f})'

def load(name):
    """an exam's takes with the server's whole answer: [{'per', 'ps', 'nikud', 'out', ...}] (a run still going: what it has)"""
    p = os.path.join(V, f'exam_{name}.full.jsonl'); op = open
    if not os.path.exists(p): p += '.gz'; op = gzip.open
    rows, seen = [], set()
    for l in op(p, 'rt', encoding='utf-8'):
        if not l.strip(): continue
        try: r = json.loads(l)
        except ValueError: continue   # the line being written
        if (r['per'], r['ps']) not in seen: seen.add((r['per'], r['ps'])); rows.append(r)
    return rows

def planted(row, kind):
    """the server's answer as it would be for the line with one word rewritten and no hazzan -> (answer, [planted word])"""
    assert 'planted' not in row, 'replay a planted kind from a run of the correct reading'
    out = dict(row['out']); nik, idx, _ = PLANT[kind](row['nikud'], random.Random(row['per'] * 1000 + row['ps']))
    for k in ('ref', 'fit', 'ref_err', 'vowels', 'vowels_nikud'): out.pop(k, None)
    pv = NK.parse_verse(nik)
    if len(pv) == len(out['words']):   # as app.run_check
        ctx = VW.vowel_context(pv); exp = {i: VW.expected_vowels(us, ctx['stress'][i]) for i, (_, _, us) in enumerate(pv)}
        _, vn = VW.vowel_notes({i: w.get('vow', []) for i, w in enumerate(out['take']['words'])}, None, exp, {i: l for i, (_, l, _) in enumerate(pv)}, ctx)
        out['vowels_nikud'] = {str(i): v for i, v in vn.items()}
    return opinion(out), idx, nik

def opinion(out):
    """the server's last step on the vowel notes, on an answer kept before the server did it, or rewritten for a planted
       line: the phone ear's opinion and the note's trust (rule.rate_notes — the same lines app.run_check runs)"""
    return rule.rate_notes(out)

def answer(row, kind=None):
    """-> (the server's answer for this kind, the planted words)"""
    if kind is None: return opinion(row['out']), []
    out, idx, _ = planted(row, kind); return out, idx

def tally(rows, kind, summarize=rule.summarize):
    """-> Counter: takes n, those with the vowels checked; the planted words P and those told (a vowel note on the
       word, or the word red); the other words W and those with a vowel note (all false; for the correct reading
       every word is "other")"""
    c = collections.Counter()
    for r in rows:
        out, P = answer(r, kind); P = set(P); sm = summarize(out); S = {v['i'] for v in sm['vowels']}; m = sm['marks']
        c['n'] += 1; c['vclean'] += bool(sm['vclean']); c['vlost'] += bool(sm.get('vlost')); c['noisy'] += bool(sm.get('noisy'))
        if kind and not P: c['no_plant'] += 1; continue
        c['P'] += len(P); c['told'] += sum(1 for i in P if i in S or m[i] == 'off'); c['noted_p'] += len(P & S)
        c['W'] += sum(1 for i, x in enumerate(m) if x and i not in P); c['noted'] += len(S - P)
        c['red'] += sum(1 for i, x in enumerate(m) if x == 'off' and i not in P); c['unsure'] += sum(1 for i, x in enumerate(m) if x == 'unsure' and i not in P)
        if not sm['vclean']:   # the takes under the gate, where v5.9 showed no vowel note at all (can't-hear and no-speech takes among them)
            c['P_u'] += len(P); c['told_u'] += sum(1 for i in P if i in S or m[i] == 'off'); c['W_u'] += sum(1 for i, x in enumerate(m) if x and i not in P); c['noted_u'] += len(S - P)
    return c

def report(name, summarize=rule.summarize, label=''):
    rows = load(name); c = tally(rows, None, summarize)
    print(f'== {name}{label}: {c["n"]} takes; vowels checked on {pct(c["vclean"], c["n"])}; the noise line {c["noisy"]}, the not-checked line {c["vlost"]}')
    print(f'   correct reading: words with a vowel note (all false) {pct(c["noted"], c["W"])}; red {c["red"]}, not sure {pct(c["unsure"], c["W"])}')
    under = f'   on the takes under the gate ({c["n"] - c["vclean"]}): false notes {pct(c["noted_u"], c["W_u"])}'
    tot = collections.Counter()
    for k in ORDER:
        c = tally(rows, k, summarize); tot.update({x: c[x] for x in ('P', 'told', 'noted_p', 'P_u', 'told_u')})
        if not os.environ.get('BRIEF'): print(f'   planted {k}: told {pct(c["told"], c["P"])} (by a note {c["noted_p"]}); other words noted {pct(c["noted"], c["W"])}')
    print(f'   all five kinds: told {pct(tot["told"], tot["P"])} (by a note {tot["noted_p"]})')
    print(under + f'; planted told {pct(tot["told_u"], tot["P_u"])}')

def check(name, planted_name, kind):
    """the replay of a planted kind against the server's own run of it (exam_voice.py PLANT=<kind> PLANT_ONE=1 NO_REF=1)"""
    A = {(r['per'], r['ps']): r for r in load(name)}; n = bad = 0
    key = lambda sm: (sm['marks'], sm['why'], sm['clean'], sm['vclean'], sm['noisy'], sm.get('vlost'), sorted((v['i'], v['k'], v['you'], v['ref'], v['against']) for v in sm['vowels']))
    for q in load(planted_name):
        r = A.get((q['per'], q['ps']))
        if r is None: continue
        out, idx, nik = planted(r, kind); n += 1; opinion(q['out'])   # (an answer from before v6.0 gets the opinions the same way)
        same = nik == q['nikud'] and idx == q['planted'] and key(rule.summarize(out)) == key(rule.summarize(q['out'])) and out.get('vowels_nikud') == q['out'].get('vowels_nikud')
        if not same:
            bad += 1
            if bad <= 5: print(f"  differs {q['per']}:{q['ps'] + 1}: planted {q['planted']} / {idx}; server {q['out'].get('vowels_nikud')}; replay {out.get('vowels_nikud')}")
    print(f'{name} replayed as {kind} against {planted_name}: {n - bad} of {n} takes the same (the planted line, its words, the nikud notes, and all the page shows: marks, gates, vowel notes)')
    return bad == 0 and n > 0

def live(name):
    """an exam run on a server that rates its notes (v6.0): does the replay give every note the same second opinion and
       the same trust? The notes are stripped and rated again here (rule.rate_notes) — the server's own lines, but its
       numbers went through JSON and this checkout may have other weights: this is the check that they are the same"""
    import copy
    n = bad = notes = 0
    for r in load(name):
        out = r['out']
        if not out.get('vowels_trust'): continue
        n += 1; mine = copy.deepcopy(out)
        for k in ('vowels', 'vowels_nikud'):
            for ds in (mine.get(k) or {}).values():
                for d in ds:
                    for f in ('ph', 'phc', 'phd', 'p'): d.pop(f, None)
        rule.rate_notes(mine); same = all(mine.get(k) == out.get(k) for k in ('vowels', 'vowels_nikud')); notes += sum(len(ds) for k in ('vowels', 'vowels_nikud') for ds in (out.get(k) or {}).values())
        if not same:
            bad += 1
            if bad <= 3: print(f"  differs {r['per']}:{r['ps'] + 1}: server {out.get('vowels_nikud')}\n      replay {mine.get('vowels_nikud')}")
    print(f'{name}: {n - bad} of {n} takes rated by the server carry the replay\'s opinions and trust on every note ({notes} notes)')
    return bad == 0 and n > 0

def ruleset(spec):
    """'vp=.4' -> rule.RULE changed for this run"""
    for kv in (spec or '').split(','):
        if kv: k, v = kv.split('='); assert k in rule.RULE, k; rule.RULE[k] = float(v)

if __name__ == '__main__':
    if sys.argv[1] == '--check': sys.exit(0 if check(*sys.argv[2:5]) else 1)
    if sys.argv[1] == '--live': sys.exit(0 if all([live(nm) for nm in sys.argv[2:]]) else 1)
    sets = os.environ['RULESETS'].split(';') if os.environ.get('RULESETS') else ['']   # e.g. RULESETS='vp=.4;vp=.5;vp=.6'
    if os.environ.get('TRUST'):   # TRUST=<json from bench/trust.py> (weights to try before they are written into vowels.py); TRUST=off: no trust, the take's gate as in v5.9
        VW.TRUST_W = None if os.environ['TRUST'] == 'off' else json.load(open(os.environ['TRUST']))['w']
    base = dict(rule.RULE)
    for name in sys.argv[1:]:
        for sp in sets:
            rule.RULE.clear(); rule.RULE.update(base); ruleset(sp); report(name, label=f'  [{sp}]' if sp else '')
