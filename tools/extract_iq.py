"""IqraEval's training set (huggingface.co/datasets/IqraEval/Iqra_train, CC BY-NC 4.0; its authors allowed this free,
non-commercial checker to use it): Arabic read speech (Common Voice) and Quran recitation by many people, with a phoneme
transcript of what was said. Used here as THROAT training data for the Hebrew-letter head, the way extract_eg.py uses
FLEURS Egyptian Arabic: the sentence is mapped letter by letter onto Hebrew letters (ع -> ע, ح -> ח, خ -> כ, ...), the
clip is aligned on the Arabic ear, and layer 12 (int8, as perek_to_manifest.py) goes to feat/<id>.npz with a manifest
line, src "iq". Many more throats than the 410 Egyptian clips, and recitation, which is closer to how a hazzan reads.
Only sentences whose phoneme transcript has as many ع (E) and ح (H) as the writing are kept (the two agree on what was
said), clips with ع or ح first. Written as it goes; ids already in the manifest are skipped.
usage: [IQ_QURAN=n] [IQ_READ=n] [IQ_MAX_SECONDS=s] extract_iq.py <parquet shard> [max_clips_per_kind] [max_plain]"""
import sys, os, json, time, re, subprocess, tempfile
import numpy as np, torch, pyarrow.parquet as pq
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'feat'); os.makedirs(OUT, exist_ok=True)
MAN = os.path.join(HERE, 'manifest.jsonl')
SHARD = sys.argv[1]; MAXN = int(sys.argv[2]) if len(sys.argv) > 2 else 2500; MAXP = int(sys.argv[3]) if len(sys.argv) > 3 else MAXN // 8
torch.set_num_threads(int(os.environ.get('THREADS', '2')))
MID = 'jonatasgrosman/wav2vec2-large-xlsr-53-arabic'
proc = Wav2Vec2Processor.from_pretrained(MID); model = Wav2Vec2ForCTC.from_pretrained(MID).eval()
V = proc.tokenizer.get_vocab(); PAD = proc.tokenizer.pad_token_id
AR = {'א': ['ع', 'ا', 'أ', 'ء'], 'ב': ['ب'], 'ג': ['ج', 'غ'], 'ד': ['د', 'ذ'], 'ה': ['ه'], 'ו': ['و'], 'ז': ['ز'], 'ח': ['ح', 'خ', 'ه'], 'ט': ['ط', 'ت'],
      'י': ['ي'], 'כ': ['ك', 'خ'], 'ל': ['ل'], 'מ': ['م'], 'נ': ['ن'], 'ס': ['س'], 'ע': ['ع', 'ا', 'أ', 'ء'], 'פ': ['ف', 'ب'], 'צ': ['ص', 'س'],
      'ק': ['ق', 'ك'], 'ר': ['ر'], 'ש': ['ش', 'س'], 'ת': ['ت', 'ث']}
AR = {h: [c for c in cs if c in V] for h, cs in AR.items()}

def decode_audio(data):
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f: f.write(data); src = f.name
    try:
        out = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True, timeout=180)
        return np.frombuffer(out.stdout, dtype=np.float32).copy()
    finally: os.unlink(src)

