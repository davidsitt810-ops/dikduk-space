"""Who is who: speaker embeddings (SpeechBrain ECAPA, VoxCeleb) of 45-s snippets from LearnTefillah's folders and of
the voices we already have — the never-heard test voices (Faraj Samra, Be'eri, Shmuelof) above all, so none of them
slips into training by another name. Prints each snippet's nearest known voice and the LearnTefillah groups' mutual
similarity. usage: spk_check.py <snippet dir> <out json>"""
import sys, os, glob, json, subprocess, numpy as np, torch
from speechbrain.inference.speaker import EncoderClassifier
S = '/tmp/claude-0/-home-claude/13b8b04f-7b29-591b-ba7b-28708cdbf43a/scratchpad'
SNIP, OUT = sys.argv[1], sys.argv[2]
torch.set_num_threads(1)
enc = EncoderClassifier.from_hparams(source='speechbrain/spkrec-ecapa-voxceleb', savedir=os.path.join(S, 'hf', 'ecapa'), run_opts={'device': 'cpu'})

def load(path, ss=20, t=45):
    raw = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(ss), '-t', str(t), '-i', path, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768

def emb(x):
    """mean of the unit embeddings of 15-s pieces (the pieces with sound in them)"""
    vs = []
    for a in range(0, max(1, len(x) - 16000 * 5), 16000 * 15):
        seg = x[a:a + 16000 * 15]
        if len(seg) < 16000 * 5 or np.sqrt(np.mean(seg ** 2)) < 0.005: continue
        with torch.no_grad(): v = enc.encode_batch(torch.from_numpy(seg)[None]).squeeze().numpy()
        vs.append(v / np.linalg.norm(v))
    if not vs: return None
    m = np.mean(vs, 0); return m / np.linalg.norm(m)

known = {}
def add(name, path, ss=20):
    e = emb(load(path, ss));
    if e is not None: known.setdefault(name, []).append(e)
for n in ('003', '011', '019'): add('samra (Faraj, NEVER HEARD)', f'{S}/data_samra/{n}.mp3')
add('beeri (NEVER HEARD)', f'{S}/data_beeri/19_psalms.mp3', 30); add('beeri (NEVER HEARD)', f'{S}/data_beeri/19_psalms.mp3', 400)
for n in ('001', '010'): add('shmuelof (NEVER HEARD)', f'{S}/data_shmuelof/hbofPsa_{n}.mp3', 5)
for who in ('benhaim', 'tawil'):
    for n in ('001', '050', '119'):
        p = f'{S}/data_miqra/{who}/{n}.mp3'
        if os.path.exists(p): add(f'miqra {who}', p, 5)
for who in ('riahi', 'daya', 'shrem'):
    for p in sorted(glob.glob(f'{S}/data_miqra/{who}/*.mp3'))[:2]: add(f'miqra {who}', p, 5)
for n in ('001', '050', '119'): add('alouf', f'{S}/space/static/tehillim/tehillim-{n}.mp3', 5)
for f in sorted(glob.glob(os.path.join(SNIP, 'mac_*.wav'))): add(os.path.basename(f)[4:-4] + ' (in training)', f, 0)
lt = {}
for f in sorted(glob.glob(os.path.join(SNIP, '*.wav'))):
    b = os.path.basename(f)[:-4]
    if b.startswith('mac_'): continue
    e = emb(load(f, 0));
    if e is not None: lt[b] = e
K = {k: np.mean(v, 0) / np.linalg.norm(np.mean(v, 0)) for k, v in known.items()}
print('known voices:', {k: len(v) for k, v in known.items()})
# within-voice spread of the known ones, as a yardstick
for k, v in known.items():
    if len(v) > 1: print(f'  same voice, two files: {k:32s} {np.mean([v[i] @ v[j] for i in range(len(v)) for j in range(i + 1, len(v))]):.2f}')
res = {}
print('\nLearnTefillah snippet -> nearest known voices (cosine)')
for b, e in lt.items():
    sims = sorted(((float(e @ K[k]), k) for k in K), reverse=True)
    res[b] = {'nearest': sims[:3]}
    print(f'  {b:10s} ' + '   '.join(f'{k} {s:.2f}' for s, k in sims[:3]))
names = list(lt); M = np.array([[lt[a] @ lt[b] for b in names] for a in names])
print('\nLearnTefillah snippets among themselves (>= .55 shown)')
for i, a in enumerate(names):
    print(f'  {a:10s} ' + ' '.join(f'{names[j]}:{M[i, j]:.2f}' for j in np.argsort(-M[i]) if j != i and M[i, j] >= .55))
json.dump({'nearest': res, 'names': names, 'M': M.round(3).tolist()}, open(OUT, 'w'), indent=1)
