"""Planted-mistake exams through the server (exam_voice.py with PLANT=OU NO_REF=1), side by side: of the words with a
planted mistake ("he says o where the page says u"), how many the checker tells him about — a vowel note, or the
word marked ✕ — and how it treats the other words. Vowel notes come only on clean takes, so both are counted there.
usage: planted_catch.py exam_a.json [exam_b.json ...]"""
import sys, json, collections
pct = lambda a, b: f'{100 * a / b:.1f}%' if b else '-'
for fn in sys.argv[1:]:
    rows = [r for r in json.load(open(fn, encoding='utf-8')) if 'words' in r and r.get('planted') is not None and len(r['words']) == r['nw']]
    C = collections.Counter(); pairs = collections.Counter()
    for r in rows:
        C['takes'] += 1
        if not r['clean']: continue
        C['clean'] += 1; noted = {v['w'] for v in r['vowels']}; pl = set(r['planted'])
        for i, w in enumerate(r['words']):
            k = 'mis' if i in pl else 'oth'; m = r['marks'][i]
            C[k] += 1; C[k + ' note'] += w in noted; C[k + ' off'] += m == 'off'; C[k + ' unsure'] += m == 'unsure'
            C[k + ' told'] += (w in noted) or m == 'off'
        for v in r['vowels']:
            if any(r['words'][i] == v['w'] for i in pl): pairs[(v['ref'], v['you'])] += 1
    print(f"{fn}: {C['takes']} takes, {C['clean']} clean; on clean takes —")
    print(f"   planted-mistake words {C['mis']}: told {pct(C['mis told'], C['mis'])} (vowel note {pct(C['mis note'], C['mis'])}, ✕ {pct(C['mis off'], C['mis'])}), not sure {pct(C['mis unsure'], C['mis'])}"
          f"   | notes there: " + ', '.join(f'{a}->{b} {n}' for (a, b), n in pairs.most_common(4)))
    print(f"   other words {C['oth']}: vowel note {pct(C['oth note'], C['oth'])}, ✕ {pct(C['oth off'], C['oth'])}, not sure {pct(C['oth unsure'], C['oth'])}")
