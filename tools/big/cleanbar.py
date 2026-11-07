"""The clean bar (rule.clean_of: the letter head's median score on the line's words >= .7) replayed lower, from the
exams' stored rule inputs and raw vowel slots, under v5.6 (the drop bar at 20, the furtive patah). A take under the
bar gets no vowel notes, no "dropped"/"swapped" call of the clean kind, no "sure" green and no strict check; on the
phone a third of Faraj's clean takes fell under it (LAB_NOTES §39). The replay at .70 must give the stored marks of a
v5.6 server run on every take (checked first). For each bar: correct readers — clean takes, words with a vowel note
(every one false), right words red / not sure; planted exams — planted words told (a note or red), other words
noted; skipped-word exams — the skipped word red / not sure / passed.
usage: cleanbar.py <exam>[,<kind>] ...   kinds: right (default), plant, skip; bars from BARS=.70,.67,.65,.62,.60;
GAP=<g>: a take under .70 counts as clean at the lower bar only if its line gap is at most g (the written line explains
the audio nearly as well as free decoding: a poor recording's gap is high); VOWELS_ONLY=1: the lower bar (and GAP) for
the vowel notes alone, the word marks as v5.6 (clean at .70)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU, drops as D
rule = D.rule; V = D.V; pct = D.pct
BARS = [float(x) for x in os.environ.get('BARS', '.70,.67,.65,.62,.60').split(',')]
GAP = float(os.environ['GAP']) if os.environ.get('GAP') else None
VOWELS_ONLY = bool(os.environ.get('VOWELS_ONLY'))   # the lower bar for the vowel notes alone; every word mark as v5.6
def is_clean(m, gap, bar):
    return m is not None and (m >= .70 if bar >= .70 else (m >= .70 or (m >= bar and (GAP is None or (gap is not None and gap <= GAP)))))

def replay(r, bar):
    """-> (clean, marks, cant_hear) for the take at this clean bar (v5.6's word rule from the stored inputs)"""
    ri = r['raw']['rule_in']; TW = ri['tw']; F = [({'fit': x} if x is not None else None) for x in ri['fit']] or None
    m = rule.head_median(TW); clean = is_clean(m, r['gap'], bar)
    old = dict(rule.RULE); rule.RULE['drop'] = 20
    try: marks, why, lw, ch = D.marks_of(.8, .6)(TW, F, r['gap'], clean, r['rival'])
    finally: rule.RULE.clear(); rule.RULE.update(old)
    if r.get('no_speech'): marks = ['unsure' if x else x for x in marks]; ch = False
    return clean, marks, ch

def selfcheck(name='samra_v56B'):
    n = bad = 0
    for r in RU.load(V, name):
        if 'rule_in' not in r['raw']: continue
        c, m, _ = replay(r, .70); n += 1; bad += (m != r['marks']) or (c != r['clean'])
    return n, bad

if __name__ == '__main__':
    n, bad = selfcheck(); print(f'self-check: the replay at .70 gives the v5.6 server marks and clean flag on {n - bad} of {n} takes (samra_v56B)')
    for spec in sys.argv[1:]:
        name, _, kind = spec.partition(','); kind = kind or 'right'
        rows = [r for r in RU.load(V, name) if 'rule_in' in r['raw']]
        if kind == 'skip': rows = [r for r in rows if r.get('skip_ok')]
        # the vowel notes do not depend on the bar except through the gate and the red words: computed once per take
        raw = [RU.notes(dict(r, clean=True, marks=['ok'] * len(r['marks'])), furtive=True) for r in rows]
        print(f'== {name} ({kind}): {len(rows)} takes')
        for bar in BARS:
            c = collections.Counter()
            for r, rn in zip(rows, raw):
                clean, marks, ch = replay(r, bar); P = set(r.get('planted') or [])
                if VOWELS_ONLY:   # the lower bar for the vowel notes only: the word marks stay v5.6's (clean at .70)
                    vclean = clean; clean, marks, ch = replay(r, .70); clean_shown = vclean
                else: clean_shown = clean
                shown = {i for i in rn if clean_shown and not ch and marks[i] != 'off'} if not r.get('no_speech') else set()
                clean = clean_shown
                c['clean'] += clean; c['n'] += 1
                if kind == 'skip':
                    j = r['planted'][0]; c['s_' + marks[j]] += 1
                    c['red_other'] += sum(1 for i, x in enumerate(marks) if x == 'off' and i != j); c['W'] += len(marks) - 1
                    continue
                c['told'] += sum(1 for i in P if i in shown or marks[i] == 'off'); c['P'] += len(P)
                c['noted'] += len(shown - P); c['W'] += len(marks) - len(P)
                c['red'] += sum(1 for i, x in enumerate(marks) if x == 'off' and i not in P)
                c['unsure'] += sum(1 for i, x in enumerate(marks) if x == 'unsure' and i not in P)
            line = f'  bar {bar:.2f}: clean {pct(c["clean"], c["n"])}'
            if kind == 'skip': line += f';  skipped word red {pct(c["s_off"], c["n"])}, not sure {c["s_unsure"]}, passed {c["s_ok"]};  other words red {c["red_other"]}'
            elif kind == 'plant': line += f';  planted told {pct(c["told"], c["P"])};  other words noted {pct(c["noted"], c["W"])}, red {c["red"]}'
            else: line += f';  words noted {pct(c["noted"], c["W"])};  red {c["red"]}, not sure {pct(c["unsure"], c["W"])}'
            print(line)