def ctc_align(lp, toks, blank):
    T = lp.shape[0]; S = 2 * len(toks) + 1
    ext = [blank if s % 2 == 0 else toks[(s - 1) // 2] for s in range(S)]
    NEG = -1e30; prev = np.full(S, NEG); prev[0] = lp[0, ext[0]]
    if S > 1: prev[1] = lp[0, ext[1]]
    bp = np.zeros((T, S), dtype=np.int8); ext_a = np.array(ext)
    skip_ok = np.array([s > 1 and ext[s] != blank and ext[s] != ext[s - 2] for s in range(S)])
    for t in range(1, T):
        step = np.concatenate(([NEG], prev[:-1])); skip = np.where(skip_ok, np.concatenate(([NEG, NEG], prev[:-2])), NEG)
        best = prev; b = np.zeros(S, dtype=np.int8)
        m = step > best; best = np.where(m, step, best); b = np.where(m, 1, b)
        m = skip > best; best = np.where(m, skip, best); b = np.where(m, 2, b)
        bp[t] = b; prev = best + lp[t, ext_a]
    s = S - 1
    if S > 1 and prev[S - 2] > prev[S - 1]: s = S - 2
    path = np.zeros(T, dtype=np.int32)
    for t in range(T - 1, -1, -1): path[t] = s; s = int(s) - int(bp[t, s])
    out = [{'f0': -1, 'f1': -1, 'sum': 0.0, 'n': 0} for _ in toks]
    for t in range(T):
        st = int(path[t])
        if st % 2 == 0: continue
        o = out[(st - 1) // 2]
        if o['f0'] < 0: o['f0'] = t
        o['f1'] = t + 1; o['sum'] += float(np.exp(lp[t, ext[st]])); o['n'] += 1
    return [{'f0': o['f0'], 'f1': o['f1'], 'score': (o['sum'] / o['n']) if o['n'] else 0.0} for o in out]

def align_letters(lp, words):
    sets, key, toks, meta = [], {}, [], []
    for i, hl in enumerate(words):
        for k, c in enumerate(hl):
            alts = AR.get(c)
            if c == 'ה' and k == len(hl) - 1: alts = None
            if not alts: meta.append((i, k, c, None)); continue
            kk = ','.join(alts)
            if kk not in key: key[kk] = len(sets); sets.append(alts)
            toks.append(lp.shape[1] + key[kk]); meta.append((i, k, c, alts))
    if not toks: return []
    cols = [np.logaddexp.reduce(lp[:, [V[c] for c in alts]], axis=1) for alts in sets]
    al = ctc_align(np.concatenate([lp, np.stack(cols, 1)], 1), toks, PAD)
    out, j = [], 0
    for (i, k, c, alts) in meta:
        if alts is None: out.append({'w': i, 'k': k, 'c': c, 'f0': -1, 'f1': -1, 'p': 0, 'heard': None}); continue
        a = al[j]; j += 1
        if a['f0'] < 0: out.append({'w': i, 'k': k, 'c': c, 'f0': -1, 'f1': -1, 'p': 0, 'heard': None}); continue
        mass = {m: float(np.exp(lp[a['f0']:a['f1'], V[m]]).sum()) for m in alts}
        out.append({'w': i, 'k': k, 'c': c, 'f0': a['f0'], 'f1': a['f1'], 'p': round(a['score'], 3), 'heard': max(mass, key=mass.get), 'mass': {m: round(v, 3) for m, v in mass.items()}})
    return out

A2H = {'ا': 'א', 'أ': 'א', 'إ': 'א', 'آ': 'א', 'ٱ': 'א', 'ء': 'א', 'ئ': 'א', 'ؤ': 'א', 'ب': 'ב', 'ت': 'ת', 'ث': 'ת', 'ج': 'ג', 'ح': 'ח', 'خ': 'כ',
       'د': 'ד', 'ذ': 'ד', 'ر': 'ר', 'ز': 'ז', 'س': 'ס', 'ش': 'ש', 'ص': 'צ', 'ض': 'ד', 'ط': 'ט', 'ع': 'ע', 'غ': 'ג', 'ف': 'פ', 'ق': 'ק', 'ك': 'כ',
       'ل': 'ל', 'م': 'מ', 'ن': 'נ', 'ه': 'ה', 'و': 'ו', 'ي': 'י', 'ى': 'י'}
SUN = set('تثدذرزسشصضطظلن')
DIAC = re.compile('[ً-ْٰـۖ-ۭ]')
def map_word(w, first):
    w = DIAC.sub('', w)
    w = ''.join(c for c in w if c in A2H or c == 'ة' or c == 'ظ')
    if 'ظ' in w or not w: return None
    if w[0] in 'اٱ' and w[1:2] == 'ل' and len(w) > 2:
        if w[2] in SUN: w = w[0] + w[2:]           # the lam of al- assimilates before a sun letter
        if not first: w = w[1:]                       # inside a sentence the alef of al- is not said (wasl)
    elif w[0] == 'ٱ' and not first: w = w[1:]
    if w.endswith('ة'): w = w[:-1]                   # ta marbuta: a vowel at pause
    out = ''.join(A2H.get(c, '') for c in w)
    return out or None

# budgets per kind (a resumed run counts what it already wrote): recited verses with ע/ח, read sentences with ע/ח, and
# a few sentences without either (so "no throat sound" is heard in these voices too)
BUD = {'quran': int(os.environ.get('IQ_QURAN', MAXN)), 'read': int(os.environ.get('IQ_READ', MAXN)), 'plain': MAXP}
is_quran = lambda s: len(re.findall('[ً-ْ]', s)) >= .4 * len(re.findall('[ء-ي]', s))   # recited verses come fully pointed; read sentences hardly
kind_of = lambda s: ('quran' if is_quran(s) else 'read') if ('ع' in s or 'ح' in s) else 'plain'
done = set(); n = {'quran': 0, 'read': 0, 'plain': 0}
if os.path.exists(MAN):
    for l in open(MAN, encoding='utf-8'):
        if '"src": "iq"' in l:
            try: d = json.loads(l)
            except Exception: continue
            done.add(d['id']); n[kind_of(d['arabic'])] += 1
t_start = time.time(); n_skip = 0
MAXS = float(os.environ.get('IQ_MAX_SECONDS', '0'))   # a planned stop after this long (a later run goes on: it counts what is written)
pf = pq.ParquetFile(SHARD); stop = False
for batch in pf.iter_batches(batch_size=64, columns=['id', 'sentence', 'phoneme_ref', 'audio']):
    if stop: break
    for r in batch.to_pylist():
        if MAXS and time.time() - t_start > MAXS: print(f'planned stop after {int(MAXS)} s (IQ_MAX_SECONDS)', flush=True); stop = True; break
        cid = 'iq_' + r['id']
        if cid in done: continue
        ph = (r['phoneme_ref'] or '').split(); s = r['sentence'] or ''
        nE = sum(1 for p in ph if 'E' in p); nH = sum(1 for p in ph if 'H' in p)   # a doubled one ('EE') is one letter said long
        if nE != s.count('ع') or nH != s.count('ح'): n_skip += 1; continue
        k = kind_of(s)
        if n[k] >= BUD[k]: continue
        toks = s.split(); words = [m for m in (map_word(w, i == 0) for i, w in enumerate(toks)) if m]
        if len(words) < 2 or len(words) < len(toks) - 1: continue
        x = decode_audio(r['audio']['bytes'])
        if x.shape[0] < 1.5 * 16000 or x.shape[0] > 15 * 16000: continue
        inp = proc(x, sampling_rate=16000, return_tensors='pt')
        with torch.inference_mode(): o = model(inp.input_values, output_hidden_states=True)
        lp = torch.log_softmax(o.logits[0], -1).numpy(); h = o.hidden_states[12][0].numpy()
        al = align_letters(lp, words); scores = [a['p'] for a in al if a['f0'] >= 0]
        sc = np.maximum(np.abs(h).max(1), 1e-6)
        np.savez(os.path.join(OUT, cid + '.npz'), lp=lp.astype(np.float16), h12q=np.round(h / sc[:, None] * 127).astype(np.int8), h12s=sc.astype(np.float16))
        meta = {'id': cid, 'src': 'iq', 'pid': 'iq', 'rec': r['id'], 'line': 0, 'text': ' '.join(words), 'dur': round(x.shape[0] / 16000, 3), 'T': int(lp.shape[0]),
                'spf': x.shape[0] / 16000 / lp.shape[0], 'skel': round(float(np.mean(scores)), 3) if scores else 0.0,
                'good': round(float(np.mean([v > .3 for v in scores])), 3) if scores else 0.0, 'align': al, 'arabic': s,
                'kind': 'quran' if is_quran(s) else 'read'}
        with open(MAN, 'a', encoding='utf-8') as f: f.write(json.dumps(meta, ensure_ascii=False) + '\n')
        n[k] += 1
        if sum(n.values()) % 100 == 0: print(f'iq {n}, {n_skip} transcripts disagreed [{int(time.time() - t_start)} s]', flush=True)
    if all(n[k] >= BUD[k] for k in n): break
print(f'done: {n} from {os.path.basename(SHARD)}, {n_skip} transcripts disagreed [{int(time.time() - t_start)} s]', flush=True)
