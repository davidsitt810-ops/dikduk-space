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
