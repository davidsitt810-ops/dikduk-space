"""ctc_local: CTC Viterbi with free states before and after the text (copied from voice_register.py)."""
import numpy as np

def ctc_local(lp, toks, blank, vocab_n, pen=0.05):
    """Viterbi over [free-before] + blank-interleaved tokens + [free-after]; the free states score each frame's best
    real symbol minus `pen`. -> (per token {'f0','f1','score'} or f0=-1, first frame, end frame) in window frames"""
    Tn = lp.shape[0]; S = 2 * len(toks) + 1
    ext = np.array([blank if s % 2 == 0 else toks[(s - 1) // 2] for s in range(S)])
    skip_ok = np.array([s > 1 and ext[s] != blank and ext[s] != ext[s - 2] for s in range(S)])
    free = lp[:, :vocab_n].max(1) - pen
    NEG = -1e30
    pre = free[0]; cur = np.full(S, NEG); cur[0] = lp[0, ext[0]]
    if S > 1: cur[1] = lp[0, ext[1]]
    post = NEG
    bp = np.zeros((Tn, S), dtype=np.int8)          # 0 stay, 1 step, 2 skip, 3 from free-before
    bp_post = np.zeros(Tn, dtype=np.int8)          # 0 stay in post, 1 from last blank, 2 from last token
    for t in range(1, Tn):
        prev = cur
        step = np.concatenate(([NEG], prev[:-1])); skip = np.where(skip_ok, np.concatenate(([NEG, NEG], prev[:-2])), NEG)
        best = prev.copy(); b = np.zeros(S, dtype=np.int8)
        m = step > best; best[m] = step[m]; b[m] = 1
        m = skip > best; best[m] = skip[m]; b[m] = 2
        for s0 in (0, 1):                           # entering the text from free-before
            if s0 < S and pre > best[s0]: best[s0] = pre; b[s0] = 3
        # free-after: stay, or arrive from the last blank / last token (their scores at t-1)
        cands = [post, prev[S - 1], prev[S - 2] if S > 1 else NEG]
        k = int(np.argmax(cands)); post = cands[k] + free[t]; bp_post[t] = k
        cur = best + lp[t, ext]; bp[t] = b
        pre = pre + free[t]
    ends = [post, cur[S - 1], cur[S - 2] if S > 1 else NEG]
    k = int(np.argmax(ends))
    path = np.full(Tn, -1, dtype=np.int64)          # -1 free-before, -2 free-after, else state
    t = Tn - 1
    if k == 0:
        while t > 0 and bp_post[t] == 0: path[t] = -2; t -= 1
        if t == 0: return [{'f0': -1, 'f1': -1, 'score': 0.0} for _ in toks], -1, -1
        path[t] = -2; s = S - 1 if bp_post[t] == 1 else S - 2; t -= 1
    else:
        s = S - 1 if k == 1 else S - 2
    while t >= 0:
        path[t] = s
        if t == 0: break
        d = int(bp[t, s])
        if d == 3:
            t -= 1
            while t >= 0: path[t] = -1; t -= 1
            break
        s -= d; t -= 1
    out = [{'f0': -1, 'f1': -1, 'sum': 0.0, 'n': 0} for _ in toks]
    for t in range(Tn):
        st = int(path[t])
        if st < 0 or st % 2 == 0: continue
        o = out[(st - 1) // 2]
        if o['f0'] < 0: o['f0'] = t
        o['f1'] = t + 1; o['sum'] += float(np.exp(lp[t, ext[st]])); o['n'] += 1
    inside = np.where(path >= 0)[0]
    first = int(inside[0]) if len(inside) else -1; last = int(inside[-1]) + 1 if len(inside) else -1
    return [{'f0': o['f0'], 'f1': o['f1'], 'score': (o['sum'] / o['n']) if o['n'] else 0.0} for o in out], first, last
