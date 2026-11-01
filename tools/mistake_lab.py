"""Does learning a student's voice (calibration on ~30 of his pesukim) also teach the checker his MISTAKES?
A planted, consistent mistake on a correct reader: every vowel of class X he says is written Y in his text ("he says
o where the page says u" for X=O, Y=U), in his 30 calibration pesukim and in his held-out pesukim alike. The Name
(read adonay) keeps its vowels — the server reads it from the Name, not from the page's points.
  maps <voice> <XY>   -> mistake_<voice>_<XY>.json   {id: planted pron} for all his items (exams, naive calibration);
                         XY = OU: always; OU30: only in 30% of his words (the same words each time)
                         safe1_<voice>_<XY|none>.json {id: null} for the calibration pesukim the shipped head flags
                         safe2_<voice>_<XY|none>.json {id: pron} the calibration pesukim with every vowel the shipped
                                                      head CLEARLY hears otherwise relabeled to what it hears
                         safe3_<voice>_<XY|none>.json the same, only for a confusion that is his usual way (>= half the
                                                      slots of that vowel) — a sometimes-confusion is learned as his voice
  exam <head.pt> <voice> [map.json]  -> on his held-out pesukim: words flagged; with a planted mistake, the share of
                         mistake words caught and of the other words flagged, and what the head hears at the mistakes
(train_head2.py: HEAD_NV_PRON=<map> trains on the map; HEAD_DUMP gives ids_<voice>.json: nv_train / test_nv)"""
import json, os, sys, collections, zlib, numpy as np, torch, torch.nn as nn
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'space')); sys.path.insert(0, '/home/claude/dikduk-space')
from vowels import vowel_place, compare_vowels, clear
LETTERS = list('אבגדהוזחטיכלמנסעפצקרשת'); VOWELS = list('AEIOU')
SYM = ['<b>', ' '] + LETTERS + VOWELS; S2I = {s: i for i, s in enumerate(SYM)}
NAME_PRE = {'', 'ו', 'ל', 'ב', 'כ', 'מ', 'ש', 'וב', 'ול', 'וכ', 'ומ', 'וש'}

