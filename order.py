"""Word-order and word-presence evidence from forced alignment scores.

The checker's other signals look at each word on its own (its consonants found, its letters kept). These compare
WHOLE LINES: the best-path log-probability of the line as written, against the same line with
  - two neighbouring words swapped        -> swap gain  (positive: the audio prefers the swapped order)
  - one word left out                      -> drop gain  (positive: the audio prefers the line without that word)
  - nothing forced at all (the free path)  -> line gap   (nats per frame the written line costs; large = another text)
All on one log-prob matrix (the letter head's, or the phone recognizer's with the skeleton's virtual columns), so a
dozen extra Viterbi passes cost well under a second. Gains are in nats; a swapped pair of short words gains a few,
a swapped pair of long words tens; the per-token versions divide by the letters involved."""
import numpy as np

NEG = -1e30

def ctc_best(lp, toks, blank):
    """log-probability of the best blank-interleaved path for toks on lp (plain Viterbi, no optional tokens)"""
    T = lp.shape[0]; S = 2 * len(toks) + 1
    if S == 1: return float(lp[:, blank].sum())
    ext = np.array([blank if s % 2 == 0 else toks[(s - 1) // 2] for s in range(S)])
    skip_ok = np.array([s > 1 and ext[s] != blank and ext[s] != ext[s - 2] for s in range(S)])
    prev = np.full(S, NEG); prev[0] = lp[0, ext[0]]; prev[1] = lp[0, ext[1]]
    col = lp[:, ext]
    for t in range(1, T):
        step = np.concatenate(([NEG], prev[:-1]))
        skip = np.where(skip_ok, np.concatenate(([NEG, NEG], prev[:-2])), NEG)
        prev = np.maximum(np.maximum(prev, step), skip) + col[t]
    return float(max(prev[S - 1], prev[S - 2]))

def line_tokens(lp, words, s2i, he_read, pairs=(('ע', 'א'), ('ח', 'כ'))):
    """the letters of each word as tokens on the head (ע/א and ח/כ merged into a virtual 'either' column, as the
       other letter signals do) -> (lp2 with the extra columns, [tokens per word], space token or None)"""
    cols, extra, per_word = {}, [], []
    for w in words:
        toks = []
        for c in he_read(w):
            if c not in s2i: continue
            pair = next((p for p in pairs if c in p), None)
            if pair:
                key = ''.join(pair)
                if key not in cols: cols[key] = lp.shape[1] + len(extra); extra.append(np.logaddexp.reduce(lp[:, [s2i[m] for m in pair]], axis=1))
                toks.append(cols[key])
            else: toks.append(s2i[c])
        per_word.append(toks)
    lp2 = np.concatenate([lp] + ([np.stack(extra, 1)] if extra else []), 1)
    return lp2, per_word, s2i.get(' ')

def joined(per_word, space):
    out = []
    for i, t in enumerate(per_word):
        out += t
        if space is not None and i + 1 < len(per_word): out.append(space)
    return out

def order_from_tokens(lp2, per_word, space=None, blank=0):
    """the scores for a tokenized line (see order_evidence for the shape of the answer)"""
    n = len(per_word)
    if n == 0 or not any(per_word): return {'gap': None, 'orig': None, 'drop': [0.0] * n, 'swap': [0.0] * max(0, n - 1), 'drop_tok': [0.0] * n, 'swap_tok': [0.0] * max(0, n - 1)}
    orig = ctc_best(lp2, joined(per_word, space), blank)
    free = float(lp2.max(1).sum())
    drop, drop_tok = [], []
    for j in range(n):
        if not per_word[j]: drop.append(0.0); drop_tok.append(0.0); continue
        sc = ctc_best(lp2, joined(per_word[:j] + per_word[j + 1:], space), blank)
        drop.append(round(sc - orig, 2)); drop_tok.append(round((sc - orig) / len(per_word[j]), 3))
    swap, swap_tok = [], []
    for j in range(n - 1):
        if not per_word[j] or not per_word[j + 1]: swap.append(0.0); swap_tok.append(0.0); continue
        pw = per_word[:j] + [per_word[j + 1], per_word[j]] + per_word[j + 2:]
        sc = ctc_best(lp2, joined(pw, space), blank)
        swap.append(round(sc - orig, 2)); swap_tok.append(round((sc - orig) / (len(per_word[j]) + len(per_word[j + 1])), 3))
    return {'gap': round((free - orig) / lp2.shape[0], 4), 'orig': round(orig, 1), 'drop': drop, 'swap': swap, 'drop_tok': drop_tok, 'swap_tok': swap_tok}

def order_evidence(lp, words, s2i, he_read, blank=0, pairs=(('ע', 'א'), ('ח', 'כ'))):
    """on the letter head: -> {'gap': nats/frame the written line costs over the free path, 'orig': its score,
           'drop': [gain of leaving word j out], 'swap': [gain of swapping j and j+1], 'drop_tok', 'swap_tok': per letter}"""
    lp2, per_word, space = line_tokens(lp, words, s2i, he_read, pairs)
    return order_from_tokens(lp2, per_word, space, blank)
