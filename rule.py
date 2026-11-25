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

# drop (v5.6): a word is "not heard" (red, "dropped") when the line is at least 20 nats better without it (was 10). On a voice
# the checker never heard (Faraj Samra, every pasuk: 13,498 right words) 47 of his 50 red words were this call, at 10-29
# nats; at 20, 39 of them go (25 to ok, 14 to "not sure"), while a word cut out of his audio is still red 344 of 500
# times (was 350; the 6 become "not sure", none passes). On the committed exams (tools/rule_baseline.py) no skipped,
# swapped or replaced word passes either; five go from red to "not sure" — three of Rabbi Alouf's 80 skipped words
# (exam2, dropped by 11-14 nats), one Israeli swapped pair, one replaced word — and right words red 1-2 fewer per
# Israeli exam (LAB_NOTES §39).
# The skip-vs-swap guard below also reads this bar, but cannot move with it: a swap that could fire has swap >= 8, and
# the guard needs swap < 0.35 x the drop, so a drop above 22.9 — over both bars.
RULE = {'drop': 20, 'margin': 4, 'swap': 8, 'rival': 0.3, 'altFit': 0.4, 'hear': 0.3, 'share': 0.35, 'half': 0.5, 'swap2': 12, 'vhead': 0.62, 'vgap': 0.17, 'noisy': 26, 'vp': 0.5}   # kept in step with static/index.html and embed.js

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

# vowel notes (v5.7): on a clean take, and also on a take the letter head hears fairly well (median >= .62) whose written
# line the audio follows closely (the line gap to free decoding <= .17). A phone in a room puts a third to a half of a
# good reader's takes under .70 while the vowel ear still hears them as well: on those the notes came back (planted
# e-for-i told on the phone 52% -> 69% for Faraj Samra, 44% -> 68% for Shmuelof; his correct reading noted 1.5% -> 1.9%),
# and the gap keeps out a poor recording, where the ear does not (Daya's Tehillim: 1.2% -> 1.8%, against 4.6% with the
# head alone). The word marks keep the .70 bar: moved for them too, right words red rise (LAB_NOTES §39).
def vclean_of(TW, gap, clean, nikud=True):
    """the take is clear enough for the vowel notes (kept in step with vcleanOf in index.html and embed.js). The lower
       bar only where the line has nikud, where it was measured (Tehillim; the nikud cross-checks the hazzan's notes).
       Against another hazzan alone (a pizmon) it is not measured: on the archive's accompanied takes it opened 9 right
       takes of 98 with notes on 7 of their 54 words (the clean ones: 12 of 86), and there were no mistakes to catch
       (LAB_NOTES §40)"""
    if clean: return True
    if not nikud: return False
    m = head_median(TW)
    return m is not None and m >= RULE['vhead'] and gap is not None and gap <= RULE['vgap']

# How far to trust each vowel note (v6.0). Until v5.9 the TAKE alone decided (vclean_of): under the gate no vowel note,
# over it all of them. Now the server gives every note of a line with nikud its own number ('p', 0..1:
# vowels.note_trust — how well the two heads heard the note's word, how much of the slot the vowel holds, and whether
# the phone ear, another network, wrote the same vowel at that moment), and a note shows when it is at least 'vp'.
# So a word heard well is checked also in a take that is not clear overall (David's own phone takes of Tehillim 23:2,
# Nov 1: nothing shown, a real "menohot" among them), and a doubtful note on a clear take is left out.
# No 'p' (a server before v6.0) or a line without nikud, where it is not measured: the take's gate, as before.
def note_shown(d, vclean, nikud=True):
    """is this vowel note shown? d: the note ('p' when the server rated it); vclean: the take's gate (vclean_of).
       Kept in step with noteShown in index.html and embed.js"""
    p = d.get('p')
    if p is None or not nikud: return bool(vclean)
    return p >= RULE['vp']