class Head(nn.Module):   # as train_head2.py
    def __init__(self, d_in=1024, h=384, n=len(SYM), k=5, layers=3):
        super().__init__(); self.inp = nn.Sequential(nn.LayerNorm(d_in), nn.Linear(d_in, h), nn.GELU(), nn.Dropout(0.15))
        self.convs = nn.ModuleList([nn.Sequential(nn.Conv1d(h, h, k, padding=k // 2), nn.GELU(), nn.Dropout(0.15)) for _ in range(layers)])
        self.norms = nn.ModuleList([nn.LayerNorm(h) for _ in range(layers)]); self.out = nn.Linear(h, n)
    def forward(self, x):
        y = self.inp(x)
        for conv, norm in zip(self.convs, self.norms): y = norm(y + conv(y.transpose(1, 2)).transpose(1, 2))
        return self.out(y)
def load_head(path):
    ck = torch.load(path, map_location='cpu'); assert ck['sym'] == SYM, 'not a full (vowel) head'
    m = Head(); m.load_state_dict(ck['state']); m.eval(); return m
def feats(r):
    d = np.load(os.path.join(HERE, 'feat', r['id'] + '.npz'))
    if 'h12q' in d.files: return torch.from_numpy(d['h12q'].astype(np.float32) * (d['h12s'].astype(np.float32)[:, None] / 127))
    return torch.from_numpy(d['h12'].astype(np.float32))
def logp(model, r):
    with torch.no_grad(): return torch.log_softmax(model(feats(r)[None]), -1)[0].numpy()
ROWS = {}
for l in open(os.path.join(HERE, 'manifest_voices.jsonl'), encoding='utf-8'):
    r = json.loads(l); ROWS[r['id']] = r
def is_name(w): return w.endswith('אדני') and w[:-4] in NAME_PRE
def plant(r, X, Y, rate=100):
    """his pron with every X written Y (the Name kept) — or, rate < 100, in that share of his words only (the same words
       every time: a mistake he makes in some words, not a sound he always says that way)"""
    some = lambda i: rate >= 100 or zlib.crc32(f"{r['id']}:{i}".encode()) % 100 < rate
    return ' '.join(p if is_name(w) or not some(i) else p.replace(X, Y) for i, (w, p) in enumerate(zip(r['text'].split(), r['pron'].split())))
def vowels_of(p): return [c for c in p if c in VOWELS]
def ref_of(pron): return {i: [{'heard': c} for c in vowels_of(p)] for i, p in enumerate(pron.split())}

def maps(voice, XY):
    ids = json.load(open(os.path.join(HERE, f'ids_{voice}.json')))
    cal = [ROWS[i] for i in ids['nv_train']]
    mine = {i: r for i, r in ROWS.items() if r['voice'] == voice}
    planted = {i: plant(r, XY[0], XY[1], int(XY[2:] or 100)) for i, r in mine.items()} if XY != 'none' else {}   # OU = always, OU30 = in 30% of his words
    if planted:
        json.dump(planted, open(os.path.join(HERE, f'mistake_{voice}_{XY}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    shipped = load_head('/home/claude/dikduk-space/full_head.pt')
    s1 = dict(planted); n_drop = n_mis = 0; seen = []   # seen: (id, word, slot j, page's vowel, heard, clear, planted?)
    per = {}
    for r in cal:
        pron = planted.get(r['id'], r['pron']); words = r['text'].split(); pw = pron.split(); tw = r['pron'].split()
        if len(words) != len(pw): continue
        slots, _ = vowel_place(logp(shipped, r), words, S2I, lambda w: w)
        ref = ref_of(pron); flags = compare_vowels(slots, ref)
        if flags: s1[r['id']] = None; n_drop += 1
        per[r['id']] = pw
        for i, (p, t) in enumerate(zip(pw, tw)):
            sl = slots.get(i, []); pv = vowels_of(p); tv = vowels_of(t)
            n_mis += sum(a != b for a, b in zip(pv, tv))
            if len(sl) != len(pv): continue
            for j, (s, c) in enumerate(zip(sl, pv)): seen.append((r['id'], i, j, c, s['heard'], clear(s, 2.0), c != tv[j]))
    # how this reader says each of the page's vowels, by the shipped head: the share of its slots clearly heard as
    # another vowel. A confusion that is his USUAL way (>= half) is a consistent mistake or a voice the head cannot
    # tell from one — safe3 does not learn it; a sometimes-confusion is his voice wobbling, and safe3 learns it.
    n_c = collections.Counter(c for *_, c, h, cl, _ in seen)
    f = collections.Counter((c, h) for *_, c, h, cl, _ in seen if h != c and cl)
    usual = {(c, h) for (c, h), n in f.items() if n_c[c] < 10 or n >= .5 * n_c[c]}
    def relabel(which):
        out = {i: list(p) for i, p in per.items()}; n = n_m = 0
        for rid, i, j, c, h, cl, pl in seen:
            if h != c and cl and which(c, h):
                w = out[rid][i]; k = [q for q, ch in enumerate(w) if ch in VOWELS][j]
                out[rid][i] = w[:k] + h + w[k + 1:]; n += 1; n_m += pl
        return {**planted, **{i: ' '.join(p) for i, p in out.items()}}, n, n_m
    s2, n2, m2 = relabel(lambda c, h: True)
    s3, n3, m3 = relabel(lambda c, h: (c, h) in usual)
    tag = XY if planted else 'none'
    for nm, mp in (('safe1', s1), ('safe2', s2), ('safe3', s3)):
        json.dump(mp, open(os.path.join(HERE, f'{nm}_{voice}_{tag}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    top = ', '.join(f'{c}->{h} {n}/{n_c[c]}' for (c, h), n in f.most_common(5))
    print(f'{voice} {tag}: {len(cal)} calibration pesukim, planted vowels in them {n_mis}; safe1 drops {n_drop} pesukim '
          f'(keeps {len(cal) - n_drop}); safe2 relabels {n2} vowels to what the shipped head clearly hears ({m2} planted); '
          f'safe3 only his usual confusions {sorted(usual)}: {n3} ({m3} planted). Clear confusions: {top}')

def exam(head, voice, mp=None):
    ids = json.load(open(os.path.join(HERE, f'ids_{voice}.json')))
    items = [ROWS[i] for i in ids['test_nv'] if ROWS[i]['voice'] == voice]
    M = json.load(open(mp, encoding='utf-8')) if mp else {}
    model = load_head(head); C = collections.Counter(); heard = collections.Counter()
    for r in items:
        words = r['text'].split(); true = r['pron'].split(); pw = (M.get(r['id']) or r['pron']).split()
        if len(words) != len(pw): continue
        slots, _ = vowel_place(logp(model, r), words, S2I, lambda w: w)
        ref = ref_of(' '.join(pw)); flags = compare_vowels(slots, ref)
        for i, (p, t) in enumerate(zip(pw, true)):
            mistake = vowels_of(p) != vowels_of(t); same = len(slots.get(i, [])) == len(ref[i])
            kind = 'mistake' if mistake else 'other'
            C[kind] += 1; C[kind + ' compared'] += same; C[kind + ' flagged'] += i in flags
            if mistake and same:
                for s, a, b in zip(slots[i], vowels_of(p), vowels_of(t)):
                    if a != b: heard[(s['heard'], clear(s, 2.0))] += 1
    pct = lambda a, b: f'{100 * a / b:.1f}%' if b else '-'
    name = os.path.basename(head)
    if C['mistake']:
        tot = sum(heard.values())
        hs = ', '.join(f'{v}{"" if c else " (unclear)"} {pct(n, tot)}' for (v, c), n in sorted(heard.items(), key=lambda z: -z[1]))
        print(f'{name:34s} {voice}: mistake words caught {C["mistake flagged"]}/{C["mistake"]} = {pct(C["mistake flagged"], C["mistake"])} '
              f'(of those compared {pct(C["mistake flagged"], C["mistake compared"])}); other words flagged {pct(C["other flagged"], C["other"])}; '
              f'at the mistakes the head hears: {hs}')
    else:
        print(f'{name:34s} {voice}: words flagged {C["other flagged"]}/{C["other"]} = {pct(C["other flagged"], C["other"])}')

if __name__ == '__main__':
    if sys.argv[1] == 'maps': maps(sys.argv[2], sys.argv[3])
    else: exam(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
