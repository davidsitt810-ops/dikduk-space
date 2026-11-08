"""The vowel ear: the full head (letters + the vowel classes A E I O U, trained on Rabbi Alouf's pointed Tehillim)
and a CTC aligner that allows OPTIONAL tokens, so a line without nikud can be aligned as
   letter [vowel?] letter [vowel?] ... (space) letter [vowel?] ...
where every vowel slot is a virtual column (the five vowel classes summed) that the path may skip. For every slot
the path used, the mass of each vowel class on its frames says which vowel was sung. The same template is aligned
on the hazzan's recording and on the student's; slots that disagree with a clear margin are reported.
Vowel classes: A = patah/kamatz, E = segol/tsere, I = hiriq, O = holam/kamatz katan, U = shuruk/kubutz."""
import numpy as np

VOWELS = ['A', 'E', 'I', 'O', 'U']
VOWEL_NAME = {'A': 'ah (patah / kamatz)', 'E': 'eh (segol / tsere)', 'I': 'ee (hiriq)', 'O': 'oh (holam)', 'U': 'oo (shuruk / kubutz)'}
# v5.5: "ee where the page says eh" only when the ear heard no eh at all in that vowel (at most this share of its mass).
# Hazzan Faraj Samra, never heard by the ear, says a clear eh (David listened) that the ear often takes for ee — 67 of
# his 96 false notes; those keep a trace of eh (median 1.6% of the mass), while a real ee read where the page says eh
# (his own hiriq with the page rewritten, PLANT=IE) has none (0.0% at the 90th percentile). At 0.5%: his false notes
# 50 -> 26 words of 1,300, the real ee still told 96.5% as before (tools/LAB_NOTES.md §38).
EI_MAX_E = 0.005

def expected_vowels(units, sk=None):
    """One word's vowels from the nikud (nikud.parse_word's units), each with the letter it follows (k), as
       vowel_notes wants them. (v5.6) A furtive patah (רוּחַ, לַמְנַצֵּחַ: said BEFORE the final ח / ע / הּ, so the parser
       puts it before its own consonant) is expected where it is said, in the slot after the letter before it: the
       ear's template has a vowel slot only AFTER each letter, so the "ah" lands in the slot of the vowel before it
       and the slot after the final letter is empty. That made a false "you said ah where the page says eh" on
       לַמְנַצֵּחַ, which opens more than fifty perakim, and on כֹּחַ, בוֹטֵחַ, יָרֵחַ, שָׁמֵעַ… Faraj Samra (never heard), Tehillim
       1-55 where this was found: 13 of his 198 false notes go, none is added; 56-150, held out: 11 of 170 go, 1 is
       added. Of 1,450 planted i-for-e it stops telling one, לַשְׁמִעַ, whose old note was this very artifact ("ah where
       the page says eh"); tools/LAB_NOTES.md §39."""
    out = []
    for j, u in enumerate(units):
        if u['kind'] != 'vowel': continue
        k = u['k']
        if k > 0 and j + 1 < len(units) and units[j + 1]['kind'] == 'cons' and units[j + 1]['k'] == k: k -= 1   # furtive: before its consonant
        out.append({'heard': u['c'], 'k': k, **({'stress': u['k'] == sk} if sk is not None else {})})   # (v5.8) sk: vowel_context
    return out

# (v5.8) two rules from David's listening (LAB_NOTES §41), applied where the line has nikud (vowel_context):
#  - a kamats katan said "a" is right too ("both are right" where he learns, on all four he heard: before a hataf
#    kamats, with a meteg, before a shva) — no "ah where the page / the hazzan says oh" on a letter that carries one;
#  - on an unstressed vowel in a closed syllable, "eh where the page says ah" or "eh where it says ee" only when the
#    ear is very sure (its winner at least SURE_UNST of the slot's mass): Hazzan Faraj Samra's "a" there, and his "i"
#    before a shva, he heard as written or swallowed (7 of the 8), and those are where these false notes are (144 of
#    173 on two readers). Replayed: his false notes 2.64% -> 2.25% (Tehillim 1-55), 2.47% -> 2.16% (56-150), Shmuelof
#    0.85% -> 0.79%; a real "e for i" told 76.8% -> 75.8%, "e for a" 83.8% -> 82.7%, the other kinds as before.
SURE_UNST = 0.99
SURE_KINDS = {('A', 'E'), ('I', 'E')}
QAMATS_QATAN = '\u05C7'
NOT_STRESS = {'\u05AD', '\u059D', '\u05AE'}            # dehi (before the word), geresh muqdam, tsinnor (after it)
STRESS_MARKS = {chr(c) for c in range(0x0591, 0x05B0)} - NOT_STRESS

