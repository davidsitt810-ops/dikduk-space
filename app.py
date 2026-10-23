"""Dikduk fit-score server for the pizmonim site (runs as a Hugging Face Space, CPU). No Whisper. Two ears:
a phone recognizer for the words and the ח, and an Arabic-letter recognizer for the throat sounds (see below).

The idea, in plain words. We already know the words of the line, so we never ask "what did you say?" (Whisper copies
the hint when it is unsure and mishears singing when it has no hint). We ask "how well does the audio fit the
expected sounds, word by word?" and we take the EXPECTED SOUNDS FROM THE HAZZAN'S OWN RECORDING, not from a
dictionary, so the yardstick is Sephardic singing, not Israeli speech.

The model: wav2vec2-xlsr-53-espeak-cv-ft, a phone recognizer (IPA, 20 ms frames). Measured Oct 13 on Moshe Dwek's
319 (in the browser, same weights): his line 1 came out "m z i | a z | k a l a k | ɛ s s | h ɑ z ə b i | l a m a";
aligning those phones onto the same audio gave every word a fit of .62-.94; onto the audio with עזבי cut out, עזבי
got .00; with אז and כלה swapped, אז got .00; onto line 2's audio every word got .00-.37. The same bytes always
give the same numbers. Its weakness, also measured: on his sung ayins it hears ʕ at most .17 (mostly nothing), so
the ע/ח question needs more than this model's phone head; see /check's "throat" and "emb" below.

Steps for any audio (the hazzan's line or a take):
  1. phone log-probabilities, one model run;
  2. the consonant skeleton of each word (IPA, Sephardic) force-aligned on those probabilities (CTC Viterbi): this
     puts every consonant in time, deterministically, without needing vowels (the lyrics carry no nikud);
  3. word spans from the consonant spans (the stretch between two words goes to the word whose vowel it is);
  4. the phones the model heard inside each word, and, for every ע and ח, the window where it must have been said.
For the hazzan (/ref, cached), step 4 gives the expected phones per word. For a take (/check), those expected phones
are force-aligned onto the take: each word's FIT = the mean probability of its phones along the alignment, and its
place in the take. For the throat letters, the take's window gets the model's own probabilities of ʕ ʔ ħ h x χ and,
with emb=1, the mean hidden state of the window (1024 numbers) for a classifier to be trained on David's recordings.

v4 (Oct 2026) adds Rabbi Alouf's Tehillim: a Hebrew-LETTER head and the throat classifiers retrained with his 144
perakim, a VOWEL head (letters + the five vowel classes, from the nikud of Tehillim) that compares the student's
vowels with the hazzan's — or with the nikud when the line has it — and the perakim themselves in /lyrics
(ids t1..t150, lines = pesukim, timings from forced alignment) with their audio at /tehillim/audio/<file> when the
files are in static/tehillim (or DK_TEHILLIM_BASE points at them).

v4.1 (the night after): the letter head retrained on 3,510 archive lines from 700 more recordings (every synced
recording, not just the best one per pizmon) plus 400 clips of Egyptian Arabic read speech (FLEURS, CC BY 4.0) whose
ع and ح are the same throat sounds, mapped onto Hebrew letters — held-out hazzan ayin 94% (from 85%), an Israeli ayin
still heard as ayin 12% (from 24%); a LETTERS-KEPT signal (every letter optional at a cost on the letter head: which
letters were actually heard, and "not heard" feedback per letter); a combined word score pw (logistic on the
reference-free signals, fitted on tampered clean pesukim) that the page trusts only on clean takes; the Arabic ear's
throat vote by its ع/ح peak; the hazzan's reference cache keyed by server version.

v4.2 (Oct 15, on the Hugging Face Space davidsitt/pizmonim-dikduk): the proxy in front of a Space cuts a request
that runs too long, and the first check of a line did (its hazzan line is analysed on the way) — so a check can be
queued (POST /check?…&job=1 answers at once with a job id; GET /job/<id> is polled by the page, which shows what
the server is doing); one worker thread runs the queue. The page also asks for the hazzan's line (/ref) the moment
a line is picked, so it is analysed while the person records. torch gets the container's real CPU quota as its
thread count (os.cpu_count() reports the host's cores inside a Space; too many threads crawl).

Endpoints (JSON, CORS open):  GET /health   GET /info   GET /lyrics (the site's lyrics.json + the Tehillim perakim)
  GET  /ref?f=<archive mp3 | tehillim-NNN.mp3>&t0=&t1=&words=<line>   the hazzan's line
  POST /check?words=<line>[&ref=<f>&t0=&t1=][&nikud=<pointed line>][&drill=throat|plain][&job=1]  body=audio  the
       take, against the hazzan when ref is given (fit, throat letters, vowels), against the nikud when given;
       with job=1 the answer is {"job": id} and GET /job/<id> returns {state, stage, result} when done
  GET  /drill, /drill/export                                   the drill recordings kept here (features + labels)
  GET  /tehillim/audio/<file>                                  a Rabbi Alouf recording
Nothing here deploys or changes the site.
"""
import os, re, sys, json, time, hashlib, subprocess, tempfile, threading, queue, uuid
import numpy as np
import torch
import requests
from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

T_START = time.time()