def rate_notes(out):
    """the server's last step on a take's vowel notes (app.run_check; the bench replays answers through the same
       lines): on every note the phone ear's second opinion ('ph', 'phc': vowels.second_opinion) and, on a line with
       nikud, its trust ('p': vowels.note_trust)"""
    import vowels as VW
    take = out['take']; TW = take['words']
    for k in ('vowels', 'vowels_nikud'): VW.second_opinion(out.get(k), TW, take.get('phones'))
    out['vowels_2nd'] = True
    if VW.TRUST_W is not None and out.get('vowels_nikud') is not None:
        gate = vclean_of(TW, take.get('gap'), clean_of(TW), True); hm = head_median(TW)
        for k in ('vowels', 'vowels_nikud'):
            for i, ds in (out.get(k) or {}).items():
                for d in ds: d['p'] = VW.note_trust(d, TW[int(i)], gate, hm, take.get('gap'))
        out['vowels_trust'] = True
    return out

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
    has_nik = out.get('vowels_nikud') is not None
    vclean = vclean_of(TW, out['take'].get('gap'), clean, has_nik)
    # vowel notes: each by its own trust where the server gives one (note_shown, v6.0); else on a take clear enough for
    # them (vclean_of, v5.7; another voice with instruments gave one note per 4.5 right words)
    for src, against in ((out.get('vowels'), 'hazzan'), (out.get('vowels_nikud'), 'nikud')):
        for i, ds in (src or {}).items():
            if marks[int(i)] == 'off': continue   # a word that was not there has no vowels to speak of
            for d in ds:
                if note_shown(d, vclean, has_nik): vow.append({'i': int(i), 'w': W[int(i)], 'k': d['k'], 'you': nm(d['you']), 'ref': nm(d['ref']), 'against': against})
    miss = {W[i]: t['miss'] for i, t in enumerate(TW) if t.get('miss')}
    # shva na / nah notes (v4.9): as the vowels, only on a clean take and only in words that were there
    shv = [{'w': W[int(i)], 'k': d['k'], 'c': d['c'], 'you': d['you'], 'want': d['want'], 'rule': d['rule'], 'by': d['by']}
           for i, ds in ((out.get('shva') or {}).items() if clean else ()) if int(i) < len(W) and marks[int(i)] != 'off' for d in ds]
    if cant_hear or no_speech: throat, vow, miss, shv = [], [], {}, []   # the words were not made out: no claims about the letters inside them
    # too noisy (v5.7): background noise where the take lost its vowel check (or its words) — the page says so, with the
    # remedy. The take's own estimate (app.snr_of) under 26 dB: 93 of the 94 such takes on the phone, 182 of 182 with
    # the noise 10 dB under, 4 of the 26 as recorded (LAB_NOTES §40)
    snr = out['take'].get('snr'); noisy = bool(snr is not None and snr < RULE['noisy'] and not no_speech and (not vclean or cant_hear))
    # vowels not checked (v6.0): the take had vowels to check (a hazzan or a nikud to compare with) and was not clear
    # enough for them, and nothing else on the page says so — no noise line, no "can't hear", not another line. The
    # page then says it, instead of looking as if the vowels had passed: David's own phone takes of Tehillim 23:2 (the
    # letter head at .54 and .56, 42-44 dB) showed nothing about vowels, a real "menohot" in one of them (LAB_NOTES §43)
    # ... only partly checked (v6.0): on a line with nikud a take under the gate now shows the notes that stand on
    # their own (note_shown) — the page says "only partly checked" there (also in the noise line), "not checked" elsewhere
    vpart = bool(not vclean and has_nik and out.get('vowels_trust') and not (no_speech or cant_hear or line_wrong))
    vlost = bool(not vclean and not vpart and not noisy and not (no_speech or cant_hear or line_wrong) and (out.get('vowels') is not None or out.get('vowels_nikud') is not None))
    return {'marks': marks, 'why': why, 'line_wrong': line_wrong, 'cant_hear': cant_hear, 'no_speech': no_speech, 'rival': out['take'].get('rival'), 'gap': out['take'].get('gap'), 'throat': throat, 'vowels': vow, 'shva': shv, 'miss': miss, 'clean': clean, 'vclean': vclean and not (cant_hear or no_speech), 'noisy': noisy, 'vlost': vlost, 'vpart': vpart, 'snr': snr, 'head': head_median(TW), 'hazzan': bool(F), 'dur': out['take'].get('dur')}

