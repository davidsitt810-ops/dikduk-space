"""Replay the server's vowel notes from an exam's raw slots (RAW=1) under rule variants, to compare them on the same
takes. The default (ei=0.005, furtive=False) is the server's v5.5 exactly (replay.py checks this on every take).
  furtive=True: a furtive patah (רוּחַ, לַמְנַצֵּחַ: said BEFORE the final ח / ע / הּ) is expected in the slot after the
  letter before it, where it is said — not after the final letter, where the ear's template puts every vowel."""
import sys, os, json
R = '/home/claude/dikduk-space'; sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, 'tools'))
import vowels
from nikud import parse_verse
import vowel_rules as VR

NOT_STRESS = {'\u05AD', '\u059D', '\u05AE'}            # dehi (before the word), geresh muqdam, tsinnor (after it)
ACC = {chr(c) for c in range(0x0591, 0x05B0)} - NOT_STRESS
def stress_letter(word, last):
    """the letter that carries the word's stress accent (Tehillim's poetic te'amim); silluq on the pasuk's last word;
       None if no accent says (a word joined by maqaf, or only dehi)"""
    i = -1; got = None; meteg = None
    for ch in word:
        if '\u05D0' <= ch <= '\u05EA': i += 1
        elif ch in ACC and got is None: got = i
        elif ch == '\u05BD': meteg = i
    if got is None and last and meteg is not None: got = meteg
    return got

def raw_words(nikud):
    import re
    from nikud import clean_verse
    return [w for w in clean_verse(nikud).split(' ') if re.search('[א-ת]', w)]

def expected(pv, furtive=False, raw=None):
    exp = {}
    for i, (_, _, us) in enumerate(pv):
        sk = stress_letter(raw[i], i == len(pv) - 1) if raw is not None and len(raw) == len(pv) else None
        vk = [u['k'] for u in us if u['kind'] == 'vowel']
        if sk is None and vk: sk = vk[-1]   # no accent: the last vowel (most words are stressed at the end)
        e = []
        for j, u in enumerate(us):
            if u['kind'] != 'vowel': continue
            k = u['k']
            # a furtive patah is the one vowel the parser puts BEFORE its own consonant (same k, the word's last letter)
            f = furtive and j + 1 < len(us) and us[j + 1]['kind'] == 'cons' and us[j + 1]['k'] == k and k > 0
            if f: k = k - 1
            e.append({'heard': u['c'], 'k': k, 'stress': u['k'] == sk, **({'opt': True} if f and furtive == 2 else {})})
        exp[i] = e
    return exp

def noted(r, ei=0.005, furtive=False, keep=None):
    """-> the words (indices) shown with a vowel note on this take: clean takes only, never a word marked red"""
    return set(notes(r, ei, furtive, keep))

def notes(r, ei=0.005, furtive=False, keep=None):
    """-> {word: [note {k, you, ref, m, src}]} as shown on this take (clean takes only, never on a word marked red)"""
    raw = r['raw']
    if not r['clean']: return {}
    pv = parse_verse(raw['nikud'])
    if len(pv) != len(r['words']): return {}
    letters = {i: l for i, (_, l, _) in enumerate(pv)}
    stu = {i: VR.slots(w) for i, w in enumerate(raw['tw'])}
    haz = {i: VR.slots(w) for i, w in enumerate(raw['rw'])} if raw['rw'] else None
    old = vowels.EI_MAX_E; vowels.EI_MAX_E = ei; oc = vowels.compare_aligned
    rw = raw_words(raw['nikud'])
    if keep is not None:
        ctx = context(pv, rw)
        # the take's own profile: every page vowel the nikud comparison paired with a slot, and what the ear heard there
        _, pairs = vowels.compare_aligned(stu, expected(pv, furtive), letters, with_pairs=True)
        ctx['profile'] = [(i, k, ref, next(x['heard'] for x in stu[i] if x['k'] == k)) for i, pm in pairs.items() for k, ref in pm.items()]
        kp = lambda st, rs, L, i: keep(st, rs, L, i, ctx)
    else: kp = None
    if furtive == 2 or keep is not None: vowels.compare_aligned = lambda *a, **k: compare_aligned_opt(*a, keep=kp, **k)
    try: vh, vn = vowels.vowel_notes(stu, haz, expected(pv, furtive, rw), letters)
    finally: vowels.EI_MAX_E = old; vowels.compare_aligned = oc
    out = {}
    for src, d in (('hazzan', vh or {}), ('nikud', vn or {})):
        for i, ds in d.items():
            if ds and r['marks'][int(i)] != 'off': out.setdefault(int(i), []).extend(dict(x, src=src) for x in ds)
    return out

