"""A reader's perakim -> training items for the heads, with ONE ear: the Arabic-letter model over the perek (letter
log-probs + hidden layer 12, in 20 s windows with 1 s context), the perek's letters aligned LOCALLY on it (free
start and end, so an announcement or the next perek is not forced onto the text), the pesukim cut from the letters'
frames, and per pasuk an item in the shape alouf_to_manifest.py writes (space_test/feat/<id>.npz + a manifest line:
letters, the pronounced sequence with vowel classes, the letters' frames). Layer 12 is stored as int8 with a scale
per frame (h12q, h12s) — half the disk of fp16. The exams' held-out perakim (TEST) are never written.
usage: perek_to_manifest.py <tag> <job> [<job> ...]
  job = path:perek            (one perek per file)
  job = path:perek:t0-t1      (a stretch of a longer file, in seconds — Be'eri's book)
  ... :text=<file>:book=<tag> (this job's own text and book tag instead of TEXT and BOOK: a haftarah or an aliyah,
                               whose text keeps only the verses read, the others empty, so one run does many files)
appends to space_test/manifest_voices.jsonl (resumes: a perek with items already written is skipped)"""
import sys, os, json, time, subprocess
import numpy as np, torch
S = '/tmp/claude-0/-home-claude/13b8b04f-7b29-591b-ba7b-28708cdbf43a/scratchpad'
sys.path.insert(0, os.path.join(S, 'tehillim')); sys.path.insert(0, os.path.join(S, 'voices'))
if os.environ.get('DK_LAB_CODE'): sys.path.insert(0, os.environ['DK_LAB_CODE'])   # nikud.py, ctcutil.py, ctclocal.py elsewhere (the Mac night batch)
from nikud import parse_verse, clean_verse
from ctcutil import with_virtual_columns
from ctclocal import ctc_local
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
torch.set_num_threads(int(os.environ.get('THREADS', '2')))
TAG = sys.argv[1]; JOBS = sys.argv[2:]
TEST = {3, 7, 11, 15, 19, 23, 27, 31, 35, 39, 43, 47, 115, 123, 127, 131, 135, 143, 147}
FEAT = os.environ.get('DK_LAB_FEAT') or os.path.join(S, 'space_test', 'feat'); MAN = os.environ.get('DK_LAB_MAN') or os.path.join(S, 'space_test', 'manifest_voices.jsonl')
T_ALL = json.load(open(os.environ.get('TEXT') or os.path.join(S, 'tehillim', 'tehillim_nikud.json'), encoding='utf-8'))
BOOK = os.environ.get('BOOK', '')   # another book (TEXT = its {chapter: [verses]}): ids <voice>_<book><chapter>; the Tehillim exam perakim (TEST) only matter for Tehillim
AR_ID = 'jonatasgrosman/wav2vec2-large-xlsr-53-arabic'
PROC = Wav2Vec2Processor.from_pretrained(AR_ID); AR = Wav2Vec2ForCTC.from_pretrained(AR_ID).eval()
DEV = os.environ.get('DK_DEVICE', 'cpu'); AR.to(DEV)   # DK_DEVICE=mps: the Mac's GPU (the night batch)
V = PROC.tokenizer.get_vocab(); PAD = PROC.tokenizer.pad_token_id; NV = len(V)
ALT = {'א': ['ع', 'ا', 'أ', 'ء', 'إ', 'ئ', 'ؤ'], 'ב': ['ب'], 'ג': ['ج', 'غ'], 'ד': ['د', 'ذ'], 'ה': ['ه'], 'ו': ['و'], 'ז': ['ز'], 'ח': ['ح', 'خ', 'ه'], 'ט': ['ط', 'ت'],
       'י': ['ي'], 'כ': ['ك', 'خ'], 'ל': ['ل'], 'מ': ['م'], 'נ': ['ن'], 'ס': ['س'], 'ע': ['ع', 'ا', 'أ', 'ء', 'إ', 'ئ', 'ؤ'], 'פ': ['ف', 'ب'], 'צ': ['ص', 'س'],
       'ק': ['ق', 'ك'], 'ר': ['ر'], 'ש': ['ش', 'س'], 'ת': ['ت', 'ث']}
