"""Heads raised on the archive AND on Rabbi Alouf's Tehillim, on the frozen hidden layer 12 of the Arabic-letter model.
  mode 'letters': targets = Hebrew letters (22 + space); data = archive lines + Alouf pesukim (Alouf oversampled);
  mode 'full':    targets = the pronounced sequence, letters + vowel classes A E I O U (+ space); data = Alouf only
                  (the archive has no nikud). The vowel ear.
Held out: 10% of pizmonim and 10% of perakim. Exams: letter error rate; at every ע/א and ח/כ of held-out hazzan
lines and held-out Alouf pesukim, which letter the head prefers; Israeli read speech (ע said like א, ח like כ); for
'full', the vowel confusion on held-out Alouf (each vowel offered all five classes).
usage: train_head2.py letters|full EPOCHS [warm-start .pt] [alouf_weight]   (EPOCHS 0: only the exams, of the warm-start head)"""
import json, os, sys, time, random, numpy as np, torch, torch.nn as nn
HERE = os.path.dirname(os.path.abspath(__file__))
torch.manual_seed(0); random.seed(0); np.random.seed(0); torch.set_num_threads(2)
MODE = sys.argv[1]; EPOCHS = int(sys.argv[2]); WARM = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != '-' else None
AL_W = int(sys.argv[4]) if len(sys.argv) > 4 else 3
LR = float(os.environ.get('HEAD_LR', '1e-3')); MAXN = int(os.environ.get('HEAD_MAX', '0')); HEAD_OUT = os.environ.get('HEAD_OUT')
LETTERS = list('אבגדהוזחטיכלמנסעפצקרשת'); VOWELS = list('AEIOU')
SYM = ['<b>', ' '] + LETTERS + (VOWELS if MODE == 'full' else []); S2I = {s: i for i, s in enumerate(SYM)}
rows = [json.loads(l) for l in open(os.path.join(HERE, 'manifest.jsonl'), encoding='utf-8')]
rows += [json.loads(l) for l in open(os.path.join(HERE, 'manifest_alouf.jsonl'), encoding='utf-8')] if os.path.exists(os.path.join(HERE, 'manifest_alouf.jsonl')) else []
rows += [json.loads(l) for l in open(os.path.join(HERE, 'manifest_voices.jsonl'), encoding='utf-8')] if os.path.exists(os.path.join(HERE, 'manifest_voices.jsonl')) else []   # readers the heads never heard (Be'eri, Ben Haim, Tawil: voice_register / perek_to_manifest)
ar = [r for r in rows if r['src'] == 'ar' and r['skel'] >= .35 and r['good'] >= .5 and r['T'] >= 20]
al = [r for r in rows if r['src'] == 'al' and r['skel'] >= .5 and r['T'] >= 20]
il = [r for r in rows if r['src'] == 'il']
eg = [r for r in rows if r['src'] == 'eg' and r['skel'] >= .4 and r['T'] >= 20]   # Egyptian Arabic read speech mapped to Hebrew letters (HEAD_EG=1 to train on it)
EG_W = int(os.environ.get('HEAD_EG', '0'))
il2 = [r for r in rows if r['src'] == 'il2' and r['skel'] >= .3 and r['T'] >= 20]   # Israeli read speech, ayin/het written as alef/khaf (HEAD_IL=1 to train on it)
IL_W = int(os.environ.get('HEAD_IL', '0')); il2_hold = set(r['rec'] for r in il2[::10])
nv = [r for r in rows if r['src'] == 'nv' and r['skel'] >= .5 and r['T'] >= 20]   # new voices, pointed Tehillim (HEAD_NV=k: k copies in training)
NV_W = int(os.environ.get('HEAD_NV', '0'))
if MAXN: ar = ar[:MAXN]; il = il[:MAXN // 4]   # smoke tests
pids = sorted(set(r['pid'] for r in ar)); random.shuffle(pids); hold = set(pids[:max(1, len(pids) // 10)])
pers = sorted(set(r['pid'] for r in al), key=lambda s: int(s[2:])); random.shuffle(pers); hold_al = set(pers[:max(1, len(pers) // 10)])
eg_hold = set(r['rec'] for r in eg[::10])   # every 10th Egyptian clip held out for its own exam
nvp = sorted(set(r['pid'] for r in nv)); random.shuffle(nvp); hold_nv = set(nvp[:max(1, len(nvp) // 10)]) if nvp else set()   # 10% of their perakim (the exams' perakim are never in the manifest)
# the new voices never train on the TEXT of Rabbi Alouf's held-out perakim either, so his held-out exams (here and in
# exam_alouf.py) stay unseen in voice AND text
al_held_text = {int(p[2:]) for p in hold_al}
NV_SKIP = set(v for v in os.environ.get('HEAD_NV_SKIP', '').split(',') if v)   # leave a voice out entirely (does the head help a voice it never heard?)
nv_train = [r for r in nv if r['pid'] not in hold_nv and int(r['pid'][len(r['voice']):]) not in al_held_text and r['voice'] not in NV_SKIP]
# calibration test: only K pesukim of one voice (HEAD_NV_KEEP=voice:K, seeded) — can a reader's first K pesukim teach
# the head his voice? — and Rabbi Alouf subsampled to anchor it (HEAD_AL_SUB=n)
if os.environ.get('HEAD_NV_KEEP'):
    kv, kk = os.environ['HEAD_NV_KEEP'].split(':'); pool = [r for r in nv_train if r['voice'] == kv]; random.Random(1).shuffle(pool); nv_train = pool[:int(kk)]
al_train = [r for r in al if r['pid'] not in hold_al]
if os.environ.get('HEAD_AL_SUB'): random.Random(2).shuffle(al_train); al_train = al_train[:int(os.environ['HEAD_AL_SUB'])]
if MODE == 'letters':
    train = [r for r in ar if r['pid'] not in hold] + [r for r in al if r['pid'] not in hold_al] * AL_W + [r for r in eg if r['rec'] not in eg_hold] * EG_W + [r for r in il2 if r['rec'] not in il2_hold] * IL_W + nv_train * NV_W
else:
    train = al_train * int(os.environ.get('HEAD_AL_FULL', '1')) + nv_train * NV_W   # HEAD_AL_FULL=k: Rabbi Alouf k times
test_ar = [r for r in ar if r['pid'] in hold]; test_al = [r for r in al if r['pid'] in hold_al]; test_nv = [r for r in nv if r['pid'] in hold_nv]
print(f'mode {MODE}: archive lines {len(ar)}, Alouf pesukim {len(al)} (weight {AL_W}), israeli {len(il)}, egyptian {len(eg)} (weight {EG_W}), israeli train {len(il2)} (weight {IL_W}); train items {len(train)}; held out {len(test_ar)} hazzan lines of {len(hold)} pizmonim, {len(test_al)} Alouf pesukim of {len(hold_al)} perakim; new voices {len(nv)} (weight {NV_W}; {len(nv_train)} in training, none from his held-out perakim {sorted(al_held_text)}), held out {len(test_nv)} of {len(hold_nv)} perakim')

def feats(r):
    d = np.load(os.path.join(HERE, 'feat', r['id'] + '.npz'))
    if 'h12q' in d.files:   # int8 with a scale per frame (perek_to_manifest.py)
        return torch.from_numpy(d['h12q'].astype(np.float32) * (d['h12s'].astype(np.float32)[:, None] / 127))
    return torch.from_numpy(d['h12'].astype(np.float32))
def target(r):
    src = r['pron'] if MODE == 'full' else r['text']
    out = [S2I[c] for c in src if c in S2I]
    return out
class Head(nn.Module):
    def __init__(self, d_in=1024, h=384, n=len(SYM), k=5, layers=3):
        super().__init__(); self.inp = nn.Sequential(nn.LayerNorm(d_in), nn.Linear(d_in, h), nn.GELU(), nn.Dropout(0.15))
        self.convs = nn.ModuleList([nn.Sequential(nn.Conv1d(h, h, k, padding=k // 2), nn.GELU(), nn.Dropout(0.15)) for _ in range(layers)])
        self.norms = nn.ModuleList([nn.LayerNorm(h) for _ in range(layers)]); self.out = nn.Linear(h, n)
    def forward(self, x):
        y = self.inp(x)
        for conv, norm in zip(self.convs, self.norms): y = norm(y + conv(y.transpose(1, 2)).transpose(1, 2))
        return self.out(y)
model = Head()
if WARM:
    ck = torch.load(WARM, map_location='cpu'); st = ck['state']
    if len(ck['sym']) != len(SYM):   # a letters head warm-starting the full head: keep all but the output layer
        st = {k: v for k, v in st.items() if not k.startswith('out.')}
    model.load_state_dict(st, strict=False); print('warm start from', WARM)
opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-2); ctc = nn.CTCLoss(blank=0, zero_infinity=True)
# features are read from disk per batch (6,000 items would not fit in RAM); the list keeps the repeats
data = [(r, target(r)) for r in train]; data = [(r, y) for r, y in data if len(y) and r['T'] > 2 * len(y)]
print('train clips', len(data), 'frames', sum(r['T'] for r, _ in data), flush=True)
def batches(items, bs=12):
    items = sorted(items, key=lambda z: z[0]['T']); out = [items[i:i + bs] for i in range(0, len(items), bs)]; random.shuffle(out); return out
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=LR, total_steps=EPOCHS * (len(data) // 12 + 1)) if EPOCHS else None   # EPOCHS 0: the warm head's exams only
t0 = time.time()
for ep in range(EPOCHS):
    model.train(); tot = 0; nb = 0
    for b in batches(data):
        b = [(feats(r), y) for r, y in b]
        xs = nn.utils.rnn.pad_sequence([x for x, _ in b], batch_first=True); xl = torch.tensor([x.shape[0] for x, _ in b])
        ys = torch.cat([torch.tensor(y) for _, y in b]); yl = torch.tensor([len(y) for _, y in b])
        lp = torch.log_softmax(model(xs), -1).transpose(0, 1)
        loss = ctc(lp, ys, xl, yl); opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 5.0); opt.step(); sched.step()
        tot += loss.item(); nb += 1
    print(f'epoch {ep + 1}/{EPOCHS} loss {tot / nb:.3f} {int(time.time() - t0)} s', flush=True)
    if HEAD_OUT: torch.save({'state': model.state_dict(), 'sym': SYM, 'layer': 'h12', 'd_in': 1024, 'mode': MODE, 'epoch': ep + 1}, HEAD_OUT + '.part')   # kept if a run is stopped

# ---------------- exams
sys.path.insert(0, os.path.join(HERE, '..', 'tehillim'))
from ctcutil import ctc_align, with_virtual_columns
model.eval()
def greedy(lp):
    ids = lp.argmax(-1).tolist(); out, prev = [], -1
    for i in ids:
        if i != prev and i != 0: out.append(SYM[i])
        prev = i
    return ''.join(out)
def ler(a, b):
    import difflib; return 1 - difflib.SequenceMatcher(None, a, b).ratio()
def judge(lp, src, pairs):
    """align the sequence with each member of a pair offered; -> [(symbol, winner, mass)]"""
    lp = lp.numpy(); toks, meta, alt_sets, key = [], [], [], {}
    for c in src:
        if c not in S2I: continue
        pair = next((p for p in pairs if c in p), None)
        if pair:
            k = ''.join(pair)
            if k not in key: key[k] = len(alt_sets); alt_sets.append(list(pair))
            toks.append(('v', key[k])); meta.append((c, pair))
        else: toks.append(('s', S2I[c])); meta.append((c, None))
    lp2, ids = with_virtual_columns(lp, alt_sets, S2I)
    tk = [ids[t[1]] if t[0] == 'v' else t[1] for t in toks]
    al = ctc_align(lp2, tk, 0, band=None if lp2.shape[0] * (2 * len(tk) + 1) < 150_000_000 else max(1500, int(len(tk) * .25)))
    out = []
    for (c, pair), a in zip(meta, al):
        if not pair or a['f0'] < 0: continue
        mass = {m: float(np.exp(lp[a['f0']:a['f1'], S2I[m]]).sum()) for m in pair}
        out.append((c, max(mass, key=mass.get), mass))
    return out
def exam(name, items, src_key, pairs):
    conf = {}; errs = []
    with torch.no_grad():
        for r in items:
            lp = torch.log_softmax(model(feats(r)[None]), -1)[0]
            src = r[src_key]; errs.append(ler(greedy(lp), ''.join(c for c in src if c in S2I)))
            for c, win, _ in judge(lp, src, pairs): conf[(c, win)] = conf.get((c, win), 0) + 1
    print(f'\n{name}: {len(items)} items, symbol error rate {100 * np.mean(errs):.0f}%')
    for pair in pairs:
        for c in pair:
            tot = sum(conf.get((c, o), 0) for o in pair)
            if tot: print(f'   {c} heard as: ' + ', '.join(f'{o} {100 * conf.get((c, o), 0) / tot:.0f}%' for o in pair) + f'  (n={tot})')
def exam_vowel_ear(items, title='held-out Alouf'):
    """the vowel ear as the server will use it: the optional-slot template (no nikud) aligned on the head, the vowels
       found per word compared with the nikud's; a correct reader (Rabbi Alouf) should raise no flags"""
    sys.path.insert(0, os.path.join(HERE, '..', 'space'))
    from vowels import vowel_place, compare_vowels, clear
    n_words = n_same = n_flag = n_clear = n_clear_ok = 0; conf = {}
    with torch.no_grad():
        for r in items:
            lp = torch.log_softmax(model(feats(r)[None]), -1)[0].numpy()
            words = r['text'].split(); pw = r['pron'].split()
            if len(words) != len(pw): continue
            slots, _ = vowel_place(lp, words, S2I, lambda w: w)
            ref = {i: [{'heard': c} for c in p if c in VOWELS] for i, p in enumerate(pw)}
            for i, w in enumerate(words):
                n_words += 1; sl = slots.get(i, [])
                if len(sl) == len(ref[i]):
                    n_same += 1
                    for s_, e in zip(sl, ref[i]):
                        conf[(e['heard'], s_['heard'])] = conf.get((e['heard'], s_['heard']), 0) + 1
                        if clear(s_, 2.0): n_clear += 1; n_clear_ok += (s_['heard'] == e['heard'])
            n_flag += sum(len(v) for v in compare_vowels(slots, ref).values())
    print(f'\nvowel ear on {title}: {n_words} words, vowel count matched the nikud in {100 * n_same / max(1, n_words):.0f}%; '
          f'clear slots {n_clear} of which right {100 * n_clear_ok / max(1, n_clear):.0f}%; words flagged (false alarms on a correct reader) {n_flag} = {100 * n_flag / max(1, n_words):.1f}%')
    for e in VOWELS:
        tot = sum(conf.get((e, o), 0) for o in VOWELS)
        if tot: print(f'   nikud {e} -> found: ' + ', '.join(f'{o} {100 * conf.get((e, o), 0) / tot:.0f}%' for o in VOWELS) + f'  (n={tot})')
QUICK = bool(os.environ.get('HEAD_QUICK'))   # only the vowel ear's exams (Alouf + the new voices)
if not QUICK: exam('held-out hazzan lines', test_ar, 'text', [('ע', 'א'), ('ח', 'כ')])
if not QUICK: exam('held-out Alouf pesukim', test_al, 'pron' if MODE == 'full' else 'text', [('ע', 'א'), ('ח', 'כ')] + ([('A', 'E', 'I', 'O', 'U')] if MODE == 'full' else []))
if not QUICK: exam('Israeli read speech (ע said like א, ח like כ)', il, 'text', [('ע', 'א'), ('ח', 'כ')])
if eg and not QUICK: exam('held-out Egyptian Arabic clips (ع ح said from the throat)', [r for r in eg if r['rec'] in eg_hold], 'text', [('ע', 'א'), ('ח', 'כ')])
for vname in sorted(set(r['voice'] for r in test_nv)) if not QUICK else []:
    exam(f'held-out {vname} pesukim', [r for r in test_nv if r['voice'] == vname], 'pron' if MODE == 'full' else 'text', [('ע', 'א'), ('ח', 'כ')] + ([('A', 'E', 'I', 'O', 'U')] if MODE == 'full' else []))
if MODE == 'full':
    exam_vowel_ear(test_al)
    for vname in sorted(set(r['voice'] for r in test_nv)): exam_vowel_ear([r for r in test_nv if r['voice'] == vname], f'held-out {vname}')
out = HEAD_OUT or os.path.join(HERE, '..', 'space', 'letter_head.pt' if MODE == 'letters' else 'full_head.pt')
if not EPOCHS: sys.exit(0)
torch.save({'state': model.state_dict(), 'sym': SYM, 'layer': 'h12', 'd_in': 1024, 'mode': MODE, 'n_train': len(train)}, out)
print('saved', out, os.path.getsize(out) // 1024, 'KB')