def usable_cpus():
    """the CPUs this process may really use: inside a container os.cpu_count() reports the host's cores (a Space
       says 2 vCPU, the host has dozens), and torch with more threads than cores crawls. The cgroup quota wins."""
    n = os.cpu_count() or 1
    try: n = min(n, len(os.sched_getaffinity(0)))
    except Exception: pass
    try:   # cgroup v2
        q, p = open('/sys/fs/cgroup/cpu.max').read().split()[:2]
        if q != 'max': n = min(n, max(1, -(-int(q) // int(p))))
    except Exception: pass
    try:   # cgroup v1
        q = int(open('/sys/fs/cgroup/cpu/cpu.cfs_quota_us').read()); p = int(open('/sys/fs/cgroup/cpu/cpu.cfs_period_us').read())
        if q > 0: n = min(n, max(1, -(-q // p)))
    except Exception: pass
    try: n = int(os.environ.get('DK_THREADS') or n)
    except Exception: pass
    return max(1, n)
THREADS = usable_cpus(); torch.set_num_threads(THREADS)
# DK_DEVICE=cuda runs the two big models on a GPU when one is there (a Colab T4 answers a check in a second or two);
# anything else, or a GPU that fails to load, means CPU. The heads and the aligner stay on the CPU either way.
DEV = 'cpu'
if os.environ.get('DK_DEVICE', '').lower().startswith('cuda') and torch.cuda.is_available(): DEV = 'cuda'
SR = 16000
ARCHIVE = 'https://www.pizmonim.org/MP3/'
UA = {'User-Agent': 'Mozilla/5.0 (pizmonim dikduk checker)', 'Accept': '*/*'}
CACHE_DIR = os.environ.get('DK_CACHE', '/tmp/dkcache')
os.makedirs(CACHE_DIR, exist_ok=True)
LYRICS_URL = os.environ.get('DK_LYRICS', 'https://holiday.thepizmonim.pages.dev/app/lyrics.json')
EMB_LAYER = int(os.environ.get('DK_EMB_LAYER', '16'))   # an extra hidden layer kept in drill features (of 24)

app = FastAPI(title='dikduk fit-score')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

# ---------------------------------------------------------------- the model (loaded once)
LOCK = threading.Lock()
print('loading phone model ...', flush=True)
from transformers import Wav2Vec2ForCTC, Wav2Vec2FeatureExtractor
from huggingface_hub import hf_hub_download
PH_ID = os.environ.get('DK_PHONE_MODEL', 'facebook/wav2vec2-xlsr-53-espeak-cv-ft')
FE = Wav2Vec2FeatureExtractor.from_pretrained(PH_ID)
MODEL = Wav2Vec2ForCTC.from_pretrained(PH_ID).eval()
try: MODEL = MODEL.to(DEV)
except Exception as e: DEV = 'cpu'; print('GPU refused, staying on the CPU:', e, flush=True)
with open(hf_hub_download(PH_ID, 'vocab.json'), encoding='utf-8') as f:
    VOCAB = json.load(f)
ID2TOK = {v: k for k, v in VOCAB.items()}
PAD = VOCAB.get('<pad>', 0)
THROAT = ['ʕ', 'ʔ', 'ħ', 'h', 'x', 'χ', 'ɣ', 'q', 'k']
THROAT_IDS = {k: VOCAB[k] for k in THROAT if k in VOCAB}
print('phone model ready; vocab', len(VOCAB), flush=True)
# The second ear: an Arabic-LETTER recognizer with no language model behind it (Whisper's Arabic mode failed because
# its language model wrote the Arabic words it knows). Measured Oct 13 on the archive (44 pizmonim, best recordings):
# a hazzan's ע is heard as ع 45% of the time and an א as ع 16%; a ח as ح 43% / خ 29% / ه 28%, a כ never as ح.
# So "ع heard" is good evidence of a throat ayin; "nothing heard" is not evidence of a plain one.
from transformers import Wav2Vec2Processor
AR_ID = os.environ.get('DK_ARABIC_MODEL', 'jonatasgrosman/wav2vec2-large-xlsr-53-arabic')
AR_PROC = Wav2Vec2Processor.from_pretrained(AR_ID)
AR_MODEL = Wav2Vec2ForCTC.from_pretrained(AR_ID).eval()
try: AR_MODEL = AR_MODEL.to(DEV)
except Exception as e: DEV = 'cpu'; MODEL = MODEL.to('cpu'); print('GPU refused, staying on the CPU:', e, flush=True)
print('device:', DEV, flush=True)
AR_V = AR_PROC.tokenizer.get_vocab(); AR_PAD = AR_PROC.tokenizer.pad_token_id
AR = {'א': ['ع', 'ا', 'أ', 'ء'], 'ב': ['ب'], 'ג': ['ج', 'غ'], 'ד': ['د', 'ذ'], 'ה': ['ه'], 'ז': ['ز'], 'ח': ['ح', 'خ', 'ه'], 'ט': ['ط', 'ت'],
      'כ': ['ك', 'خ'], 'ל': ['ل'], 'מ': ['م'], 'נ': ['ن'], 'ס': ['س'], 'ע': ['ع', 'ا', 'أ', 'ء'], 'פ': ['ف', 'ب'], 'צ': ['ص', 'س'],
      'ק': ['ق', 'ك'], 'ר': ['ر'], 'ש': ['ش', 'س'], 'ת': ['ت', 'ث']}
AR = {h: [c for c in cs if c in AR_V] for h, cs in AR.items()}
AR_GROUPS = {'ع': ['ع'], 'alef': ['ا', 'أ', 'إ', 'آ', 'ء'], 'ه': ['ه', 'ة'], 'ح': ['ح'], 'خ': ['خ'], 'ك': ['ك']}
AR_GROUPS = {g: [AR_V[c] for c in cs if c in AR_V] for g, cs in AR_GROUPS.items()}
print('arabic ear ready; vocab', len(AR_V), flush=True)
# Throat classifiers on the phone model's hidden features, trained on the archive's hazzanim (space_test/exp_throat*.py):
# ח vs כ/ה on layer 6 (held-out recordings and words: AUC .94-.97), ע vs א on layer 10 (AUC .73: a partial ear).
# Each is a logistic regression on [mean, max] of the layer over the letter's window, scaler folded into the weights.
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'throat_models.json'), encoding='utf-8') as f:
        CLF = json.load(f)
    for k in CLF: CLF[k]['w'] = np.array(CLF[k]['w'], dtype=np.float32)
    print('throat classifiers:', {k: (v['layer'], v['n']) for k, v in CLF.items()}, flush=True)
except Exception as e:
    CLF = {}; print('no throat classifiers:', e, flush=True)
CLF_LAYERS = sorted(set(v['layer'] for v in CLF.values()) | {EMB_LAYER})
# v2 classifiers: on the ARABIC model's hidden states, windows from its own letter alignment (space_test/train_ayin.py)
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'throat_models_v2.json'), encoding='utf-8') as f:
        CLF2 = json.load(f)
    for k in CLF2: CLF2[k]['w'] = np.array(CLF2[k]['w'], dtype=np.float32)
    print('throat classifiers v2:', {k: (v['layer'], v['n'], v.get('auc_cv')) for k, v in CLF2.items()}, flush=True)
except Exception as e:
    CLF2 = {}; print('no v2 classifiers:', e, flush=True)
# The third ear: a Hebrew-LETTER head raised on the archive (space_test/train_head.py): small temporal convolutions on
# the Arabic model's hidden layer, trained with the synced lines' letters as targets, so ע/א and ח/כ are separate
# outputs it learned from hazzanim. Loaded when the file is there.
import torch.nn as nn
class LetterHead(nn.Module):
    def __init__(self, d_in=1024, h=384, n=24, k=5, layers=3):
        super().__init__(); self.inp = nn.Sequential(nn.LayerNorm(d_in), nn.Linear(d_in, h), nn.GELU(), nn.Dropout(0.15))
        self.convs = nn.ModuleList([nn.Sequential(nn.Conv1d(h, h, k, padding=k // 2), nn.GELU(), nn.Dropout(0.15)) for _ in range(layers)])
        self.norms = nn.ModuleList([nn.LayerNorm(h) for _ in range(layers)]); self.out = nn.Linear(h, n)
    def forward(self, x):
        y = self.inp(x)
        for conv, norm in zip(self.convs, self.norms):
            y = norm(y + conv(y.transpose(1, 2)).transpose(1, 2))
        return self.out(y)
HEAD = None; HEAD_SYM = []; HEAD_LAYER = 12
try:
    ck = torch.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'letter_head.pt'), map_location='cpu')
    HEAD_SYM = ck['sym']; HEAD_LAYER = int(str(ck.get('layer', 'h12')).replace('h', ''))
    HEAD = LetterHead(d_in=ck.get('d_in', 1024), n=len(HEAD_SYM)); HEAD.load_state_dict(ck['state']); HEAD.eval()
    HEAD_S2I = {c: i for i, c in enumerate(HEAD_SYM)}
    print('letter head ready: layer', HEAD_LAYER, 'symbols', len(HEAD_SYM), flush=True)
except Exception as e:
    print('no letter head:', e, flush=True)
# The vowel ear: the same head shape, trained on Rabbi Alouf's pointed Tehillim with letters AND vowel classes
# (A E I O U) as targets (space_test/train_head2.py full). vowels.py aligns a line as letter [vowel?] letter [vowel?] …
# and reads which vowel class was sung in each slot; the student's vowels are compared with the hazzan's (or with the
# nikud when the line has it). Loaded when the file is there.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vowels import vowel_place, compare_vowels, letters_kept, VOWEL_NAME, VOWELS
from order import order_evidence, order_from_tokens
FULL = None; FULL_SYM = []; FULL_LAYER = 12
try:
    ck = torch.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'full_head.pt'), map_location='cpu')
    FULL_SYM = ck['sym']; FULL_LAYER = int(str(ck.get('layer', 'h12')).replace('h', ''))
    FULL = LetterHead(d_in=ck.get('d_in', 1024), n=len(FULL_SYM)); FULL.load_state_dict(ck['state']); FULL.eval()
    FULL_S2I = {c: i for i, c in enumerate(FULL_SYM)}
    print('vowel head ready: layer', FULL_LAYER, 'symbols', len(FULL_SYM), flush=True)
except Exception as e:
    print('no vowel head:', e, flush=True)
# The heavy version, when David has run space_test/finetune_gpu.py on a GPU: a whole XLS-R encoder fine-tuned on
# Rabbi Alouf and the archive with its own two heads (letters; letters + vowels). DK_FT_MODEL = a folder (or a Hub
# repo id) holding encoder/ and heads.pt. When present it replaces the two CPU heads above (same outputs, same code).
FT = None; FT_HEADS = None
FT_PATH = os.environ.get('DK_FT_MODEL', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ft'))
try:
    if os.path.isdir(FT_PATH) or os.environ.get('DK_FT_MODEL'):
        from transformers import Wav2Vec2Model
        if not os.path.isdir(FT_PATH):
            from huggingface_hub import snapshot_download
            FT_PATH = snapshot_download(FT_PATH)
        FT = Wav2Vec2Model.from_pretrained(os.path.join(FT_PATH, 'encoder')).eval()
        FT_FE = Wav2Vec2FeatureExtractor.from_pretrained(os.path.join(FT_PATH, 'encoder'))
        ck = torch.load(os.path.join(FT_PATH, 'heads.pt'), map_location='cpu')
        class _Heads(nn.Module):
            def __init__(self, d, nl, nf):
                super().__init__(); self.drop = nn.Dropout(0.1); self.letters = nn.Linear(d, nl); self.full = nn.Linear(d, nf)
            def forward(self, h): return self.letters(h), self.full(h)
        FT_HEADS = _Heads(FT.config.hidden_size, len(ck['sym_letters']), len(ck['sym_full'])); FT_HEADS.load_state_dict(ck['state']); FT_HEADS.eval()
        HEAD_SYM = ck['sym_letters']; HEAD_S2I = {c: i for i, c in enumerate(HEAD_SYM)}; FULL_SYM = ck['sym_full']; FULL_S2I = {c: i for i, c in enumerate(FULL_SYM)}
        print('fine-tuned encoder ready (replaces the CPU heads):', FT_PATH, 'trained on', ck.get('n_train'), 'items', flush=True)
except Exception as e:
    FT = None; print('no fine-tuned encoder:', e, flush=True)

def head_lp(AH):
    """Hebrew-letter log-probs from the head, on the Arabic model's hidden layer"""
    if HEAD is None or HEAD_LAYER not in AH: return None
    with torch.inference_mode():
        return torch.log_softmax(HEAD(torch.from_numpy(AH[HEAD_LAYER].astype(np.float32))[None]), -1)[0].numpy()

def head_place(lp, words, pairs=(('ע', 'א'), ('ח', 'כ'))):
    """the line's letters aligned on the head's output, each letter of a pair offered both members; per word the mean
       letter score (a words check on Hebrew letters, no IPA in between), per ע/ח/א/כ which member had the mass"""
    cols, toks, meta = {}, [], []
    for i, w in enumerate(words):
        hl = he_read(w)
        for k, c in enumerate(hl):
            if c not in HEAD_S2I: continue
            pair = next((p for p in pairs if c in p), None)
            if pair:
                key = ''.join(pair)
                if key not in cols: cols[key] = lp.shape[1] + len(cols)
                toks.append(cols[key]); meta.append((i, k, c, pair))
            else:
                toks.append(HEAD_S2I[c]); meta.append((i, k, c, None))
        if ' ' in HEAD_S2I and i + 1 < len(words):
            toks.append(HEAD_S2I[' ']); meta.append((i, -1, ' ', None))
    if not toks: return {}, {}
    lp2 = np.concatenate([lp, np.stack([np.logaddexp.reduce(lp[:, [HEAD_S2I[c] for c in key]], axis=1) for key in cols], 1)], 1) if cols else lp
    al = ctc_align(lp2, toks, blank=0)
    per_word, per_letter = {}, {}
    for (i, k, c, pair), a in zip(meta, al):
        if c == ' ' or a['f0'] < 0: continue
        per_word.setdefault(i, []).append(a['score'])
        if pair:
            mass = {m: float(np.exp(lp[a['f0']:a['f1'], HEAD_S2I[m]]).sum()) for m in pair}
            per_letter[(i, k)] = {'heard': max(mass, key=mass.get), 'mass': {m: round(v, 3) for m, v in mass.items()}, 'p': round(a['score'], 3), 'f0': a['f0'], 'f1': a['f1']}
    return {i: round(float(np.mean(v)), 3) for i, v in per_word.items()}, per_letter

# ---------------------------------------------------------------- Hebrew words and their consonant skeletons
# Each Hebrew consonant as the IPA sounds it may be in Sephardic reading (the lyrics have no nikud, so bet/vet,
# kaf/khaf, pe/fe, shin/sin, tsadi cannot be told apart): the aligner is given ALL of a letter's sounds at once (one
# virtual column = the sum of their probabilities) and reports which one it found. Measured Oct 13 on four hazzanim
# of 319: גפני -> ɡ f n, קץ -> k s, שורי -> ʃ, עשה -> s, and their ח -> h every time (never x). א ע י ו are left out:
# they are vowels or throat sounds the model does not hear as consonants in singing; ה is a consonant except at
# the end of a word, where it is silent (כלה, למה), and at the start, where singers hardly voice it.
ALT = {'ב': ['b', 'v'], 'ג': ['ɡ', 'ɣ'], 'ד': ['d', 'ð'], 'ז': ['z'], 'ח': ['ħ', 'h', 'x', 'χ'], 'ט': ['t'], 'כ': ['k', 'x', 'χ'],
       'ל': ['l'], 'מ': ['m'], 'נ': ['n'], 'ס': ['s'], 'פ': ['p', 'f'], 'צ': ['ts', 's'], 'ק': ['k', 'q'], 'ר': ['r', 'ɾ', 'ʁ'],
       'ש': ['ʃ', 's'], 'ת': ['t', 'θ', 's'], 'ה': ['h']}
# ת is offered 's' too, so a tav said the Ashkenazi way (sav) is found rather than missed, and reported as such
ALT = {c: [p for p in alts if p in VOCAB] for c, alts in ALT.items()}
CONSONANTS = set(ALT)
NIK = re.compile('[\u0591-\u05C7]')
FIN = {'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ'}

def he_letters(w):
    w = NIK.sub('', str(w or ''))
    return ''.join(FIN.get(c, c) for c in w if 'א' <= c <= 'ת')

def he_read(w):
    """the letters as they are READ: the Name (יי / יהוה) is said אדני"""
    hl = he_letters(w)
    return 'אדני' if hl in ('יי', 'יהוה') else hl

def he_words(text):
    return [w for w in re.split(r"[\s,.;:!?\"'״׳()\[\]{}|/\\־-]+", str(text or '')) if he_letters(w)]

def skeleton(w):
    """[(letter index, letter, [its possible sounds])] for the word's consonants; the Name reads adonay -> d n"""
    hl = he_letters(w)
    if hl in ('יי', 'יהוה'):
        return [(0, 'ד', ALT['ד']), (1, 'נ', ALT['נ'])]
    out = []
    for k, c in enumerate(hl):
        if c == 'ה' and (k == 0 or k == len(hl) - 1):
            continue   # a final he is silent (כלה); an opening he is barely voiced in singing (האיש, הלך scored .06-.08)
        if c in ALT and ALT[c]:
            out.append((k, c, ALT[c]))
    return out

# ---------------------------------------------------------------- audio in
def decode_audio(data: bytes) -> np.ndarray:
    """any container ffmpeg reads -> float32 mono 16 kHz"""
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
        f.write(data); src = f.name
    try:
        out = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                             capture_output=True, timeout=120)
        if out.returncode != 0:
            raise ValueError('ffmpeg: ' + out.stderr.decode(errors='replace')[:300])
        return np.frombuffer(out.stdout, dtype=np.float32).copy()
    finally:
        os.unlink(src)

TEHILLIM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'tehillim')
TEHILLIM_BASE = os.environ.get('DK_TEHILLIM_BASE', '')   # where the Tehillim mp3s live when they are not in static/tehillim

def tehillim_file(fname: str):
    """a Rabbi Alouf file (tehillim-NNN.mp3 / extra-*.mp3): the local copy, or None"""
    if not re.fullmatch(r'(tehillim-\d{3}|extra-[a-z0-9-]+)\.mp3', fname): return None
    p = os.path.join(TEHILLIM_DIR, fname)
    return p if os.path.exists(p) else ''

def fetch_archive(fname: str) -> bytes:
    """an archive mp3 (or a Tehillim file), cached on disk (the archive answers 406 without a browser-like user agent)"""
    tf = tehillim_file(fname)
    if tf: return open(tf, 'rb').read()
    key = os.path.join(CACHE_DIR, 'mp3_' + hashlib.sha1(fname.encode()).hexdigest())
    if os.path.exists(key):
        return open(key, 'rb').read()
    if tf == '':
        if not TEHILLIM_BASE: raise ValueError('no Tehillim audio on this server (put the files in static/tehillim or set DK_TEHILLIM_BASE)')
        r = requests.get(TEHILLIM_BASE.rstrip('/') + '/' + fname, headers=UA, timeout=120)
        r.raise_for_status(); open(key, 'wb').write(r.content); return r.content
    r = requests.get(ARCHIVE + requests.utils.quote(fname), headers=UA, timeout=120)
    r.raise_for_status()
    open(key, 'wb').write(r.content)
    return r.content

# ---------------------------------------------------------------- the model run
def run_model(x: np.ndarray, want_emb=False):
    """-> log-probs (T, V) as numpy, seconds per frame, and the hidden layers the classifiers use {layer: (T, 1024)}"""
    inp = FE(x, sampling_rate=SR, return_tensors='pt')
    with torch.inference_mode(), LOCK:
        out = MODEL(inp.input_values.to(DEV), output_hidden_states=True)
    lp = torch.log_softmax(out.logits[0].float(), dim=-1).cpu().numpy()
    H = {l: out.hidden_states[l][0].float().cpu().numpy() for l in CLF_LAYERS}
    return lp, x.shape[0] / SR / lp.shape[0], H

def arabic_lp(x: np.ndarray):
    """-> Arabic-letter log-probs (T, V), seconds per frame, hidden layers {12, 18} (T, 1024)"""
    inp = AR_PROC(x, sampling_rate=SR, return_tensors='pt')
    with torch.inference_mode(), LOCK:
        out = AR_MODEL(inp.input_values.to(DEV), output_hidden_states=True)
    lp = torch.log_softmax(out.logits[0].float(), dim=-1).cpu().numpy()
    AH = {l: out.hidden_states[l][0].float().cpu().numpy() for l in (12, 18) if l < len(out.hidden_states)}
    return lp, x.shape[0] / SR / lp.shape[0], AH

def arabic_place(lp, words):
    """the words as Arabic letters (a letter with several possible sounds as one virtual column), aligned; for every
       ע / ח (and א / כ / ה, for the record) which member had the mass on its own frames"""
    sets, key, toks, meta = [], {}, [], []
    for i, w in enumerate(words):
        hl = he_read(w)
        for k, c in enumerate(hl):
            if c == 'ה' and k == len(hl) - 1: continue
            alts = AR.get(c)
            if not alts: continue
            kk = ','.join(alts)
            if kk not in key: key[kk] = len(sets); sets.append(alts)
            toks.append(lp.shape[1] + key[kk]); meta.append((i, k, c, alts))
    if not toks: return {}
    cols = [np.logaddexp.reduce(lp[:, [AR_V[c] for c in alts]], axis=1) for alts in sets]
    al = ctc_align(np.concatenate([lp, np.stack(cols, 1)], 1), toks, blank=AR_PAD)
    out = {}
    for (i, k, c, alts), a in zip(meta, al):
        if c not in ('ע', 'ח', 'א', 'כ', 'ה') or a['f0'] < 0: continue
        mass = {m: float(np.exp(lp[a['f0']:a['f1'], AR_V[m]]).sum()) for m in alts}
        out[(i, k)] = {'heard': max(mass, key=mass.get), 'mass': {m: round(v, 3) for m, v in mass.items()}, 'f0': a['f0'], 'f1': a['f1'], 'p': round(a['score'], 3)}
    return out

def greedy(lp, spf):
    ids = lp.argmax(-1)
    seq, prev = [], -1
    for t, i in enumerate(ids.tolist()):
        if i != prev and i != PAD:
            seq.append({'p': ID2TOK.get(i, '?'), 't': round(t * spf, 3), 'c': round(float(np.exp(lp[t, i])), 3)})
        prev = i
    return seq

# ---------------------------------------------------------------- CTC forced alignment (Viterbi, blank-interleaved)
def ctc_align(lp: np.ndarray, toks, blank=None):
    """lp (T, V) log-probs; toks token ids. -> per token {'f0', 'f1', 'score' = mean prob on its frames}"""
    PAD = blank if blank is not None else globals()['PAD']
    T = lp.shape[0]; S = 2 * len(toks) + 1
    ext = [PAD if s % 2 == 0 else toks[(s - 1) // 2] for s in range(S)]
    NEG = -1e30
    prev = np.full(S, NEG); prev[0] = lp[0, ext[0]]
    if S > 1: prev[1] = lp[0, ext[1]]
    bp = np.zeros((T, S), dtype=np.int8)
    ext_a = np.array(ext)
    skip_ok = np.array([s > 1 and ext[s] != PAD and ext[s] != ext[s - 2] for s in range(S)])
    for t in range(1, T):
        stay = prev
        step = np.concatenate(([NEG], prev[:-1]))
        skip = np.concatenate(([NEG, NEG], prev[:-2]))
        skip = np.where(skip_ok, skip, NEG)
        best = stay; b = np.zeros(S, dtype=np.int8)
        m = step > best; best = np.where(m, step, best); b = np.where(m, 1, b)
        m = skip > best; best = np.where(m, skip, best); b = np.where(m, 2, b)
        bp[t] = b
        prev = best + lp[t, ext_a]
    s = S - 1
    if S > 1 and prev[S - 2] > prev[S - 1]:
        s = S - 2
    path = np.zeros(T, dtype=np.int32)
    for t in range(T - 1, -1, -1):
        path[t] = s; s = int(s) - int(bp[t, s])
    out = [{'f0': -1, 'f1': -1, 'sum': 0.0, 'n': 0} for _ in toks]
    for t in range(T):
        st = int(path[t])
        if st % 2 == 0: continue
        o = out[(st - 1) // 2]
        if o['f0'] < 0: o['f0'] = t
        o['f1'] = t + 1; o['sum'] += float(np.exp(lp[t, ext[st]])); o['n'] += 1
    return [{'f0': o['f0'], 'f1': o['f1'], 'score': (o['sum'] / o['n']) if o['n'] else 0.0} for o in out]

# ---------------------------------------------------------------- words in time
def place_words(lp, spf, words):
    """consonant skeletons aligned -> per word: consonant spans (with the sound found), the word's span, the throat windows"""
    sets, key = [], {}
    toks, own, meta = [], [], []
    for i, w in enumerate(words):
        for k, c, alts in skeleton(w):
            kk = ','.join(alts)
            if kk not in key:
                key[kk] = len(sets); sets.append(alts)
            toks.append(lp.shape[1] + key[kk]); own.append(i); meta.append((k, c, alts))
    # one virtual column per set of sounds: log of the summed probability
    if sets:
        cols = [np.logaddexp.reduce(lp[:, [VOCAB[p] for p in alts]], axis=1) for alts in sets]
        lp_ext = np.concatenate([lp, np.stack(cols, axis=1)], axis=1)
        al = ctc_align(lp_ext, toks)
    else:
        al = []
    T = lp.shape[0]; end_t = T * spf
    W = []
    for i, w in enumerate(words):
        cons = []
        for j in range(len(toks)):
            if own[j] != i or al[j]['f0'] < 0: continue
            k, c, alts = meta[j]; a = al[j]
            mass = {p: float(np.exp(lp[a['f0']:a['f1'], VOCAB[p]]).sum()) for p in alts}
            heard = max(mass, key=mass.get)
            cons.append({'k': k, 'c': c, 'heard': heard, 't0': a['f0'] * spf, 't1': a['f1'] * spf, 'p': a['score'],
                         'mass': {p: round(v, 3) for p, v in mass.items()}})
        notes = []
        for c in cons:
            if c['c'] == 'ת' and c['heard'] == 's' and c['mass'].get('s', 0) >= 2 * max(c['mass'].get('t', 0), c['mass'].get('θ', 0), 1e-6):
                notes.append({'k': c['k'], 'c': 'ת', 'say': 'sav'})   # a tav said like samekh (the Ashkenazi way)
        W.append({'w': w, 'cons': cons, 'n': len(cons), 'notes': notes})
    # word spans: the cut between two words is at the next word's first consonant; when the next word opens with
    # א/ע/ה (a vowel or a throat sound, not in the skeleton) the cut is right after this word's last consonant if this
    # word ends in a consonant (what follows cannot be its vowel), else halfway (both words have a vowel there).
    # Checked on Dwek's 319 line 1: קץ|עזבי cut at the end of the ץ, so עזבי keeps its "h ɑ" opening.
    # the clip's edges: the first word starts a little before its first consonant and the last word ends a little
    # after its last one, so leading silence, an announcement, or a line sung a second time (the sync events only
    # mark where a line starts) do not get swallowed into the first or last word's sounds
    first_c = min([c['t0'] for c in W[0]['cons']], default=None) if W else None
    last_c = max([c['t1'] for c in W[-1]['cons']], default=None) if W else None
    cuts = [max(0.0, first_c - 0.6) if first_c is not None else 0.0]
    for i in range(len(W) - 1):
        my_last = max([c['t1'] for c in W[i]['cons']], default=cuts[-1])
        next_start = min([c['t0'] for c in W[i + 1]['cons']], default=my_last)
        nxt = he_letters(W[i + 1]['w'])[:1]
        my_end = he_letters(W[i]['w'])[-1:]
        if nxt not in ('א', 'ע', 'ה'):
            cut = next_start
        elif my_end in CONSONANTS and my_end != 'ה':
            cut = my_last
        else:
            cut = (my_last + next_start) / 2
        cuts.append(max(cuts[-1], min(cut, end_t)))
    cuts.append(min(end_t, last_c + 0.8) if last_c is not None else end_t)
    if cuts[-1] < cuts[-2]: cuts[-1] = cuts[-2] + spf
    for i, w in enumerate(W):
        a, b = cuts[i], cuts[i + 1]
        hl = he_letters(w['w'])
        w['t0'] = round(a, 3); w['t1'] = round(max(b, a + spf), 3)
        w['skel'] = round(float(np.mean([c['p'] for c in w['cons']])), 3) if w['cons'] else None
        for c in w['cons']:
            c['t0'] = round(c['t0'], 3); c['t1'] = round(c['t1'], 3); c['p'] = round(c['p'], 3)
        # throat windows: an ע or ח between its neighbouring consonants (or the word edge)
        w['throat'] = []
        for k, ch in enumerate(hl):
            if ch not in ('ע', 'ח'): continue
            own = next((c for c in w['cons'] if c['k'] == k), None)
            if own:
                left, right = own['t0'], own['t1']
            else:
                left = max([c['t1'] for c in w['cons'] if c['k'] < k], default=w['t0'])
                right = min([c['t0'] for c in w['cons'] if c['k'] > k], default=w['t1'])
                if right <= left: right = left + 0.1
            w['throat'].append({'k': k, 'c': ch, 't0': round(max(0.0, left - 0.04), 3), 't1': round(right + 0.04, 3)})
    return W

def phone_line_tokens(lp, words):
    """each word's consonant skeleton as virtual 'either of these sounds' columns (as place_words builds them)"""
    sets, key, per_word = [], {}, []
    for w in words:
        toks = []
        for k, c, alts in skeleton(w):
            kk = ','.join(alts)
            if kk not in key: key[kk] = len(sets); sets.append(alts)
            toks.append(lp.shape[1] + key[kk])
        per_word.append(toks)
    lp_ext = np.concatenate([lp, np.stack([np.logaddexp.reduce(lp[:, [VOCAB[p] for p in alts]], axis=1) for alts in sets], 1)], 1) if sets else lp
    return lp_ext, per_word

def heard_in(seq, t0, t1):
    return [s['p'] for s in seq if t0 <= s['t'] < t1]

def clf_prob(name, H, f0, f1):
    m = CLF.get(name)
    if not m or m['layer'] not in H: return None
    seg = H[m['layer']][f0:f1]
    if not len(seg): return None
    z = float(np.dot(m['w'], np.concatenate([seg.mean(0), seg.max(0)])) + m['b'])
    return round(1.0 / (1.0 + np.exp(-z)), 3)

def clf2_prob(name, AH, ar_hit, T):
    """v2: the Arabic model's hidden layer around the letter's own aligned frames"""
    m = CLF2.get(name)
    if not m or not ar_hit or m['layer'] not in AH: return None
    f0, f1 = max(0, ar_hit['f0'] - m['pad']), min(T, ar_hit['f1'] + m['pad'])
    seg = AH[m['layer']][f0:f1]
    if not len(seg): return None
    z = float(np.dot(m['w'], np.concatenate([seg.mean(0), seg.max(0)])) + m['b'])
    return round(1.0 / (1.0 + np.exp(-z)), 3)

def throat_probe(lp, spf, H, win, ar_lp, ar_spf, ar_hit, want_emb=False, AH=None, head_hit=None):
    """one ע or ח: the phone head's own throat sounds in the window, the classifier's probability, the Arabic ear's
       peaks in the window and its aligned winner, and a provisional verdict (thresholds to be calibrated on David)"""
    f0, f1 = int(win['t0'] / spf), max(int(win['t0'] / spf) + 1, int(win['t1'] / spf) + 1)
    names = [k for k in THROAT if k in THROAT_IDS]
    seg = np.exp(lp[f0:f1][:, [THROAT_IDS[k] for k in names]])
    out = {'peak': {n: round(float(seg[:, j].max()), 3) for j, n in enumerate(names)}}
    out['p'] = clf_prob('ayin' if win['c'] == 'ע' else 'het', H, f0, f1)
    g0, g1 = int(win['t0'] / ar_spf), max(int(win['t0'] / ar_spf) + 1, int(win['t1'] / ar_spf) + 1)
    aseg = np.exp(ar_lp[g0:g1])
    out['ar'] = {g: round(float(aseg[:, ids].sum(1).max()), 3) for g, ids in AR_GROUPS.items() if ids and len(aseg)}
    out['ar_heard'] = ar_hit['heard'] if ar_hit else None
    out['ar_mass'] = ar_hit['mass'] if ar_hit else None
    out['p2'] = clf2_prob('ayin' if win['c'] == 'ע' else 'het', AH, ar_hit, ar_lp.shape[0]) if AH is not None else None
    out['head'] = {'heard': head_hit['heard'], 'mass': head_hit['mass'], 'p': head_hit['p']} if head_hit else None
    # the verdict: three ears vote (the trained head, the v2 classifier, the Arabic ear); "throat" needs two votes for
    # and none against, "plain" the same the other way, anything else is "unsure" and said so. Numbers behind the votes
    # are in LAB_NOTES (hazzanim held out of training; Israeli speech where ע is said like א and ח like כ).
    p = out['p']; p2 = out['p2']; ar = out['ar']; heard = out['ar_heard']; hd = out['head']
    votes = {'throat': [], 'plain': []}
    if win['c'] == 'ע':
        if hd and sum(hd['mass'].values()) >= .2:   # the head votes only where it put real mass on one of the two letters
            r = hd['mass'].get('ע', 0) / sum(hd['mass'].values())
            if r >= .7: votes['throat'].append('head')
            elif r <= .3: votes['plain'].append('head')
        pc = p2 if p2 is not None else p
        if pc is not None:
            if pc >= .6: votes['throat'].append('classifier')
            elif pc <= .3: votes['plain'].append('classifier')
        # v4: the ع PEAK in the window is the vote (measured on ±4-frame windows: Rabbi Alouf's ע 82% >= .5, his א 4%,
        # Israeli ע 12%, Israeli א 6%, archive hazzanim ע 53% / א 12%); "heard" over the aligned frames was too strict
        pk = ar.get('ع', 0); al = ar.get('alef', 0)
        # v4.3: an ע where neither the Arabic ear nor the head heard any throat sound at all (an Israeli ע is often
        # nothing — a glottal catch or silence) counts as plain too, not only one where an alef was heard
        nothing = pk < .1 and (hd is None or (hd.get('mass') or {}).get('ע', 0) < .05)
        if pk >= .5: votes['throat'].append('arabic')
        elif heard != 'ع' and pk < .15 and (al >= .4 or nothing): votes['plain'].append('arabic')
    else:
        if hd and sum(hd['mass'].values()) >= .2:
            r = hd['mass'].get('ח', 0) / sum(hd['mass'].values())
            if r >= .7: votes['throat'].append('head')
            elif r <= .3: votes['plain'].append('head')
        # v4.3: the v2 classifier (trained with Alouf and Israeli negatives, AUC .98) votes for ח as it does for ע; v1 only
        # where v2 is missing. v1 alone left 8 of 79 of Rabbi Alouf's ח "unsure" while the other two ears heard the throat.
        pc = p2 if p2 is not None else p
        if pc is not None:
            if pc >= .6: votes['throat'].append('classifier')
            elif pc <= .3: votes['plain'].append('classifier')
        if ar.get('ح', 0) >= .5: votes['throat'].append('arabic')   # v4: the ح peak (Alouf ח 98%, כ 0%, ה 1%; Israeli ח 0%)
        elif heard in ('خ', 'ه') and ar.get('ح', 0) < .15 and max(ar.get('خ', 0), ar.get('ه', 0)) >= .4: votes['plain'].append('arabic')
    if len(votes['throat']) >= 2 and not votes['plain']: v = 'throat'
    elif len(votes['plain']) >= 2 and not votes['throat']: v = 'plain'
    else: v = 'unsure'
    out['votes'] = votes
    out['v'] = v
    if want_emb:
        out['feat'] = {str(l): [round(float(x), 4) for x in np.concatenate([H[l][f0:f1].mean(0), H[l][f0:f1].max(0)])] for l in CLF_LAYERS}
    return out

def ft_lps(x: np.ndarray):
    """the fine-tuned encoder's two heads over the audio -> (letters log-probs, full log-probs), 20 ms frames"""
    inp = FT_FE(x, sampling_rate=SR, return_tensors='pt')
    with torch.inference_mode(), LOCK:
        h = FT(inp.input_values).last_hidden_state; lo_l, lo_f = FT_HEADS(h)
    return torch.log_softmax(lo_l[0], -1).numpy(), torch.log_softmax(lo_f[0], -1).numpy()

def full_lp(AH):
    if FULL is None or FULL_LAYER not in AH: return None
    with torch.inference_mode():
        return torch.log_softmax(FULL(torch.from_numpy(AH[FULL_LAYER].astype(np.float32))[None]), -1)[0].numpy()

def analyse(x: np.ndarray, words, want_emb=False):
    """everything the page needs about one audio: where each word is, the phones heard in it, the throat letters, the vowels"""
    t = time.time()
    lp, spf, H = run_model(x)
    seq = greedy(lp, spf)
    W = place_words(lp, spf, words)
    ar_lp, ar_spf, AH = arabic_lp(x); ar_hits = arabic_place(ar_lp, words)
    if FT is not None: hlp, flp = ft_lps(x)
    else: hlp, flp = head_lp(AH), full_lp(AH)
    hw, hl = head_place(hlp, words) if hlp is not None else ({}, {})
    # which letters were actually heard: every letter optional at a cost of 3 nats on the letter head (measured on
    # Rabbi Alouf: right words keep 98% of their letters, the words of another pasuk 33%, a skipped word 20-50%)
    kp = letters_kept(hlp, words, HEAD_S2I, he_read, 3.0) if hlp is not None else {}
    vs, vl = vowel_place(flp, words, FULL_S2I, he_read) if flp is not None else ({}, {})
    # whole-line evidence: does the audio prefer the line with a word left out, or two neighbours swapped? (order.py)
    try:
        ev_h = order_evidence(hlp, words, HEAD_S2I, he_read, 0) if hlp is not None else None
    except Exception as e:
        print('order (head):', e, flush=True); ev_h = None
    try:
        lp_ext, pw_ph = phone_line_tokens(lp, words); ev_p = order_from_tokens(lp_ext, pw_ph, None, PAD)
    except Exception as e:
        print('order (phones):', e, flush=True); ev_p = None
    for i, w in enumerate(W):
        w['drop'] = ev_h['drop'][i] if ev_h else None; w['swap'] = (ev_h['swap'][i] if i < len(words) - 1 else None) if ev_h else None
        w['drop_ph'] = ev_p['drop'][i] if ev_p else None; w['swap_ph'] = (ev_p['swap'][i] if i < len(words) - 1 else None) if ev_p else None
        w['phones'] = heard_in(seq, w['t0'], w['t1'])
        w['ids'] = [VOCAB[p] for p in w['phones'] if p in VOCAB]
        w['hskel'] = hw.get(i)
        w['kept'] = kp.get(i, {}).get('kept'); w['miss'] = kp.get(i, {}).get('miss', [])
        if flp is not None and (FULL is not None or FT is not None):
            w['vow'] = [{'k': s['k'], 'heard': s['heard'], 'mass': s['mass'], 'p': s['p'], 't0': round(s['f0'] * ar_spf, 3), 't1': round(s['f1'] * ar_spf, 3)} for s in vs.get(i, [])]
            w['vskel'] = vl.get(i)
        for th in w['throat']:
            th.update(throat_probe(lp, spf, H, th, ar_lp, ar_spf, ar_hits.get((i, th['k'])), want_emb, AH, hl.get((i, th['k'])))); th['heard'] = heard_in(seq, th['t0'], th['t1'])
    return {'dur': round(x.shape[0] / SR, 3), 'spf': round(spf, 5), 'words': W, 'phones': seq, 'gap': ev_h['gap'] if ev_h else None, 'gap_ph': ev_p['gap'] if ev_p else None, 'ms': int((time.time() - t) * 1000)}, lp, spf

# A combined "this word was not sung" score: logistic on the word's reference-free signals (skel, letter head, vowel
# head, consonant count, letters kept), fitted on Rabbi Alouf's held-out pesukim tampered the way a student errs
# (space_test/words_study3.py + words_rule.py). On clean reading, pw >= .9 flags 0.9% of right words and catches 92-100%
# of skipped words, 50-59% of swapped ones. On the archive's accompanied takes it misfires often (the heads hear
# little there), so the page uses it only where the line is clean (its median letter-head score >= .7) — and the
# hazzan "fit" stays in the hand rule, because a model fitted with the hazzan being the same voice over-trusts it.
WORD_MODEL = {'w': [-2.66, 0.0, -1.43, -3.36, 0.24, -2.65], 'b': 7.21}   # skel, (fit: unused), hskel, vskel, n/6, kept
def word_pw(w, fit=None):
    x = [w.get('skel') or 0.0, 0.0, w.get('hskel') or 0.0, w.get('vskel') or 0.0, min(w.get('n', 0), 6) / 6, w.get('kept') if w.get('kept') is not None else 1.0]
    z = sum(a * b for a, b in zip(WORD_MODEL['w'], x)) + WORD_MODEL['b']
    return round(1.0 / (1.0 + np.exp(-z)), 3)

def fit_against(lp, spf, ref_words):
    """the hazzan's phones per word, force-aligned onto the take -> fit per word"""
    toks, own = [], []
    for i, rw in enumerate(ref_words):
        for tid in rw.get('ids', []):
            toks.append(tid); own.append(i)
    if not toks: return []
    al = ctc_align(lp, toks)
    out = []
    for i, rw in enumerate(ref_words):
        L = [al[j] for j in range(len(toks)) if own[j] == i and al[j]['f0'] >= 0]
        if not L:
            out.append({'fit': None}); continue
        sc = [a['score'] for a in L]
        out.append({'fit': round(float(np.mean(sc)), 3), 'min': round(float(min(sc)), 3),
                    't0': round(L[0]['f0'] * spf, 3), 't1': round(L[-1]['f1'] * spf, 3), 'n': len(L)})
    return out

# ---------------------------------------------------------------- routes
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'index.html')

# On a Space the page (and the recording booth and its scripts) are served from the newest copy in the GitHub repo
# (refreshed at most once a minute; GitHub's own cache adds a few minutes), so they can change without rebuilding the
# Space; the files shipped in static/ are the fallback when GitHub does not answer. DK_PAGE_BASE overrides the base
# URL (empty = always the local files; locally the default).
PAGE_BASE = os.environ.get('DK_PAGE_BASE', 'https://raw.githubusercontent.com/davidsitt810-ops/dikduk-space/main/static/' if os.environ.get('SPACE_ID') else '')
_PAGES = {}
STATIC_OK = {'index.html': '<script>', 'record.html': '<script>', 'scripts.json': '{', 'embed.js': 'Dikduk'}

def static_text(name):
    """a static file by name: GitHub's copy when it answers and looks whole, else the local file"""
    assert name in STATIC_OK
    now = time.time(); P = _PAGES.setdefault(name, {'t': 0.0, 'body': None})
    if PAGE_BASE and now - P['t'] > 60:
        P['t'] = now
        try:
            r = requests.get(PAGE_BASE + name, timeout=8, headers={'Cache-Control': 'no-cache'})
            if r.ok and STATIC_OK[name] in r.text and (not name.endswith('.html') or '</script>' in r.text): P['body'] = r.text
        except Exception as e:
            print('static from github failed:', name, e, flush=True)
    return P['body'] or open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', name), encoding='utf-8').read()

def page_body():
    return static_text('index.html')

@app.get('/', response_class=HTMLResponse)
def home():
    """the lab page itself, from the same origin so the phone's microphone works in it"""
    try:
        body = page_body()
    except Exception:
        return HTMLResponse('<p>dikduk fit-score server is running. See /health.</p>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}[hidden]{display:none!important}</style>'
            '</head><body>' + body + '</body></html>')

@app.get('/try', response_class=HTMLResponse)
def try_page():
    """the visitor page: the same lab page with the lab panels hidden (for a hazzan or a student to try the checker)"""
    return home()

@app.get('/health')
def health():
    return {'ok': True, 'version': 4.3, 'device': DEV, 'threads': THREADS, 'cpu_count': os.cpu_count(), 'uptime_s': int(time.time() - T_START), 'phone_model': PH_ID, 'arabic_model': AR_ID, 'vocab': len(VOCAB), 'classifiers': list(CLF),
            'page_from': 'github' if (_PAGES.get('index.html') or {}).get('body') else 'local', 'jobs': {'queued': sum(1 for v in JOBS.values() if v['state'] == 'queued'), 'running': sum(1 for v in JOBS.values() if v['state'] == 'running')},
            'ears': {'letter_head': HEAD is not None, 'vowel_head': FULL is not None, 'fine_tuned': FT is not None, 'classifier_v2': bool(CLF2), 'tehillim_lyrics': len(TEHILLIM_LYR), 'tehillim_audio': os.path.isdir(TEHILLIM_DIR) and len(os.listdir(TEHILLIM_DIR)) or (TEHILLIM_BASE or 0),
                     'tehillim_perakim': sorted(int(m.group(1)) for m in (re.match(r'tehillim-(\d{3})\.mp3$', f) for f in (os.listdir(TEHILLIM_DIR) if os.path.isdir(TEHILLIM_DIR) else [])) if m)}}

@app.get('/info')
def info():
    return {'phone_model': PH_ID, 'phones': list(VOCAB.keys()), 'throat': THROAT, 'alt': ALT, 'emb_layer': EMB_LAYER}

_LYR = {'t': 0, 'data': None}

def warm_up():
    """after start: analyse Rabbi Alouf's pesukim of the perakim whose audio is here (23 first), so a visitor's first
       check does not wait a minute for the hazzan's line; cached under DK_CACHE like any reference"""
    try:
        time.sleep(5)
        for n in (23, 1, 121, 130, 150, 117, 133, 134):
            s = TEHILLIM_LYR.get(f't{n}'); f = f'tehillim-{n:03d}.mp3'
            if not s or not tehillim_file(f): continue
            ev = [tuple(map(int, x.split(','))) for x in s['t'].get(f, '').split(';') if x]
            for i, (t, k) in enumerate(ev):
                if k < 0: continue
                t1 = ev[i + 1][0] / 10 if i + 1 < len(ev) else t / 10 + 8
                try: ref_line(f, t / 10, t1, he_words(s['l'][k]))
                except Exception as e: print('warm-up skip', n, k, str(e)[:80], flush=True)
            print('warm-up done: perek', n, flush=True)
    except Exception as e:
        print('warm-up stopped:', e, flush=True)
if not os.environ.get('DK_NO_WARM'): threading.Thread(target=warm_up, daemon=True).start()

TEHILLIM_LYR = {}
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lyrics_tehillim.json'), encoding='utf-8') as f:
        TEHILLIM_LYR = json.load(f).get('s', {})
    print('tehillim lyrics:', len(TEHILLIM_LYR), 'perakim', flush=True)
except Exception as e:
    print('no tehillim lyrics:', e, flush=True)
try:
    from nikud import parse_verse
except Exception as e:
    parse_verse = None; print('no nikud parser:', e, flush=True)

@app.get('/tehillim/audio/{fname}')
def tehillim_audio(fname: str):
    tf = tehillim_file(fname)
    if tf: return FileResponse(tf, media_type='audio/mpeg')
    if tf == '' and TEHILLIM_BASE: return RedirectResponse(TEHILLIM_BASE.rstrip('/') + '/' + fname)
    return JSONResponse({'err': 'no such Tehillim file here'}, status_code=404)

@app.get('/lyrics')
def lyrics():
    """the site's lyrics.json (445 pizmonim: lines, and for each recording the line start times), passed through with
       CORS so a page on another origin can read it; refreshed once an hour"""
    if _LYR['data'] is None or time.time() - _LYR['t'] > 3600:
        try:
            r = requests.get(LYRICS_URL, headers=UA, timeout=60)
            r.raise_for_status()
            _LYR['data'] = r.json(); _LYR['t'] = time.time()
        except Exception as e:
            if _LYR['data'] is None:
                if not TEHILLIM_LYR: return JSONResponse({'err': 'lyrics: ' + str(e)[:200]}, status_code=502)
                _LYR['data'] = {'v': 1, 's': {}}
    if TEHILLIM_LYR and not _LYR['data'].get('_th'):
        _LYR['data'] = {**_LYR['data'], 's': {**_LYR['data'].get('s', {}), **TEHILLIM_LYR}, '_th': True}
    return _LYR['data']

REF_TAG = 'v4.1'   # part of the reference cache key: a new server version re-analyses the hazzan's lines

def ref_line(f: str, t0: float, t1: float, words, want_emb=False):
    key = os.path.join(CACHE_DIR, 'ref_' + hashlib.sha1(f'{REF_TAG}|{f}|{t0}|{t1}|{" ".join(words)}|{int(want_emb)}'.encode()).hexdigest() + '.json')
    if os.path.exists(key):
        return json.load(open(key, encoding='utf-8'))
    x = decode_audio(fetch_archive(f))
    seg = x[int(max(0, t0) * SR):int(t1 * SR)] if t1 > 0 else x
    if seg.shape[0] < SR * 0.3:
        raise ValueError('the line is empty at those times')
    res, lp, spf = analyse(seg, words, want_emb)
    res['f'] = f; res['t0'] = t0; res['t1'] = t1
    # the hazzan against himself: the ceiling each word can reach
    self_fit = fit_against(lp, spf, res['words'])
    for w, s in zip(res['words'], self_fit): w['selffit'] = s.get('fit')
    json.dump(res, open(key, 'w', encoding='utf-8'), ensure_ascii=False)
    return res

@app.get('/ref')
def ref(f: str, words: str, t0: float = 0, t1: float = 0, emb: int = 0):
    W = he_words(words)
    if not W:
        return JSONResponse({'err': 'no words'}, status_code=400)
    try:
        return ref_line(f, t0, t1, W, bool(emb))
    except Exception as e:
        return JSONResponse({'err': str(e)[:300]}, status_code=502)

DRILL_DIR = os.path.join(CACHE_DIR, 'drill'); os.makedirs(DRILL_DIR, exist_ok=True)

@app.get('/drill')
def drill_list():
    """the drill recordings kept on this server (features + David's label), newest last"""
    items = []
    for fn in sorted(os.listdir(DRILL_DIR)):
        try:
            d = json.load(open(os.path.join(DRILL_DIR, fn), encoding='utf-8'))
            items.append({'id': fn[:-5], 'word': d['word'], 'style': d['style'], 'c': d['c'], 'v': d.get('v'), 'p': d.get('p'), 'ar_heard': d.get('ar_heard'), 't': d['t']})
        except Exception: pass
    return {'n': len(items), 'items': items}

@app.get('/drill/export')
def drill_export():
    """everything, features included (for training the next classifier)"""
    return [json.load(open(os.path.join(DRILL_DIR, fn), encoding='utf-8')) for fn in sorted(os.listdir(DRILL_DIR)) if fn.endswith('.json')]

# ---- jobs: a check can take longer than the reverse proxy in front of a Space allows one request (the first check of
# a line analyses the hazzan's line too; on 2 vCPUs that is 30–60 s). With job=1 the check is queued, the request
# returns at once with a job id, and the page polls /job/<id> every second or two until the result is there. One
# worker thread runs the queue, so two visitors never run the models at the same time (which would slow both).
JOBS = {}; JOB_Q = queue.Queue(); JOB_LOCK = threading.Lock()

def new_job(fn):
    jid = uuid.uuid4().hex[:12]
    with JOB_LOCK:
        JOBS[jid] = {'state': 'queued', 'stage': 'waiting for the server', 't': time.time()}
    JOB_Q.put((jid, fn))
    return jid

def job_worker():
    while True:
        jid, fn = JOB_Q.get()
        J = JOBS.get(jid)
        if J is None: continue
        J['state'] = 'running'; J['stage'] = 'starting'
        try:
            J['result'] = fn(lambda s: J.__setitem__('stage', s)); J['state'] = 'done'
        except Exception as e:
            J['err'] = str(e)[:300]; J['state'] = 'error'
        J['t'] = time.time()
        with JOB_LOCK:   # results are kept a quarter of an hour
            for k in [k for k, v in JOBS.items() if v['state'] in ('done', 'error') and time.time() - v['t'] > 900]: JOBS.pop(k, None)
threading.Thread(target=job_worker, daemon=True).start()

@app.get('/job/{jid}')
def job_status(jid: str):
    J = JOBS.get(jid)
    if J is None:
        return JSONResponse({'err': 'no such job (the server may have restarted); check again', 'state': 'gone'}, status_code=404)
    out = {'state': J['state'], 'stage': J.get('stage'), 'queued': sum(1 for v in JOBS.values() if v['state'] == 'queued')}
    if J['state'] == 'done': out['result'] = J['result']
    if J['state'] == 'error': out['err'] = J.get('err')
    return out

@app.post('/check')
async def check(request: Request, words: str = Query(...), ref: str = None, t0: float = 0, t1: float = 0, emb: int = 0, drill: str = None, nikud: str = None, job: int = 0):
    W = he_words(words)
    if not W:
        return JSONResponse({'err': 'no words'}, status_code=400)
    data = await request.body()
    if len(data) < 1000:
        return JSONResponse({'err': 'no audio'}, status_code=400)
    try:
        x = await run_in_threadpool(decode_audio, data)
    except Exception as e:
        return JSONResponse({'err': 'decode: ' + str(e)[:200]}, status_code=400)
    if x.shape[0] < SR * 0.5:
        return JSONResponse({'err': 'too short'}, status_code=400)
    if x.shape[0] > SR * 40:
        x = x[:SR * 40]
    if job:
        return JSONResponse({'job': new_job(lambda progress: run_check(x, W, ref, t0, t1, emb, drill, nikud, progress))}, status_code=202)
    # the plain path (scripts, older pages): the same work in a thread, so /health and the polls keep answering
    return await run_in_threadpool(run_check, x, W, ref, t0, t1, emb, drill, nikud)

def run_check(x, W, ref, t0, t1, emb, drill, nikud, progress=lambda s: None):
    progress('listening to your take')
    take, lp, spf = analyse(x, W, bool(emb) or bool(drill))
    out = {'words': W, 'take': take}
    for w in take['words']: w['pw'] = word_pw(w, None)
    if drill in ('throat', 'plain'):
        # a drill recording: one word, said from the throat or plain; kept with its features for the next classifier
        for w in take['words']:
            for th in w['throat']:
                rec = {'t': int(time.time()), 'word': w['w'], 'k': th['k'], 'c': th['c'], 'style': drill, 'v': th.get('v'), 'p': th.get('p'),
                       'ar_heard': th.get('ar_heard'), 'ar': th.get('ar'), 'peak': th.get('peak'), 'feat': th.get('feat'), 'win': [th['t0'], th['t1']]}
                fn = f"{rec['t']}_{abs(hash((w['w'], th['k'], drill))) % 100000}.json"
                json.dump(rec, open(os.path.join(DRILL_DIR, fn), 'w', encoding='utf-8'), ensure_ascii=False)
                th.pop('feat', None)
        out['drill_saved'] = len(os.listdir(DRILL_DIR))
    if ref:
        try:
            progress("listening to the hazzan's line")
            R = ref_line(ref, t0, t1, W, bool(emb))
            out['ref'] = R
            out['fit'] = fit_against(lp, spf, R['words'])
            if FULL is not None or FT is not None:
                out['vowels'] = compare_vowels({i: w.get('vow', []) for i, w in enumerate(take['words'])}, {i: w.get('vow', []) for i, w in enumerate(R['words'])})
        except Exception as e:
            out['ref_err'] = str(e)[:300]
    if nikud and (FULL is not None or FT is not None):
        # a pointed line (Tehillim): the vowels expected from the nikud, word by word
        try:
            exp = {i: [{'heard': u['c']} for u in us if u['kind'] == 'vowel'] for i, (_, _, us) in enumerate(parse_verse(nikud))}
            if len(exp) == len(W):
                out['vowels_nikud'] = compare_vowels({i: w.get('vow', []) for i, w in enumerate(take['words'])}, exp)
        except Exception as e:
            out['nikud_err'] = str(e)[:200]
    out['vowel_names'] = VOWEL_NAME
    return out

# ================================================================= the recording booth (/record)
# A page that walks a person through a list of short recordings — read this line right; read it with the ayin in
# this word said like alef; leave a word out and tap which — and keeps every recording with its label. Nothing is
# judged on the page: the person records, the server checks each take in the background and keeps the verdicts
# next to the audio, and the scoreboard (/score) compares the two. That is the training and testing data in one.
# Recordings live in TAKES_DIR: /data/takes when the Space has persistent storage, else under DK_CACHE (gone on a
# rebuild) — and every file is mirrored to a private GitHub repo when GH_TOKEN is set (a fine-grained token with
# "Contents: read and write" on that one repo), so nothing is lost either way.
import base64, uuid as _uuid
TAKES_DIR = os.path.join('/data', 'takes') if os.path.isdir('/data') and os.access('/data', os.W_OK) else os.path.join(CACHE_DIR, 'takes')
os.makedirs(TAKES_DIR, exist_ok=True)
GH_TOKEN = os.environ.get('GH_TOKEN', '') if os.environ.get('DK_MIRROR', 'github' if os.environ.get('SPACE_ID') else '') == 'github' else ''
GH_REPO = os.environ.get('GH_REPO', 'davidsitt810-ops/dikduk-recordings')
# Other people's recordings and names are not public: listing them, fetching their audio and the all-hands scoreboard
# need the key David sets as the Space secret DK_KEY. A person sees their own scoreboard with the token their phone
# made (sent with each take). Locally, with no key set, everything is open; on a Space with no key set, it is closed.
DK_KEY = os.environ.get('DK_KEY', '')

def key_ok(key):
    if DK_KEY: return key == DK_KEY
    return not os.environ.get('SPACE_ID')

def need_key(key):
    if not key_ok(key): return JSONResponse({'err': 'this needs the key (the Space secret DK_KEY)' if DK_KEY or os.environ.get('SPACE_ID') else 'no key set'}, status_code=403)
PHR_TIMES = {"md cd08 15.mp3": [[0.35, 6.9, 0], [7.4, 14, 1], [20.75, 27.7, 2], [28.1, 34.35, 3], [41.4, 50.25, 4], [50.5, 55.25, 5], [55.7, 61.35, 6], [61.85, 66.5, 7]]}

def sync_lines(s, f):
    """line k -> (t0, t1) from a recording's sync events, as the page computes them"""
    if f in PHR_TIMES: return {k: (a, b) for a, b, k in PHR_TIMES[f]}
    ev = [tuple(map(int, x.split(','))) for x in ((s.get('t') or {}).get(f) or '').split(';') if x]; out = {}
    for i, (t, k) in enumerate(ev):
        if k < 0 or k in out: continue
        out[k] = (t / 10, ev[i + 1][0] / 10 if i + 1 < len(ev) else t / 10 + 8)
    return out

def resolve_text(spec: str):
    """'t23:1' (Tehillim perek:pasuk) or '200:3' (pizmon:line) or plain Hebrew words -> what a check needs"""
    data = lyrics(); S = data.get('s', {}) if isinstance(data, dict) else {}
    m = re.fullmatch(r't(\d+):(\d+)', spec.strip())
    if m:
        n, k = int(m.group(1)), int(m.group(2)) - 1; s = S.get(f't{n}')
        if not s or k >= len(s['l']): raise ValueError(f'no Tehillim {n}:{k + 1}')
        out = {'label': f'Tehillim {n}:{k + 1}', 'words': s['l'][k], 'nikud': (s.get('ln') or [None] * len(s['l']))[k], 'ref': None, 't0': None, 't1': None}
        f = f'tehillim-{n:03d}.mp3'
        if tehillim_file(f) and f in (s.get('t') or {}):
            L = sync_lines(s, f)
            if k in L: out.update({'ref': f, 't0': L[k][0], 't1': L[k][1]})
        return out
    m = re.fullmatch(r't(\d+)', spec.strip())
    if m:
        n = int(m.group(1)); s = S.get(f't{n}')
        if not s: raise ValueError(f'no Tehillim {n}')
        return {'label': f'Tehillim {n}, the whole perek', 'words': ' '.join(s['l']), 'nikud': ' '.join(s.get('ln') or []), 'ref': None, 't0': None, 't1': None, 'lines': s['l'], 'nlines': s.get('ln')}
    m = re.fullmatch(r'(\d+):(\d+)', spec.strip())
    if m:
        pid, k = m.group(1), int(m.group(2)) - 1; s = S.get(pid)
        if not s or k >= len(s['l']): raise ValueError(f'no pizmon {pid} line {k + 1}')
        out = {'label': f'pizmon {pid} line {k + 1}', 'words': s['l'][k], 'nikud': None, 'ref': None, 't0': None, 't1': None}
        recs = list((s.get('t') or {}).keys()); b = s.get('b') if s.get('b') in recs else (recs[0] if recs else None)
        if b:
            L = sync_lines(s, b)
            if k in L: out.update({'ref': b, 't0': L[k][0], 't1': L[k][1]})
        return out
    return {'label': 'words', 'words': spec, 'nikud': None, 'ref': None, 't0': None, 't1': None}

@app.get('/record', response_class=HTMLResponse)
def record_page():
    """the booth"""
    body = static_text('record.html')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}[hidden]{display:none!important}</style>'
            '</head><body>' + body + '</body></html>')

@app.get('/embed.js')
def embed_js():
    """the drop-in checker for a site page (see the top of static/embed.js)"""
    from fastapi.responses import Response
    return Response(static_text('embed.js'), media_type='application/javascript; charset=utf-8', headers={'Cache-Control': 'public, max-age=300'})

@app.get('/scripts')
def scripts():
    """the recording lists (sets), each task with its text resolved"""
    try:
        J = json.loads(static_text('scripts.json'))
    except Exception as e:
        return JSONResponse({'err': 'scripts: ' + str(e)[:200]}, status_code=500)
    for name, st in J.items():
        for t in st.get('tasks', []):
            try:
                R = resolve_text(t['text']); t['label'] = R['label']; t['words'] = R['words']; t['nikud'] = R['nikud']; t['ref'] = R['ref']; t['t0'] = R['t0']; t['t1'] = R['t1']
                if R.get('lines'): t['lines'] = R['lines']; t['nlines'] = R.get('nlines')
            except Exception as e:
                t['error'] = str(e)[:120]
    return J

def safe_name(x, n=40):
    return re.sub(r'[^\w֐-׿-]+', '_', str(x or ''))[:n].strip('_') or 'anon'

def gh_put(path, data: bytes, message: str):
    """one file into the mirror repo (GitHub contents API; the path is new, so no sha is needed)"""
    r = requests.put(f'https://api.github.com/repos/{GH_REPO}/contents/{requests.utils.quote(path)}',
                     headers={'Authorization': 'Bearer ' + GH_TOKEN, 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'},
                     json={'message': message, 'content': base64.b64encode(data).decode(), 'branch': 'main'}, timeout=60)
    if r.status_code == 422 and 'sha' in r.text:   # it is already there (a retry): fetch the sha and overwrite
        g = requests.get(f'https://api.github.com/repos/{GH_REPO}/contents/{requests.utils.quote(path)}', headers={'Authorization': 'Bearer ' + GH_TOKEN}, timeout=60)
        if g.ok:
            r = requests.put(f'https://api.github.com/repos/{GH_REPO}/contents/{requests.utils.quote(path)}', headers={'Authorization': 'Bearer ' + GH_TOKEN, 'Accept': 'application/vnd.github+json'},
                             json={'message': message, 'content': base64.b64encode(data).decode(), 'branch': 'main', 'sha': g.json().get('sha')}, timeout=60)
    r.raise_for_status()

def mirror_pending():
    """push every take file that has no .pushed marker yet"""
    if not GH_TOKEN: return 0
    n = 0
    for root, _, files in os.walk(TAKES_DIR):
        for fn in sorted(files):
            if fn.endswith('.pushed') or fn.endswith('.tmp'): continue
            full = os.path.join(root, fn)
            if os.path.exists(full + '.pushed'): continue
            if fn.endswith('.json'):
                try:
                    if not json.load(open(full, encoding='utf-8')).get('graded', True): continue   # wait for the verdicts
                except Exception: continue
            rel = os.path.relpath(full, TAKES_DIR).replace(os.sep, '/')
            try:
                gh_put('takes/' + rel, open(full, 'rb').read(), 'take ' + rel); open(full + '.pushed', 'w').write(str(int(time.time()))); n += 1
            except Exception as e:
                print('mirror failed:', rel, str(e)[:120], flush=True); return n
    return n

def mirror_ok():
    """is the mirror repo reachable with this token? (checked once at start; a wrong token or a missing repo turns the mirror off, loudly)"""
    global GH_TOKEN
    if not GH_TOKEN: return False
    try:
        r = requests.get(f'https://api.github.com/repos/{GH_REPO}', headers={'Authorization': 'Bearer ' + GH_TOKEN, 'Accept': 'application/vnd.github+json'}, timeout=20)
        if r.ok and r.json().get('permissions', {}).get('push'): print('mirror: recordings go to github.com/' + GH_REPO, flush=True); return True
        print('mirror OFF: github answered', r.status_code, flush=True)
    except Exception as e:
        print('mirror OFF:', e, flush=True)
    GH_TOKEN = ''
    return False

def mirror_loop():
    if not mirror_ok(): return
    while True:
        try: mirror_pending()
        except Exception as e: print('mirror loop:', e, flush=True)
        time.sleep(60)
if GH_TOKEN: threading.Thread(target=mirror_loop, daemon=True).start()

def take_paths(tid):
    """id -> (json path, audio path); the id is the json's path relative to TAKES_DIR without .json"""
    tid = tid.replace('..', '').strip('/'); jp = os.path.join(TAKES_DIR, tid + '.json')
    if not os.path.isfile(jp): return None, None
    base = jp[:-5]; aud = [p for p in (base + e for e in ('.m4a', '.mp4', '.webm', '.wav', '.mp3', '.ogg', '.bin')) if os.path.isfile(p)]
    return jp, (aud[0] if aud else None)

@app.post('/submit')
async def submit(request: Request, meta: str = Query(...)):
    """one recording from the booth: body = audio; meta = JSON {set, task, name, text, do, labels, note, mime, device}.
       Saved at once, checked in the background (the verdicts land in the take's JSON), mirrored to GitHub if set up."""
    try:
        M = json.loads(meta)
    except Exception:
        return JSONResponse({'err': 'bad meta'}, status_code=400)
    data = await request.body()
    if len(data) < 1000:
        return JSONResponse({'err': 'no audio'}, status_code=400)
    try:
        R = resolve_text(M.get('text', ''))
    except Exception as e:
        return JSONResponse({'err': str(e)[:200]}, status_code=400)
    mime = str(M.get('mime') or ''); ext = '.m4a' if 'mp4' in mime or 'm4a' in mime else '.webm' if 'webm' in mime else '.wav' if 'wav' in mime else '.ogg' if 'ogg' in mime else '.bin'
    ts = time.strftime('%Y%m%d-%H%M%S'); tid = f"{safe_name(M.get('set'))}/{safe_name(M.get('name'))}/{ts}-{safe_name(M.get('task'), 24)}-{_uuid.uuid4().hex[:6]}"
    full = os.path.join(TAKES_DIR, tid); os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full + ext, 'wb').write(data)
    rec = {'id': tid, 't': int(time.time()), 'set': M.get('set'), 'task': M.get('task'), 'name': M.get('name'), 'who': str(M.get('who') or '')[:40], 'text': M.get('text'), 'label': R['label'], 'words': R['words'],
           'do': M.get('do'), 'labels': M.get('labels'), 'note': M.get('note'), 'mime': mime, 'bytes': len(data), 'device': str(M.get('device') or '')[:200], 'check': bool(M.get('check', True)),
           'graded': False, 'result': None}
    json.dump(rec, open(full + '.json', 'w', encoding='utf-8'), ensure_ascii=False)
    if rec['check']:
        def grade(progress):
            try:
                x = decode_audio(data)
                if x.shape[0] > SR * 40: x = x[:SR * 40]
                if x.shape[0] < SR * 0.5: raise ValueError('too short')
                out = run_check(x, he_words(R['words']), R['ref'], R['t0'] or 0, R['t1'] or 0, 0, None, R['nikud'], progress)
                rec['summary'] = summarize(out)
                out.pop('ref', None)   # the hazzan's analysis is big and lives in the reference cache anyway
                rec['result'] = out
            except Exception as e:
                rec['error'] = str(e)[:200]
            rec['graded'] = True; json.dump(rec, open(full + '.json', 'w', encoding='utf-8'), ensure_ascii=False)
            return {'ok': True}
        new_job(grade)
    else:
        rec['graded'] = True; json.dump(rec, open(full + '.json', 'w', encoding='utf-8'), ensure_ascii=False)
    return JSONResponse({'id': tid, 'saved': True, 'durable': bool(GH_TOKEN) or TAKES_DIR.startswith('/data')}, status_code=202)

def mark_of(y, f, clean):
    """the page's rule for one word (kept in step with static/index.html markOf)"""
    n = y.get('n') or 0; sk = y.get('skel'); ft = f.get('fit') if f else None
    if not n or sk is None: return ''
    kp = y.get('kept'); pw = y.get('pw'); hs = y.get('hskel')
    sure = clean and kp is not None and kp >= .75 and hs is not None and hs >= .6 and (pw is None or pw < .8)
    if n >= 2:
        if sk < .2 and (ft is None or ft < .15):
            if ft is None and clean and not (kp is not None and kp < .75): return 'unsure'   # no hazzan to confirm: red needs the head's agreement
            return 'off'
        if clean and pw is not None and pw >= .95: return 'off'
        if sure: return 'ok'
        if sk < .4 or (ft is not None and ft < .2) or (kp is not None and kp < .5) or (pw is not None and pw >= .8): return 'unsure'
        return 'ok'
    return 'unsure' if sk < .2 and not sure else 'ok'

RULE = {'drop': 10, 'margin': 4, 'swap': 8, 'gap': 0.6}   # kept in step with static/index.html and embed.js

def marks_of(TW, F, gap, clean):
    """the page's verdict per word (markOf + the whole-line evidence on a clean take) -> (marks, why, line_wrong)"""
    marks = [mark_of(TW[i], F[i] if F else None, clean) for i in range(len(TW))]; why = [None] * len(TW); line_wrong = False
    if clean and TW:
        ds = [t['drop'] if t.get('drop') is not None else -1e9 for t in TW]; top = int(np.argmax(ds)); second = max([d for i, d in enumerate(ds) if i != top], default=-1e9)
        if (TW[top].get('n') or 0) >= 2 and ds[top] >= RULE['drop'] and ds[top] - second >= RULE['margin']: marks[top] = 'off'; why[top] = 'dropped'
        for j in range(len(TW) - 1):
            g = TW[j].get('swap')
            if g is not None and g >= RULE['swap'] and (TW[j].get('n') or 0) >= 2 and (TW[j + 1].get('n') or 0) >= 2: marks[j] = marks[j + 1] = 'off'; why[j] = why[j + 1] = 'swapped'
        if gap is not None and gap >= RULE['gap']:
            line_wrong = True; marks = ['unsure' if m == 'ok' else m for m in marks]
    return marks, why, line_wrong

def summarize(out):
    """the machine's claims about one take, in the page's words: marks per word, throat verdicts, vowel differences"""
    W, TW, F = out['words'], out['take']['words'], out.get('fit')
    hs = sorted(t['hskel'] for t in TW if (t.get('n') or 0) >= 2 and t.get('hskel') is not None); clean = bool(hs) and hs[len(hs) // 2] >= .7
    marks, why, line_wrong = marks_of(TW, F, out['take'].get('gap'), clean)
    RW = (out.get('ref') or {}).get('words')
    def hv(i, k):
        if not RW or i >= len(RW): return None
        r = next((x for x in (RW[i].get('throat') or []) if x.get('k') == k), None); return r.get('v') if r else None
    throat = [{'c': th['c'], 'w': W[i], 'k': th['k'], 'v': th.get('v'), 'hazzan': hv(i, th['k'])} for i, t in enumerate(TW) for th in (t.get('throat') or [])]
    VN = out.get('vowel_names') or {}; nm = lambda k: (VN.get(k) or k).split(' ')[0]
    vow = []
    for src, against in ((out.get('vowels'), 'hazzan'), (out.get('vowels_nikud'), 'nikud')):
        for i, ds in (src or {}).items():
            for d in ds: vow.append({'w': W[int(i)], 'k': d['k'], 'you': nm(d['you']), 'ref': nm(d['ref']), 'against': against})
    miss = {W[i]: t['miss'] for i, t in enumerate(TW) if t.get('miss')}
    return {'marks': marks, 'why': why, 'line_wrong': line_wrong, 'gap': out['take'].get('gap'), 'throat': throat, 'vowels': vow, 'miss': miss, 'clean': clean, 'hazzan': bool(F), 'dur': out['take'].get('dur')}

def list_takes(set_=None, name=None, who=None):
    items = []
    for root, _, files in os.walk(TAKES_DIR):
        for fn in files:
            if not fn.endswith('.json'): continue
            try: J = json.load(open(os.path.join(root, fn), encoding='utf-8'))
            except Exception: continue
            if set_ and J.get('set') != set_: continue
            if name and J.get('name') != name: continue
            if who and J.get('who') != who: continue
            J.pop('result', None); items.append(J)
    items.sort(key=lambda j: j.get('t', 0))
    return items

@app.get('/takes')
def takes(set_: str = Query(None, alias='set'), name: str = None, key: str = None):
    """every recording's label and verdicts (no audio) — with the key"""
    d = need_key(key)
    if d: return d
    items = list_takes(set_, name)
    return {'n': len(items), 'dir': 'persistent' if TAKES_DIR.startswith('/data') else 'temporary', 'mirror': bool(GH_TOKEN), 'items': items}

@app.get('/takes/full/{tid:path}')
def take_full(tid: str, key: str = None):
    d = need_key(key)
    if d: return d
    jp, _ = take_paths(tid)
    if not jp: return JSONResponse({'err': 'no such take'}, status_code=404)
    return json.load(open(jp, encoding='utf-8'))

@app.get('/takes/audio/{tid:path}')
def take_audio(tid: str, key: str = None):
    d = need_key(key)
    if d: return d
    jp, ap = take_paths(tid)
    if not ap: return JSONResponse({'err': 'no such take'}, status_code=404)
    return FileResponse(ap, media_type={'m4a': 'audio/mp4', 'mp4': 'audio/mp4', 'webm': 'audio/webm', 'wav': 'audio/wav', 'mp3': 'audio/mpeg', 'ogg': 'audio/ogg'}.get(ap.rsplit('.', 1)[-1], 'application/octet-stream'), filename=os.path.basename(ap))

def score_take(J):
    """one take: what the person did (its labels) against what the machine claimed -> verdict lines and tallies"""
    S = J.get('summary'); do = J.get('do') or 'right'; L = J.get('labels') or {}; W = he_words(J.get('words') or '')
    if not J.get('check', True): return {'state': 'stored'}
    if not J.get('graded'): return {'state': 'waiting'}
    if not S: return {'state': 'error', 'why': J.get('error') or 'no result'}
    marks = dict(zip(W, S['marks'])); claims = []; tally = {'false_alarm': 0, 'caught': 0, 'missed': 0, 'unsure': 0, 'claims': 0}
    changed = set(L.get('words') or [])
    if do in ('skip', 'wrong', 'swap', 'free', 'vowel') and L.get('word'): changed.add(L['word'])
    if do == 'swap': changed |= set(L.get('pair') or [])
    # words
    for w in W:
        m = marks.get(w, '')
        if w in changed and do in ('skip', 'wrong', 'swap', 'free'):
            if m == 'off': tally['caught'] += 1; claims.append(f'{w}: you changed it, machine said not heard ✓')
            elif m == 'unsure': tally['unsure'] += 1; claims.append(f'{w}: you changed it, machine said not sure ~')
            else: tally['missed'] += 1; claims.append(f'{w}: you changed it, machine passed it ✕')
        else:
            if m == 'off': tally['false_alarm'] += 1; claims.append(f'{w}: you sang it, machine said not heard ✕ (false alarm)')
            elif m == 'unsure': tally['unsure'] += 1; claims.append(f'{w}: you sang it, machine said not sure ~')
    # throat letters
    for th in S['throat']:
        planted = (do == 'ayin' and th['c'] == 'ע' or do == 'het' and th['c'] == 'ח') and (not L.get('word') or L.get('word') == th['w']) and L.get('done', True)
        if planted:
            if th['v'] == 'plain': tally['caught'] += 1; claims.append(f"{th['c']} in {th['w']}: you said it plain, machine heard plain ✓")
            elif th['v'] == 'unsure': tally['unsure'] += 1; claims.append(f"{th['c']} in {th['w']}: you said it plain, machine not sure ~")
            else: tally['missed'] += 1; claims.append(f"{th['c']} in {th['w']}: you said it plain, machine heard the throat ✕")
        else:
            if th['v'] == 'plain' and th.get('hazzan') == 'plain': claims.append(f"{th['c']} in {th['w']}: plain, as the hazzan says it there (not counted)")
            elif th['v'] == 'plain': tally['false_alarm'] += 1; claims.append(f"{th['c']} in {th['w']}: machine said plain ✕ (false alarm, unless you did say it plain)")
            elif th['v'] == 'unsure': tally['unsure'] += 1; claims.append(f"{th['c']} in {th['w']}: machine not sure ~")
    # vowels
    vw = [v for v in S['vowels']]
    if do == 'vowel' and L.get('word'):
        hit = [v for v in vw if v['w'] == L['word']]
        if hit: tally['caught'] += 1; claims.append(f"{L['word']}: you changed a vowel, machine heard {hit[0]['you']} for {hit[0]['ref']} ✓")
        else: tally['missed'] += 1; claims.append(f"{L['word']}: you changed a vowel, machine heard nothing ✕")
        vw = [v for v in vw if v['w'] != L['word']]
    for v in vw:
        tally['claims'] += 1; claims.append(f"{v['w']}: machine says you sang {v['you']} where the {v['against']} has {v['ref']} — right or wrong?")
    return {'state': 'scored', 'claims': claims, 'tally': tally, 'clean': S['clean'], 'hazzan': S['hazzan']}

@app.get('/score')
def score(set_: str = Query(None, alias='set'), name: str = None, who: str = None, key: str = None):
    """the scoreboard: every take scored against its own label, and the totals. A person's own takes with the
       token their phone sent (who); everyone's with the key."""
    if not who:
        d = need_key(key)
        if d: return d
    items = list_takes(set_, name, who); rows = []; tot = {'false_alarm': 0, 'caught': 0, 'missed': 0, 'unsure': 0, 'claims': 0, 'waiting': 0, 'error': 0, 'stored': 0}
    for J in items:
        sc = score_take(J); rows.append({'id': J['id'], 'task': J.get('task'), 'label': J.get('label'), 'words': J.get('words'), 'do': J.get('do'), 'labels': J.get('labels'), 'note': J.get('note'), 'name': J.get('name'), 't': J.get('t'), **sc})
        if sc['state'] == 'scored':
            for k, v in sc['tally'].items(): tot[k] += v
        else: tot[sc['state']] += 1
    return {'n': len(rows), 'totals': tot, 'rows': rows}
