"""The drop bar on the Israeli (FLEURS, unpointed) and pizmonim-archive exams: their rows keep each word's rule inputs
and the page's mark; replayed through rule.marks_of (the live bar must reproduce the stored marks)."""
import sys, os, json, collections
sys.path.insert(0, '/home/claude/dikduk-space'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rule, drops as D
T = '/tmp/claude-0/-home-claude/13b8b04f-7b29-591b-ba7b-28708cdbf43a/scratchpad/space_test'
def takes_of(fn, key):
    rows = json.load(open(os.path.join(T, fn))); tk = collections.defaultdict(list)
    for r in rows: tk[key(r)].append(r)
    return tk
def run(tk, drop=None, margin=None):
    out = collections.Counter(); old = dict(rule.RULE)
    try:
        if drop is not None: rule.RULE['drop'] = drop
        if margin is not None: rule.RULE['margin'] = margin
        for key, ws in tk.items():
            ws = sorted(ws, key=lambda w: w['k']); case = key[0]
            TW = [{k: w.get(k) for k in ('n', 'skel', 'kept', 'pw', 'hskel', 'drop', 'swap')} for w in ws]
            F = [{'fit': w.get('fit')} if w.get('fit') is not None else None for w in ws]
            F = F if any(f is not None for f in F) else None
            rv = {'gain': ws[0].get('rival'), 'head': ws[0].get('rival_head')}
            m, why, lw, ch = rule.marks_of(TW, F, ws[0].get('gap'), rule.clean_of(TW), rv)
            out['replay differs'] += sum(1 for w, x in zip(ws, m) if w.get('mark') is not None and w['mark'] != x) if drop is None and margin is None else 0
            bad = [i for i, w in enumerate(ws) if w['bad']]
            if case == 'right': out['right red'] += sum(x == 'off' for x in m); out['right words'] += len(m)
            elif case == 'skip':
                for i in bad: out['skip ' + (m[i] or 'none')] += 1
                out['skip takes'] += 1
            elif case == 'swap': out['swap both red'] += bool(bad) and all(m[i] == 'off' for i in bad); out['swap takes'] += 1
    finally: rule.RULE.clear(); rule.RULE.update(old)
    return out
for fn, key in (('exam_israeli_shipped_rows.json', lambda r: (r['case'], r['f'])), ('exam_archive_sep_rows.json', lambda r: (r['case'], r['rec'], r['line']))):
    tk = takes_of(fn, key); print('==', fn, len(tk), 'takes')
    for v in ['-', 'drop=15', 'drop=20', 'drop=25']:
        o = run(tk, **D.parse(v))
        print(f"   {v:8s} right words red {o['right red']}/{o['right words']} | skipped red {o['skip off']} not sure {o['skip unsure']} passed {o['skip ok']} of {o['skip takes']} | swapped both red {o['swap both red']}/{o['swap takes']}" + (f" | replay differs on {o['replay differs']} words" if v == '-' else ''))
