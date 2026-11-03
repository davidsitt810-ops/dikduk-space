"""Are LearnTefillah's haftarah reader, Sion Levy and the Shir HaShirim reader really new? Their snippets against one
recording of every hazzan in the pizmonim.com archive's sections (data_sections/catalog.json), same ECAPA embeddings
as spk_check.py. usage: spk_archive.py <snippet dir>"""
import sys, os, glob, json, re, subprocess, collections, numpy as np, torch
from speechbrain.inference.speaker import EncoderClassifier
S = '/tmp/claude-0/-home-claude/13b8b04f-7b29-591b-ba7b-28708cdbf43a/scratchpad'; SNIP = sys.argv[1]
torch.set_num_threads(1)
enc = EncoderClassifier.from_hparams(source='speechbrain/spkrec-ecapa-voxceleb', savedir=os.path.join(S, 'hf', 'ecapa'), run_opts={'device': 'cpu'})
def load(path, ss=60, t=45):
    raw = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(ss), '-t', str(t), '-i', path, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768
def emb(x):
    vs = []
    for a in range(0, max(1, len(x) - 16000 * 5), 16000 * 15):
        seg = x[a:a + 16000 * 15]
        if len(seg) < 16000 * 5 or np.sqrt(np.mean(seg ** 2)) < 0.005: continue
        with torch.no_grad(): v = enc.encode_batch(torch.from_numpy(seg)[None]).squeeze().numpy()
        vs.append(v / np.linalg.norm(v))
    if not vs: return None
    m = np.mean(vs, 0); return m / np.linalg.norm(m)
cat = json.load(open(os.path.join(S, 'data_sections', 'catalog.json'), encoding='utf-8'))
by = collections.defaultdict(list)
for r in cat.values():
    f = r.get('file')
    if not f or not os.path.exists(f) or os.path.getsize(f) < 2e6: continue
    who = re.split(r'\s*[-:–]\s*', r['label'])[0].strip()
    by[who].append(f)
known = {}
for who, fs in sorted(by.items()):
    es = [e for e in (emb(load(f)) for f in fs[:2]) if e is not None]
    if es: m = np.mean(es, 0); known[who] = m / np.linalg.norm(m)
print(len(known), 'archive hazzanim:', ', '.join(known))
groups = {'haftarot (LT)': 'haf', 'Sion Levy (LT)': 'levy', 'Shir HaShirim (LT)': 'shir', 'Torah aliyot (LT, tagged Abe Zami)': 'par[bkvdr]', 'Tawil books (LT)': '(ruth|eikha|koh|mish|iyov|esttw)'}
snips = {os.path.basename(f)[:-4]: f for f in glob.glob(os.path.join(SNIP, '*.wav'))}
for g, pat in groups.items():
    es = [e for e in (emb(load(f, 0)) for b, f in sorted(snips.items()) if re.match(pat, b) and b not in ('parpes', 'parshav')) if e is not None]
    m = np.mean(es, 0); m /= np.linalg.norm(m)
    sims = sorted(((float(m @ k), w) for w, k in known.items()), reverse=True)[:4]
    print(f'{g:36s} ' + '   '.join(f'{w} {s:.2f}' for s, w in sims))