ALT = {h: [c for c in cs if c in V] for h, cs in ALT.items()}
# The model writes Arabic vowels too (the harakat, long vowels as ا و ي ى, the word bar |). The text path has no
# such tokens: it can only stay in blank there, while the free states took each frame's best symbol — so on a clear
# reader (Be'eri: every vowel written out) the free states won the whole perek and the text was squeezed into its
# last seconds (0 of 9 pesukim kept in perek 4). The blank now carries the mass of every vowel-like token.
BLANKISH = [V[c] for c in ['<pad>', '<s>', '</s>', '<unk>', '|', '-', 'ـ', 'ا', 'آ', 'ى', 'ة', 'و', 'ي', 'ً', 'ٌ', 'ٍ', 'َ', 'ُ', 'ِ', 'ّ', 'ْ'] if c in V]
def blank_merge(lp2):
    lp2 = lp2.copy(); lp2[:, PAD] = np.logaddexp.reduce(lp2[:, BLANKISH], axis=1); return lp2
have = set()
if os.path.exists(MAN):
    for l in open(MAN, encoding='utf-8'):
        try: have.add(json.loads(l)['pid'])
        except Exception: pass

def decode(path, t0=None, t1=None):
    cmd = ['ffmpeg', '-v', 'error'] + (['-ss', f'{t0:.3f}'] if t0 is not None else []) + ['-i', path] + (['-t', f'{t1 - t0:.3f}'] if t0 is not None else []) + ['-ac', '1', '-ar', '16000', '-f', 'f32le', '-']
    x = np.frombuffer(subprocess.run(cmd, capture_output=True, timeout=1800).stdout, dtype=np.float32).copy()
    return degrade(x, path) if DG else x

# DEGRADE=phone|noisy|room,snr=<dB>,kbps=<n> (LAB_NOTES §39, as exam_voice.py's): the whole perek as a phone in a room
# would send it, before the ear hears it — a student's enrollment made on his phone. Seeded by the file's name.
DG = {}
if os.environ.get('DEGRADE'):
    for part in {'phone': 'room,snr=20,kbps=24', 'noisy': 'room,snr=10,kbps=24'}.get(os.environ['DEGRADE'], os.environ['DEGRADE']).split(','):
        k, _, v = part.partition('='); DG[k] = float(v) if v else 1.0
    assert set(DG) <= {'room', 'snr', 'kbps'}, os.environ['DEGRADE']