def load(V, names, lo=1, hi=150):
    rows = []
    for nm in names.split('+'):
        p = os.path.join(V, f'exam_{nm}.json')
        if os.path.exists(p): rows += [r for r in json.load(open(p, encoding='utf-8')) if 'raw' in r and 'words' in r and lo <= r['per'] <= hi]
    return rows

def compare_aligned_opt(student, ref, letters, ratio=2.0, with_pairs=False, skip=0.5, sub=0.9, keep=None):
    """vowels.compare_aligned, except that passing over an expected vowel marked opt costs nothing, and a note is
       kept only if keep(student slot, expected or hazzan slot, the word's letters) says so (when keep is given)"""
    clear, compat, EI = vowels.clear, vowels.compat, vowels.EI_MAX_E
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
                if b < m and D[a][b] + (0.0 if r[b].get('opt') else skip) < D[a][b + 1]: D[a][b + 1] = D[a][b] + (0.0 if r[b].get('opt') else skip); B[a][b + 1] = (a, b, 'r')
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
            if rs['heard'] == 'E' and st['heard'] == 'I' and mm.get('E', 0) > EI * sum(mm.values()): continue
            if keep is not None and not keep(st, rs, L, i): continue
            out.setdefault(i, []).append({'k': st['k'], 'you': st['heard'], 'ref': rs['heard'], 'm': round(mm[st['heard']] / max(1e-6, sum(mm.values())), 2)})
    return (out, pairs) if with_pairs else out

def context(pv, rw):
    """per word: the stressed letter, and per letter k whether a vowel after it would close its syllable (the next
       consonant has no vowel of its own, or is doubled by a dagesh)"""
    ctx = {'stress': {}, 'closed': {}, 'units': {}}
    for i, (_, l, us) in enumerate(pv):
        sk = stress_letter(rw[i], i == len(pv) - 1) if len(rw) == len(pv) else None
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
        ctx['closed'][i] = closed; ctx['units'][i] = us
    return ctx

def calibrated(theta, min_n=2, kinds=(('E', 'I'),), same_word=True):
    """a keep-hook: drop a note "you said Y where the page says X" (for the given kinds) when, among the take's OTHER
       page-X vowels (at least min_n of them), a share >= theta was heard as Y too: the reader's own way of saying X,
       not a mistake on this one word. same_word=False: only vowels of the take's other words count"""
    def keep(st, rs, L, i, ctx):
        X, Y = rs['heard'], st['heard']
        if (X, Y) not in kinds: return True
        others = [h for (j, k, ref, h) in ctx['profile'] if ref == X and not (j == i and (k == st['k'] or not same_word))]
        if len(others) < min_n: return True
        return sum(1 for h in others if h == Y) / len(others) < theta
    return keep

def unstressed(kinds=(('A', 'E'), ('I', 'E')), closed_only=False):
    """a keep-hook: drop a note "you said Y where the page says X" (for the given kinds) on an unstressed vowel —
       a vowel said quickly, away from the stress, drifts toward e (reduction) in good readers too. closed_only: only
       in a closed syllable (the next letter doubled, or without a vowel of its own: a short, lax vowel)"""
    def keep(st, rs, L, i, ctx):
        if (rs['heard'], st['heard']) not in kinds: return True
        s = rs.get('stress')
        if s is None: s = st['k'] == ctx['stress'].get(i)
        if s: return True
        if closed_only:
            cl = ctx['closed'].get(i, {}); c = cl.get(rs['k'], cl.get(st['k']))
            return not c
        return False
    return keep

def both(*hooks):
    hooks = [h for h in hooks if h is not None]
    if not hooks: return None
    return lambda *a: all(h(*a) for h in hooks)

def after_letters(kinds, letters='עח'):
    """a keep-hook: drop a note "you said Y where the page says X" (for the given kinds) on a vowel said right after
       one of the letters (by default ע / ח: a throat letter said from the throat lowers the vowel after it)"""
    def keep(st, rs, L, i, ctx):
        if (rs['heard'], st['heard']) not in kinds: return True
        k = rs.get('k', st['k'])
        return not ((0 <= k < len(L) and L[k] in letters) or (0 <= st['k'] < len(L) and L[st['k']] in letters))
    return keep
