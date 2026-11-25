"""How well could the facts known about a vowel note be combined into one "how far to trust it" number? A logistic
fit on the note tables (bench/notes_table.py), to see what is to be had beyond simple bars — not a rule in itself.
A note on the correct reading is false; a note of the planted kind on the planted word is true. The planted exam has
one mistake per pasuk and a reader has far fewer, so the true notes are weighed down to PRIOR mistakes per 100 words
(default 5) before anything is counted as precision.

usage: trust.py <train table>[+<table>...] [<test table>[+...]]      PRIOR=5 (mistakes per 100 words)
       FEATS=bias,vskel,you,...  only these facts (vowels.TRUST_NAMES); L2=1; OUT=<json to keep the weights in>
       GRID=.3,.4,.5,.6          the bars to list (default: quantiles of the scores)
       CV=1 trust.py <table>[+...]   out-of-fold: what each group of facts adds"""
import sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as RP
PRIOR = float(os.environ.get('PRIOR', 5)) / 100

def load(spec):
    T = []
    for nm in spec.split('+'): T += json.load(open(os.path.join(RP.V, f'table_{nm}.json'), encoding='utf-8'))
    return T
def cands(T):
    """the notes that could be shown: (features, true?, row)"""
    out = []
    for x in T:
        if not x['note'] or x['mark'] == 'off' or x['cant']: continue
        if x['kind'] == 'right': y = 0
        elif x['planted'] and x.get('hit'): y = 1
        else: continue
        out.append((feat(x), y, x))
    return out
NAMES = RP.VW.TRUST_NAMES
def feat(x): return x['f']   # vowels.note_features, kept in the table: the fit and the server read the same numbers
def weights(C, T):
    """true notes weighed so that the planted words stand for PRIOR mistakes per word of the correct reading"""
    W = sum(1 for x in T if x['kind'] == 'right'); P = sum(1 for x in T if x['planted'])
    wt = PRIOR * W / max(1, P) / (1 - PRIOR)
    return np.array([wt if y else 1.0 for _, y, _ in C]), wt
def fit(C, w, l2=1.0, it=3000, lr=.5):
    X = np.array([f for f, _, _ in C]); y = np.array([y for _, y, _ in C], dtype=float); b = np.zeros(X.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-X @ b)); g = X.T @ (w * (p - y)) / w.sum() + l2 * np.r_[0, b[1:]] / len(y); b -= lr * g
    return b
def curve(C, T, score, label):
    w, wt = weights(C, T); W = sum(1 for x in T if x['kind'] == 'right'); P = sum(1 for x in T if x['planted'])
    s = np.array([score(f, x) for f, _, x in C]); y = np.array([y for _, y, _ in C])
    print(f'   {label}: {int(y.sum())} true notes of {P} planted words, {int((1 - y).sum())} false on {W} right words (a true note weighs {wt:.3f})')
    ths = sorted(set(np.round(np.quantile(s, [0, .02, .05, .1, .15, .2, .3, .4, .5]), 4))) if len(set(np.round(s, 6))) > 3 and not os.environ.get('GRID') else sorted(set(np.round(s, 6)))
    if os.environ.get('GRID') and len(set(np.round(s, 6))) > 3: ths = [float(x) for x in os.environ['GRID'].split(',')]
    for th in ths:
        k = s >= th; tp = int((y[k] == 1).sum()); fp = int((y[k] == 0).sum())
        print(f'     score >= {th:7.3f}: told {100 * tp / P:5.1f}% of planted | false notes {100 * fp / W:5.2f}% of right words | of the notes shown, true {100 * tp * wt / max(1e-9, tp * wt + fp):5.1f}%')

def cv_scores(C, T, cols, folds=5):
    """out-of-fold scores: the takes split in folds by perek and pasuk, a fit on the rest (only the columns cols)"""
    keys = sorted({(x['per'], x['ps']) for _, _, x in C}); fold = {k: i % folds for i, k in enumerate(keys)}; s = np.zeros(len(C))
    for f in range(folds):
        tr = [c for c in C if fold[(c[2]['per'], c[2]['ps'])] != f]; te = [i for i, c in enumerate(C) if fold[(c[2]['per'], c[2]['ps'])] == f]
        Ctr = [([c[0][j] for j in cols], c[1], c[2]) for c in tr]; w, _ = weights(Ctr, T); b = fit(Ctr, w)
        for i in te: s[i] = float(np.dot([C[i][0][j] for j in cols], b))
    return s
