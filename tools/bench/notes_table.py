"""Every vowel note the ear could give on an exam's takes — shown by the page or not — as one flat table, with what is
known about the word and the slot it sits on. For choosing where a note may be shown (a gate per word, a second
opinion from the phone ear): bench/wordgate.py reads the table.

From the kept answers of ONE run per kind of recording (bench/replay.py): the reader's correct reading (a note there
is false) and the five planted kinds (a note on the planted word is a catch). One row per word:
  exam, per, ps, kind ('right' or EI EA IE OU UO), i (the word), planted (the word is the planted one), note (the
  ear gives a vowel note on it), shown (rule.summarize shows it today), mark, n (consonants), hskel, vskel, skel,
  kept, pw, head (the take's letter-head median), gap, snr, vclean (the take's gate), cant (can't hear / no speech),
  and for a note: you, ref, m (the winner's share of the slot), against, ph (the phone ear's vowel class at the slot:
  classes, '' = it wrote none within 80 ms), phc (its confidence), pha ('you' / 'ref' / 'other' / 'none': vowels.opinion_of)
For the planted kinds only the planted word's row is kept (the other words are the correct reading's, without the
hazzan's cross-check: kind '<K>-other', kept only with OTHER=1).

usage: notes_table.py <exam name> [...]   -> <DK_LAB_V>/table_<exam name>.json"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as RP
rule = RP.rule
VW = RP.VW

def rows_of(exam, r, kind, other=False):
    out, P = RP.answer(r, kind); P = set(P); sm = rule.summarize(out); TW = out['take']['words']; m = sm['marks']
    shown = {}
    for v in sm['vowels']: shown.setdefault(v['i'], []).append(v)
    raw = {}
    for src, against in ((out.get('vowels'), 'hazzan'), (out.get('vowels_nikud'), 'nikud')):
        for i, ds in (src or {}).items():
            for d in ds: raw.setdefault(int(i), []).append((d, against))
    base = {'exam': exam, 'per': r['per'], 'ps': r['ps'], 'head': sm['head'], 'gap': sm['gap'], 'snr': sm['snr'], 'vclean': bool(sm['vclean']),
            'cant': bool(sm['cant_hear'] or sm['no_speech']), 'lw': bool(sm['line_wrong']), 'nw': len(m)}
    res = []
    for i, t in enumerate(TW):
        if not m[i]: continue
        if kind and i not in P and not other: continue
        row = dict(base, kind=(kind or 'right') + ('' if (not kind or i in P) else '-other'), i=i, planted=i in P, note=i in raw, shown=i in shown, mark=m[i],
                   n=t.get('n'), hskel=t.get('hskel'), vskel=t.get('vskel'), skel=t.get('skel'), kept=t.get('kept'), pw=t.get('pw'), w=out['words'][i])
        if i in raw:
            # the note that matters: on a planted word the one of the planted kind ("you E where the page has I" for EI),
            # else the surest note on the word (and how many there are); 'hit': it is of the planted kind
            d, against = max(raw[i], key=lambda x: (bool(kind) and x[0]['you'] + x[0]['ref'] == kind, x[0].get('m') or 0))
            slot = next((s for s in (t.get('vow') or []) if s['k'] == d['k']), None)
            ph, phc = VW.phone_vowel_at(out['take'].get('phones'), (slot['t0'] + slot['t1']) / 2) if slot and slot.get('t0') is not None else ('', None)
            pha = VW.opinion_of(dict(d, ph=ph))   # the phone ear's opinion: 'you' / 'ref' / 'other' / 'none' (vowels.opinion_of)
            row.update(hit=bool(kind) and d['you'] + d['ref'] == kind, you=d['you'], ref=d['ref'], m=d.get('m'), against=against, notes=len(raw[i]), k=d['k'], ph=ph, phc=phc, pha=pha,
                       mass=round(sum(slot['mass'].values()), 3) if slot else None, sp=slot.get('p') if slot else None)
        res.append(row)
    return res

def build(exam, other=False):
    T = []
    for r in RP.load(exam):
        for kind in (None,) + RP.ORDER: T += rows_of(exam, r, kind, other)
    return T

if __name__ == '__main__':
    for exam in sys.argv[1:]:
        T = build(exam, bool(os.environ.get('OTHER'))); p = os.path.join(RP.V, f'table_{exam}.json'); json.dump(T, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
        nr = [x for x in T if x['kind'] == 'right']; pl = [x for x in T if x['planted']]
        print(f'{exam}: {len({(x["per"], x["ps"]) for x in T})} takes -> {p}: correct reading {len(nr)} words, {sum(x["note"] for x in nr)} with a note ({sum(x["shown"] for x in nr)} shown); '
              f'planted {len(pl)} words, {sum(x["note"] for x in pl)} with a note ({sum(x["shown"] for x in pl)} shown)')
