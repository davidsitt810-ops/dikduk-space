"""The word rule: what the page shows for a take (green / "not sure" / red per word, the whole-line verdicts) from the
numbers /check returns. One copy for the server (the booth's scoreboard), the exams and the tests; static/index.html
(markOf) and static/embed.js carry the same rule in JavaScript, and tools/t_parity.py checks them against this file
on every exam row. No models here: numpy only, so the tests and the exams can import it anywhere."""
import numpy as np

def mark_of(y, f, clean):
    """the page's rule for one word (kept in step with static/index.html markOf and embed.js)"""
    n = y.get('n') or 0; sk = y.get('skel'); ft = f.get('fit') if f else None
    if not n or sk is None: return ''
    kp = y.get('kept'); pw = y.get('pw'); hs = y.get('hskel')
    sure = clean and kp is not None and kp >= .75 and hs is not None and hs >= .6 and (pw is None or pw < .8)
    if n >= 2:
        if sk < .2 and (ft is None or ft < .15):
            if ft is None and clean and not (kp is not None and kp < .75): return 'unsure'   # no hazzan to confirm: red needs the head's agreement
            if not clean and kp is not None and kp >= .5: return 'unsure'   # v4.4: a take the heads hear poorly: red needs the head to agree (under half the letters heard)
            return 'off'
        if clean and pw is not None and pw >= .95 and (ft is None or ft < .5): return 'off'   # v4.4: not when the hazzan's own sounds for the word were found
        if sure: return 'ok'
        if sk < .4 or (ft is not None and ft < .2) or (kp is not None and kp < .5) or (pw is not None and pw >= .8): return 'unsure'
        return 'ok'
    return 'unsure' if sk < .2 and not sure else 'ok'

RULE = {'drop': 10, 'margin': 4, 'swap': 8, 'rival': 0.3, 'altFit': 0.4, 'hear': 0.3, 'share': 0.35, 'half': 0.5, 'swap2': 12}   # kept in step with static/index.html and embed.js