def at_false(C, T, s, targets=(0.5, 0.75, 1.0, 1.25, 1.5)):
    """planted told at given false-note rates (per 100 right words): the scores' curve read at those points"""
    W = sum(1 for x in T if x['kind'] == 'right'); P = sum(1 for x in T if x['planted']); y = np.array([c[1] for c in C]); order = np.argsort(-s); out = []
    for t in targets:
        fp = tp = 0; best = 0
        for i in order:
            if y[i]: tp += 1
            else:
                fp += 1
                if 100 * fp / W > t: break
            best = tp
        out.append(f'{100 * best / P:5.1f}%')
    return ' '.join(out)

if __name__ == '__main__':
    if os.environ.get('CV'):
        A = load(sys.argv[1]); C = cands(A); ix = {n: i for i, n in enumerate(NAMES)}
        EAR = ['you', 'you*c', 'ref', 'ref*c', 'none']; FAR = ['you far', 'ref far']
        sets = [('the take gate alone', ['bias', 'gate']), ('the gate + the word (hskel, vskel)', ['bias', 'gate', 'hskel', 'vskel']), ('the gate + the word + the slot (m)', ['bias', 'gate', 'hskel', 'vskel', 'm']),
                ('... + the phone ear at the same moment', ['bias', 'gate', 'hskel', 'vskel', 'm'] + EAR), ('... + the phone ear in the same syllable', ['bias', 'gate', 'hskel', 'vskel', 'm'] + EAR + FAR),
                ('... + the take (head, gap) = everything', NAMES), ('everything but the gate', [n for n in NAMES if n != 'gate']),
                ('the word, the slot, the phone ear (no take)', ['bias', 'hskel', 'vskel', 'm'] + EAR + FAR), ('vskel, the slot, the phone ear', ['bias', 'vskel', 'm'] + EAR + FAR),
                ('the word alone', ['bias', 'hskel', 'vskel']), ('the phone ear alone', ['bias'] + EAR + FAR), ('the phone ear alone, same moment only', ['bias'] + EAR)]
        W = sum(1 for x in A if x['kind'] == 'right'); P = sum(1 for x in A if x['planted'])
        print(f'{sys.argv[1]}: {len(C)} notes ({sum(c[1] for c in C)} true of {P} planted words, {sum(1 - c[1] for c in C)} false on {W} right words); out-of-fold, planted told at 0.5 / 0.75 / 1.0 / 1.25 / 1.5 false notes per 100 right words:')
        for label, names in sets: print(f'   {label:38s} {at_false(C, A, cv_scores(C, A, [ix[n] for n in names]))}')
        sys.exit(0)
    # the fit itself: on the first tables, with only the facts named in FEATS (the others weigh 0); kept in OUT (json)
    A = load(sys.argv[1]); B = load(sys.argv[2]) if len(sys.argv) > 2 else None
    use = os.environ['FEATS'].split(',') if os.environ.get('FEATS') else NAMES; cols = [NAMES.index(n) for n in use]
    CA = cands(A); Csub = [([c[0][j] for j in cols], c[1], c[2]) for c in CA]; w, _ = weights(Csub, A); bs = fit(Csub, w, l2=float(os.environ.get('L2', 1.0)))
    b = np.zeros(len(NAMES)); b[cols] = bs
    print('fitted on', sys.argv[1], f'(a mistake on {100 * PRIOR:g} of 100 words; {len(CA)} notes, {sum(c[1] for c in CA)} true):'); print('   TRUST_W = [' + ', '.join(f'{v:.3f}' for v in b) + ']'); print('   ' + ', '.join(f'{n} {v:+.2f}' for n, v in zip(NAMES, b)))
    if os.environ.get('OUT'): json.dump({'names': NAMES, 'w': [round(float(v), 4) for v in b], 'fitted_on': sys.argv[1], 'prior': PRIOR}, open(os.environ['OUT'], 'w'))
    sig = lambda z: 1 / (1 + math.exp(-z))
    for nm, T in ((sys.argv[1], A),) + (((sys.argv[2], B),) if B else ()):
        C = cands(T); print(f'== on {nm}')
        curve(C, T, lambda f, x: sig(float(np.dot(f, b))), "the fit (the note's trust, 0..1)")
        curve(C, T, lambda f, x: 1.0 if x['vclean'] else 0.0, 'v5.9 (the take gate): score 1 = shown')