def degrade(x, path, sr=16000):
    import zlib
    x = x * 32768.0; y = x.copy()
    if DG.get('room'):
        for ms, g in ((11, .35), (23, .22), (37, .14), (53, .08)):   # early reflections of a small room
            d = int(sr * ms / 1000); y[d:] += g * x[:-d]
    if 'snr' in DG:
        n = len(y); rng = np.random.default_rng(zlib.crc32(os.path.basename(path).encode())); f = np.fft.rfftfreq(n, 1 / sr)
        spec = rng.normal(size=len(f)) + 1j * rng.normal(size=len(f)); spec[0] = 0; spec[1:] /= np.sqrt(f[1:])   # pink: power 1/f
        noise = np.fft.irfft(spec, n).astype(np.float32)
        e = (y[: n // 320 * 320].reshape(-1, 320) ** 2).mean(1); act = e[e >= .2 * np.percentile(e, 95)]   # the singing's own level
        y = y + noise * np.sqrt(float(act.mean()) / max(1e-9, float((noise ** 2).mean())) / 10 ** (DG['snr'] / 10))
    y = y * min(1.0, 30000 / max(1.0, float(np.abs(y).max())))
    raw = np.clip(y, -32768, 32767).astype(np.int16).tobytes()
    if 'kbps' in DG:
        ogg = subprocess.run(['ffmpeg', '-v', 'error', '-f', 's16le', '-ar', str(sr), '-ac', '1', '-i', 'pipe:0', '-c:a', 'libopus', '-b:a', f'{int(DG["kbps"])}k', '-f', 'ogg', 'pipe:1'],
                             input=raw, capture_output=True, timeout=1800).stdout
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', 'pipe:0', '-ac', '1', '-ar', str(sr), '-f', 's16le', 'pipe:1'], input=ogg, capture_output=True, timeout=1800).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

def ear(x, win=20.0, pad=1.0):
    """the Arabic ear over the whole stretch: log-probs and layer 12, the windows' context dropped"""
    SR = 16000; n = x.shape[0]; lps, hs = [], []; t0 = 0.0
    while True:
        a = max(0.0, t0 - pad); b = min(n / SR, t0 + win + pad); seg = x[int(a * SR):int(b * SR)]
        if seg.shape[0] < SR * 0.5: break
        inp = PROC(seg, sampling_rate=SR, return_tensors='pt')
        with torch.inference_mode(): o = AR(inp.input_values.to(DEV), output_hidden_states=True)
        lp = torch.log_softmax(o.logits[0].float(), -1).cpu().numpy(); h = o.hidden_states[12][0].float().cpu().numpy()
        spf = (b - a) / lp.shape[0]; f0 = int(round((t0 - a) / spf)); f1 = int(round((min(t0 + win, n / SR) - a) / spf))
        lps.append(lp[f0:f1]); hs.append(h[f0:f1])
        if t0 + win >= n / SR: break
        t0 += win
    lp = np.concatenate(lps); return lp, np.concatenate(hs), (n / SR) / lp.shape[0]

t_start = time.time(); n_items = 0; TEXTS = {}; EAR_LAST = [None, None, None]
for job in JOBS:
    try:
        parts = job.split(':'); path, n = parts[0], int(parts[1]); rng = None; T_JOB = T_ALL; bk = BOOK
        for extra in parts[2:]:
            if extra.startswith('text='):
                if extra[5:] not in TEXTS: TEXTS[extra[5:]] = json.load(open(extra[5:], encoding='utf-8'))
                T_JOB = TEXTS[extra[5:]]
            elif extra.startswith('book='): bk = extra[5:]
            elif extra: rng = extra
        pid = f'{TAG}_{bk}{n}' if bk else f'{TAG}{n}'
        if (n in TEST and not bk) or pid in have or str(n) not in T_JOB: continue
        if not any(v.strip() for v in T_JOB[str(n)]): continue
        t0, t1 = (float(v) for v in rng.split('-')) if rng else (None, None)
        if EAR_LAST[0] != (path, t0, t1):                                    # the same stretch as the job before (a haftarah's next chapter): heard once
            x = decode(path, t0, t1)
            EAR_LAST[:] = [(path, t0, t1), x, ear(x) if x.shape[0] >= 16000 else None]
        x = EAR_LAST[1]
        if EAR_LAST[2] is None: continue
        lp, h12, spf = EAR_LAST[2]
        verses = T_JOB[str(n)]
        toks, meta, alt_list, sets, P = [], [], [], {}, []
        for vi, v in enumerate(verses):
            pw = parse_verse(v); P.append(pw)
            for wi, (w, letters, us) in enumerate(pw):
                for k, c in enumerate(letters):
                    if c == 'ה' and k == len(letters) - 1: continue
                    alts = ALT.get(c)
                    if not alts: continue
                    key = ','.join(alts)
                    if key not in sets: sets[key] = len(alt_list); alt_list.append(alts)
                    toks.append(sets[key]); meta.append((vi, wi, k, c))
        lp2, ids = with_virtual_columns(lp.astype(np.float32), alt_list, V); lp2 = blank_merge(lp2)
        if lp2.shape[0] < 2 * len(toks) + 1: print(f'{pid}: audio too short for the text', flush=True); continue
        al, fa, fb = ctc_local(lp2, [ids[t] for t in toks], PAD, NV)
        if fa < 0: print(f'{pid}: not found', flush=True); continue
        by_v = {}
        for (vi, wi, k, c), a in zip(meta, al): by_v.setdefault(vi, []).append((wi, k, c, a))
        T = lp.shape[0]; m = int(round(0.25 / spf)); kept = 0
        for vi, v in enumerate(verses):
            L = by_v.get(vi, []); placed = [x for x in L if x[3]['f0'] >= 0]
            if not placed: continue
            pv = float(np.mean([x[3]['score'] for x in placed]))
            words_hit = {x[0] for x in placed}; n_words = len(P[vi])
            if pv < .5 or len(words_hit) < n_words: continue                  # the stretch does not match this pasuk well
            f0 = max(0, min(x[3]['f0'] for x in placed) - m); f1 = min(T, max(x[3]['f1'] for x in placed) + m)
            if f1 - f0 < 20 or (f1 - f0) * spf > 40: continue
            align = []
            for wi, k, c, a in L:
                r = {'w': wi, 'k': k, 'c': c, 'f0': a['f0'] - f0 if a['f0'] >= 0 else -1, 'f1': a['f1'] - f0 if a['f0'] >= 0 else -1, 'p': round(a['score'], 3)}
                if a['f0'] >= 0:
                    mass = {mm: float(np.exp(lp[a['f0']:a['f1'], V[mm]]).sum()) for mm in ALT[c]}
                    r['heard'] = max(mass, key=mass.get); r['mass'] = {mm: round(val, 3) for mm, val in mass.items()}
                align.append(r)
            h = h12[f0:f1]; sc = np.maximum(np.abs(h).max(1), 1e-6)
            cid = f'{TAG}_{bk}{n}_{vi + 1}' if bk else f'{TAG}_{n}_{vi + 1}'
            np.savez(os.path.join(FEAT, cid + '.npz'), lp=lp[f0:f1].astype(np.float16), h12q=np.round(h / sc[:, None] * 127).astype(np.int8), h12s=sc.astype(np.float16))
            text = ' '.join(letters for _, letters, _ in P[vi])
            pron = ' '.join(''.join(u['c'] for u in us) for _, _, us in parse_verse(clean_verse(v)))
            row = {'id': cid, 'src': 'nv', 'voice': TAG, 'pid': pid, 'book': bk or 'tehillim', 'rec': os.path.basename(path), 'line': vi + 1, 'text': text, 'pron': pron,
                   'dur': round((f1 - f0) * spf, 3), 'T': int(f1 - f0), 'spf': spf, 'skel': round(pv, 3), 'good': 1.0, 'align': align,
                   't0': round((t0 or 0.0) + f0 * spf, 3), 't1': round((t0 or 0.0) + f1 * spf, 3)}
            with open(MAN, 'a', encoding='utf-8') as fo: fo.write(json.dumps(row, ensure_ascii=False) + '\n')
            kept += 1; n_items += 1
        if kept: have.add(pid)   # a perek that kept nothing may be tried again (the same file under another perek: Mishlei's mislabelled 3 and 4)
        print(f'{pid}: {kept} of {len(verses)} pesukim kept ({x.shape[0] / 16000:.0f} s audio) [{int(time.time() - t_start)} s, {n_items} items]', flush=True)
    except Exception as e:   # one bad file (a text the parser cannot read, a broken mp3) does not stop the batch
        print(f'{job}: FAILED {type(e).__name__}: {e}', flush=True)
print(f'{TAG}: done, {n_items} new items [{int(time.time() - t_start)} s]', flush=True)
