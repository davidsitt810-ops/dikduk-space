"""Shva na / shva nah in pointed Hebrew, the Sephardic way: for every letter with a sheva, whether it is SAID (na — a
short "e", as in בְּרֵאשִׁית be-reshit) or SILENT (nah — it closes the syllable, as in יִשְׁמְרוּ yish-me-ru), and why.

The rules (as a Sephardic teacher gives them), in order:
  start      the first letter of a word                                  -> na   (בְּרֵאשִׁית, וְהָיָה)
  final      the last letter of a word (also both of two at the end)     -> nah  (לֵךְ, אַתְּ)
  second     the second of two shvas in a row                            -> na   (יִשְׁמְרוּ: the מ)
  first      the first of two shvas in a row                             -> nah  (יִשְׁמְרוּ: the ש)
  twin       under the first of two identical letters                    -> na   (הַלְלוּ, סוֹרְרִים)
  dagesh     under a letter with a doubling dagesh (dagesh hazak)        -> na   (הַמְּלָכִים)
  meteg      after a vowel marked with a meteg (ga'ya)                   -> na   (שָֽׁמְרָה)
  long       after a long vowel (kamatz, tsere, holam, shuruk, hiriq
             with yod) — the Sephardic rule                              -> na   (שׁוֹמְרִים, כּוֹתְבִים)
  short      after a short vowel (patah, segol, hiriq, kubutz,
             kamatz katan)                                               -> nah  (מַלְכּוֹ, יִכְתֹּב)
Every mark comes with its rule, so a check can use only the rules it trusts (the study in space_test/shva_study.py
measures how often Rabbi Alouf actually says a vowel under each rule)."""
import re, unicodedata

DAGESH = 'ּ'; SHEVA = 'ְ'; METEG = 'ֽ'; SHIN = 'ׁ'; SIN = 'ׂ'
HAT = {'ֱ', 'ֲ', 'ֳ'}
HIRIQ = 'ִ'; TSERE = 'ֵ'; SEGOL = 'ֶ'; PATAH = 'ַ'; QAMATS = 'ָ'; HOLAM = 'ֹ'
HOLAM_VAV = 'ֺ'; QUBUTS = 'ֻ'; QAMATS_QATAN = 'ׇ'
VOWEL_MARKS = {SHEVA, HIRIQ, TSERE, SEGOL, PATAH, QAMATS, HOLAM, HOLAM_VAV, QUBUTS, QAMATS_QATAN} | HAT
LONG = {QAMATS, TSERE, HOLAM, HOLAM_VAV}
SHORT = {PATAH, SEGOL, HIRIQ, QUBUTS, QAMATS_QATAN}
BGDKFT = set('בגדכפת')
FIN = {'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ'}
VNAME = {QAMATS: 'kamatz', TSERE: 'tsere', HOLAM: 'holam', HOLAM_VAV: 'holam', PATAH: 'patah', SEGOL: 'segol', HIRIQ: 'hiriq',
         QUBUTS: 'kubutz', QAMATS_QATAN: 'kamatz katan', SHEVA: 'sheva', 'SHURUK': 'shuruk', 'HIRIQ_MALE': 'hiriq male',
         '\u05b1': 'hataf segol', '\u05b2': 'hataf patah', '\u05b3': 'hataf kamatz', None: None}
NA_RULES = ('start', 'second', 'twin', 'dagesh', 'meteg', 'long')
NAH_RULES = ('final', 'first', 'short')

def groups(w):
    """[(letter, marks)] — accents dropped except the meteg"""
    out = []
    for ch in w:
        if 'א' <= ch <= 'ת': out.append([ch, ''])
        elif out and unicodedata.category(ch).startswith('M'):
            if '֑' <= ch <= '֯': continue            # te'amim
            out[-1][1] += ch
    return [(c, m) for c, m in out]

def vowel_of(marks):
    return next((m for m in marks if m in VOWEL_MARKS), None)

