"""Two exams of the same reader on the same pesukim (exam_voice.py rows: before / after a change), side by side, on the
pesukim both have. Prints the summary of each and what moved pasuk by pasuk (new false alarms, notes gone / new).
usage: compare_exams.py <before.json> <after.json> [label]"""
import sys, json, collections
A = {(r['per'], r['ps']): r for r in json.load(open(sys.argv[1], encoding='utf-8')) if 'words' in r}
B = {(r['per'], r['ps']): r for r in json.load(open(sys.argv[2], encoding='utf-8')) if 'words' in r}
LABEL = sys.argv[3] if len(sys.argv) > 3 else ''
keys = sorted(set(A) & set(B))
pct = lambda a, b: f'{100 * a / b:.1f}%' if b else '-'

def summary(rows):
    W = sum(len(r['marks']) for r in rows); C = collections.Counter(m for r in rows for m in r['marks'])
    cl = [r for r in rows if r['clean']]; Wc = sum(len(r['marks']) for r in cl)
    out = {'takes': len(rows), 'clean': len(cl), 'words': W, 'off': C['off'], 'unsure': C['unsure'], 'ok': C['ok'], 'clean_words': Wc,
           'line_wrong': sum(r['line_wrong'] for r in rows), 'cant_hear': sum(r['cant_hear'] for r in rows),
           'vowel_notes': sum(len({(v['w'], v['k']) for v in r['vowels']}) for r in rows), 'shva_notes': sum(len(r['shva']) for r in rows)}   # a vowel noted against the hazzan AND the nikud counts once
    for c in 'עח':
        th = collections.Counter(t['v'] for r in rows for t in r['throat'] if t['c'] == c)
        out[c] = (sum(th.values()), th['throat'], th['unsure'], th['plain'])
    out['vconf'] = collections.Counter((v['ref'], v['you']) for r in rows for v in {(v['w'], v['k']): v for v in r['vowels']}.values()).most_common(5)
    return out

a = summary([A[k] for k in keys]); b = summary([B[k] for k in keys])
print(f'== {LABEL} {len(keys)} pesukim in both (before {len(A)}, after {len(B)})')
row = lambda name, fa, fb: print(f'  {name:28s} {fa:>18s}  ->  {fb:<18s}')
row('clean takes', f"{a['clean']} ({pct(a['clean'], a['takes'])})", f"{b['clean']} ({pct(b['clean'], b['takes'])})")
row('✕ (all false alarms)', f"{a['off']} ({pct(a['off'], a['words'])})", f"{b['off']} ({pct(b['off'], b['words'])})")
row('not sure', f"{a['unsure']} ({pct(a['unsure'], a['words'])})", f"{b['unsure']} ({pct(b['unsure'], b['words'])})")
row('line called wrong', str(a['line_wrong']), str(b['line_wrong']))
for c in 'עח':
    na, ta, ua, pa = a[c]; nb, tb, ub, pb = b[c]
    row(f'{c} throat / unsure / plain', f'{pct(ta, na)} / {pct(ua, na)} / {pct(pa, na)}', f'{pct(tb, nb)} / {pct(ub, nb)} / {pct(pb, nb)}')
row('words-slots with a vowel note', f"{a['vowel_notes']} ({pct(a['vowel_notes'], a['clean_words'])})", f"{b['vowel_notes']} ({pct(b['vowel_notes'], b['clean_words'])})")
row('shva notes', str(a['shva_notes']), str(b['shva_notes']))
print('  vowel notes before:', ', '.join(f'{x}->{y} {n}' for (x, y), n in a['vconf']))
print('  vowel notes after: ', ', '.join(f'{x}->{y} {n}' for (x, y), n in b['vconf']))
# pasuk by pasuk
new_off = [(k[0], k[1] + 1, B[k]['words'][i], B[k]['why'][i]) for k in keys for i, m in enumerate(B[k]['marks']) if m == 'off' and (i >= len(A[k]['marks']) or A[k]['marks'][i] != 'off')]
gone_off = [(k[0], k[1] + 1, A[k]['words'][i]) for k in keys for i, m in enumerate(A[k]['marks']) if m == 'off' and (i >= len(B[k]['marks']) or B[k]['marks'][i] != 'off')]
print(f'  new ✕: {len(new_off)}', *new_off[:12], sep='\n    ')
print(f'  ✕ gone: {len(gone_off)}', *gone_off[:12], sep='\n    ')
vk = lambda r: {(v['w'], v['k']) for v in r['vowels']}
vn_new = sum(len(vk(B[k]) - vk(A[k])) for k in keys); vn_gone = sum(len(vk(A[k]) - vk(B[k])) for k in keys)
print(f'  vowel notes: {vn_gone} gone, {vn_new} new')
cl_lost = [(k[0], k[1] + 1) for k in keys if A[k]['clean'] and not B[k]['clean']]; cl_won = [(k[0], k[1] + 1) for k in keys if B[k]['clean'] and not A[k]['clean']]
print(f'  takes now clean: {len(cl_won)}, no longer clean: {len(cl_lost)} {cl_lost[:10]}')