# ---------------------------------------------------------------- the line's score (v5.1)
# A score out of 100 for a take, and how sure the checker is of it (the reader scores of LAB_NOTES §31, per line):
# throat letters 30, vowels 25, shva 15, words 20, clarity 10 — over the parts the line has (no ע/ח, no nikud: those
# parts drop out and the rest are weighed up). The words part is computed from the marks the page shows (so the
# strict switch moves it); everything else comes from the server once (score_parts). Kept in step with scoreOf in
# static/embed.js (tools/t_score.py).
SCORE_W = {'throat': .30, 'vowels': .25, 'shva': .15, 'words': .20, 'clarity': .10}

def score_parts(out, sm, n_shva=0):
    """the parts of the line score other than the words, from a /check result and its summarize(): None = not judged"""
    skip = bool(sm['no_speech'] or sm['cant_hear'] or sm['line_wrong'])
    th = [t for t in sm['throat'] if t['c'] in 'עח']
    throat = (sum(1.0 if t['v'] == 'throat' else .5 if t['v'] == 'unsure' else 0.0 for t in th) / len(th)) if th else None
    n_vow = sum(len(w.get('vow') or []) for w in out['take']['words'])
    has_vow = out.get('vowels') is not None or out.get('vowels_nikud') is not None
    # (v6.0) judged wherever the vowel notes were checked — since v5.7 that is vclean, not only clean: until now a take the
    # page showed vowel notes on (a phone's, under the .70 bar) had them left out of its score
    vowels = max(0.0, 1 - len({(v.get('i', v['w']), v['k']) for v in sm['vowels']}) / n_vow) if (sm.get('vclean', sm['clean']) and has_vow and n_vow) else None
    shva = max(0.0, 1 - len(sm['shva']) / n_shva) if (sm['clean'] and n_shva and out.get('shva') is not None) else None
    h = head_median(out['take']['words'])
    clarity = min(1.0, h / .85) if h is not None else None
    n_words = len(out['words'])
    base = 1.0 if sm['clean'] else (min(.9, .9 * h / .7) if h is not None else .3)
    sure = base * min(1.0, (max(1, n_words) / 6) ** .35)
    return {'skip': skip, 'p': {'throat': throat, 'vowels': vowels, 'shva': shva, 'clarity': clarity}, 'sure': round(sure, 4)}

def js_round(x):
    """Math.round: the nearest integer, halves up (int(x + .5) is off by one when x + .5 rounds up in floating point)"""
    import math
    f = math.floor(x); return int(f + 1 if x - f >= .5 else f)

def score_of(parts, marks):
    """-> {'score': 0-100 or None (not scored: no speech, can't hear, another line), 'sure': 0-100}"""
    if not parts or parts.get('skip'): return {'score': None, 'sure': 0}
    m = [x for x in marks if x]
    words = (sum(x == 'ok' for x in m) + .5 * sum(x == 'unsure' for x in m)) / len(m) if m else None
    p = dict(parts['p'], words=words)
    num = den = 0.0
    for k in ('throat', 'vowels', 'shva', 'clarity', 'words'):   # plain additions in a fixed order, as the page does (Python's sum() compensates)
        if p.get(k) is None: continue
        num += SCORE_W[k] * p[k]; den += SCORE_W[k]
    if not den: return {'score': None, 'sure': 0}
    score = 100 * num / den
    sure = parts['sure'] * (.8 if m and sum(x == 'unsure' for x in m) / len(m) > .3 else 1.0)
    return {'score': js_round(score), 'sure': js_round(100 * sure)}