def _before(G, k):
    """the vowel said just before letter k: (vowel mark, has meteg, mater?) — a vav with holam/shuruk, a yod or alef
       without a vowel after hiriq/tsere/kamatz are read as the vowel before them (matres lectionis)"""
    j = k - 1
    if j < 0: return None, False
    c, m = G[j]; v = vowel_of(m)
    if c == 'ו' and v is None and DAGESH in m: return 'SHURUK', METEG in m
    if c == 'ו' and v in (HOLAM, HOLAM_VAV) and DAGESH not in m: return HOLAM, METEG in m
    if c in 'יא' and v is None and DAGESH not in m and j >= 1:
        pc, pm = G[j - 1]; pv = vowel_of(pm)
        if c == 'י' and pv == HIRIQ: return 'HIRIQ_MALE', METEG in pm
        if pv in (TSERE, SEGOL, QAMATS, PATAH, HOLAM): return pv, METEG in pm
    return v, METEG in m

def _hazak(G, k):
    """a dagesh that doubles the letter: any dagesh after a vowel (not at the start, not after a sheva), and every
       dagesh in a letter outside בגדכפת (but not a shuruk or a mappiq)"""
    c, m = G[k]
    if DAGESH not in m: return False
    if c == 'ו' and vowel_of(m) is None: return False           # shuruk
    if c == 'ה' and k == len(G) - 1: return False              # mappiq
    if k == 0: return False
    pv = vowel_of(G[k - 1][1])
    if c in BGDKFT: return pv is not None and pv != SHEVA or (G[k - 1][0] == 'ו' and DAGESH in G[k - 1][1])
    return True

def shva_marks(word):
    """-> [{'k': letter index, 'c': letter, 'kind': 'na'|'nah', 'rule': ...}] for every sheva in the pointed word"""
    G = groups(word); n = len(G); out = []
    for k, (c0, m) in enumerate(G):
        if SHEVA not in m: continue
        c = FIN.get(c0, c0)
        nxt = G[k + 1][1] if k + 1 < n else ''
        prv = G[k - 1][1] if k else ''
        last_two = k + 1 < n and k + 2 == n and SHEVA in nxt   # two shvas at the very end (אַתְּ, וַיֵּשְׁתְּ)
        if k == n - 1 or last_two: kind, rule = 'nah', 'final'
        elif k == 0: kind, rule = 'na', 'start'
        elif SHEVA in prv and k >= 2: kind, rule = 'na', 'second'
        elif SHEVA in nxt: kind, rule = 'nah', 'first'
        elif k + 1 < n and FIN.get(G[k + 1][0], G[k + 1][0]) == c: kind, rule = 'na', 'twin'
        elif _hazak(G, k): kind, rule = 'na', 'dagesh'
        elif k == 1 and G[0][0] == 'ו' and DAGESH in G[0][1] and vowel_of(G[0][1]) is None:
            kind, rule = 'nah', 'shuruk'                    # the conjunction וּ: וּבְדֶרֶךְ is "uvderekh" (Rabbi Alouf)
        elif c == 'י' and vowel_of(prv) in (PATAH, QAMATS, SEGOL):
            kind, rule = 'nah', 'diphthong'                 # לַיְלָה "layla", וַיְהִי "vayhi": the yod closes an "ay"
        else:
            v, meteg = _before(G, k)
            if meteg: kind, rule = 'na', 'meteg'
            elif v in LONG or v in ('SHURUK', 'HIRIQ_MALE'): kind, rule = 'na', 'long'
            elif v in SHORT: kind, rule = 'nah', 'short'
            elif v in HAT: kind, rule = 'na', 'hataf'       # (rare: a hataf before a sheva)
            else: kind, rule = 'nah', 'other'
        v, meteg = _before(G, k) if k else (None, False)
        out.append({'k': k, 'c': c, 'kind': kind, 'rule': rule, 'after': VNAME.get(v, v), 'meteg': meteg})
    return out

if __name__ == '__main__':
    import json, sys
    for w in sys.argv[1:] or ['בְּרֵאשִׁית', 'יִשְׁמְרוּ', 'הַלְלוּ', 'הַמְּלָכִים', 'שׁוֹמְרִים', 'מַלְכּוֹ', 'אַתְּ', 'לֵךְ', 'וַיֵּלְכוּ', 'וּבְנֵי', 'תִּשְׁמְעוּ', 'שָֽׁמְרָה']:
        print(w, [(x['c'], x['kind'], x['rule']) for x in shva_marks(w)])


