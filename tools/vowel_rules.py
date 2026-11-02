"""Vowel-note rules tried offline on exams run with RAW=1 (exam_voice.py keeps the vowel ear's slots of the take and of
the hazzan): what a reader would be told under each rule, on correct readers (every note a false alarm) and on the
planted "o where the page says u" (PLANT=OU, notes on the planted words are catches).

  base   the server's rule (v5.2): vowels compared position by position, only in a word where the take and the
         reference have the same number of vowels; notes shown on clean takes only (rule.summarize)
  A      the slots are lined up by the letter each vowel follows (compare_aligned below): a vowel heard after a mater
         (ו י א, a final ה) may stand for the letter before it, an extra vowel the reference lacks (a shva heard as a
         vowel) is passed over instead of leaving the whole word alone
  B<p>   also on a take that is not clean: a note the hazzan comparison and the nikud comparison both make, on a slot
         the ear placed with score >= p (without a hazzan, the nikud note alone)
usage: vowel_rules.py exam_a.json [exam_b.json ...]"""
import sys, os, json, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from nikud import parse_verse
from vowels import compare_vowels, clear

def compat(a, b, letters):
    """a vowel slot after letter a and one after letter b can be the same vowel: the same letter, or neighbours where
       the later letter is a mater (ו י א) or a final ה, which the ear may pass over"""
    if a == b: return True
    hi = max(a, b)
    return abs(a - b) == 1 and hi < len(letters) and (letters[hi] in 'ויא' or (letters[hi] == 'ה' and hi == len(letters) - 1))

def compare_aligned(student, ref, letters, ratio=2.0, with_pairs=False, skip=0.5, sub=0.9):
    """student: slots per word (vowel_place); ref: per word the expected vowels with the letter each follows (k): the
       hazzan's slots, or the nikud's vowels. Each word's two lists are lined up in order (a slot may pair only with a
       vowel after a compatible letter; passing over one costs `skip`, a pair of different vowels `sub` < 2 skips),
       and every pair of different vowels whose slot is clear (and, for the hazzan, his slot too) is a note.
       -> {word: [{k, you, ref, m}]} (and {word: {student k: the vowel it was paired with}} if with_pairs)"""
    out, pairs = {}, {}
    for i, sl in student.items():
        r = ref.get(i)
        if not r or not sl: continue
        L = letters.get(i, '') if isinstance(letters, dict) else letters
        n, m = len(sl), len(r); INF = 1e9
        D = [[INF] * (m + 1) for _ in range(n + 1)]; B = [[None] * (m + 1) for _ in range(n + 1)]; D[0][0] = 0.0
        for a in range(n + 1):
            for b in range(m + 1):
                if D[a][b] >= INF: continue
                if a < n and D[a][b] + skip < D[a + 1][b]: D[a + 1][b] = D[a][b] + skip; B[a + 1][b] = (a, b, 's')
                if b < m and D[a][b] + skip < D[a][b + 1]: D[a][b + 1] = D[a][b] + skip; B[a][b + 1] = (a, b, 'r')
                if a < n and b < m and compat(sl[a]['k'], r[b]['k'], L):
                    c = D[a][b] + (0.0 if sl[a]['heard'] == r[b]['heard'] else sub)
                    if c <= D[a + 1][b + 1]: D[a + 1][b + 1] = c; B[a + 1][b + 1] = (a, b, 'm')
        a, b = n, m; got = []
        while (a, b) != (0, 0):
            pa, pb, t = B[a][b]
            if t == 'm': got.append((pa, pb))
            a, b = pa, pb
        for a, b in reversed(got):
            s, rs = sl[a], r[b]; pairs.setdefault(i, {})[s['k']] = rs['heard']
            if s['heard'] == rs['heard'] or not clear(s, ratio): continue
            if rs.get('mass') is not None and not clear(rs, ratio): continue
            mm = s['mass']; out.setdefault(i, []).append({'k': s['k'], 'you': s['heard'], 'ref': rs['heard'], 'm': round(mm[s['heard']] / max(1e-6, sum(mm.values())), 2)})
    return (out, pairs) if with_pairs else out

def slots(raw_word):
    return [{'k': k, 'heard': h, 'mass': m, 'p': p} for k, h, m, p in raw_word]

