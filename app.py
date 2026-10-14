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

Endpoints (JSON, CORS open):  GET /health   GET /info   GET /lyrics (the site's lyrics.json + the Tehillim perakim)
  GET  /ref?f=<archive mp3 | tehillim-NNN.mp3>&t0=&t1=&words=<line>   the hazzan's line
  POST /check?words=<line>[&ref=<f>&t0=&t1=][&nikud=<pointed line>][&drill=throat|plain]  body=audio  the take,
       against the hazzan when ref is given (fit, throat letters, vowels), against the nikud when given
  GET  /drill, /drill/export                                   the drill recordings kept here (features + labels)
  GET  /tehillim/audio/<file>                                  a Rabbi Alouf recording
Nothing here deploys or changes the site.
"""
import os, re, sys, json, time, hashlib, subprocess, tempfile, threading
import numpy as np
import torch
import requests
from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, RedirectResponse

T_START = time.time()
torch.set_num_threads(max(1, os.cpu_count() or 1))
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
        if pk >= .5: votes['throat'].append('arabic')
        elif heard != 'ع' and pk < .15 and al >= .4: votes['plain'].append('arabic')
    else:
        if hd and sum(hd['mass'].values()) >= .2:
            r = hd['mass'].get('ח', 0) / sum(hd['mass'].values())
            if r >= .7: votes['throat'].append('head')
            elif r <= .3: votes['plain'].append('head')
        if p is not None:
            if p >= .7: votes['throat'].append('classifier')
            elif p <= .3: votes['plain'].append('classifier')
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
    for i, w in enumerate(W):
        w['phones'] = heard_in(seq, w['t0'], w['t1'])
        w['ids'] = [VOCAB[p] for p in w['phones'] if p in VOCAB]
        w['hskel'] = hw.get(i)
        w['kept'] = kp.get(i, {}).get('kept'); w['miss'] = kp.get(i, {}).get('miss', [])
        if flp is not None and (FULL is not None or FT is not None):
            w['vow'] = [{'k': s['k'], 'heard': s['heard'], 'mass': s['mass'], 'p': s['p'], 't0': round(s['f0'] * ar_spf, 3), 't1': round(s['f1'] * ar_spf, 3)} for s in vs.get(i, [])]
            w['vskel'] = vl.get(i)
        for th in w['throat']:
            th.update(throat_probe(lp, spf, H, th, ar_lp, ar_spf, ar_hits.get((i, th['k'])), want_emb, AH, hl.get((i, th['k'])))); th['heard'] = heard_in(seq, th['t0'], th['t1'])
    return {'dur': round(x.shape[0] / SR, 3), 'spf': round(spf, 5), 'words': W, 'phones': seq, 'ms': int((time.time() - t) * 1000)}, lp, spf

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

@app.get('/', response_class=HTMLResponse)
def home():
    """the lab page itself, from the same origin so the phone's microphone works in it"""
    try:
        body = open(STATIC, encoding='utf-8').read()
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
    return {'ok': True, 'version': 4.1, 'device': DEV, 'uptime_s': int(time.time() - T_START), 'phone_model': PH_ID, 'arabic_model': AR_ID, 'vocab': len(VOCAB), 'classifiers': list(CLF),
            'ears': {'letter_head': HEAD is not None, 'vowel_head': FULL is not None, 'fine_tuned': FT is not None, 'classifier_v2': bool(CLF2), 'tehillim_lyrics': len(TEHILLIM_LYR), 'tehillim_audio': os.path.isdir(TEHILLIM_DIR) and len(os.listdir(TEHILLIM_DIR)) or (TEHILLIM_BASE or 0)}}

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
threading.Thread(target=warm_up, daemon=True).start()

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

@app.post('/check')
async def check(request: Request, words: str = Query(...), ref: str = None, t0: float = 0, t1: float = 0, emb: int = 0, drill: str = None, nikud: str = None):
    W = he_words(words)
    if not W:
        return JSONResponse({'err': 'no words'}, status_code=400)
    data = await request.body()
    if len(data) < 1000:
        return JSONResponse({'err': 'no audio'}, status_code=400)
    try:
        x = decode_audio(data)
    except Exception as e:
        return JSONResponse({'err': 'decode: ' + str(e)[:200]}, status_code=400)
    if x.shape[0] < SR * 0.5:
        return JSONResponse({'err': 'too short'}, status_code=400)
    if x.shape[0] > SR * 40:
        x = x[:SR * 40]
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