# ================================================================= hearing it (the phone ear)
# The pasuk's sounds (nikud.py units) are force-aligned on the phone ear with an OPTIONAL short-vowel slot after every
# consonant that carries a sheva. A slot the path uses, holding real short-vowel mass, is a vowel said there; an unused
# slot with no short-vowel frame between the two consonants is no vowel. space_test/shva_study.py measured it on
# Rabbi Alouf's 144 perakim (see the README for the table).
SCHWA = ['ə', 'ɛ', 'e', 'ɪ', 'ɨ', 'ɐ', 'ʌ', 'e̞', 'ɛː', 'eː']
# every vowel: before a guttural or a yod the shva na takes the colour of what follows (בְּיִרְאָה "bi-yir'a")
ALLV = SCHWA + ['a', 'ɑ', 'aː', 'æ', 'i', 'iː', 'o', 'ɔ', 'oː', 'ɔː', 'o̞', 'u', 'uː', 'ʊ']

def template(pointed, vocab, slot_set=None):
    """-> tokens (each a tuple of phones = one virtual column), meta per token, the optional slots; words as nikud.parse_verse splits them"""
    from nikud import parse_verse
    toks, meta, opt = [], [], set()
    PV = parse_verse(pointed)
    for wi, (w, letters, units) in enumerate(PV):
        sh = {m['k']: m for m in shva_marks(w)}; done = set()
        for u in units:
            alts = tuple(p for p in (u['alts'] or []) if p in vocab)
            if not alts: continue
            toks.append(alts); meta.append({'w': wi, 'k': u['k'], 'kind': u['kind']})
            if u['kind'] == 'cons' and u['k'] in sh and u['k'] not in done:
                done.add(u['k']); opt.add(len(toks)); toks.append(tuple(p for p in (slot_set or SCHWA) if p in vocab)); meta.append({'w': wi, 'k': u['k'], 'kind': 'slot', 'm': sh[u['k']]})
    return toks, meta, opt, len(PV)

def _probe1(lp, pointed, vocab, pad, slot_set):
    import numpy as np
    from vowels import ctc_align_opt
    toks, meta, opt, nw = template(pointed, vocab, slot_set)
    if not toks: return {}, nw
    sk = tuple(p for p in slot_set if p in vocab)
    keys = sorted(set(toks) | {sk}); col = {k: lp.shape[1] + i for i, k in enumerate(keys)}
    lp2 = np.concatenate([lp, np.stack([np.logaddexp.reduce(lp[:, [vocab[p] for p in k]], axis=1) for k in keys], 1)], 1)
    al = ctc_align_opt(lp2, [col[k] for k in toks], pad, optional=opt, skip_cost=0.0)
    sch = np.exp(lp2[:, col[sk]]); out = {}
    for j, (m, a) in enumerate(zip(meta, al)):
        if m['kind'] != 'slot': continue
        prev = al[j - 1]; nxt = next((al[q] for q in range(j + 1, len(al)) if al[q]['f0'] >= 0), None)
        # the line's last slot looks only ~100 ms past its consonant (5 frames), and its own frames count only there: it
        # could reach to the end of the recording, so an 'e' after the line (a hesitation, the next words) was a false 'final'
        g0 = prev['f1'] if prev['f0'] >= 0 else None; g1 = nxt['f0'] if nxt else min(lp.shape[0], (g0 if g0 is not None else 0) + 5)
        gap = sch[g0:g1] if g0 is not None and g1 > g0 else np.zeros(0)
        own = sch[max(a['f0'], g0 or 0):min(a['f1'], g1)] if a['f0'] >= 0 else np.zeros(0)
        mm = m['m']
        out.setdefault(m['w'], []).append({'k': mm['k'], 'c': mm['c'], 'kind': mm['kind'], 'rule': mm['rule'], 'used': bool(a['f0'] >= 0),
                                           'mass': round(float(own.sum()), 3), 'gapmax': round(float(gap.max()) if gap.size else 0.0, 3),
                                           'f0': int(a['f0']), 'f1': int(a['f1']), 'g0': int(g0) if g0 is not None else -1, 'g1': int(g1)})
    return out, nw

