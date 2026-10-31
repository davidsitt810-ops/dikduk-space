"""Choosing the shva hearing thresholds offline: false alarms on Rabbi Alouf's own reading (shva_rows2.json, all
perakim: A = the e-like slot, B = the any-vowel slot) against detection on the tampered takes (shva_eval.json: a shva
na's vowel cut out / a short vowel put into a silent shva).
  vowel = A slot used and A mass >= tv
  none  = B slot not used (or used with B mass < m0) and B's strongest frame between the consonants < tn
usage: shva_tune.py"""
import json, os, sys, itertools, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
import shva as SH
R = json.load(open(os.path.join(HERE, 'shva_rows2.json'), encoding='utf-8'))
E = json.load(open(os.path.join(HERE, 'shva_eval.json'), encoding='utf-8'))['feats']
held = {int(p) for p in ['7', '12', '18', '21', '23', '32', '35', '40', '46', '94', '118', '123', '126', '140']}
intact = [{'rule': r['rule'], 'kind': r['kind'], 'per': r['per'], 'f': {'used': r['A']['used'], 'mass': r['A']['mass'], 'gapmax': r['A']['gapmax'], 'used_any': r['B']['used'], 'mass_any': r['B']['mass'], 'gapmax_any': r['B']['gapmax']}} for r in R if r['B']]
drop = [e for e in E if e['case'] == 'drop']; add = [e for e in E if e['case'] == 'add']
def heard(f, tv, tn, m0):
    if f['used'] and f['mass'] >= tv: return 'vowel'
    if (not f['used_any'] or f['mass_any'] < m0) and f['gapmax_any'] < tn: return 'none'
    return 'unsure'
NA = {'start', 'second', 'twin', 'dagesh'}; NAH = {'short', 'first', 'final'}
def score(tv, tn, m0):
    fa_na = sum(heard(r['f'], tv, tn, m0) == 'none' for r in intact if r['rule'] in NA) / max(1, sum(r['rule'] in NA for r in intact))
    fa_nah = sum(heard(r['f'], tv, tn, m0) == 'vowel' for r in intact if r['rule'] in NAH) / max(1, sum(r['rule'] in NAH for r in intact))
    det_drop = sum(heard(e['f'], tv, tn, m0) == 'none' for e in drop) / max(1, len(drop))
    det_add = sum(heard(e['f'], tv, tn, m0) == 'vowel' for e in add) / max(1, len(add))
    return fa_na, fa_nah, det_drop, det_add
print(f'{len(intact)} intact shvas, {len(drop)} drop tests, {len(add)} add tests')
print(f"{'tv':>4s} {'tn':>5s} {'m0':>4s} | {'FA say-e':>8s} {'FA no-vowel':>11s} | {'drop caught':>11s} {'add caught':>10s}")
rows = []
for tv, tn, m0 in itertools.product([.3, .4, .5, .6], [.05, .1, .15, .2, .3], [0, .2, .4, .6]):
    rows.append((tv, tn, m0) + score(tv, tn, m0))
for r in sorted(rows, key=lambda r: (r[0], r[1], r[2])):
    if r[3] <= .03 and r[4] <= .03:
        print(f"{r[0]:4.1f} {r[1]:5.2f} {r[2]:4.1f} | {r[3]:8.1%} {r[4]:11.1%} | {r[5]:11.0%} {r[6]:10.0%}")
print('\ncurrent (.5, .05, 0):', ['%.1f%%' % (100 * v) for v in score(.5, .05, 0)])
