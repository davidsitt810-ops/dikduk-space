"""The letter checker's pure logic (no models here): where the FIRST consonant of a short take is, what each ear heard in
that window, and the verdict for the letter the student was asked to say. app.letter_probe runs the ears and calls in.

A letter cannot be said alone; the student says it with a vowel (עַ), or in the hazzan's word (עַל), or by its name
(עַיִן) — all three open with the letter, so the checker judges the take's opening consonant and nothing after it.
The rules were set on Rabbi Alouf's word-initial letters (the Sephardic sounds) against Israelis reading (ע as alef,
ח as khaf, ק as kaf, ט as tav, צ as ts, ר from the back of the mouth): space_test/letters_study.py, LAB_NOTES §27.
"""
import numpy as np

VOWEL_CHARS = set('aeiouyæɐɑɒəɛɜɞɤɪɨɯɵøœɔʉʊʌʏ')
AR_VOWELISH = set('اويىَُِآأإءًٌٍ')   # the Arabic ear's long vowels, semi-vowels, hamza seats and short-vowel marks
AR_WEAK = AR_VOWELISH | set('لّْ')   # …plus lam, shadda, sukun: what the Arabic ear writes at the start of a take when nothing was said yet

def is_vowel(p):
    return bool(p) and (p[0] in VOWEL_CHARS or p[0] in AR_VOWELISH)

def onset_window(seq, dur, ar_seq=None, energy_on=0.0, min_c=0.3, ar_min_c=0.5):
    """seq: the phone ear's greedy symbols [{'p','t','c'}]; ar_seq: the Arabic ear's; energy_on: where the take's
       energy starts (symbols more than 50 ms before it are noise in the leading quiet and are ignored).
       -> (t_on, t0, t1): where speech starts (each ear's first confident symbol; the earlier one), and the window that
       holds the opening consonant: from a little before it to a little after each ear's SECOND symbol begins (the
       vowel that follows the consonant, or the next consonant when the vowel was not heard; whichever ear's comes
       first). A consonant with nothing after it gets 0.3 s."""
    ends, ons = [], []
    floor = max(0.0, (energy_on or 0.0) - 0.05)
    for S, mc, weak in ((seq or [], min_c, set()), (ar_seq or [], ar_min_c, AR_WEAK)):
        S = [s for s in S if s.get('c', 1.0) >= mc and s['t'] >= floor]
        # the Arabic ear often opens with a confident "ال" (alef, lam, a sukun) that is not there: its onset is its
        # first real consonant; the phone ear's onset covers a take that truly opens with a vowel or an alef
        first = next((i for i, s in enumerate(S) if s['p'] not in weak), None)
        if first is None: continue
        S = S[first:]
        on = S[0]['t']; ons.append(on)
        nxt = next((s for s in S[1:] if s['t'] >= on + 0.03), None)
        if nxt is not None: ends.append(nxt['t'] + (0.06 if is_vowel(nxt['p']) else 0.02))
    if not ons:
        S = [s for s in (seq or []) if s['t'] >= floor] or [s for s in (ar_seq or []) if s['t'] >= floor] or list(seq or []) or list(ar_seq or [])
        if not S: return None
        ons = [S[0]['t']]
    t_on = min(ons)
    t1 = min(ends) if ends else t_on + 0.3
    t1 = min(t1, t_on + 0.4)
    t0 = max(0.0, t_on - 0.06)
    t1 = min(dur, max(t1, t0 + 0.1))
    return round(t_on, 3), round(t0, 3), round(t1, 3)

def peaks(lp, spf, t0, t1, ids):
    """max probability of each id over the window's frames"""
    f0, f1 = int(t0 / spf), max(int(t0 / spf) + 1, int(np.ceil(t1 / spf)))
    seg = np.exp(lp[f0:f1])
    if not len(seg): return {k: 0.0 for k in ids}, f0, f1
    return {k: round(float(seg[:, i].max()), 3) for k, i in ids.items()}, f0, f1

def masses(lp, f0, f1, ids):
    seg = np.exp(lp[f0:f1])
    if not len(seg): return {k: 0.0 for k in ids}
    return {k: round(float(seg[:, i].sum()), 3) for k, i in ids.items()}