def stress_letter(word, last):
    """the letter that carries the word's stress accent (Tehillim's poetic te'amim); silluq (a meteg) on the pasuk's
       last word; None if no accent says (a word joined by maqaf, or only dehi)"""
    i = -1; got = None; meteg = None
    for ch in word:
        if '\u05D0' <= ch <= '\u05EA': i += 1
        elif ch in STRESS_MARKS and got is None: got = i
        elif ch == '\u05BD': meteg = i
    if got is None and last and meteg is not None: got = meteg
    return got

def vowel_context(pv):
    """per word of a pointed line (nikud.parse_verse): the stressed letter (or, with no accent, the last vowel's),
       whether a vowel after letter k closes its syllable (the next consonant doubled, or without a vowel of its own),
       and the letters that carry a kamats katan"""
    ctx = {'stress': {}, 'closed': {}, 'qq': {}}
    for i, (w, _, us) in enumerate(pv):
        sk = stress_letter(w, i == len(pv) - 1)
        vk = [u['k'] for u in us if u['kind'] == 'vowel']
        ctx['stress'][i] = sk if sk is not None else (vk[-1] if vk else None)
        closed = {}
        cons = [(j, u) for j, u in enumerate(us) if u['kind'] == 'cons']
        for j, u in enumerate(us):
            if u['kind'] != 'vowel': continue
            nxt = next(((jj, c) for jj, c in cons if jj > j), None)
            if nxt is None: closed[u['k']] = False; continue   # open at the word's end
            jj, c = nxt
            after = us[jj + 1] if jj + 1 < len(us) else None
            closed[u['k']] = bool(c.get('dagesh') and c['c'] not in 'אהחער') or after is None or after['kind'] == 'cons'
        ctx['closed'][i] = closed
        k = -1; q = set()
        for ch in w:
            if '\u05D0' <= ch <= '\u05EA': k += 1
            elif ch == QAMATS_QATAN and k >= 0: q.add(k)
        ctx['qq'][i] = q
    return ctx

def keep_note(st, rs, i, ctx):
    """the two v5.8 rules above, for one note: st the student's slot, rs the page's vowel or the hazzan's slot"""
    X, Y = rs['heard'], st['heard']
    if X == 'O' and Y == 'A':
        q = ctx['qq'].get(i, ())
        if rs.get('k') in q or st['k'] in q: return False
    if (X, Y) in SURE_KINDS:
        s = rs.get('stress')
        if s is None: s = st['k'] == ctx['stress'].get(i)
        if not s:
            cl = ctx['closed'].get(i, {})
            if cl.get(rs['k'], cl.get(st['k'])):
                mm = st['mass']
                return mm[Y] >= SURE_UNST * max(1e-6, sum(mm.values()))
    return True