def probe(lp, pointed, vocab, pad):
    """lp: the phone ear's log-probs over the pasuk. -> (per word [{k, c, kind, rule, heard, ...}], number of words).
       Two alignments: an e-like slot (SCHWA) and an any-vowel slot (ALLV). heard = 'vowel' when the e-like slot is
       used and holds >= .5 of short-vowel mass; 'none' when even the any-vowel slot is not used and no frame between
       the two consonants reaches .15 of any vowel; else 'unsure'. Rabbi Alouf, perakim 41-150 (6,714 shvas; the
       rules were set on perakim 1-40): under "start" he is heard 'vowel' 78%, 'none' 1%; under "short" 'vowel' 1%,
       'none' 91%."""
    a, nw = _probe1(lp, pointed, vocab, pad, SCHWA); b, _ = _probe1(lp, pointed, vocab, pad, ALLV)
    for w, slots in a.items():
        bs = {s['k']: s for s in b.get(w, [])}
        for s in slots:
            t = bs.get(s['k'], {'used': True, 'mass': 0.0, 'gapmax': 1.0})
            s['mass_any'] = t['mass']; s['gapmax_any'] = t['gapmax']; s['used_any'] = t['used']
            s['heard'] = 'vowel' if s['used'] and s['mass'] >= HEARD['vowel'] else 'none' if (not t['used'] and t['gapmax'] < HEARD['none']) else 'unsure'
    return a, nw

# chosen offline (space_test/shva_tune.py) on Rabbi Alouf's own reading (false alarms) against his takes with a shva
# na's vowel cut out / a short vowel put into a silent shva (shva_eval.py): at (.5, .15) a trusted shva na is heard
# 'none' 1.1% of the time when he says it, a trusted silent shva 'vowel' 1.0%; about half the cut vowels and three
# quarters of the added ones are caught (the cut is a crude stand-in for a real swallowed shva)
HEARD = {'vowel': 0.5, 'none': 0.15}

# the rules a note may rest on without the hazzan (measured on Rabbi Alouf: what he does under them, near always);
# under the others (long, meteg, shuruk, diphthong, hataf, other) readers differ, and only the hazzan's own reading decides
TRUSTED = {'start', 'second', 'twin', 'dagesh', 'short', 'first', 'final'}

def notes(student, ref=None, trusted=None):
    """student / ref: probe() results per word (keys may be ints or strings). -> per word (string key) the shvas where
       the take clearly differs from what is expected: [{k, c, kind, rule, you, want, by}]
       expected = the hazzan's clear reading when he agrees with a trusted rule or the rule is not trusted; the rule
       alone when the hazzan is unclear or absent; nothing when the hazzan clearly contradicts a trusted rule (one of
       the two ears is wrong there, and a note would teach a mistake half the time)"""
    trusted = TRUSTED if trusted is None else trusted
    R = {str(k): v for k, v in (ref or {}).items()}
    out = {}
    for i, slots in (student or {}).items():
        rs = {s['k']: s for s in R.get(str(i), [])}
        for s in slots:
            if s['heard'] not in ('vowel', 'none'): continue
            rule_want = 'vowel' if s['kind'] == 'na' else 'none'
            r = rs.get(s['k']); hz = r['heard'] if r and r['heard'] in ('vowel', 'none') else None
            if s['rule'] in trusted:
                if hz is not None and hz != rule_want: continue
                want, by = rule_want, ('hazzan' if hz else 'rule')
            elif hz is not None:
                want, by = hz, 'hazzan'
            else:
                continue
            if s['heard'] != want:
                out.setdefault(str(i), []).append({'k': s['k'], 'c': s['c'], 'kind': s['kind'], 'rule': s['rule'], 'you': s['heard'], 'want': want, 'by': by})
    return out
