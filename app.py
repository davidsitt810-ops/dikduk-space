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
import os, re, sys, json, time, hashlib, subprocess, tempfile, threading, queue, uuid, shutil, urllib.parse, asyncio
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
# DK_DEVICE=mps uses an Apple-Silicon Mac's GPU (mac/bench.sh compares it with the CPU: the numbers differ in the last
# digits, as CUDA's do); anything else, or a GPU that fails to load, means CPU. The heads and the aligner stay on the
# CPU either way.
DEV = 'cpu'
if os.environ.get('DK_DEVICE', '').lower().startswith('cuda') and torch.cuda.is_available(): DEV = 'cuda'
elif os.environ.get('DK_DEVICE', '').lower().startswith('mps') and getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available(): DEV = 'mps'
SR = 16000
ARCHIVE = 'https://www.pizmonim.org/MP3/'
UA = {'User-Agent': 'Mozilla/5.0 (pizmonim dikduk checker)', 'Accept': '*/*'}
CACHE_DIR = os.environ.get('DK_CACHE', '/tmp/dkcache')
os.makedirs(CACHE_DIR, exist_ok=True)

def data_writable():
    """is /data (a Space's persistent storage) there AND writable by this process? Tried with a file, not os.access:
       a mount can be there and still refuse the app's user, and then everything would quietly go to /tmp"""
    if not os.path.isdir('/data'): return False
    p = os.path.join('/data', f'.dk_write_test_{os.getpid()}')
    try:
        with open(p, 'w') as f: f.write('ok')
        os.unlink(p); return True
    except Exception as e:
        print('/data is there but not writable:', e, flush=True); return False
# Where recordings (booth takes, drill items) are kept: /data when it works, else under DK_CACHE. Kept means: on /data,
# on a disk the owner says is kept (DK_DURABLE=1: the Mac), or mirrored to GitHub (GH_TOKEN, below). Anything else
# (a Space's /tmp, Colab) is gone at the next rebuild, restart or sleep, and the booth says so before anyone records.
DATA_OK = data_writable()
KEEP_DIR = '/data' if DATA_OK else CACHE_DIR
# On a Mac the default is "kept" unless DK_CACHE is in a temporary folder (installs made before v4.8 have no DK_DURABLE)
_MAC_KEPT = sys.platform == 'darwin' and not os.path.realpath(CACHE_DIR).startswith(('/tmp', '/private/tmp', '/var/folders', '/private/var/folders'))
DURABLE_DISK = DATA_OK or os.environ.get('DK_DURABLE', '1' if _MAC_KEPT else '') == '1'
LYRICS_URL = os.environ.get('DK_LYRICS', 'https://holiday.thepizmonim.pages.dev/app/lyrics.json')
EMB_LAYER = int(os.environ.get('DK_EMB_LAYER', '16'))   # an extra hidden layer kept in drill features (of 24)

from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(_app):
    housekeeping()   # defined below; runs when uvicorn starts serving, not when a tool imports this file
    yield