def ctc_align_opt(lp, toks, blank, optional=None, band=None, skip_cost=0.0):
    """Viterbi forced alignment on the blank-interleaved trellis; `optional` = set of token positions the path may
       skip, each skip costing `skip_cost` (log-prob units). -> per token {'f0','f1','score'} (f0 = -1 when skipped)."""
    T = lp.shape[0]; N = len(toks); S = 2 * N + 1
    opt = np.zeros(N, dtype=bool)
    for j in (optional or ()): opt[j] = True
    ext = np.array([blank if s % 2 == 0 else toks[(s - 1) // 2] for s in range(S)])
    tokpos = lambda s: (s - 1) // 2                      # token index of an odd state
    # which jumps d = 2, 3, 4 are allowed INTO each state
    ok2 = np.zeros(S, dtype=bool); ok3 = np.zeros(S, dtype=bool); ok4 = np.zeros(S, dtype=bool)
    for s in range(S):
        if s >= 2:
            if s % 2 == 1: ok2[s] = ext[s] != ext[s - 2]                       # token <- token (blank between skipped)
            else: ok2[s] = opt[tokpos(s - 1)]                                   # blank <- blank, skipping an optional token
        if s >= 3:
            if s % 2 == 1: ok3[s] = opt[tokpos(s - 2)]                          # token m <- blank before token m-1 (optional)
            else: ok3[s] = opt[tokpos(s - 1)]                                   # blank 2m <- token m-2, skipping blank + optional token m-1
        if s >= 4:
            if s % 2 == 1: ok4[s] = opt[tokpos(s - 2)] and ext[s] != ext[s - 4]  # token m <- token m-2 over an optional token m-1
            else: ok4[s] = opt[tokpos(s - 1)] and opt[tokpos(s - 3)]            # blank <- blank over two optional tokens
    # the cost of the skips each jump makes: d=2 into a blank skips one token; d=3 always one; d=4 into a token one, into a blank two
    cost = {2: np.array([skip_cost if s % 2 == 0 else 0.0 for s in range(S)]), 3: np.full(S, skip_cost),
            4: np.array([skip_cost if s % 2 == 1 else 2 * skip_cost for s in range(S)])}
    W = band if band else S + 1
    NEG = -1e30
    prev = np.full(S, NEG); prev[0] = lp[0, ext[0]]
    if S > 1: prev[1] = lp[0, ext[1]]
    if N > 0 and opt[0]:
        if S > 2: prev[2] = lp[0, ext[2]] - skip_cost
        if S > 3: prev[3] = lp[0, ext[3]] - skip_cost
    lo_of = np.zeros(T, dtype=np.int64); bps = [None] * T
    for t in range(1, T):
        c = int(S * t / T); lo = max(0, c - W); hi = min(S, c + W)
        best = prev.copy(); b = np.zeros(S, dtype=np.int8)
        for d, ok in ((1, None), (2, ok2), (3, ok3), (4, ok4)):
            cand = np.concatenate(([NEG] * d, prev[:-d])) if S > d else np.full(S, NEG)
            if ok is not None: cand = np.where(ok, cand - cost[d], NEG)
            m = cand > best; best[m] = cand[m]; b[m] = d
        cur = best + lp[t, ext]
        if W <= S: cur[:lo] = NEG; cur[hi:] = NEG
        lo_of[t] = lo; bps[t] = b[lo:hi].copy()
        prev = cur
    ends = [(S - 1, 0.0), (S - 2, 0.0)] + ([(S - 3, skip_cost), (S - 4, skip_cost)] if N > 0 and opt[N - 1] else [])
    ends = [(e, c) for e, c in ends if e >= 0]
    s = max(ends, key=lambda ec: prev[ec[0]] - ec[1])[0]
    if prev[s] <= NEG / 2: return [{'f0': -1, 'f1': -1, 'score': 0.0} for _ in toks]
    path = np.zeros(T, dtype=np.int64)
    for t in range(T - 1, 0, -1):
        path[t] = s; k = s - lo_of[t]; bp = bps[t]
        s -= int(bp[k]) if 0 <= k < len(bp) else 0
    path[0] = s
    out = [{'f0': -1, 'f1': -1, 'sum': 0.0, 'n': 0} for _ in toks]
    for t in range(T):
        st = int(path[t])
        if st % 2 == 0: continue
        o = out[(st - 1) // 2]
        if o['f0'] < 0: o['f0'] = t
        o['f1'] = t + 1; o['sum'] += float(np.exp(lp[t, ext[st]])); o['n'] += 1
    return [{'f0': o['f0'], 'f1': o['f1'], 'score': (o['sum'] / o['n']) if o['n'] else 0.0} for o in out]

OPTIONAL_LETTERS = set('ויא')   # matres lectionis / a glottal catch: the path may skip the letter (its sound is then the vowel slot's)

def vowel_place(lp, words, s2i, he_read, pairs=(('ע', 'א'), ('ח', 'כ'))):
    """lp: the full head's log-probs (T, V). words: the line's words. Template per word: letter [vowel?] letter [vowel?] …
       with ו י א and a final ה optional too. -> (slots, letter score): slots[i] = the vowel slots the path used in word i,
       in order, each {k: letter the vowel follows, heard, mass{A..U}, p, f0, f1}; letter score = mean letter certainty."""
    vid = [s2i[v] for v in VOWELS if v in s2i]
    if len(vid) < 5 or ' ' not in s2i: return {}, {}
    cols = {'V': lp.shape[1]}; extra = [np.logaddexp.reduce(lp[:, vid], axis=1)]
    toks, meta, optional = [], [], set()
    for i, w in enumerate(words):
        hl = he_read(w)
        for k, c in enumerate(hl):
            if c not in s2i: continue
            pair = next((p for p in pairs if c in p), None)
            if pair:
                key = ''.join(pair)
                if key not in cols: cols[key] = lp.shape[1] + len(extra); extra.append(np.logaddexp.reduce(lp[:, [s2i[m] for m in pair]], axis=1))
                tok = cols[key]
            else: tok = s2i[c]
            if c in OPTIONAL_LETTERS or (c == 'ה' and k == len(hl) - 1): optional.add(len(toks))
            toks.append(tok); meta.append((i, k, 'L'))
            optional.add(len(toks)); toks.append(cols['V']); meta.append((i, k, 'V'))   # the optional vowel slot after the letter
        if i + 1 < len(words): toks.append(s2i[' ']); meta.append((i, -1, 'S'))
    if not toks: return {}, {}
    lp2 = np.concatenate([lp, np.stack(extra, 1)], 1)
    al = ctc_align_opt(lp2, toks, 0, optional=optional)
    slots, letters = {}, {}
    for (i, k, kind), a in zip(meta, al):
        if a['f0'] < 0 or kind == 'S': continue
        if kind == 'L': letters.setdefault(i, []).append(a['score']); continue
        mass = {v: float(np.exp(lp[a['f0']:a['f1'], s2i[v]]).sum()) for v in VOWELS}
        slots.setdefault(i, []).append({'k': k, 'heard': max(mass, key=mass.get), 'mass': {v: round(m, 3) for v, m in mass.items()}, 'p': round(a['score'], 3), 'f0': a['f0'], 'f1': a['f1']})
    return slots, {i: round(float(np.mean(v)), 3) for i, v in letters.items()}

def clear(slot, ratio):
    """a slot whose winner carries a clear majority of the vowel mass"""
    m = slot['mass']; tot = sum(m.values()); w = slot['heard']
    return tot >= 0.3 and m[w] >= ratio * max([v for k, v in m.items() if k != w] + [1e-6])

def compare_vowels(student, ref, ratio=2.0):
    """student: slots per word (vowel_place). ref: per word the expected vowels in order — the hazzan's slots, or from
       the nikud a list of {'heard': class} (no mass). Compared position by position only when both have the same
       number of vowels in the word (otherwise the word is left alone: unsure). -> per word [{k, you, ref, m}]"""
    out = {}
    for i, sl in student.items():
        r = ref.get(i)
        if not r or len(r) != len(sl): continue
        for s, rs in zip(sl, r):
            R = rs['heard']; W = s['heard']
            if R == W or not clear(s, ratio): continue
            if rs.get('mass') is not None and not clear(rs, ratio): continue   # the hazzan's own vowel must be clear too
            m = s['mass']; out.setdefault(i, []).append({'k': s['k'], 'you': W, 'ref': R, 'm': round(m[W] / max(1e-6, sum(m.values())), 2)})
    return out


def compat(a, b, letters):
    """a vowel slot after letter a and one after letter b can be the same vowel: the same letter, or neighbours where
       the later letter is a mater (ו י א) or a final ה, which the ear may pass over (holam male, hiriq male...)"""
    if a == b: return True
    hi = max(a, b)
    return abs(a - b) == 1 and hi < len(letters) and (letters[hi] in 'ויא' or (letters[hi] == 'ה' and hi == len(letters) - 1))

def compare_aligned(student, ref, letters, ratio=2.0, with_pairs=False, skip=0.5, sub=0.9, ctx=None):
    """(v5.3) student: slots per word (vowel_place); ref: per word the expected vowels with the letter each follows (k):
       the hazzan's slots, or the nikud's vowels. Each word's two lists are lined up in order — a slot may pair only
       with a vowel after a compatible letter, passing over one costs `skip`, a pair of different vowels `sub` (less
       than two skips) — so an extra vowel heard (a shva said as a vowel) or one not heard no longer leaves the whole
       word unchecked, as compare_vowels does when the counts differ. Every pair of different vowels whose slot is
       clear (and, for the hazzan, his slot too) is a note. letters: {word: its letters as read}.
       -> {word: [{k, you, ref, m}]} (and {word: {student k: the vowel it was paired with}} if with_pairs)"""
    out, pairs = {}, {}
    for i, sl in student.items():
        r = ref.get(i)
        if not r or not sl: continue
        L = letters.get(i, '')
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
            st, rs = sl[a], r[b]; pairs.setdefault(i, {})[st['k']] = rs['heard']
            if st['heard'] == rs['heard'] or not clear(st, ratio): continue
            if rs.get('mass') is not None and not clear(rs, ratio): continue
            mm = st['mass']
            if rs['heard'] == 'E' and st['heard'] == 'I' and mm.get('E', 0) > EI_MAX_E * sum(mm.values()): continue   # v5.5, below
            if ctx is not None and not keep_note(st, rs, i, ctx): continue   # v5.8, above
            out.setdefault(i, []).append({'k': st['k'], 'you': st['heard'], 'ref': rs['heard'], 'm': round(mm[st['heard']] / max(1e-6, sum(mm.values())), 2)})
    return (out, pairs) if with_pairs else out

def vowel_notes(student, hazzan, expected, letters, ctx=None):
    """(v5.3) the take's vowel notes against the hazzan and against the nikud, with the two cross-checks:
       a nikud note where the hazzan is heard saying the same vowel there is dropped (v4.9: the ear mishears some of
       the hazzan's vowels the same way, and the student who sings as he does is right), and a hazzan note where the
       student said the vowel the nikud writes is dropped (v5.1). hazzan / expected may be None. ctx (v5.8, a pointed
       line's vowel_context): the kamats-katan and very-sure rules, on both comparisons.
       -> (notes against the hazzan or None, notes against the nikud or None)"""
    vh = compare_aligned(student, hazzan, letters, ctx=ctx) if hazzan is not None else None
    if expected is None: return vh, None
    vn, pair = compare_aligned(student, expected, letters, with_pairs=True, ctx=ctx)
    for i in list(vn):
        hv = (hazzan or {}).get(i) or []
        vn[i] = [d for d in vn[i] if not any(h['heard'] == d['you'] and compat(h['k'], d['k'], letters.get(i, '')) for h in hv)]
        if not vn[i]: del vn[i]
    if vh:
        for i in list(vh):
            pm = pair.get(i, {})
            vh[i] = [d for d in vh[i] if not (d['k'] in pm and pm[d['k']] == d['you'])]
            if not vh[i]: del vh[i]
    return vh, vn


def letters_kept(lp, words, s2i, he_read, skip_cost=4.0, pairs=(('ע', 'א'), ('ח', 'כ'))):
    """Which letters of the line were actually heard: the line's letters aligned on the head with EVERY letter
       optional at a cost, so a letter is kept only where the head's evidence for it beats the cost of skipping it.
       -> per word {'kept': fraction of its letters kept, 'miss': [letters skipped], 'p': mean score of kept letters}"""
    toks, meta, optional, cols, extra = [], [], set(), {}, []
    for i, w in enumerate(words):
        for k, c in enumerate(he_read(w)):
            if c not in s2i: continue
            pair = next((p for p in pairs if c in p), None)
            if pair:
                key = ''.join(pair)
                if key not in cols: cols[key] = lp.shape[1] + len(extra); extra.append(np.logaddexp.reduce(lp[:, [s2i[m] for m in pair]], axis=1))
                tok = cols[key]
            else: tok = s2i[c]
            optional.add(len(toks)); toks.append(tok); meta.append((i, k, c))
        if i + 1 < len(words) and ' ' in s2i: toks.append(s2i[' ']); meta.append((i, -1, ' '))
    if not toks: return {}
    lp2 = np.concatenate([lp] + ([np.stack(extra, 1)] if extra else []), 1)
    al = ctc_align_opt(lp2, toks, 0, optional=optional, skip_cost=skip_cost)
    out = {}
    for (i, k, c), a in zip(meta, al):
        if c == ' ': continue
        o = out.setdefault(i, {'n': 0, 'kept': 0, 'miss': [], 'scores': []})
        o['n'] += 1
        if a['f0'] >= 0: o['kept'] += 1; o['scores'].append(a['score'])
        else: o['miss'].append(c)
    return {i: {'kept': round(o['kept'] / o['n'], 3), 'miss': o['miss'], 'p': round(float(np.mean(o['scores'])), 3) if o['scores'] else 0.0} for i, o in out.items()}