# ---------------------------------------------------------------- the letters offered, and what "right" means
# c: the letter; name: its Sephardic name; want: the variants a student can be asked for (None = the letter itself)
LETTERS = [
    {'c': 'ע', 'name': 'ʿayin', 'he': 'עַיִן', 'kind': 'throat', 'tip': 'From the throat — like the Arabic ع. Not a plain alef.'},
    {'c': 'ח', 'name': 'ḥet', 'he': 'חֵית', 'kind': 'throat', 'tip': 'From the throat — like the Arabic ح. Softer than the Israeli khaf (כ without dagesh).'},
    {'c': 'א', 'name': 'alef', 'he': 'אָלֶף', 'kind': 'plain', 'tip': 'Plain — just the vowel, with a light catch. Not from the throat (that is ʿayin).'},
    {'c': 'ק', 'name': 'qof', 'he': 'קוֹף', 'kind': 'emphatic', 'tip': 'Deep k, from the back — like the Arabic ق. Not the plain k of kaf. Say it with "a": קָ.'},
    {'c': 'ט', 'name': 'ṭet', 'he': 'טֵית', 'kind': 'emphatic', 'tip': 'Heavy t — like the Arabic ط. Not the light t of tav. Say it with "a": טָ.'},
    {'c': 'צ', 'name': 'ṣadi', 'he': 'צָדִי', 'kind': 'emphatic', 'tip': 'Heavy s — like the Arabic ص. Not the Israeli "ts". Say it with "a": צָ.'},
    {'c': 'ר', 'name': 'resh', 'he': 'רֵישׁ', 'kind': 'resh', 'tip': 'Rolled with the tip of the tongue — like the Arabic ر. Not from the back of the throat (the Israeli r). The machine confirms a rolled r well and catches the Israeli r only sometimes.'},
    {'c': 'ב', 'name': 'bet / vet', 'he': 'בֵּית', 'kind': 'dagesh', 'want': [('b', 'בּ bet: b'), ('v', 'ב vet: v')],
     'tips': {'b': 'With the dagesh — a hard b, lips closed.', 'v': 'No dagesh — v, the lips nearly touching. Not b.'}},
    {'c': 'כ', 'name': 'kaf / khaf', 'he': 'כַּף', 'kind': 'dagesh', 'want': [('k', 'כּ kaf: k'), ('kh', 'כ khaf: kh')],
     'tips': {'k': 'With the dagesh — a plain k (not the deep q of qof).', 'kh': 'No dagesh — kh, a rough sound from the back of the mouth. Not k, and not the throat ḥet.'}},
    {'c': 'פ', 'name': 'pe / fe', 'he': 'פֵּא', 'kind': 'dagesh', 'want': [('p', 'פּ pe: p'), ('f', 'פ fe: f')],
     'tips': {'p': 'With the dagesh — p, lips closed.', 'f': 'No dagesh — f. Not p.'}},
    {'c': 'ש', 'name': 'shin / sin', 'he': 'שִׁין', 'kind': 'dagesh', 'want': [('sh', 'שׁ shin: sh'), ('s', 'שׂ sin: s')],
     'tips': {'sh': 'Dot on the right — sh.', 's': 'Dot on the left — s, like samekh.'}},
    {'c': 'ת', 'name': 'tav', 'he': 'תָּו', 'kind': 'tav', 'tip': 'Always t (with or without dagesh). Never s or th.'},
]
BY_C = {L['c']: L for L in LETTERS}

# the phone ear's symbols each verdict looks at
PH = {'ʕ', 'ʔ', 'ħ', 'h', 'x', 'χ', 'ɣ', 'q', 'k', 'ɡ', 't', 'd', 'ts', 's', 'ʃ', 'z', 'r', 'ɾ', 'ɹ', 'ʁ', 'b', 'v', 'p', 'f', 'w', 'θ', 'ð', 'l', 'm', 'n', 'j', 'β', 'ʋ', 'tʃ', 'dʒ', 'ʒ'}
# the Arabic ear's letters each verdict looks at (groups: one name -> several tokens)
AR_LOOK = {'ع': ['ع'], 'ا': ['ا', 'أ', 'إ', 'آ', 'ء'], 'ه': ['ه', 'ة'], 'ح': ['ح'], 'خ': ['خ'], 'ك': ['ك'], 'ق': ['ق'], 'ط': ['ط'], 'ت': ['ت'],
           'ص': ['ص'], 'س': ['س'], 'ش': ['ش'], 'ب': ['ب'], 'ف': ['ف'], 'ر': ['ر'], 'غ': ['غ'], 'ج': ['ج'], 'د': ['د'], 'ذ': ['ذ'], 'ث': ['ث'],
           'ز': ['ز'], 'و': ['و'], 'ي': ['ي'], 'ل': ['ل'], 'م': ['م'], 'ن': ['ن'], 'ض': ['ض'], 'ظ': ['ظ']}