def notes_for(row, aligned, gate_p=None):
    """-> {word index: set of student slot k with a shown note}"""
    raw = row['raw']; W = row['words']; marks = row['marks']; clean = row['clean']
    pv = parse_verse(raw['nikud'])
    if len(pv) != len(W): return {}
    letters = {i: l for i, (_, l, _) in enumerate(pv)}
    exp = {i: [{'heard': u['c'], 'k': u['k']} for u in us if u['kind'] == 'vowel'] for i, (_, _, us) in enumerate(pv)}
    stu = {i: slots(w) for i, w in enumerate(raw['tw'])}
    haz = {i: slots(w) for i, w in enumerate(raw['rw'])} if raw['rw'] else {}
    if aligned:
        vh = compare_aligned(stu, haz, letters) if haz else {}
        vn, pair = compare_aligned(stu, exp, letters, with_pairs=True)
    else:
        vh = compare_vowels(stu, haz) if haz else {}
        vn = compare_vowels(stu, exp); pair = None
    # v4.9: a nikud note where the hazzan is heard saying the same vowel there is dropped
    for i in list(vn):
        hv = haz.get(i) or []
        def same(d):
            if aligned: return any(h['heard'] == d['you'] and compat(h['k'], d['k'], letters.get(i, '')) for h in hv)
            return {h['k']: h['heard'] for h in hv}.get(d['k']) == d['you']
        vn[i] = [d for d in vn[i] if not same(d)]
        if not vn[i]: del vn[i]
    # v5.1: a hazzan note where the student said the nikud's vowel is dropped
    for i in list(vh):
        sl = stu.get(i) or []; ev = exp.get(i) or []
        if aligned:
            pm = (pair or {}).get(i, {})   # student k -> the nikud vowel it was lined up with
            vh[i] = [d for d in vh[i] if not (d['k'] in pm and pm[d['k']] == d['you'])]
        else:
            if len(ev) != len(sl): continue
            pos = {s['k']: j for j, s in enumerate(sl)}
            vh[i] = [d for d in vh[i] if not (d['k'] in pos and ev[pos[d['k']]]['heard'] == d['you'])]
        if not vh[i]: del vh[i]
    out = collections.defaultdict(set)
    if clean:
        for src in (vh, vn):
            for i, ds in src.items():
                if marks[int(i)] != 'off':
                    for d in ds: out[int(i)].add(d['k'])
    elif gate_p is not None:
        for i, ds in vn.items():
            if marks[int(i)] == 'off': continue
            pk = {s['k']: s['p'] for s in stu.get(i, [])}
            for d in ds:
                if pk.get(d['k'], 0) < gate_p: continue
                if haz and not any(e['k'] == d['k'] and e['you'] == d['you'] for e in vh.get(i, [])): continue
                out[int(i)].add(d['k'])
    return dict(out)

RULES = [('base', False, None), ('A', True, None), ('B.9', False, .9), ('A+B.9', True, .9), ('A+B.8', True, .8)]
if __name__ == '__main__':
    for fn in sys.argv[1:]:
        rows = [r for r in json.load(open(fn, encoding='utf-8')) if 'raw' in r and 'words' in r]
        planted = any(r.get('planted') is not None for r in rows)
        nw = sum(len(r['words']) for r in rows); ncw = sum(len(r['words']) for r in rows if r['clean'])
        print(f"\n== {os.path.basename(fn)}: {len(rows)} takes ({sum(r['clean'] for r in rows)} clean), {nw} words; {'PLANTED o->u' if planted else 'a correct reader'}")
        # sanity: the base rule should reproduce the server's own shown notes
        for name, al, gp in RULES:
            told = other = cl_other = ncl_other = 0; pw = ow = 0; words_noted = 0
            for r in rows:
                n = notes_for(r, al, gp)
                if planted:
                    P = set(r['planted'] or [])
                    pw += len(P); ow += len(r['words']) - len(P)
                    told += sum(1 for i in P if i in n or r['marks'][i] == 'off')
                    other += sum(1 for i in n if i not in P)
                else:
                    words_noted += len(n)
                    if r['clean']: cl_other += len(n)
                    else: ncl_other += len(n)
            if planted:
                print(f"   {name:7s} planted words told {told}/{pw} ({100 * told / max(1, pw):.1f}%)   other words with a note {other}/{ow} ({100 * other / max(1, ow):.1f}%)")
            else:
                print(f"   {name:7s} words with a note {words_noted}/{nw} ({100 * words_noted / max(1, nw):.1f}% of all words; on clean takes {cl_other}/{ncw} = {100 * cl_other / max(1, ncw):.1f}%, on unclear takes {ncl_other})")