app = FastAPI(title='dikduk fit-score', lifespan=lifespan)
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
    ck = torch.load(os.environ.get('DK_LETTER_HEAD') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'letter_head.pt'), map_location='cpu')   # DK_LETTER_HEAD: another head file (experiments)
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
from order import order_evidence, order_from_tokens, rival_evidence
import shva as SH
from rule import RULE, mark_of, head_median, no_speech_in, clean_of, marks_of, strict_of, summarize   # the word rule (rule.py)
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
def decode_audio(data: bytes, max_s=None) -> np.ndarray:
    """any container ffmpeg reads -> float32 mono 16 kHz; max_s: decode no more than that many seconds (a small upload
       can hold hours of silence, which would decode to gigabytes)"""
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
        f.write(data); src = f.name
    try:
        out = subprocess.run(['ffmpeg', '-v', 'error', '-i', src] + (['-t', str(max_s)] if max_s else []) + ['-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
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
        W.append({'w': w, 'cons': cons, 'n': len(cons), 'notes': []})
    # a tav said like samekh (the Ashkenazi way): the ת's own frames hold 's' and no 't' — unless an s-sound next to it
    # (the ש of עשה before אות: David's take, Oct 24) is what the aligner's ת token was put on; then no note. "Next to"
    # is within 70 ms (v5.2): 60 ms missed Rabbi Alouf's own ת in 121:1, its neighbour 3 frames of 20.02 ms = 60.06 ms away
    allc = [c for w in W for c in w['cons']]
    for j, c in enumerate(allc):
        if c['c'] != 'ת' or c['heard'] != 's' or c['mass'].get('s', 0) < 2 * max(c['mass'].get('t', 0), c['mass'].get('θ', 0), 1e-6): continue
        near = [allc[i] for i in (j - 1, j + 1) if 0 <= i < len(allc)]
        if any(n['heard'] in ('s', 'ʃ', 'ts', 'z') and n['t1'] >= c['t0'] - 0.07 and n['t0'] <= c['t1'] + 0.07 for n in near): continue
        w = next(w for w in W if c in w['cons']); w['notes'].append({'k': c['k'], 'c': 'ת', 'say': 'sav'})
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

def prefix_reached(lp_ext, toks, pad):
    """CTC Viterbi over the blank-interleaved tokens with the path free to END ANYWHERE (the audio so far may stop in
       the middle of the line) -> how many tokens it has reached: the end state with the best path score"""
    T = lp_ext.shape[0]; S = 2 * len(toks) + 1
    if not toks or T == 0: return 0
    ext = np.array([pad if s % 2 == 0 else toks[(s - 1) // 2] for s in range(S)])
    skip_ok = np.array([s > 1 and s % 2 == 1 and ext[s] != ext[s - 2] for s in range(S)])
    NEG = -1e30; prev = np.full(S, NEG); prev[0] = lp_ext[0, ext[0]]; prev[1] = lp_ext[0, ext[1]]
    for t in range(1, T):
        step = np.concatenate(([NEG], prev[:-1])); skip = np.where(skip_ok, np.concatenate(([NEG, NEG], prev[:-2])), NEG)
        prev = np.maximum(np.maximum(prev, step), skip) + lp_ext[t, ext]
    return (int(np.argmax(prev)) + 1) // 2

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

def analyse(x: np.ndarray, words, want_emb=False, alts=None):
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
    # does another line of the same text fit better than the one that was picked? (order.rival_evidence; v4.5)
    try:
        rival = rival_evidence(hlp, words, alts, HEAD_S2I, he_read, 0) if (hlp is not None and alts) else None
        if rival:
            # is the other line actually heard? its words placed on the head, the median letter score (as head_median does for the written line)
            hw_alt, _ = head_place(hlp, alts[rival['best']]); vals = sorted(v for i, v in hw_alt.items() if len([c for c in he_read(alts[rival['best']][i]) if c in HEAD_S2I and c not in 'אעהוי']) >= 2 and v is not None)
            if len(vals) >= 3: vals = vals[1:]
            rival['head'] = round(vals[(len(vals) - 1) // 2], 3) if vals else None
    except Exception as e:
        print('rival:', e, flush=True); rival = None
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
    return {'dur': round(x.shape[0] / SR, 3), 'spf': round(spf, 5), 'words': W, 'phones': seq, 'gap': ev_h['gap'] if ev_h else None, 'gap_ph': ev_p['gap'] if ev_p else None,
            'rival': ({'gain': rival['gain'], 'n': rival['n'], 'head': rival.get('head'), 'line': ' '.join(alts[rival['best']])} if rival else None), 'ms': int((time.time() - t) * 1000)}, lp, spf

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

# ---------------------------------------------------------------- one letter (the letter checker, /letter)
import letters as LT
AR_I2T = {v: k for k, v in AR_V.items()}
AR_LOOK_IDS = {g: [AR_V[c] for c in cs if c in AR_V] for g, cs in LT.AR_LOOK.items()}
AR_LOOK_IDS = {g: ids for g, ids in AR_LOOK_IDS.items() if ids}
PH_IDS = {p: VOCAB[p] for p in LT.PH if p in VOCAB}

def trim_silence(x, pad=0.15, floor_db=-35.0):
    """the take without its leading and trailing silence (20 ms energy frames; the louder of a fixed floor and 5% of
       the peak decides); -> (x, start_s, energy_on_s): the cut, where it began in the original, and where the energy
       starts inside the cut (the pad, unless the take began mid-sound)"""
    n = int(SR * 0.02)
    if x.shape[0] < 2 * n: return x, 0.0, 0.0
    fr = x[: (x.shape[0] // n) * n].reshape(-1, n)
    rms = np.sqrt((fr ** 2).mean(1) + 1e-12)
    peak = rms.max()
    if peak <= 0: return x, 0.0, 0.0
    thr = max(peak * 10 ** (floor_db / 20), peak * 0.05)
    on = np.nonzero(rms >= thr)[0]
    if not len(on): return x, 0.0, 0.0
    a = max(0, int(on[0] * n - pad * SR)); b = min(x.shape[0], int((on[-1] + 1) * n + pad * SR))
    return x[a:b], round(a / SR, 3), round((on[0] * n - a) / SR, 3)

def ar_greedy(lp, spf):
    ids = lp.argmax(-1); seq, prev = [], -1
    for t, i in enumerate(ids.tolist()):
        if i != prev and i != AR_PAD:
            tok = AR_I2T.get(i, '?')
            if tok not in ('|', ' ', '<s>', '</s>', '<unk>'): seq.append({'p': tok, 't': round(t * spf, 3), 'c': round(float(np.exp(lp[t, i])), 3)})
        prev = i
    return seq

def letter_probe(x: np.ndarray, c: str = None):
    """one short take that opens with a letter: the ears' readings of its opening consonant (letters.py decides the
       window; the verdict is letters.verdict). c: the letter the student was asked for (ע/ח/א add the throat probe)."""
    t = time.time()
    x, cut, energy_on = trim_silence(x)
    dur = x.shape[0] / SR
    if dur < 0.15: return {'dur': round(dur, 3), 'no_speech': True, 'ms': int((time.time() - t) * 1000)}
    lp, spf, H = run_model(x); seq = greedy(lp, spf)
    ar_lp, ar_spf, AH = arabic_lp(x); ar_seq = ar_greedy(ar_lp, ar_spf)
    hlp = head_lp(AH) if FT is None else ft_lps(x)[0]
    win = LT.onset_window(seq, dur, ar_seq, energy_on)
    out = {'dur': round(dur, 3), 'cut': cut, 'energy_on': energy_on, 'phones': seq[:12], 'arabic': ar_seq[:8], 'ms': 0}
    if win is None or not seq:
        out['no_speech'] = True; out['ms'] = int((time.time() - t) * 1000); return out
    t_on, t0, t1 = win
    out.update({'onset': t_on, 'win': [t0, t1]})
    out['peak'], f0, f1 = LT.peaks(lp, spf, t0, t1, PH_IDS)
    # groups of Arabic tokens: the summed probability per frame, then the max (and the sum over the window)
    g0, g1 = int(t0 / ar_spf), max(int(t0 / ar_spf) + 1, int(np.ceil(t1 / ar_spf)))
    aseg = np.exp(ar_lp[g0:g1])
    out['ar_peak'] = {g: round(float(aseg[:, ids].sum(1).max()), 3) for g, ids in AR_LOOK_IDS.items()} if len(aseg) else {}
    out['ar_mass'] = {g: round(float(aseg[:, ids].sum()), 3) for g, ids in AR_LOOK_IDS.items()} if len(aseg) else {}
    if hlp is not None:
        hseg = np.exp(hlp[g0:g1])
        out['head_mass'] = {s: round(float(hseg[:, i].sum()), 3) for s, i in HEAD_S2I.items() if 'א' <= s <= 'ת'} if len(hseg) else {}
        out['head_peak'] = {s: round(float(hseg[:, i].max()), 3) for s, i in HEAD_S2I.items() if 'א' <= s <= 'ת'} if len(hseg) else {}
    out['heard'] = [s['p'] for s in seq if t0 <= s['t'] < t1]
    if c in ('ע', 'ח', 'א'):
        cc = 'ח' if c == 'ח' else 'ע'
        alts = AR.get(cc) or []
        am = {m: float(np.exp(ar_lp[g0:g1, AR_V[m]]).sum()) for m in alts if m in AR_V} if len(aseg) else {}
        ar_hit = {'heard': max(am, key=am.get), 'mass': {m: round(v, 3) for m, v in am.items()}, 'f0': g0, 'f1': g1, 'p': None} if am else None
        head_hit = None
        if hlp is not None and len(hseg):
            pair = ('ע', 'א') if cc == 'ע' else ('ח', 'כ')
            hm = {m: float(hseg[:, HEAD_S2I[m]].sum()) for m in pair if m in HEAD_S2I}
            head_hit = {'heard': max(hm, key=hm.get), 'mass': {m: round(v, 3) for m, v in hm.items()}, 'p': round(float(max(hseg[:, HEAD_S2I[m]].max() for m in pair if m in HEAD_S2I)), 3)}
        th = throat_probe(lp, spf, H, {'c': cc, 't0': t0, 't1': t1, 'k': 0}, ar_lp, ar_spf, ar_hit, False, AH, head_hit)
        out['throat'] = {k: th.get(k) for k in ('p', 'p2', 'ar', 'ar_heard', 'ar_mass', 'head', 'votes', 'v', 'peak')}
    out['ms'] = int((time.time() - t) * 1000)
    return out

# ---------------------------------------------------------------- routes
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'index.html')

# On a Space the page (and the recording booth and its scripts) are served from the newest copy in the GitHub repo
# (refreshed at most once a minute; GitHub's own cache adds a few minutes), so they can change without rebuilding the
# Space; the files shipped in static/ are the fallback when GitHub does not answer. DK_PAGE_BASE overrides the base
# URL (empty = always the local files; locally the default).
PAGE_BASE = os.environ.get('DK_PAGE_BASE', 'https://raw.githubusercontent.com/davidsitt810-ops/dikduk-space/main/static/' if os.environ.get('SPACE_ID') else '')
_PAGES = {}
STATIC_OK = {'index.html': '<script>', 'record.html': '<script>', 'letters.html': '<script>', 'hazzan.html': '<script>', 'scripts.json': '{', 'letters.json': '{', 'embed.js': 'Dikduk'}

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
    return {'ok': True, 'version': VERSION, 'build': {'commit': COMMIT, 'commit_from': COMMIT_FROM, 'files': FILES, 'models': MODEL_REV, 'rule': RULE_HASH, 'ref_tag': REF_TAG},
            'storage': storage(), 'device': DEV, 'threads': THREADS, 'cpu_count': os.cpu_count(), 'uptime_s': int(time.time() - T_START), 'phone_model': PH_ID, 'arabic_model': AR_ID, 'vocab': len(VOCAB), 'classifiers': list(CLF),
            'page_from': 'github' if (_PAGES.get('index.html') or {}).get('body') else 'local', 'jobs': {'queued': sum(1 for v in JOBS.values() if v['state'] == 'queued'), 'running': sum(1 for v in JOBS.values() if v['state'] == 'running'), 'plain': PLAIN[0]},
            # v5.2: 'reviews' (ask a hazzan, send a hidden note) only where they are kept: on a kept disk (a GitHub mirror only
            # pushes, so after a restart /hazzan would not have them); the v5.1 embed hides both when false
            'letters': sorted(LT.BY_C), 'follow': True, 'reviews': DURABLE_DISK, 'ears': {'letter_head': HEAD is not None, 'vowel_head': FULL is not None, 'fine_tuned': FT is not None, 'classifier_v2': bool(CLF2), 'tehillim_lyrics': len(TEHILLIM_LYR), 'tehillim_audio': os.path.isdir(TEHILLIM_DIR) and len(os.listdir(TEHILLIM_DIR)) or (TEHILLIM_BASE or 0),
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
            ev = [tuple(map(int, x.split(','))) for x in s['t'].get(f, '').split(';') if x]; ln = s.get('ln') or []
            for i, (t, k) in enumerate(ev):
                if k < 0: continue
                t1 = ev[i + 1][0] / 10 if i + 1 < len(ev) else t / 10 + 8
                # with the line's nikud, as the pages send it: since v4.9 it is part of the cache key (v5.2: it was left out,
                # so the warm-up filled entries no page asks for)
                try: ref_line(f, t / 10, t1, he_words(s['l'][k]), nikud=(ln[k] if k < len(ln) else None) or None)
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
            # try the site again in five minutes, not on every request (each try can wait a minute) — in half a minute
            # while there are no pizmonim at all yet (only the Tehillim fallback below)
            _LYR['t'] = time.time() - 3600 + (30 if _LYR['data'] is None or _LYR['data'].get('_fallback') else 300)
            if _LYR['data'] is None:
                if not TEHILLIM_LYR: return JSONResponse({'err': 'lyrics: ' + str(e)[:200]}, status_code=502)
                _LYR['data'] = {'v': 1, 's': {}, '_fallback': True}
    if TEHILLIM_LYR and not _LYR['data'].get('_th'):
        _LYR['data'] = {**_LYR['data'], 's': {**_LYR['data'].get('s', {}), **TEHILLIM_LYR}, '_th': True}
    return _LYR['data']

# ---- what this server is: the code, the heads and the models it runs, so every verdict can be traced to them
VERSION = 5.2
HERE_DIR = os.path.dirname(os.path.abspath(__file__))

def file_sha(path, n=12):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()[:n]

def write_json(path, obj):
    """the whole file or nothing: a crash or a full disk mid-write must not leave half a JSON file that every later read
       fails on (written next to it, then renamed over it)"""
    tmp = f'{path}.{uuid.uuid4().hex[:6]}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)

def write_wav(path, x):
    """16 kHz mono float audio -> a 16-bit wav file"""
    import wave
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())

def build_commit():
    """the GitHub commit this code came from: DK_COMMIT; else BUILD_COMMIT beside this file (the Dockerfile writes it
       from the tarball it copied the code from); else the git checkout (the Mac, Colab); else the commit feed the
       Dockerfile fetched while building (/tmp/github_main.atom, newest first: readable only when the Dockerfile makes it
       so) -> (sha, where it came from)"""
    if os.environ.get('DK_COMMIT'): return os.environ['DK_COMMIT'], 'DK_COMMIT'
    try:
        c = open(os.path.join(HERE_DIR, 'BUILD_COMMIT'), encoding='utf-8').read().strip()
        if re.fullmatch(r'[0-9a-f]{40}', c): return c, 'build'
    except Exception: pass
    try:
        r = subprocess.run(['git', '-C', HERE_DIR, 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and re.fullmatch(r'[0-9a-f]{40}', r.stdout.strip()):
            d = subprocess.run(['git', '-C', HERE_DIR, 'status', '--porcelain', '--untracked-files=no'], capture_output=True, text=True, timeout=10)
            return r.stdout.strip(), 'git, with local changes' if d.stdout.strip() else 'git'
    except Exception: pass
    try:
        m = re.search(r'Grit::Commit/([0-9a-f]{40})', open('/tmp/github_main.atom', encoding='utf-8').read())
        if m: return m.group(1), 'build feed'
    except Exception: pass
    return None, None

_FILES = {'app.py': 'app.py', 'rule.py': 'rule.py', 'order.py': 'order.py', 'vowels.py': 'vowels.py', 'nikud.py': 'nikud.py', 'shva.py': 'shva.py', 'letters.py': 'letters.py',
          'letter_head': os.environ.get('DK_LETTER_HEAD') or 'letter_head.pt', 'full_head': 'full_head.pt', 'throat_models.json': 'throat_models.json', 'throat_models_v2.json': 'throat_models_v2.json'}
if FT is not None: _FILES['ft_heads'] = os.path.join(FT_PATH, 'heads.pt')
FILES = {}
for k, p in _FILES.items():
    try: FILES[k] = file_sha(p if os.path.isabs(p) else os.path.join(HERE_DIR, p))
    except Exception: FILES[k] = None
COMMIT, COMMIT_FROM = build_commit()
if not COMMIT: print('build: the commit is not known here (see build_commit); the file fingerprints in /health still say what runs', flush=True)
MODEL_REV = {'phone': getattr(MODEL.config, '_commit_hash', None), 'arabic': getattr(AR_MODEL.config, '_commit_hash', None)}
RULE_HASH = FILES['rule.py']
# The hazzan-line cache key: everything an analysis of his line depends on (the analysis code, the heads, the
# classifiers, the two models and the device), so a change to any of them re-analyses his lines instead of quietly
# comparing students with an older reading of the hazzan. It was a hand-typed 'v4.1' until v4.8 and never moved.
REF_TAG = hashlib.sha256(json.dumps([FILES.get(k) for k in ('app.py', 'order.py', 'vowels.py', 'nikud.py', 'shva.py', 'letter_head', 'full_head', 'throat_models.json', 'throat_models_v2.json', 'ft_heads')]
                                    + [PH_ID, AR_ID, MODEL_REV, DEV, FT_PATH if FT is not None else None]).encode()).hexdigest()[:12]
REF_DIR = os.path.join(CACHE_DIR, 'ref', REF_TAG); os.makedirs(REF_DIR, exist_ok=True)
STAMP = {'version': VERSION, 'commit': COMMIT, 'rule': RULE_HASH, 'ref_tag': REF_TAG}   # kept with every take and drill item

def drop_old_refs():
    """the hazzan analyses made by another build are never read again: remove them (and the flat ref_*.json of before
       v4.8) — a folder only when nothing was written in it for a day, since another server on the same cache (the
       Mac's bench on the GPU, a test) can be using it right now"""
    n = 0
    try:
        for d in os.listdir(os.path.join(CACHE_DIR, 'ref')):
            if d != REF_TAG and os.path.isdir(os.path.join(CACHE_DIR, 'ref', d)) and time.time() - os.path.getmtime(os.path.join(CACHE_DIR, 'ref', d)) > 86400:
                for fn in os.listdir(os.path.join(CACHE_DIR, 'ref', d)): os.unlink(os.path.join(CACHE_DIR, 'ref', d, fn)); n += 1
                os.rmdir(os.path.join(CACHE_DIR, 'ref', d))
        for fn in os.listdir(CACHE_DIR):
            if fn.startswith('ref_') and fn.endswith('.json'): os.unlink(os.path.join(CACHE_DIR, fn)); n += 1
    except Exception as e:
        print('old hazzan analyses not removed:', e, flush=True)
    if n: print('removed', n, 'hazzan analyses made by another build', flush=True)
print('build:', COMMIT and COMMIT[:12], COMMIT_FROM, '· ref tag', REF_TAG, '· rule', RULE_HASH, flush=True)

REF_MAX = 60   # seconds of the hazzan's recording analysed at most (a line is 3-20 s; t1=0 used to mean the whole file)
REF_KEEP = int(os.environ.get('DK_REF_KEEP', '50000'))   # hazzan analyses kept at most (one a line, ~8 KB each)

def shva_heard(lp, nikud, nw):
    """the shvas of a pointed line as heard on the phone ear (shva.probe) -> {word index (str): [slots]}, or None when
       the pointed text does not split into the same words"""
    res, n = SH.probe(lp, nikud, VOCAB, PAD)
    return {str(i): v for i, v in res.items()} if n == nw else None

def ref_line(f: str, t0: float, t1: float, words, want_emb=False, nikud=None):
    # (a pointed line adds the hazzan's shvas: its own cache entry, so the plain one stays valid)
    key = os.path.join(REF_DIR, 'ref_' + hashlib.sha1((f'{f}|{t0}|{t1}|{" ".join(words)}|{int(want_emb)}' + (f'|{nikud}' if nikud else '')).encode()).hexdigest() + '.json')
    if os.path.exists(key):
        return json.load(open(key, encoding='utf-8'))
    x = decode_audio(fetch_archive(f))
    a = max(0.0, t0); end = min(t1, a + REF_MAX) if t1 > 0 else a + REF_MAX
    seg = x[int(a * SR):int(end * SR)]
    if seg.shape[0] < SR * 0.3:
        raise ValueError('the line is empty at those times')
    res, lp, spf = analyse(seg, words, want_emb)
    res['f'] = f; res['t0'] = t0; res['t1'] = t1
    if nikud:
        try: res['shva'] = shva_heard(lp, nikud, len(words))
        except Exception as e: res['shva_err'] = str(e)[:200]
    # the hazzan against himself: the ceiling each word can reach
    self_fit = fit_against(lp, spf, res['words'])
    for w, s in zip(res['words'], self_fit): w['selffit'] = s.get('fit')
    os.makedirs(os.path.dirname(key), exist_ok=True)   # another server on the same cache may have removed it (drop_old_refs)
    # v5.2: kept only while there is room and the folder is under REF_KEEP entries: the key holds the raw t0/t1, so
    # anyone could add an entry a call (~8 KB) for ever; past it a line is analysed again each time instead
    if room_ok(REF_DIR) and len(os.listdir(REF_DIR)) < REF_KEEP: write_json(key, res)
    return res

@app.get('/ref')
async def ref(f: str, words: str, t0: float = 0, t1: float = 0, emb: int = 0, nikud: str = None, key: str = None):
    W = he_words(words)
    if not W:
        return JSONResponse({'err': 'no words'}, status_code=400)
    if emb and not key_ok(key): return need_key(key)   # v5.2: no page asks for it, and its cache entry is 12x the size
    if too_busy(True): return busy()   # v5.2: it runs the models too, so it counts with the plain checks
    PLAIN[0] += 1
    try:
        return await run_in_threadpool(ref_line, f, t0, t1, W, bool(emb), nikud or None)
    except Exception as e:
        return JSONResponse({'err': str(e)[:300]}, status_code=502)
    finally: PLAIN[0] -= 1

DRILL_DIR = os.path.join(KEEP_DIR, 'drill'); os.makedirs(DRILL_DIR, exist_ok=True)   # beside the booth's takes (/data when the Space has it)

@app.get('/drill')
def drill_list(key: str = None):
    """the drill recordings kept on this server (features + David's label), newest last — with the key"""
    d = need_key(key)
    if d: return d
    items = []
    for fn in sorted(f for f in os.listdir(DRILL_DIR) if f.endswith('.json')):
        try:
            d = json.load(open(os.path.join(DRILL_DIR, fn), encoding='utf-8'))
            items.append({'id': fn[:-5], 'word': d['word'], 'style': d['style'], 'c': d['c'], 'v': d.get('v'), 'p': d.get('p'), 'ar_heard': d.get('ar_heard'), 't': d['t']})
        except Exception: pass
    return {'n': len(items), 'items': items}

@app.get('/drill/export')
def drill_export(key: str = None):
    """everything, features included (for training the next classifier) — with the key"""
    d = need_key(key)
    if d: return d
    return [json.load(open(os.path.join(DRILL_DIR, fn), encoding='utf-8')) for fn in sorted(os.listdir(DRILL_DIR)) if fn.endswith('.json')]

# ---- jobs: a check can take longer than the reverse proxy in front of a Space allows one request (the first check of
# a line analyses the hazzan's line too; on 2 vCPUs that is 30–60 s). With job=1 the check is queued, the request
# returns at once with a job id, and the page polls /job/<id> every second or two until the result is there. One
# worker thread runs the queue, so two visitors never run the models at the same time (which would slow both).
JOBS = {}; JOB_Q = queue.Queue(); JOB_LOCK = threading.Lock()
JOB_MAX = int(os.environ.get('DK_JOB_MAX', '40'))   # checks waiting at most: one visitor (or a script) cannot queue the server for hours
# v5.2: the checks without job=1 (scripts, older pages) and the /ref analyses run in the thread pool, outside the queue,
# and wait for the same model LOCK: they count against JOB_MAX too (3 of them made a page check take 40 s while /health
# said queued 0). Only the event loop changes the count, so a plain list cell needs no lock.
# And at most DK_PLAIN_MAX of them at once: each holds one of the thread pool's 40 threads while it waits, so 40 of them
# (JOB_MAX's default) froze /health, the job polls and every other route for minutes.
PLAIN = [0]; PLAIN_MAX = int(os.environ.get('DK_PLAIN_MAX', '4'))
def busy(): return JSONResponse({'err': 'the server is busy — try again in a minute'}, status_code=503)
def too_busy(plain): return queued() + PLAIN[0] >= JOB_MAX or (plain and PLAIN[0] >= PLAIN_MAX)

GRADE_MAX = int(os.environ.get('DK_GRADE_MAX', '200'))   # booth takes waiting to be graded at most (beyond that /submit asks to try again)

def queued(bg=False):
    """jobs waiting: the visitors' checks (bg=False) or the booth's grading (bg=True), counted apart, so a backlog of
       booth takes never makes the lab page or the embed say "busy" (and the other way round)"""
    return sum(1 for v in list(JOBS.values()) if v['state'] == 'queued' and bool(v.get('bg')) == bg)

# The largest upload each route reads (bytes): a phone take of a line is well under 1 MB, a booth perek (8 min) under
# 20 MB. Bigger is refused before it is read into memory.
MAX_BODY = {'check': 20 << 20, 'letter': 5 << 20, 'submit': 40 << 20}

async def read_body(request, cap):
    """the request's body, or None when it is larger than cap (read in pieces, so a huge upload is cut off early)"""
    n = request.headers.get('content-length')
    if n and n.isdigit() and int(n) > cap: return None
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > cap: return None
    return bytes(buf)

def too_big(cap): return JSONResponse({'err': f'the recording is too large (at most {cap >> 20} MB)'}, status_code=413)

def new_job(fn, bg=False):
    jid = uuid.uuid4().hex[:12]
    with JOB_LOCK:
        JOBS[jid] = {'state': 'queued', 'stage': 'waiting for the server', 't': time.time(), 'bg': bg}
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
    out = {'state': J['state'], 'stage': J.get('stage'), 'queued': queued() + queued(True)}
    if J['state'] == 'done': out['result'] = J['result']
    if J['state'] == 'error': out['err'] = J.get('err')
    return out

@app.post('/check')
async def check(request: Request, words: str = Query(...), ref: str = None, t0: float = 0, t1: float = 0, emb: int = 0, drill: str = None, nikud: str = None, job: int = 0, pid: str = None, alts: str = None, key: str = None, vc: str = None):
    W = he_words(words)
    VC = voice_card(vc)
    # a drill take is kept for training: only with the key, so nobody else can add to (or poison) the training data
    drill_err = None
    if drill in ('throat', 'plain') and not key_ok(key):
        drill, drill_err = None, 'not saved: the throat drill needs the key (open the lab page once as /?key=… with the Space secret DK_KEY)'
    ALT = [he_words(a) for a in alts.split('|') if he_words(a) and he_words(a) != W] if alts else pid   # a list of lines, or the text's id (its lines are looked up in the worker, off the event loop)
    if not W:
        return JSONResponse({'err': 'no words'}, status_code=400)
    if too_busy(not job): return busy()   # v5.2: both paths (the plain one was not counted)
    data = await read_body(request, MAX_BODY['check'])
    if data is None: return too_big(MAX_BODY['check'])
    if len(data) < 1000:
        return JSONResponse({'err': 'no audio'}, status_code=400)
    try:
        x = await run_in_threadpool(decode_audio, data, 41)
    except Exception as e:
        return JSONResponse({'err': 'decode: ' + str(e)[:200]}, status_code=400)
    if x.shape[0] < SR * 0.5:
        return JSONResponse({'err': 'too short'}, status_code=400)
    if x.shape[0] > SR * 40:
        x = x[:SR * 40].copy()
    def work(progress):
        out = run_check(x, W, ref, t0, t1, emb, drill, nikud, progress, ALT, VC)
        if drill_err: out['drill_err'] = drill_err
        return out
    if too_busy(not job):   # again: others were let in while this one was read and decoded (no await between here and new_job / PLAIN)
        return busy()
    if job:
        return JSONResponse({'job': new_job(work)}, status_code=202)
    # the plain path (scripts, older pages): the same work in a thread, so /health and the polls keep answering
    PLAIN[0] += 1
    try: return await run_in_threadpool(work, lambda s: None)
    finally: PLAIN[0] -= 1

# The voice card (v5, after Kriah Listener's "voice card"): a person reads Tehillim 23:1-2 once, carefully; the vowel
# notes that reading gets against the nikud are the vowel ear mishearing THAT voice, and later checks leave those
# notes out. Only the ear's own confusions can be calibrated away — kubutz/holam (U<->O) and hiriq/tsere (I<->E), 9
# of the 12 vowel notes on Rabbi Alouf's own reading — never a real dikduk mistake such as "a" for a kamatz katan.
VC_PAIRS = {'U>O', 'O>U', 'E>I', 'I>E'}
def voice_card(vc):
    return {p for p in re.split(r'[\s,]+', str(vc or '')) if p in VC_PAIRS}

def drop_card(vn, VC):
    """vowel notes {word: [{you, ref, ...}]} without the pairs the voice card names -> (kept, how many dropped)"""
    if not VC or not vn: return vn, 0
    out, n = {}, 0
    for i, ds in vn.items():
        keep = [d for d in ds if f"{d['ref']}>{d['you']}" not in VC]; n += len(ds) - len(keep)
        if keep: out[i] = keep
    return out, n

def run_check(x, W, ref, t0, t1, emb, drill, nikud, progress=lambda s: None, alts=None, VC=None):
    if isinstance(alts, str): alts = other_lines(alts, W)   # the text's id -> its other lines (may fetch the site's lyrics: not on the event loop)
    progress('listening to your take')
    take, lp, spf = analyse(x, W, bool(emb) or bool(drill), alts)
    out = {'words': W, 'take': take, 'server': STAMP}
    for w in take['words']: w['pw'] = word_pw(w, None)
    if drill in ('throat', 'plain'):
        # a drill recording: one word, said from the throat or plain; kept with its features for the next classifier,
        # and with its audio (16 kHz wav), so the next model can listen to it again instead of reusing today's features
        wav = f"{int(time.time())}_{uuid.uuid4().hex[:6]}.wav"
        try: write_wav(os.path.join(DRILL_DIR, wav), x)
        except Exception as e: wav = None; print('drill audio not kept:', e, flush=True)
        for w in take['words']:
            for th in w['throat']:
                rec = {'t': int(time.time()), 'word': w['w'], 'k': th['k'], 'c': th['c'], 'style': drill, 'v': th.get('v'), 'p': th.get('p'),
                       'ar_heard': th.get('ar_heard'), 'ar': th.get('ar'), 'peak': th.get('peak'), 'feat': th.get('feat'), 'win': [th['t0'], th['t1']], 'audio': wav, 'server': STAMP}
                fn = f"{rec['t']}_{abs(hash((w['w'], th['k'], drill))) % 100000}.json"
                write_json(os.path.join(DRILL_DIR, fn), rec)
                th.pop('feat', None)
        out['drill_saved'] = sum(1 for f in os.listdir(DRILL_DIR) if f.endswith('.json'))
    if ref:
        try:
            progress("listening to the hazzan's line")
            R = ref_line(ref, t0, t1, W, bool(emb), nikud or None)
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
                vn = compare_vowels({i: w.get('vow', []) for i, w in enumerate(take['words'])}, exp)
                # (v4.9) a vowel the hazzan himself is heard saying the same way is not the student's mistake: the
                # vowel ear hears some of Rabbi Alouf's kubutz/holam as each other (the top false alarm on his own
                # reading — e.g. מְנֻחוֹת "oh for oo"), and the student who sings it as he does is right
                RW = (out.get('ref') or {}).get('words') or []
                for i in list(vn):
                    hv = {v['k']: v['heard'] for v in (RW[i].get('vow') or [])} if i < len(RW) else {}
                    vn[i] = [d for d in vn[i] if hv.get(d['k']) != d['you']]
                    if not vn[i]: del vn[i]
                out['vowels_nikud'] = vn
                # (v5.1) and the other way round: a vowel said as the nikud writes it is not a mistake, whatever the
                # hazzan is heard saying there. A reader the checker never heard (Shmuelof, Tehillim 1, 2, 23): 3 of his
                # 6 vowel notes were "the hazzan says otherwise" on vowels said exactly as written (מְנֻחוֹת,
                # וּמִשְׁעַנְתֶּךָ, שִׁבְטְךָ) — the vowel ear hearing the hazzan's vowel wrong, not the student's
                for i in list(out.get('vowels') or {}):
                    sl = take['words'][i].get('vow', []) if i < len(take['words']) else []; ev = exp.get(i) or []
                    if len(ev) != len(sl): continue
                    pos = {s['k']: j for j, s in enumerate(sl)}
                    out['vowels'][i] = [d for d in out['vowels'][i] if not (d['k'] in pos and ev[pos[d['k']]]['heard'] == d['you'])]
                    if not out['vowels'][i]: del out['vowels'][i]
        except Exception as e:
            out['nikud_err'] = str(e)[:200]
    if nikud:
        # shva na / nah (v4.9): the take's shvas as heard, and where they clearly differ from the hazzan / the rules
        try:
            sv = shva_heard(lp, nikud, len(W))
            if sv is not None:
                out['shva_heard'] = sv
                out['shva'] = SH.notes(sv, (out.get('ref') or {}).get('shva'))
        except Exception as e:
            out['shva_err'] = str(e)[:200]
    if VC:
        n = 0
        for k in ('vowels', 'vowels_nikud'):
            if k in out: out[k], d = drop_card(out[k], VC); n += d
        out['voice_card'] = {'pairs': sorted(VC), 'dropped': n}
    out['vowel_names'] = VOWEL_NAME
    return out

# ================================================================= the recording booth (/record)
# A page that walks a person through a list of short recordings — read this line right; read it with the ayin in
# this word said like alef; leave a word out and tap which — and keeps every recording with its label. Nothing is
# judged on the page: the person records, the server checks each take in the background and keeps the verdicts
# next to the audio, and the scoreboard (/score) compares the two. That is the training and testing data in one.
# Recordings live in TAKES_DIR: /data/takes when the Space has persistent storage (and it is writable), else under
# DK_CACHE (gone on a rebuild) — and every file is mirrored to a private GitHub repo when GH_TOKEN is set (a
# fine-grained token with "Contents: read and write" on that one repo). /health and the booth say which it is.
import base64, uuid as _uuid
TAKES_DIR = os.path.join(KEEP_DIR, 'takes')
FEEDBACK_DIR = os.path.join(KEEP_DIR, 'feedback'); os.makedirs(FEEDBACK_DIR, exist_ok=True)   # v5: hidden notes sent with a yes
REVIEW_DIR = os.path.join(KEEP_DIR, 'reviews'); os.makedirs(REVIEW_DIR, exist_ok=True)       # v5: 'ask a hazzan'
os.makedirs(TAKES_DIR, exist_ok=True)
GH_TOKEN = os.environ.get('GH_TOKEN', '') if os.environ.get('DK_MIRROR', 'github' if os.environ.get('SPACE_ID') else '') == 'github' else ''

MIRROR_ERR = None   # the mirror's last failure, until a pass goes through: then the copies are not being made

def storage():
    """where this server keeps recordings, and whether they outlive a restart (the booth warns when they do not)"""
    out = {'takes': 'persistent' if DURABLE_DISK else 'temporary', 'mirror': bool(GH_TOKEN), 'durable': DURABLE_DISK or (bool(GH_TOKEN) and not MIRROR_ERR)}
    if MIRROR_ERR: out['mirror_err'] = MIRROR_ERR
    return out
GH_REPO = os.environ.get('GH_REPO', 'davidsitt810-ops/dikduk-recordings')
# Other people's recordings and names are not public: listing them, fetching their audio and the all-hands scoreboard
# need the key David sets as the Space secret DK_KEY. A person sees their own scoreboard with the token their phone
# made (sent with each take). Locally, with no key set, everything is open; on a Space with no key set, it is closed.
DK_KEY = os.environ.get('DK_KEY', '')

def key_ok(key):
    if DK_KEY: return key == DK_KEY
    return not os.environ.get('SPACE_ID') and not os.environ.get('DK_PUBLIC')   # open only on a private machine; a home server behind a tunnel sets DK_PUBLIC=1 (mac/install.sh)

def need_key(key):
    if not key_ok(key): return JSONResponse({'err': 'this needs the key (the Space secret DK_KEY)' if DK_KEY or os.environ.get('SPACE_ID') else 'no key set'}, status_code=403)
# v5.2: a key for a hazzan who answers questions (/hazzan) and nothing else: DK_KEY also opens every booth recording,
# the drill, the feedback and the report card, so it is not one to hand to a teacher. DK_KEY still works here too.
HZ_KEY = os.environ.get('DK_HAZZAN_KEY', '')
def hz_ok(key): return key_ok(key) or (bool(HZ_KEY) and key == HZ_KEY)
def need_hz(key):
    if not hz_ok(key): return JSONResponse({'err': 'this needs the hazzan key (DK_HAZZAN_KEY) or the key (DK_KEY)'}, status_code=403)
PHR_TIMES = {"md cd08 15.mp3": [[0.35, 6.9, 0], [7.4, 14, 1], [20.75, 27.7, 2], [28.1, 34.35, 3], [41.4, 50.25, 4], [50.5, 55.25, 5], [55.7, 61.35, 6], [61.85, 66.5, 7]]}

def sync_lines(s, f):
    """line k -> (t0, t1) from a recording's sync events, as the page computes them"""
    if f in PHR_TIMES: return {k: (a, b) for a, b, k in PHR_TIMES[f]}
    ev = [tuple(map(int, x.split(','))) for x in ((s.get('t') or {}).get(f) or '').split(';') if x]; out = {}
    for i, (t, k) in enumerate(ev):
        if k < 0 or k in out: continue
        out[k] = (t / 10, ev[i + 1][0] / 10 if i + 1 < len(ev) else t / 10 + 8)
    return out

def other_lines(pid, W):
    """the other lines of pizmon <pid> / Tehillim 't<n>' as word lists (for the rival-line evidence); [] when unknown"""
    if not pid: return []
    try:
        data = lyrics(); S = data.get('s', {}) if isinstance(data, dict) else {}; s = S.get(str(pid))
        if not s: return []
        out = []
        for l in s.get('l') or []:
            ws = he_words(l)
            if len(ws) >= 1 and ws != W and ws not in out: out.append(ws)
        return out[:60]
    except Exception as e:
        print('other_lines:', e, flush=True); return []

def resolve_text(spec: str):
    """'t23:1' (Tehillim perek:pasuk) or '200:3' (pizmon:line) or plain Hebrew words -> what a check needs"""
    data = lyrics(); S = data.get('s', {}) if isinstance(data, dict) else {}
    m = re.fullmatch(r't(\d+):(\d+)', spec.strip())
    if m:
        n, k = int(m.group(1)), int(m.group(2)) - 1; s = S.get(f't{n}')
        if not s or k >= len(s['l']): raise ValueError(f'no Tehillim {n}:{k + 1}')
        out = {'label': f'Tehillim {n}:{k + 1}', 'words': s['l'][k], 'nikud': (s.get('ln') or [None] * len(s['l']))[k], 'ref': None, 't0': None, 't1': None, 'pid': f't{n}'}
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
        out = {'label': f'pizmon {pid} line {k + 1}', 'words': s['l'][k], 'nikud': None, 'ref': None, 't0': None, 't1': None, 'pid': pid}
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

@app.get('/letters', response_class=HTMLResponse)
def letters_page():
    """the letter checker"""
    body = static_text('letters.html')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}[hidden]{display:none!important}</style>'
            '</head><body>' + body + '</body></html>')

@app.get('/letters.json')
def letters_json():
    """the letters offered, with Rabbi Alouf's example words (static/letters.json, made by space_test/make_letters.py)"""
    try: return JSONResponse(json.loads(static_text('letters.json')), headers={'Cache-Control': 'no-store'})
    except Exception as e: return JSONResponse({'err': 'letters: ' + str(e)[:200]}, status_code=500)

LETTERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'letters')

@app.get('/letters/audio/{fname}')
def letters_audio(fname: str):
    """one of Rabbi Alouf's example words (a second-long mp3); GitHub's copy when the file is not in this build"""
    if not re.fullmatch(r'[a-z0-9-]+\.mp3', fname): return JSONResponse({'err': 'no such file'}, status_code=404)
    p = os.path.join(LETTERS_DIR, fname)
    if os.path.exists(p): return FileResponse(p, media_type='audio/mpeg', headers={'Cache-Control': 'public, max-age=86400'})
    return RedirectResponse('https://raw.githubusercontent.com/davidsitt810-ops/dikduk-space/main/static/letters/' + fname)

@app.post('/letter')
async def letter(request: Request, c: str = Query(...), want: str = None, strict: int = 0):
    """one short take that opens with the letter c (ע ח א ק ט צ ר ב כ פ ש ת; want = the variant for ב כ פ ש):
       the verdict on its opening sound, what was heard, and the ears' numbers (letters.py)"""
    c = he_letters(c)[:1]
    if c not in LT.BY_C: return JSONResponse({'err': 'not a letter I check'}, status_code=400)
    if too_busy(True): return busy()   # v5.2: it runs the models under the LOCK too, so it counts with the plain checks
    data = await read_body(request, MAX_BODY['letter'])
    if data is None: return too_big(MAX_BODY['letter'])
    if len(data) < 500: return JSONResponse({'err': 'no audio'}, status_code=400)
    try: x = await run_in_threadpool(decode_audio, data, 7)
    except Exception as e: return JSONResponse({'err': 'decode: ' + str(e)[:200]}, status_code=400)
    if x.shape[0] > SR * 6: x = x[:SR * 6]
    if too_busy(True): return busy()   # again after the decode, then counted (no await in between)
    PLAIN[0] += 1
    try: P = await run_in_threadpool(letter_probe, x, c)
    finally: PLAIN[0] -= 1
    V = LT.verdict(c, want, P, bool(strict))
    P.update(V); P['c'] = c; P['want'] = want
    return P

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
    """one file into the mirror repo (GitHub contents API: a new path needs no sha; one already there is overwritten)"""
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
    """push every take and drill file not pushed since it last changed. A take's JSON goes up at once (with its labels)
       and again when its verdicts land, so a restart before the grading cannot lose what the person said they did.
       The .pushed marker holds the file's modification time as it was pushed."""
    global MIRROR_ERR
    if not GH_TOKEN: return 0
    n = 0
    for base, prefix in ((TAKES_DIR, 'takes/'), (DRILL_DIR, 'drill/'), (FEEDBACK_DIR, 'feedback/'), (REVIEW_DIR, 'reviews/')):
        for root, _, files in os.walk(base):
            for fn in sorted(files):
                if fn.endswith('.pushed') or fn.endswith('.tmp'): continue
                full = os.path.join(root, fn); mark = full + '.pushed'
                try: mt = os.path.getmtime(full)
                except OSError: continue
                try:
                    if float(open(mark).read().strip() or 0) >= mt: continue
                except (OSError, ValueError): pass
                rel = os.path.relpath(full, base).replace(os.sep, '/')
                if fn.endswith('.json'):
                    try: json.load(open(full, encoding='utf-8'))   # a whole file only
                    except Exception: continue
                try:
                    gh_put(prefix + rel, open(full, 'rb').read(), prefix.rstrip('/') + ' ' + rel); open(mark, 'w').write(repr(mt)); n += 1
                except Exception as e:
                    MIRROR_ERR = f'{time.strftime("%Y-%m-%d %H:%M")}: ' + str(getattr(getattr(e, 'response', None), 'status_code', '') or type(e).__name__)   # no paths: /health is public and they hold names
                    print('mirror failed:', rel, str(e)[:120], flush=True); return n
    MIRROR_ERR = None
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

# ================================================================= feedback and "ask a hazzan" (v5)
# Feedback (after Tarteel's "remove a wrong flag"): a person who thinks a note is wrong can hide it, and — only if
# they say yes — send the recording with the note they hid. That is labelled data where the checker is weakest:
# a voice it misjudged. Reviews (after Qara'a's "send it to a teacher"): a take with a question, kept until a hazzan
# with the key answers on /hazzan; the person's browser keeps the id and a token and shows the answer when it is
# there. Both live beside the booth's takes (KEEP_DIR: /data on the Space when it has it, the Mac's own disk) and go
# to the GitHub mirror with them when that is set up.
# v5.2: only where they are kept (not on the Space's temporary disk, where they were lost at the next restart); the
# upload is decoded and only the server's own 16 kHz wav is kept (the raw body was: any bytes, a phone video with a
# face, a program served back from /review/<id>/audio); the questions waiting and the notes kept are capped; a hazzan
# key (DK_HAZZAN_KEY) answers and removes questions; v5.2 pages send the meta in a header, out of the access log.
AUDIO_EXT = ('.m4a', '.mp4', '.webm', '.wav', '.mp3', '.ogg', '.bin')
AUDIO_MIME = {'m4a': 'audio/mp4', 'mp4': 'audio/mp4', 'webm': 'audio/webm', 'wav': 'audio/wav', 'mp3': 'audio/mpeg', 'ogg': 'audio/ogg'}   # by extension; anything else goes out as bytes
def ext_of(mime):
    mime = str(mime or '')
    return '.m4a' if 'mp4' in mime or 'm4a' in mime else '.webm' if 'webm' in mime else '.wav' if 'wav' in mime else '.ogg' if 'ogg' in mime else '.mp3' if 'mpeg' in mime else '.bin'
LIST_META = {'notes': (300, 30), 'marks': (20, 100)}   # lists of short strings (the hazzan page maps over notes): (chars, items)
def clip_meta(M, keys, n=4000):
    """only the expected fields, each JSON-sized: what a page sends is not trusted to be small or well formed. notes and
       marks are kept only as lists; a string too long is cut to n characters, any other value too long is dropped
       (v5.2: a cut-off JSON string was kept instead, and one question whose notes were a string blanked /hazzan)"""
    out = {}
    for k in keys:
        if k not in M: continue
        v = M[k]
        if k in LIST_META:
            if isinstance(v, list): out[k] = [str(x)[:LIST_META[k][0]] for x in v][:LIST_META[k][1]]
        elif len(json.dumps(v, ensure_ascii=False)) <= n: out[k] = v
        elif isinstance(v, str): out[k] = v[:n]
    return out
def meta_of(request, meta):
    """the page's meta -> a dict, or None: from the x-dk-meta header (v5.2 pages: encodeURIComponent of the JSON, so a
       name, a contact and a question are not written into the access log with the URL), else the query (older pages)"""
    h = request.headers.get('x-dk-meta')
    try: M = jstrict(urllib.parse.unquote(h) if h else meta)
    except Exception: return None
    return M if isinstance(M, dict) else None
def finite(s):
    v = float(s)
    if not np.isfinite(v): raise ValueError('not a number JSON can keep: ' + s)
    return v
# what a page sends, without NaN, Infinity or 1e999: Python's json takes them, and one kept in a question, a note or a
# take made the whole list a 500 (JSONResponse refuses them), so /hazzan showed nothing (v5.2)
def jstrict(s): return json.loads(s, parse_float=finite, parse_constant=finite)
def bad_meta(): return JSONResponse({'err': 'bad meta'}, status_code=400)
def not_kept(): return JSONResponse({'err': 'questions are not kept on this server'}, status_code=503)
async def sound_of(data):
    """an upload decoded (at most 41 s) -> the sound, or None when it is not at least half a second of audio"""
    try: x = await run_in_threadpool(decode_audio, data, 41)
    except Exception: return None
    return x if x.shape[0] >= SR * 0.5 else None
def quiet(x): return float(np.abs(x).max()) < 0.01   # digital silence (a 15 KB flac of it is kept as a 1.3 MB wav)
def silent(): return JSONResponse({'err': 'there is no sound in the recording'}, status_code=400)
def room_ok(d): return shutil.disk_usage(d).free >= (1 << 30)
def client_of(request):
    """the sender as well as the server can tell: Cloudflare's header on the Mac's tunnel, the proxy's on a Space"""
    h = request.headers
    return h.get('cf-connecting-ip') or (h.get('x-forwarded-for') or '').split(',')[0].strip() or (request.client.host if request.client else '')
# v5.2: one sender could fill a cap for everyone (2000 silent posts and nobody could ask a hazzan). Each sender's ids
# that still hold a place (a question waiting, a note this month) are counted apart: in memory only, so no address is
# written to disk, and a restart forgets them (the caps on disk still hold).
MINE = {}
def mine(kind, request, holds):
    k = (kind, client_of(request)); L = [i for i in MINE.pop(k, []) if holds(i)]
    if L: MINE[k] = L
    return k, L
KEEP_LOCK = asyncio.Lock()   # a count and the write after it, with no other upload let in between (12 at once all passed a cap of 5)
REVIEW_PER = int(os.environ.get('DK_REVIEW_PER', '20')); FEEDBACK_PER = int(os.environ.get('DK_FEEDBACK_PER', '200'))
FB_KEYS = ('pid', 'line', 'words', 'nikud', 'ref', 't0', 't1', 'dismissed', 'marks', 'notes', 'strict', 'voice_card', 'server', 'device', 'who')
RV_KEYS = ('pid', 'line', 'words', 'nikud', 'ref', 't0', 't1', 'note', 'contact', 'marks', 'notes', 'say', 'server', 'device', 'who')

@app.post('/feedback')
async def feedback(request: Request, meta: str = None):
    """a hidden note and, with the person's yes, the recording it was about -> kept for the next round of training"""
    M = meta_of(request, meta)
    if M is None: return bad_meta()
    if not DURABLE_DISK: return not_kept()
    data = await read_body(request, MAX_BODY['check'])
    if data is None: return too_big(MAX_BODY['check'])
    if len(data) < 1000: return JSONResponse({'err': 'no audio'}, status_code=400)
    if not room_ok(FEEDBACK_DIR): return JSONResponse({'err': 'the server is out of room'}, status_code=507)
    x = await sound_of(data)
    if x is None: return JSONResponse({'err': 'not audio'}, status_code=400)
    if quiet(x): return silent()
    # the caps, counted with no await before the write: this month's notes (a cap on every note ever closed the route
    # for good: nothing frees a note), and this sender's
    mo = time.strftime('%Y%m'); d = os.path.join(FEEDBACK_DIR, mo)
    if os.path.isdir(d) and sum(1 for f in os.listdir(d) if f.endswith('.json')) >= int(os.environ.get('DK_FEEDBACK_MAX', 2000)):
        return JSONResponse({'err': 'too many notes have been sent here this month — try again later'}, status_code=503)
    k, L = mine('fb', request, lambda i: i.startswith(mo + '/'))
    if len(L) >= FEEDBACK_PER: return JSONResponse({'err': 'you have sent many notes this month — thank you; try again later'}, status_code=429)
    fid = time.strftime('%Y%m/%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8]; full = os.path.join(FEEDBACK_DIR, fid)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    write_wav(full + '.wav', x[:SR * 40])
    rec = {'id': fid, 't': int(time.time()), 'kind': 'dismissed', **clip_meta(M, FB_KEYS), 'audio': os.path.basename(full + '.wav'), 'bytes': len(data), 'stamp': STAMP}
    write_json(full + '.json', rec); MINE[k] = L + [fid]
    return JSONResponse({'id': fid, 'saved': True}, status_code=201)

@app.get('/feedback')
def feedback_list(key: str = None):
    d = need_key(key)
    if d: return d
    items = []
    for root, _, files in os.walk(FEEDBACK_DIR):
        for fn in files:
            if fn.endswith('.json'):
                try: items.append(json.load(open(os.path.join(root, fn), encoding='utf-8')))
                except Exception: pass
    items.sort(key=lambda j: -j.get('t', 0))
    return {'n': len(items), 'items': items}

def review_path(rid):
    if not re.fullmatch(r'[0-9a-f]{12}', str(rid or '')): return None
    p = os.path.join(REVIEW_DIR, rid + '.json')
    return p if os.path.isfile(p) else None

def reviews_waiting():
    """the questions not answered yet (v5.2: the cap counted the answered ones too, so after 2000 questions ever it refused everyone)"""
    n = 0
    for f in os.listdir(REVIEW_DIR):
        if not f.endswith('.json'): continue
        try: n += json.load(open(os.path.join(REVIEW_DIR, f), encoding='utf-8')).get('state') == 'waiting'
        except Exception: pass
    return n
def is_waiting(rid):
    try: return json.load(open(review_path(rid), encoding='utf-8')).get('state') == 'waiting'
    except Exception: return False

@app.post('/review')
async def review_ask(request: Request, meta: str = None):
    """'ask a hazzan': the take and the person's question, kept until a hazzan answers -> {id, token}"""
    M = meta_of(request, meta)
    if M is None: return bad_meta()
    if not DURABLE_DISK: return not_kept()
    data = await read_body(request, MAX_BODY['check'])
    if data is None: return too_big(MAX_BODY['check'])
    if len(data) < 1000: return JSONResponse({'err': 'no audio'}, status_code=400)
    if not room_ok(REVIEW_DIR): return JSONResponse({'err': 'the server is out of room'}, status_code=507)
    x = await sound_of(data)
    if x is None: return JSONResponse({'err': 'not audio'}, status_code=400)
    if quiet(x): return silent()
    async with KEEP_LOCK:   # the questions waiting, then this sender's, then the write, with no other question let in between
        if await run_in_threadpool(reviews_waiting) >= int(os.environ.get('DK_REVIEW_MAX', 2000)):
            return JSONResponse({'err': 'too many questions are waiting — try again later'}, status_code=503)
        k, L = mine('rv', request, is_waiting)
        if len(L) >= REVIEW_PER: return JSONResponse({'err': f'you have {len(L)} questions waiting — please wait for the answers first'}, status_code=429)
        rid = uuid.uuid4().hex[:12]; tok = uuid.uuid4().hex[:16]
        write_wav(os.path.join(REVIEW_DIR, rid + '.wav'), x[:SR * 40])
        write_json(os.path.join(REVIEW_DIR, rid + '.json'), {'id': rid, 'token': tok, 't': int(time.time()), 'state': 'waiting', **clip_meta(M, RV_KEYS), 'audio': rid + '.wav', 'stamp': STAMP})
        MINE[k] = L + [rid]
    return JSONResponse({'id': rid, 'token': tok}, status_code=201)

@app.get('/review/{rid}')
def review_get(rid: str, t: str = None, key: str = None):
    """the person's view (their token) or the hazzan's (the key): the question and, once there, the answer"""
    p = review_path(rid)
    if not p: return JSONResponse({'err': 'no such question'}, status_code=404)
    J = json.load(open(p, encoding='utf-8'))
    if not (hz_ok(key) or (t and t == J.get('token'))): return JSONResponse({'err': 'not yours'}, status_code=403)
    J = dict(J); J.pop('token', None)
    return J

@app.get('/review/{rid}/audio')
def review_audio(rid: str, t: str = None, key: str = None):
    p = review_path(rid)
    if not p: return JSONResponse({'err': 'no such question'}, status_code=404)
    J = json.load(open(p, encoding='utf-8'))
    if not (hz_ok(key) or (t and t == J.get('token'))): return JSONResponse({'err': 'not yours'}, status_code=403)
    a = os.path.join(REVIEW_DIR, os.path.basename(J.get('audio') or ''))
    if not os.path.isfile(a): return JSONResponse({'err': 'no audio'}, status_code=404)
    # always as audio (a .wav since v5.2; questions kept before by their extension), never sniffed into something else
    return FileResponse(a, media_type=AUDIO_MIME.get(a.rsplit('.', 1)[-1], 'application/octet-stream'), headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

@app.get('/reviews')
def reviews_list(key: str = None):
    """the hazzan's queue (with the hazzan key or the key): waiting questions first, newest first"""
    d = need_hz(key)
    if d: return d
    items = []
    for fn in os.listdir(REVIEW_DIR):
        if fn.endswith('.json'):
            try: J = json.load(open(os.path.join(REVIEW_DIR, fn), encoding='utf-8')); J.pop('token', None); items.append(J)
            except Exception: pass
    items.sort(key=lambda j: (j.get('state') != 'waiting', -j.get('t', 0)))
    return {'n': len(items), 'waiting': sum(1 for j in items if j.get('state') == 'waiting'), 'items': items}

@app.post('/review/{rid}/reply')
async def review_reply(rid: str, request: Request, key: str = None):
    """the hazzan's answer: {text, by, words?: {index: 'ok'|'fix'}}"""
    d = need_hz(key)
    if d: return d
    p = review_path(rid)
    if not p: return JSONResponse({'err': 'no such question'}, status_code=404)
    try: A = jstrict(await request.body())
    except Exception: return JSONResponse({'err': 'bad answer'}, status_code=400)
    text = str((A or {}).get('text') or '').strip()[:4000]
    if not text: return JSONResponse({'err': 'an empty answer'}, status_code=400)
    J = json.load(open(p, encoding='utf-8'))
    J['reply'] = {'text': text, 'by': str(A.get('by') or '')[:80], 't': int(time.time()), 'words': A.get('words') if isinstance(A.get('words'), dict) else None}
    J['state'] = 'answered'; write_json(p, J)
    return {'ok': True}

@app.post('/review/{rid}/delete')
def review_delete(rid: str, key: str = None):
    """the hazzan removes a question (spam, or done with): its JSON, its audio and the mirror's markers, the JSON last
       (v5.2; a copy already pushed to the GitHub mirror stays there)"""
    d = need_hz(key)
    if d: return d
    if not review_path(rid): return JSONResponse({'err': 'no such question'}, status_code=404)
    for fn in sorted((f for f in os.listdir(REVIEW_DIR) if f.startswith(rid + '.')), key=lambda f: f.endswith('.json')):
        try: os.unlink(os.path.join(REVIEW_DIR, fn))
        except OSError as e: print('review not removed:', fn, e, flush=True)
    return {'ok': True}

@app.post('/follow')
async def follow(request: Request, words: str = Query(...)):
    """live follow-along (v5, after Tarteel's real-time reading): the recording so far -> how many of the line's words
       it has reached (the phone ear and the consonant skeleton only, the path free to end anywhere). The embed asks
       every 1.5 s while recording, and only on a fast server (the Mac's GPU); it never waits behind a check."""
    W = he_words(words)
    if not W: return JSONResponse({'err': 'no words'}, status_code=400)
    if queued() > 0 or PLAIN[0] > 0: return JSONResponse({'busy': True}, status_code=429)   # (v5.2: nor behind a plain check or a /ref)
    data = await read_body(request, MAX_BODY['check'])
    if data is None: return too_big(MAX_BODY['check'])
    if len(data) < 500: return {'done': 0, 'n': len(W)}
    try: x = await run_in_threadpool(decode_audio, data, 41)
    except Exception: return {'done': 0, 'n': len(W), 'err': 'not decodable yet'}
    if x.shape[0] < SR * 0.3: return {'done': 0, 'n': len(W)}
    def work():
        t = time.time(); lp, spf, _ = run_model(x[:SR * 40]); lp_ext, per = phone_line_tokens(lp, W)
        toks = [k for p in per for k in p]; got = prefix_reached(lp_ext, toks, PAD)
        done, end = 0, 0
        for p in per:
            end += len(p)
            if end <= got: done += 1
            else: break
        return {'done': done, 'n': len(W), 'tokens': got, 'ms': int((time.time() - t) * 1000)}
    # again after the decode, and counted (v5.2: any number of follows ran at once, uncounted, and a page check waited
    # behind all of them): one follow at a time, and never beside a check or a /ref
    if queued() > 0 or PLAIN[0] > 0: return JSONResponse({'busy': True}, status_code=429)
    PLAIN[0] += 1
    try: return await run_in_threadpool(work)
    finally: PLAIN[0] -= 1

@app.get('/hazzan', response_class=HTMLResponse)
def hazzan_page():
    """the hazzan's page: the questions waiting, each with the recording, the line and the machine's notes"""
    body = static_text('hazzan.html')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}[hidden]{display:none!important}</style>'
            '</head><body>' + body + '</body></html>')

def take_paths(tid):
    """id -> (json path, audio path); the id is the json's path relative to TAKES_DIR without .json"""
    tid = tid.replace('..', '').strip('/'); jp = os.path.join(TAKES_DIR, tid + '.json')
    if not os.path.isfile(jp): return None, None
    base = jp[:-5]; aud = [p for p in (base + e for e in ('.m4a', '.mp4', '.webm', '.wav', '.mp3', '.ogg', '.bin')) if os.path.isfile(p)]
    return jp, (aud[0] if aud else None)

@app.post('/submit')
async def submit(request: Request, meta: str = None, key: str = None):
    """one recording from the booth: body = audio; meta = JSON {set, task, name, text, do, labels, note, mime, device}
       (in the x-dk-meta header from v5.2 pages, else in the query). Saved at once, checked in the background (the
       verdicts land in the take's JSON), mirrored to GitHub if set up."""
    M = meta_of(request, meta)
    if M is None: return bad_meta()
    if M.get('check', True) and queued(True) >= GRADE_MAX:
        return JSONResponse({'err': 'the server has many recordings to check — try again in a few minutes'}, status_code=503)
    try:
        if shutil.disk_usage(TAKES_DIR).free < (1 << 30): return JSONResponse({'err': 'the server is out of room for recordings'}, status_code=507)
    except Exception: pass
    data = await read_body(request, MAX_BODY['submit'])
    if data is None: return too_big(MAX_BODY['submit'])
    if len(data) < 1000:
        return JSONResponse({'err': 'no audio'}, status_code=400)
    # v5.2: a take was stored as it came, up to 40 MB of any bytes from anyone (checked or not: the grader's failure left
    # it there): without the key it must decode to sound first. The original bytes are still what is kept (for training).
    if not key_ok(key) and await sound_of(data) is None:
        return JSONResponse({'err': 'not audio'}, status_code=400)
    try:
        R = await run_in_threadpool(resolve_text, M.get('text', ''))   # may fetch the site's lyrics: not on the event loop
    except Exception as e:
        return JSONResponse({'err': str(e)[:200]}, status_code=400)
    mime = str(M.get('mime') or ''); ext = '.m4a' if 'mp4' in mime or 'm4a' in mime else '.webm' if 'webm' in mime else '.wav' if 'wav' in mime else '.ogg' if 'ogg' in mime else '.bin'
    ts = time.strftime('%Y%m%d-%H%M%S'); tid = f"{safe_name(M.get('set'))}/{safe_name(M.get('name'))}/{ts}-{safe_name(M.get('task'), 24)}-{_uuid.uuid4().hex[:6]}"
    full = os.path.join(TAKES_DIR, tid); os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full + ext, 'wb').write(data)
    rec = {'id': tid, 't': int(time.time()), 'set': M.get('set'), 'task': M.get('task'), 'name': M.get('name'), 'who': str(M.get('who') or '')[:40], 'text': M.get('text'), 'label': R['label'], 'words': R['words'],
           'do': M.get('do'), 'labels': M.get('labels'), 'note': M.get('note'), 'mime': mime, 'bytes': len(data), 'device': str(M.get('device') or '')[:200], 'check': bool(M.get('check', True)),
           'graded': False, 'result': None, 'server': STAMP}
    if not rec['check']: rec['graded'] = True
    write_json(full + '.json', rec)
    if rec['check']: new_job(grade_job(full, ext), bg=True)
    return JSONResponse({'id': tid, 'saved': True, 'durable': storage()['durable']}, status_code=202)

def grade_job(full, ext):
    """the job that checks one saved take (full = its path without the extension) and writes the verdicts into its JSON"""
    def grade(progress):
        rec = json.load(open(full + '.json', encoding='utf-8'))
        rec['tries'] = rec.get('tries', 0) + 1; write_json(full + '.json', rec)   # before the work: a take that stops the server is not tried for ever
        try:
            R = resolve_text(rec.get('text') or '')
            x = decode_audio(open(full + ext, 'rb').read(), 41)
            if x.shape[0] > SR * 40: x = x[:SR * 40]
            if x.shape[0] < SR * 0.5: raise ValueError('too short')
            out = run_check(x, he_words(R['words']), R['ref'], R['t0'] or 0, R['t1'] or 0, 0, None, R['nikud'], progress, other_lines(R.get('pid'), he_words(R['words'])))
            rec['summary'] = summarize(out)
            out.pop('ref', None)   # the hazzan's analysis is big and lives in the reference cache anyway
            rec['result'] = out
        except Exception as e:
            rec['error'] = str(e)[:200]
        rec['graded'] = True; rec['graded_by'] = STAMP; write_json(full + '.json', rec)
        return {'ok': True}
    return grade

def regrade_waiting():
    """after a restart: the takes that were saved but not yet checked (the queue lives in memory) go back in the queue
       — twice at most: a take whose checking stopped the server twice is marked failed instead"""
    n = 0
    for root, _, files in os.walk(TAKES_DIR):
        for fn in files:
            if not fn.endswith('.json'): continue
            jp = os.path.join(root, fn)
            try: J = json.load(open(jp, encoding='utf-8'))
            except Exception: continue
            if J.get('graded', True) or not J.get('check', True): continue
            if J.get('tries', 0) >= 2:
                J['graded'] = True; J['error'] = 'not checked: the server stopped while checking it, twice'; write_json(jp, J); continue
            _, ap = take_paths(os.path.relpath(jp, TAKES_DIR)[:-5])
            if ap: new_job(grade_job(ap.rsplit('.', 1)[0], '.' + ap.rsplit('.', 1)[1]), bg=True); n += 1
    if n: print('re-queued', n, 'takes saved before the restart and not checked yet', flush=True)

def housekeeping():
    """when the server starts serving: remove other builds' hazzan analyses, and put the takes that were waiting back in
       the queue. DK_SIDE=1 (a second server on the same folders: the Mac's bench, a test) leaves the takes alone."""
    drop_old_refs()
    if not os.environ.get('DK_SIDE'): threading.Thread(target=regrade_waiting, daemon=True).start()

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
    return FileResponse(ap, media_type=AUDIO_MIME.get(ap.rsplit('.', 1)[-1], 'application/octet-stream'), filename=os.path.basename(ap), headers={'X-Content-Type-Options': 'nosniff'})

def score_take(J):
    """one take: what the person did (its labels) against what the machine claimed -> verdict lines and tallies"""
    S = J.get('summary'); do = J.get('do') or 'right'; L = J.get('labels') or {}; W = he_words(J.get('words') or '')
    if not J.get('check', True): return {'state': 'stored'}
    if not J.get('graded'): return {'state': 'waiting'}
    if not S: return {'state': 'error', 'why': J.get('error') or 'no result'}
    M = list(S.get('marks') or []); claims = []; tally = {'false_alarm': 0, 'caught': 0, 'missed': 0, 'unsure': 0, 'claims': 0}
    changed = set(he_letters(w) for w in (L.get('words') or []))
    if do in ('skip', 'wrong', 'swap', 'free', 'vowel') and L.get('word'): changed.add(he_letters(L['word']))
    if do == 'swap': changed |= set(he_letters(w) for w in (L.get('pair') or []))
    # words, by position (a line can repeat a word); a changed word that occurs more than once is judged on its best instance
    seen = set()
    for i, w in enumerate(W):
        m = M[i] if i < len(M) else ''; key = he_letters(w)
        if key in changed and do in ('skip', 'wrong', 'swap', 'free'):
            if key in seen: continue
            seen.add(key); ms = [M[k] if k < len(M) else '' for k, x in enumerate(W) if he_letters(x) == key]
            if 'off' in ms: tally['caught'] += 1; claims.append(f'{w}: you changed it, machine said not heard ✓')
            elif 'unsure' in ms: tally['unsure'] += 1; claims.append(f'{w}: you changed it, machine said not sure ~')
            else: tally['missed'] += 1; claims.append(f'{w}: you changed it, machine passed it ✕')
        else:
            if m == 'off': tally['false_alarm'] += 1; claims.append(f'{w}: you sang it, machine said not heard ✕ (false alarm)')
            elif m == 'unsure': tally['unsure'] += 1; claims.append(f'{w}: you sang it, machine said not sure ~')
    # throat letters
    for th in (S.get('throat') or []):
        if th.get('mark') == 'off' or (he_letters(th['w']) in changed and do in ('skip', 'wrong', 'swap', 'free')): continue   # the word was not there, or was changed: its letters are not judged
        planted = (do == 'ayin' and th['c'] == 'ע' or do == 'het' and th['c'] == 'ח') and (not L.get('word') or he_letters(L.get('word')) == he_letters(th['w'])) and L.get('done', True)
        if planted:
            if th['v'] == 'plain': tally['caught'] += 1; claims.append(f"{th['c']} in {th['w']}: you said it plain, machine heard plain ✓")
            elif th['v'] == 'unsure': tally['unsure'] += 1; claims.append(f"{th['c']} in {th['w']}: you said it plain, machine not sure ~")
            else: tally['missed'] += 1; claims.append(f"{th['c']} in {th['w']}: you said it plain, machine heard the throat ✕")
        else:
            if th['v'] == 'plain' and th.get('hazzan') == 'plain': claims.append(f"{th['c']} in {th['w']}: plain, as the hazzan says it there (not counted)")
            elif th['v'] == 'plain': tally['false_alarm'] += 1; claims.append(f"{th['c']} in {th['w']}: machine said plain ✕ (false alarm, unless you did say it plain)")
            elif th['v'] == 'unsure': tally['unsure'] += 1; claims.append(f"{th['c']} in {th['w']}: machine not sure ~")
    # vowels
    vw = [v for v in (S.get('vowels') or [])]
    if do == 'vowel' and L.get('word'):
        hit = [v for v in vw if he_letters(v['w']) == he_letters(L['word'])]
        if hit: tally['caught'] += 1; claims.append(f"{L['word']}: you changed a vowel, machine heard {hit[0]['you']} for {hit[0]['ref']} ✓")
        else: tally['missed'] += 1; claims.append(f"{L['word']}: you changed a vowel, machine heard nothing ✕")
        vw = [v for v in vw if he_letters(v['w']) != he_letters(L['word'])]
    for v in vw:
        tally['claims'] += 1; claims.append(f"{v['w']}: machine says you sang {v['you']} where the {v.get('against', 'hazzan')} has {v['ref']} — right or wrong?")
    # shva na / nah (v4.9): a planted one (swallowed / an extra "e") is caught or missed; any other note on a take read
    # right is a false alarm; on other takes it is a claim to look at
    sv = list(S.get('shva') or []); say = lambda v: 'no short e' if v == 'none' else 'a short e'
    if do in ('shvana', 'shvanah') and L.get('word') and L.get('done', True):
        want = 'vowel' if do == 'shvana' else 'none'
        hit = [v for v in sv if he_letters(v['w']) == he_letters(L['word']) and v['want'] == want]
        if hit: tally['caught'] += 1; claims.append(f"{L['word']}: you said {say(hit[0]['you'])} there, machine heard it ✓")
        else: tally['missed'] += 1; claims.append(f"{L['word']}: you changed its shva, machine heard nothing ✕")
        sv = [v for v in sv if he_letters(v['w']) != he_letters(L['word'])]
    for v in sv:
        if do == 'right': tally['false_alarm'] += 1; claims.append(f"{v['w']}: machine says {say(v['you'])} after the {v['c']}, wants {say(v['want'])} ✕ (false alarm, unless you did)")
        else: tally['claims'] += 1; claims.append(f"{v['w']}: machine says {say(v['you'])} after the {v['c']}, wants {say(v['want'])} — right or wrong?")
    return {'state': 'scored', 'claims': claims, 'tally': tally, 'clean': S.get('clean'), 'hazzan': S.get('hazzan'), 'cant_hear': bool(S.get('cant_hear')), 'no_speech': bool(S.get('no_speech')), 'line_wrong': bool(S.get('line_wrong'))}

@app.get('/score')
def score(set_: str = Query(None, alias='set'), name: str = None, who: str = None, key: str = None):
    """the scoreboard: every take scored against its own label, and the totals. A person's own takes with the
       token their phone sent (who); everyone's with the key."""
    if not who:
        d = need_key(key)
        if d: return d
    items = list_takes(set_, name, who); rows = []; tot = {'false_alarm': 0, 'caught': 0, 'missed': 0, 'unsure': 0, 'claims': 0, 'waiting': 0, 'error': 0, 'stored': 0}
    for J in items:
        if not isinstance(J, dict) or 'id' not in J: continue
        try: sc = score_take(J)
        except Exception as e: sc = {'state': 'error', 'why': 'scoring: ' + str(e)[:120]}
        rows.append({'id': J['id'], 'task': J.get('task'), 'label': J.get('label'), 'words': J.get('words'), 'do': J.get('do'), 'labels': J.get('labels'), 'note': J.get('note'), 'name': J.get('name'), 't': J.get('t'), **sc})
        if sc['state'] == 'scored':
            for k, v in sc['tally'].items(): tot[k] += v
        else: tot[sc['state']] += 1
    return {'n': len(rows), 'totals': tot, 'rows': rows}

@app.get('/report')
def report(set_: str = Query(None, alias='set'), key: str = None):
    """the report card (after Iqra'Eval's planted-mistake test sets): every graded booth take scored against what the
       person said they did, summed per kind of take and per person. caught / missed / unsure count the planted
       mistakes; false alarms count notes on things done right; claims are notes nobody has judged yet."""
    d = need_key(key)
    if d: return d
    by_do, by_who = {}, {}
    def add(D, k, sc):
        R = D.setdefault(k, {'takes': 0, 'scored': 0, 'false_alarm': 0, 'caught': 0, 'missed': 0, 'unsure': 0, 'claims': 0})
        R['takes'] += 1
        if sc.get('state') == 'scored':
            R['scored'] += 1
            for kk, v in sc['tally'].items(): R[kk] = R.get(kk, 0) + v
    for J in list_takes(set_):
        if not isinstance(J, dict) or 'id' not in J: continue
        try: sc = score_take(J)
        except Exception: continue
        add(by_do, J.get('do') or 'right', sc); add(by_who, J.get('name') or '?', sc)
    for D in (by_do, by_who):
        for R in D.values():
            planted = R['caught'] + R['missed'] + R['unsure']
            R['caught_rate'] = round(R['caught'] / planted, 3) if planted else None
    right = by_do.get('right') or {}
    return {'set': set_, 'by_do': by_do, 'by_who': by_who,
            'false_alarms_per_right_take': round(right.get('false_alarm', 0) / right['scored'], 3) if right.get('scored') else None}