# ---------------------------------------------------------------- the verdicts
# Measured on word-initial letters (space_test/letters_study.py, letters_rules.py; LAB_NOTES §27): Rabbi Alouf's
# Tehillim words that open with the letter (right by definition) and Israelis reading (FLEURS), whose ע ח ק ט צ ר are
# the Israeli sounds (wrong by definition). Numbers are "Alouf called right / called wrong" and "Israelis caught".
#
# Each non-throat letter: the sounds FOR the asked variant and AGAINST it, as (ear, symbol) peaks over the window —
# 'ph' the phone ear, 'ar' the Arabic ear (groups above). right: for >= hi and for > against; wrong: against >= hi
# and for < lo; else unsure.
# The emphatics (ק ט צ) are heard best before a, o, u: before i/e or a sheva the Arabic ear hears Rabbi Alouf's own
# ק as ك half the time and his צ as س — so the student is asked to say them with "a", and the examples are such words.
# ק (a/o/u): Alouf 84% / 1%, Israelis 89% caught. ט: 81% / 6%, 64%. צ: 84% / 4%, 63%.
# b/v is the phone ear's alone (the Arabic ear has no v: it writes Rabbi Alouf's vav as ب 79% of the time).
# Dagesh pairs on Alouf's word-initial letters: בּ 95% / 0, v (his word-initial vav, heard as v) 69%, כּ 96% / 0, כ 87% / 3%, פּ 90% / 0, פ 88% / 0, שׁ 98% / 1%,
# שׂ 94% / 1%, ת 83% / 1% (a plain t; unsure when the t is soft). Rabbi Alouf says a word-initial ב WITHOUT dagesh as
# b (110 of 120), so the vet examples come from inside words.
EV = {
    ('ק', None): {'for': [('ar', 'ق')], 'against': [('ar', 'ك')], 'hi': .5, 'lo': .2, 'right': 'Deep qof, from the back ✓', 'wrong': 'That was a plain k (kaf) ✕', 'alouf': 'ق', 'vowel': True},
    ('ט', None): {'for': [('ar', 'ط')], 'against': [('ar', 'ت')], 'hi': .5, 'lo': .2, 'right': 'Heavy ṭet ✓', 'wrong': 'That was a light t (tav) ✕', 'alouf': 'ط', 'vowel': True},
    ('צ', None): {'for': [('ar', 'ص')], 'against': [('ar', 'س'), ('ph', 'ts')], 'hi': .5, 'lo': .2, 'right': 'Heavy ṣadi ✓', 'wrong': 'That was a plain s or "ts" ✕', 'alouf': 'ص', 'vowel': True},
    ('ב', 'b'): {'for': [('ph', 'b')], 'against': [('ph', 'v'), ('ph', 'f')], 'hi': .5, 'lo': .2, 'right': 'bet with dagesh: b ✓', 'wrong': 'That was v (vet, no dagesh) ✕', 'alouf': 'b'},
    ('ב', 'v'): {'for': [('ph', 'v')], 'against': [('ph', 'b'), ('ph', 'p')], 'hi': .5, 'lo': .2, 'right': 'vet: v ✓', 'wrong': 'That was b (bet, with dagesh) ✕', 'alouf': 'v'},
    ('כ', 'k'): {'for': [('ph', 'k'), ('ar', 'ك')], 'against': [('ph', 'x'), ('ph', 'χ'), ('ar', 'خ')], 'hi': .5, 'lo': .2, 'right': 'kaf with dagesh: k ✓', 'wrong': 'That was kh (khaf, no dagesh) ✕', 'alouf': 'k'},
    ('כ', 'kh'): {'for': [('ph', 'x'), ('ph', 'χ'), ('ar', 'خ')], 'against': [('ph', 'k'), ('ar', 'ك')], 'hi': .5, 'lo': .2, 'right': 'khaf: kh ✓', 'wrong': 'That was k (kaf, with dagesh) ✕', 'alouf': 'x'},
    ('פ', 'p'): {'for': [('ph', 'p'), ('ar', 'ب')], 'against': [('ph', 'f'), ('ar', 'ف')], 'hi': .5, 'lo': .2, 'right': 'pe with dagesh: p ✓', 'wrong': 'That was f (fe, no dagesh) ✕', 'alouf': 'p'},
    ('פ', 'f'): {'for': [('ph', 'f'), ('ar', 'ف')], 'against': [('ph', 'p'), ('ar', 'ب')], 'hi': .5, 'lo': .2, 'right': 'fe: f ✓', 'wrong': 'That was p (pe, with dagesh) ✕', 'alouf': 'f'},
    ('ש', 'sh'): {'for': [('ph', 'ʃ'), ('ar', 'ش')], 'against': [('ph', 's'), ('ar', 'س')], 'hi': .5, 'lo': .2, 'right': 'shin: sh ✓', 'wrong': 'That was s (sin) ✕', 'alouf': 'ʃ'},
    ('ש', 's'): {'for': [('ph', 's'), ('ar', 'س')], 'against': [('ph', 'ʃ'), ('ar', 'ش')], 'hi': .5, 'lo': .2, 'right': 'sin: s ✓', 'wrong': 'That was sh (shin) ✕', 'alouf': 's'},
    ('ת', None): {'for': [('ph', 't'), ('ar', 'ت')], 'against': [('ph', 's'), ('ph', 'θ'), ('ar', 'س'), ('ar', 'ث')], 'hi': .5, 'lo': .2, 'right': 'tav: t ✓', 'wrong': 'That was s or th — a tav is always t ✕', 'alouf': 't'},
}
# ר: a rolled r is heard by the Arabic ear as ر and by the phone ear as r; the Israeli r (from the back) is heard
# as غ (ghayn) a third of the time and as nothing most of the rest — so: right when a rolled r is heard and no غ,
# wrong when غ is heard and no ر, else unsure (with a word about what was missing). Alouf 82% / 2%; Israelis 30%
# caught, 18% confirmed as rolled (some Israelis do roll it), the rest "not sure".
RESH = {'r_hi': .5, 'ph_hi': .4, 'g_hi': .3, 'lo': .15}
THROAT_SAY = {
    'ע': {'right': 'From the throat — ʿayin ✓', 'wrong': 'That was plain, like an alef ✕', 'alouf': 'ع'},
    'ח': {'right': 'From the throat — ḥet ✓', 'wrong': 'That was a khaf (כ), not from the throat ✕', 'alouf': 'ح'},
    'א': {'right': 'Plain alef ✓', 'wrong': 'That came from the throat — an ʿayin, not an alef ✕', 'alouf': 'ا'},
}
UNSURE = 'Not sure'
UNSURE_MORE = 'The ears did not agree. Try again a little closer to the phone, with nothing playing in the background.'
VOWEL_NOTE = 'Say it with "a" (as in Rabbi Alouf\'s word) — the ears tell the heavy sound from the light one best there.'

