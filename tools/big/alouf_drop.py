"""Rabbi Alouf's regression exam (exam_alouf.py rows: every word's rule inputs, intact / skip / swap / wrongword /
wrongline takes of 60 held-out pesukim) replayed through rule.marks_of with the drop bar changed."""
import sys, os, json, collections
sys.path.insert(0, '/home/claude/dikduk-space'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rule, drops as D
T = '/tmp/claude-0/-home-claude/13b8b04f-7b29-591b-ba7b-28708cdbf43a/scratchpad/space_test'
rows = json.load(open(os.path.join(T, sys.argv[1] if len(sys.argv) > 1 else 'exam_alouf_nv4_rows.json')))
takes = collections.defaultdict(list)
for r in rows: takes[(r['case'], r['per'], r['ps'])].append(r)
def run(drop=None, margin=None, hskel=.8, hkept=.6):
    out = collections.Counter()
    old = dict(rule.RULE)
    try:
        if drop is not None: rule.RULE['drop'] = drop
        if margin is not None: rule.RULE['margin'] = margin
        for (case, per, ps), ws in takes.items():
            ws = sorted(ws, key=lambda w: w['k'])
            TW = [{k: w.get(k) for k in ('n', 'skel', 'kept', 'pw', 'hskel', 'drop', 'swap')} for w in ws]
            F = [{'fit': w.get('fit')} for w in ws]
            rv = {'gain': ws[0].get('rival'), 'head': ws[0].get('rival_head')}
            m, why, lw, ch = D.marks_of(hskel, hkept)(TW, F, ws[0].get('gap'), rule.clean_of(TW), rv)
            bad = [i for i, w in enumerate(ws) if w['bad']]
            if case == 'intact': out['intact red'] += sum(x == 'off' for x in m); out['intact unsure'] += sum(x == 'unsure' for x in m); out['intact words'] += len(m)
            elif case == 'skip':
                for i in bad: out['skip ' + (m[i] or 'none')] += 1
                out['skip others red'] += sum(1 for i, x in enumerate(m) if x == 'off' and i not in bad)
            elif case == 'swap': out['swap both red'] += all(m[i] == 'off' for i in bad); out['swap takes'] += 1
            elif case == 'wrongword':
                for i in bad: out['replaced ' + (m[i] or 'none')] += 1
    finally: rule.RULE.clear(); rule.RULE.update(old)
    return out
for v in ['-', 'drop=15', 'drop=20', 'drop=25', 'drop=30']:
    o = run(**D.parse(v))
    print(f"{v:9s} intact red {o['intact red']}/{o['intact words']} unsure {o['intact unsure']} | skipped red {o['skip off']} not sure {o['skip unsure']} passed {o['skip ok']} (others red {o['skip others red']}) | swapped both red {o['swap both red']}/{o['swap takes']} | replaced red {o['replaced off']} not sure {o['replaced unsure']} passed {o['replaced ok']}")
