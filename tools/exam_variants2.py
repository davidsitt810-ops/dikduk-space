"""Candidate rule v4.4 against v4.3 on both exams: (1) the line gap speaks on every take, (2) robust CLEAN gate,
(3) on a take that is not clean, red needs the letter head's agreement (kept < .75), (4) the pw-red needs the hazzan's
sounds to be missing too (fit < .5), (5) a take the head barely hears (robust median hskel < .3) is 'can't hear':
no reds, everything doubtful is 'unsure'. usage: exam_variants2.py"""
import json, collections, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'exam_report.py'), encoding='utf-8').read().split("files = sys.argv")[0]
ns = {'__file__': os.path.join(HERE, 'exam_report.py')}; exec(src, ns)
RULE = ns['RULE']; mark_of43 = ns['mark_of']; hs_of = ns['hs_of']
def robust_median(TW):
    hs = hs_of(TW)
    if not hs: return None
    if len(hs) >= 3: hs = hs[1:]
    return hs[len(hs) // 2]
def mark_of44(r, clean, hazzan):
    m = mark_of43(r, clean)
    if m != 'off': return m
    kp = r.get('kept'); ft = r.get('fit'); sk = r.get('skel'); pw = r.get('pw')
    # the pw-red (clean take, pw >= .95) when the phone recognizer says the word is there: not red
    if clean and pw is not None and pw >= .95 and not (sk < .2 and (ft is None or ft < .15)) and ft is not None and ft >= .5: return 'unsure'
    # not clean: red needs the head to agree that the letters were not heard
    if not clean and kp is not None and kp >= .75: return 'unsure'
    return m
def line_marks(TW, V):
    """V: set of variant flags among {'gap_always','robust','head_agree','cant_hear'}"""
    clean = (ns['gate_robust'] if 'robust' in V else ns['gate_now'])(TW)
    hazzan = any(t.get('fit') is not None for t in TW)
    marks = [(mark_of44(t, clean, hazzan) if 'head_agree' in V else mark_of43(t, clean)) for t in TW]; why = [''] * len(TW); lw = False; cant = False
    gap = TW[0].get('gap')
    if clean:
        ds = [t['drop'] if t.get('drop') is not None else -1e9 for t in TW]; top = int(np.argmax(ds)); second = max([d for i, d in enumerate(ds) if i != top], default=-1e9)
        if (TW[top].get('n') or 0) >= 2 and ds[top] >= RULE['drop'] and ds[top] - second >= RULE['margin']: marks[top] = 'off'; why[top] = 'dropped'
        sw = [t['swap'] if t.get('swap') is not None else -1e9 for t in TW[:-1]]
        if sw:
            j = int(np.argmax(sw)); na, nb = TW[j].get('n') or 0, TW[j + 1].get('n') or 0
            if sw[j] >= RULE['swap'] and max(na, nb) >= 2 and min(na, nb) >= 1: marks[j] = marks[j + 1] = 'off'; why[j] = why[j + 1] = 'swapped'
    if gap is not None and gap >= RULE['gap'] and (clean or 'gap_always' in V): lw = True; marks = ['unsure' if m == 'ok' else m for m in marks]
    if 'cant_hear' in V and not clean and not lw:
        med = robust_median(TW)
        if med is not None and med < .3: cant = True; marks = ['unsure' if m == 'off' else m for m in marks]
    return marks, why, lw, cant
def evaluate(R, V):
    L = ns['lines_of'](R); out = collections.defaultdict(lambda: {'good': collections.Counter(), 'bad': collections.Counter(), 'lines': 0, 'lw': 0, 'cant': 0, 'clean': 0})
    for key, TW in L.items():
        marks, why, lw, cant = line_marks(TW, V); c = out[key[0]]; c['lines'] += 1; c['lw'] += lw; c['cant'] += cant; c['clean'] += (ns['gate_robust'] if 'robust' in V else ns['gate_now'])(TW)
        for t, m in zip(TW, marks):
            if (t.get('n') or 0) < 1: continue
            c['bad' if t['bad'] else 'good'][m or 'ok'] += 1
    return out
def show(name, out):
    s = []
    for case in ('intact', 'right', 'skip', 'swap', 'wrongword', 'wrongline'):
        if case not in out: continue
        c = out[case]; g = c['good']; b = c['bad']; ng = sum(g.values()); nb = sum(b.values())
        s.append(f"{case}[{c['lines']} lines, lw {c['lw']}, cant {c['cant']}]: FA {g['off']}/{ng} unsure {g['unsure']}" + (f" | caught {b['off']}/{nb} unsure {b['unsure']}" if nb else ''))
    print(f'  {name:8s} ' + '\n           '.join(s))
if __name__ == '__main__':
    RA = json.load(open(os.path.join(HERE, 'exam_rows.json'), encoding='utf-8')); RB = json.load(open(os.path.join(HERE, 'exam_archive_rows.json'), encoding='utf-8'))
    # the archive's right takes whose clip cannot hold the line are left out (exam_archive_truth.py)
    try:
        tsrc = open(os.path.join(HERE, 'exam_archive_truth.py'), encoding='utf-8').read().split('def plausible')[0]
        tns = {'__file__': os.path.join(HERE, 'exam_archive_truth.py')}; exec(tsrc, tns); T = tns['T']   # takes with ref_dur filled in
        bad = set((t['pid'], t['line'], t['rec']) for t in T if t['case'] == 'right' and not (0.5 * t['ref_dur'] <= t['dur'] <= 2.0 * t['ref_dur']))
        RB = [r for r in RB if not (r['case'] == 'right' and (r['pid'], r['line'], r['rec']) in bad)]
        print('archive right takes with an implausible clip left out:', len(bad))
    except Exception as e: print('takes not read:', e)
    for label, V in (('v4.3 as shipped', set()), ('+gap on every take', {'gap_always'}), ('+robust gate', {'gap_always', 'robust'}), ('+head must agree, fit', {'gap_always', 'robust', 'head_agree'}), ("+can't hear", {'gap_always', 'robust', 'head_agree', 'cant_hear'})):
        print(f'\n### {label}')
        show('Alouf', evaluate(RA, V)); show('archive', evaluate(RB, V))
    V = {'gap_always', 'robust', 'head_agree', 'cant_hear'}; L = ns['lines_of'](RB)
    print('\nremaining false alarms on the archive with the full candidate:')
    for key, TW in L.items():
        if key[0] == 'wrongline': continue
        marks, why, lw, cant = line_marks(TW, V)
        for t, m in zip(TW, marks):
            if m == 'off' and not t['bad']: print(f"  {key[1]} line {key[2] + 1} {key[3]}: {t['w']} skel={t['skel']:.2f} fit={t['fit'] if t['fit'] is None else round(t['fit'], 2)} hskel={t['hskel']:.2f} kept={t['kept']} pw={round(t['pw'], 2)} clean={ns['gate_robust'](TW)} med={robust_median(TW):.2f} why={why[TW.index(t)]}")
