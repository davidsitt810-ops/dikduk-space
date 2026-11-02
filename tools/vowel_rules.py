"""Vowel-note rules tried offline on exams run with RAW=1 (exam_voice.py keeps the vowel ear's slots of the take and of
the hazzan): what a reader would be told under each rule, on correct readers (every note a false alarm) and on the
planted "o where the page says u" (PLANT=OU, notes on the planted words are catches).

  base   the server's rule (v5.2): vowels compared position by position, only in a word where the take and the
         reference have the same number of vowels; notes shown on clean takes only (rule.summarize)
  A      the slots are lined up by the letter each vowel follows (compare_aligned below): a vowel heard after a mater
         (ו י א, a final ה) may stand for the letter before it, an extra vowel the reference lacks (a shva heard as a
         vowel) is passed over instead of leaving the whole word alone
  B<p>   also on a take that is not clean: a note the hazzan comparison and the nikud comparison both make, on a slot
         the ear placed with score >= p (without a hazzan, the nikud note alone); @h: only on takes whose clarity (the
         letter head's median) is at least h
usage: vowel_rules.py exam_a.json [exam_b.json ...]"""
import sys, os, json, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from nikud import parse_verse
from vowels import compare_vowels, compare_aligned, compat, vowel_notes   # A is the server's rule since v5.3

def slots(raw_word):
    return [{'k': k, 'heard': h, 'mass': m, 'p': p} for k, h, m, p in raw_word]

def notes_for(row, aligned, gate_p=None, min_head=None):
    """-> {word index: set of student slot k with a shown note}"""
    raw = row['raw']; W = row['words']; marks = row['marks']; clean = row['clean']
    pv = parse_verse(raw['nikud'])
    if len(pv) != len(W): return {}
    letters = {i: l for i, (_, l, _) in enumerate(pv)}
    exp = {i: [{'heard': u['c'], 'k': u['k']} for u in us if u['kind'] == 'vowel'] for i, (_, _, us) in enumerate(pv)}
    stu = {i: slots(w) for i, w in enumerate(raw['tw'])}
    haz = {i: slots(w) for i, w in enumerate(raw['rw'])} if raw['rw'] else {}
    if aligned:   # exactly what the server does since v5.3 (vowels.vowel_notes, both cross-checks included)
        vh, vn = vowel_notes(stu, haz if haz else None, exp, letters); vh = vh or {}
        return shown(row, vh, vn, stu, haz, gate_p, min_head)
    # base: the rule of v5.2 and before — position by position, only where the counts agree
    vh = compare_vowels(stu, haz) if haz else {}
    vn = compare_vowels(stu, exp)
    for i in list(vn):   # v4.9: a nikud note where the hazzan is heard saying the same vowel there is dropped
        hv = {h['k']: h['heard'] for h in (haz.get(i) or [])}
        vn[i] = [d for d in vn[i] if hv.get(d['k']) != d['you']]
        if not vn[i]: del vn[i]
    for i in list(vh):   # v5.1: a hazzan note where the student said the nikud's vowel is dropped
        sl = stu.get(i) or []; ev = exp.get(i) or []
        if len(ev) != len(sl): continue
        pos = {s['k']: j for j, s in enumerate(sl)}
        vh[i] = [d for d in vh[i] if not (d['k'] in pos and ev[pos[d['k']]]['heard'] == d['you'])]
        if not vh[i]: del vh[i]
    return shown(row, vh, vn, stu, haz, gate_p, min_head)

def shown(row, vh, vn, stu, haz, gate_p, min_head):
    marks = row['marks']; clean = row['clean']
    out = collections.defaultdict(set)
    if clean:
        for src in (vh, vn):
            for i, ds in src.items():
                if marks[int(i)] != 'off':
                    for d in ds: out[int(i)].add(d['k'])
    elif gate_p is not None and (min_head is None or (row.get('head') or 0) >= min_head):
        for i, ds in vn.items():
            if marks[int(i)] == 'off': continue
            pk = {s['k']: s['p'] for s in stu.get(i, [])}
            for d in ds:
                if pk.get(d['k'], 0) < gate_p: continue
                if haz and not any(e['k'] == d['k'] and e['you'] == d['you'] for e in vh.get(i, [])): continue
                out[int(i)].add(d['k'])
    return dict(out)

RULES = [('base', False, None, None), ('A', True, None, None), ('B.9', False, .9, None), ('A+B.9', True, .9, None), ('A+B.9@.6', True, .9, .6)]
if __name__ == '__main__':
    for fn in sys.argv[1:]:
        rows = [r for r in json.load(open(fn, encoding='utf-8')) if 'raw' in r and 'words' in r]
        planted = any(r.get('planted') is not None for r in rows)
        nw = sum(len(r['words']) for r in rows); ncw = sum(len(r['words']) for r in rows if r['clean'])
        print(f"\n== {os.path.basename(fn)}: {len(rows)} takes ({sum(r['clean'] for r in rows)} clean), {nw} words; {'PLANTED o->u' if planted else 'a correct reader'}")
        # sanity: the base rule should reproduce the server's own shown notes
        for name, al, gp, mh in RULES:
            told = other = cl_other = ncl_other = 0; pw = ow = 0; words_noted = 0
            for r in rows:
                n = notes_for(r, al, gp, mh)
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