def ev_peak(P, items):
    best = 0.0
    for ear, k in items:
        v = (P.get('peak') if ear == 'ph' else P.get('ar_peak')) or {}
        best = max(best, float(v.get(k, 0.0)))
    return round(best, 3)

def throat_votes(c, th, peak):
    """the letter checker's vote on a word-initial ע / ח (for א the same ears, read the other way round). Differs from
       the line checker's throat_probe vote in two measured ways: the Arabic ear's alef is NOT a plain vote (at the
       start of a word it writes an alef for a weak ʿayin: 34 of 120 of Rabbi Alouf's), and for ע a letter head that
       heard neither ע nor א IS one (48% of Israeli ayins, 14% of his). Word-initial, clean onsets: ע Alouf 80% right /
       2% wrong, Israelis 78% caught / 0 called throat; ח 84% / 1%, Israelis 84% / 0."""
    key = 'ח' if c == 'ח' else 'ע'; alt = 'כ' if c == 'ח' else 'א'
    hm = ((th.get('head') or {}).get('mass') or {}); tot = hm.get(key, 0) + hm.get(alt, 0)
    t, p = [], []
    if tot >= .2:
        r = hm.get(key, 0) / tot
        if r >= .6: t.append('head')
        elif r <= .3: p.append('head')
    elif key == 'ע': p.append('head heard neither')
    pc = th.get('p2') if th.get('p2') is not None else th.get('p')
    if pc is not None:
        if pc >= (.5 if key == 'ע' else .6): t.append('classifier')
        elif pc <= .3: p.append('classifier')
    ar = th.get('ar') or {}
    if key == 'ע':
        if ar.get('ع', 0) >= .4: t.append('arabic')
    else:
        if ar.get('ح', 0) >= .4: t.append('arabic')
        elif ar.get('ح', 0) < .15 and (max(ar.get('خ', 0), ar.get('ه', 0)) >= .5 or (peak or {}).get('x', 0) >= .5): p.append('arabic: khaf heard')
    v = 'throat' if len(t) >= 2 and not p else 'plain' if len(p) >= 2 and not t else 'unsure'
    return v, {'throat': t, 'plain': p}