def head_median(TW):
    """the letter head's score on the line's words (2+ consonants), the median — with the lowest word left out when
       there are three or more, so that one wrong word does not make a good recording look poor (v4.4)"""
    hs = sorted(t['hskel'] for t in TW if (t.get('n') or 0) >= 2 and t.get('hskel') is not None)
    if not hs: return None
    if len(hs) >= 3: hs = hs[1:]
    return hs[(len(hs) - 1) // 2]   # the lower middle: one well-heard word does not make a short line clean

def no_speech_in(take):
    """fewer phones heard than any singing would give: under 3, or under one every two seconds (kept in step with the page)"""
    n = len(take.get('phones') or []); dur = take.get('dur') or 0
    return n < max(3, 0.5 * dur)

def clean_of(TW):
    """a clean take: the heads hear the line well enough for the finer signals (pw, the whole-line evidence)"""
    m = head_median(TW); return m is not None and m >= .7

def marks_of(TW, F, gap, clean, rival=None):
    """the page's verdict per word (markOf + the whole-line evidence on a clean take; the line gap on every take;
       a take the head barely hears gets no red) -> (marks, why, line_wrong, cant_hear)"""
    marks = [mark_of(TW[i], F[i] if F and i < len(F) else None, clean) for i in range(len(TW))]; why = [None] * len(TW); line_wrong = False; cant_hear = False
    if clean and TW:
        ds = [t['drop'] if t.get('drop') is not None else -1e9 for t in TW]; top = int(np.argmax(ds)); second = max([d for i, d in enumerate(ds) if i != top], default=-1e9)
        dropped = (TW[top].get('n') or 0) >= 2 and ds[top] >= RULE['drop'] and ds[top] - second >= RULE['margin']
        # a word whose consonants the phone recognizer found in place, with most letters kept, is not "not heard": doubtful at most
        heard = (TW[top].get('skel') or 0) >= .8 and (TW[top].get('kept') or 0) >= .6
        if dropped and not heard: marks[top] = 'off'; why[top] = 'dropped'
        elif dropped and marks[top] == 'ok': marks[top] = 'unsure'
        sw = [t['swap'] if t.get('swap') is not None else -1e9 for t in TW[:-1]]
        if sw:
            j = int(np.argmax(sw)); na, nb = TW[j].get('n') or 0, TW[j + 1].get('n') or 0
            # a skipped word also "gains" a little from being swapped with its neighbour (8-14 nats against a drop of
            # 27-72); a real swap gains at least 0.4 of the drop (0.8-3.3 on Rabbi Alouf, 52 of 52). Under that share the
            # pair's dropped word is a skip, and the neighbour is left alone
            pd = max(ds[j], ds[j + 1]); same = pd >= RULE['drop'] and sw[j] < RULE['share'] * pd   # (the pair's own largest drop: two skipped words in one line have no single winner)
            if sw[j] >= RULE['swap'] and max(na, nb) >= 2 and min(na, nb) >= 1 and not same: marks[j] = marks[j + 1] = 'off'; why[j] = why[j + 1] = 'swapped'
    elif TW:
        # a take heard half-well (head median .5-.7): the drop evidence is not safe there (right words reach 40+ on the
        # archive), the swap evidence is — right takes top out at 5.8, real swaps 12-62 — at a higher bar
        m = head_median(TW); sw = [t['swap'] if t.get('swap') is not None else -1e9 for t in TW[:-1]]
        if m is not None and m >= RULE['half'] and sw:
            j = int(np.argmax(sw)); na, nb = TW[j].get('n') or 0, TW[j + 1].get('n') or 0
            ds = [t['drop'] if t.get('drop') is not None else -1e9 for t in TW]; pd = max(ds[j], ds[j + 1]); same = pd >= RULE['drop'] and sw[j] < RULE['share'] * pd
            if sw[j] >= RULE['swap2'] and max(na, nb) >= 2 and min(na, nb) >= 1 and not same: marks[j] = marks[j + 1] = 'off'; why[j] = why[j + 1] = 'swapped'
    # not this line: another line of the same text beats the written one by 0.3 nats a frame AND fits the audio
    # well itself (its own gap to the free path under 0.4). Measured: Rabbi Alouf's wrong pasuk 70/70, his right
    # pasuk 0/70; 80 Israelis reading other sentences — voices the head reads poorly — 0/80 right ones called wrong
    # (the free-path gap alone called 33 of those 80 wrong: a poorly read voice raises it just like a wrong text).
    # Without the text's other lines (free words) there is no wrong-line verdict.
    rg = rival.get('gain') if isinstance(rival, dict) else None; rh = rival.get('head') if isinstance(rival, dict) else None
    # ... and the other line must itself be heard (its head median >= .3): on an unreadable take a short line can "win" by a hair
    if TW and gap is not None and rg is not None and rg >= RULE['rival'] and (gap - rg) <= RULE['altFit'] and (rh is None or rh >= RULE['hear']):
        line_wrong = True; marks = ['unsure' if m == 'ok' else m for m in marks]
    # the head barely hears the words (instruments, a far microphone): nothing is red, the doubtful words are 'unsure'
    if TW and not clean and not line_wrong:
        m = head_median(TW)
        if m is not None and m < RULE['hear']: cant_hear = True; marks = ['unsure' if x == 'off' else x for x in marks]; why = [None if w in ('dropped', 'swapped') else w for w in why]
    return marks, why, line_wrong, cant_hear

def strict_of(marks, why, clean, cant_hear):
    """the strict check (the page's switch): on a clean take every 'not sure' word counts as not clearly right.
       Rabbi Alouf's exam: wrong words caught 76% -> 89%, good words marked 0 -> 0.4%. On an unclear take nothing
       changes — there it would mark a fifth of the good words — and the page asks for a clearer take instead.
       -> (marks, why, on). Kept in step with strictOf in index.html and embed.js"""
    if not clean or cant_hear: return marks, why, False
    return ['off' if m == 'unsure' else m for m in marks], ['unclear' if marks[i] == 'unsure' and w is None else w for i, w in enumerate(why)], True

def summarize(out):
    """the machine's claims about one take, in the page's words: marks per word, throat verdicts, vowel differences"""
    W, TW, F = out['words'], out['take']['words'], (out.get('fit') or None)   # an empty fit list is no fit
    clean = clean_of(TW)
    marks, why, line_wrong, cant_hear = marks_of(TW, F, out['take'].get('gap'), clean, out['take'].get('rival'))
    # no singing in the recording at all (silence, noise, a microphone that did not pick the person up): the phone
    # recognizer hears nothing — reading gives ~4 phones a second, slow singing 1.5, noise and silence 0
    no_speech = no_speech_in(out['take'])
    if no_speech: marks = ['unsure' if m else m for m in marks]; why = [None] * len(why); line_wrong = False; cant_hear = False
    RW = (out.get('ref') or {}).get('words')
    def hv(i, k):
        if not RW or i >= len(RW): return None
        r = next((x for x in (RW[i].get('throat') or []) if x.get('k') == k), None); return r.get('v') if r else None
    throat = [{'c': th['c'], 'w': W[i], 'k': th['k'], 'v': th.get('v'), 'hazzan': hv(i, th['k']), 'mark': marks[i]} for i, t in enumerate(TW) for th in (t.get('throat') or [])]
    if not clean:   # a "plain" verdict on a poorly heard take is not a fault to show (another hazzan with instruments: 9 such of 144, all on non-clean takes); the raw verdict stays for the lab
        for th in throat:
            if th['v'] == 'plain': th['raw'] = 'plain'; th['v'] = 'unsure'
    VN = out.get('vowel_names') or {}; nm = lambda k: (VN.get(k) or k).split(' ')[0]
    vow = []
    for src, against in (((out.get('vowels'), 'hazzan'), (out.get('vowels_nikud'), 'nikud')) if clean else ()):   # vowel notes only on a clean take (another voice with instruments gave one note per 4.5 right words)
        for i, ds in (src or {}).items():
            if marks[int(i)] == 'off': continue   # a word that was not there has no vowels to speak of
            for d in ds: vow.append({'w': W[int(i)], 'k': d['k'], 'you': nm(d['you']), 'ref': nm(d['ref']), 'against': against})
    miss = {W[i]: t['miss'] for i, t in enumerate(TW) if t.get('miss')}
    # shva na / nah notes (v4.9): as the vowels, only on a clean take and only in words that were there
    shv = [{'w': W[int(i)], 'k': d['k'], 'c': d['c'], 'you': d['you'], 'want': d['want'], 'rule': d['rule'], 'by': d['by']}
           for i, ds in ((out.get('shva') or {}).items() if clean else ()) if int(i) < len(W) and marks[int(i)] != 'off' for d in ds]
    if cant_hear or no_speech: throat, vow, miss, shv = [], [], {}, []   # the words were not made out: no claims about the letters inside them
    return {'marks': marks, 'why': why, 'line_wrong': line_wrong, 'cant_hear': cant_hear, 'no_speech': no_speech, 'rival': out['take'].get('rival'), 'gap': out['take'].get('gap'), 'throat': throat, 'vowels': vow, 'shva': shv, 'miss': miss, 'clean': clean, 'head': head_median(TW), 'hazzan': bool(F), 'dur': out['take'].get('dur')}