def verdict(c, want, P, strict=False):
    """-> {'v': right|wrong|unsure|no_speech, 'say', 'more', 'alouf', 'why'}"""
    if P.get('no_speech') or not P.get('win'):
        return {'v': 'no_speech', 'say': 'I did not hear anything', 'more': 'Tap, then say the letter right away — the recording is 2.5 seconds long.', 'why': 'no speech'}
    L = BY_C.get(c)
    if not L: return {'v': 'unsure', 'say': UNSURE, 'more': 'I do not know this letter.', 'why': 'unknown letter'}
    if L['kind'] in ('throat', 'plain'):
        th = P.get('throat') or {}; S = THROAT_SAY[c]
        v, votes = throat_votes(c, th, P.get('peak'))
        if L['kind'] == 'plain': v = {'throat': 'plain', 'plain': 'throat'}.get(v, v)   # an alef is right when the ears heard it plain
        out = {'alouf': S['alouf'], 'why': f"for the throat: {votes['throat'] or '-'} · for plain: {votes['plain'] or '-'}", 'votes': votes}
        if v == 'throat': out.update(v='right', say=S['right'], more='')
        elif v == 'plain': out.update(v='wrong', say=S['wrong'], more='')
        else: out.update(v='unsure', say=UNSURE, more=UNSURE_MORE)
    elif L['kind'] == 'resh':
        ar = (P.get('ar_peak') or {}); ph = (P.get('peak') or {})
        rr, g = ar.get('ر', 0), ar.get('غ', 0); r_ph = max(ph.get('r', 0), ph.get('ɾ', 0))
        out = {'alouf': 'r', 'why': f'rolled: Arabic ر {rr} · phone r {r_ph} · from the back: غ {g}'}
        if (rr >= RESH['r_hi'] or r_ph >= RESH['ph_hi']) and g < RESH['g_hi']: out.update(v='right', say='Rolled resh ✓', more='')
        elif g >= RESH['g_hi'] and rr < RESH['lo']: out.update(v='wrong', say='That came from the back of the throat (the Israeli r) ✕', more='')
        elif rr < RESH['lo'] and r_ph < RESH['lo']: out.update(v='unsure', say='I did not hear a rolled r', more='Roll it with the tip of the tongue, like the Arabic ر, and try again. (The machine confirms a rolled r well; it only sometimes catches the Israeli r.)')
        else: out.update(v='unsure', say=UNSURE, more=UNSURE_MORE)
    else:
        key = (c, want if L.get('want') else None)
        if key not in EV:
            key = (c, L['want'][0][0]) if L.get('want') else (c, None)
        E = EV.get(key)
        if not E: return {'v': 'unsure', 'say': UNSURE, 'more': 'No rule for this letter yet.', 'why': 'no rule'}
        f, a = ev_peak(P, E['for']), ev_peak(P, E['against'])
        out = {'alouf': E['alouf'], 'why': f'for {f} · against {a} (hi {E["hi"]}, lo {E["lo"]})'}
        if f >= E['hi'] and f > a: out.update(v='right', say=E['right'], more='')
        elif a >= E['hi'] and f < E['lo']: out.update(v='wrong', say=E['wrong'], more=VOWEL_NOTE if E.get('vowel') else '')
        else: out.update(v='unsure', say=UNSURE, more=(VOWEL_NOTE if E.get('vowel') else UNSURE_MORE))
    if strict and out['v'] == 'unsure':
        out.update(v='wrong', say='Not clearly right — work on this one', more=(out.get('more') or '') + ' Strict mode: a sound the ears could not confirm counts as not yet right.')
    return out
