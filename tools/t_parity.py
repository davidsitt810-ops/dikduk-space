"""Three copies of one rule — the server (app.marks_of), the page (index.html) and the embed (embed.js) — applied to the
same rows (the exam files) must agree word for word. The JS is cut out of the two files and run in node."""
import json, os, sys, subprocess, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'space'))
os.environ['DK_NO_WARM'] = '1'; os.environ.setdefault('DK_RULE_ONLY', '1')
HERE = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(HERE, '..', 'space', 'static', 'index.html'), encoding='utf-8').read(); emb = open(os.path.join(HERE, '..', 'space', 'static', 'embed.js'), encoding='utf-8').read()
def grab(src, start, end): i = src.index(start); j = src.index(end, i); return src[i:j]
JS = {'page': grab(html, "let CLEAN=false;", "/* a throat letter's verdict"), 'embed': grab(emb, " let CLEAN = false;", " const VCLS")}
# the server's rule without loading the models: exec the relevant functions out of app.py
src = open(os.path.join(HERE, '..', 'space', 'app.py'), encoding='utf-8').read()
def pyfn(name, stop):
    i = src.index(f'def {name}('); j = src.index(stop, i); return src[i:j]
code = 'import numpy as np\n' + src[src.index("RULE = {'drop'"):src.index('\ndef head_median')] + '\n' + pyfn('mark_of', '\nRULE = ') + pyfn('head_median', '\ndef clean_of') + pyfn('clean_of', '\ndef marks_of') + pyfn('marks_of', '\ndef summarize')
ns = {}; exec(code, ns)
files = sys.argv[1:] or [os.path.join(HERE, f) for f in ('exam_rows.json', 'exam_archive_rows.json')]
lines = []
for f in files:
    if not os.path.exists(f): continue
    R = json.load(open(f, encoding='utf-8')); L = collections.defaultdict(dict)
    for r in R: L[(r['case'], r.get('per', r.get('pid')), r.get('ps', r.get('line')), r.get('rec', ''))][r['k']] = r
    for key, d in L.items():
        TW = [d[k] for k in sorted(d)]; F = [{'fit': t.get('fit')} for t in TW] if any(t.get('fit') is not None for t in TW) else None
        lines.append({'TW': TW, 'F': F, 'gap': TW[0].get('gap')})
print(len(lines), 'lines')
py = []
for l in lines:
    clean = ns['clean_of'](l['TW']); marks, why, lw, cant = ns['marks_of'](l['TW'], l['F'], l['gap'], clean); py.append({'marks': marks, 'lw': lw, 'cant': cant, 'clean': clean})
json.dump(lines, open(os.path.join(HERE, '_parity_lines.json'), 'w'))
for name, js in JS.items():
    prog = js + """
const lines = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8')); const out = [];
for (const l of lines) { const HM = headMedian(l.TW); CLEAN = HM != null && HM >= .7; const r = marksOf(l.TW, l.F, l.gap); out.push({marks: r.marks.map(m => m || ''), lw: r.lineWrong, cant: r.cantHear, clean: CLEAN}); }
process.stdout.write(JSON.stringify(out));"""
    open(os.path.join(HERE, f'_parity_{name}.js'), 'w').write(prog)
    res = json.loads(subprocess.run(['node', os.path.join(HERE, f'_parity_{name}.js'), os.path.join(HERE, '_parity_lines.json')], capture_output=True, text=True, check=True).stdout)
    bad = [(i, p, j) for i, (p, j) in enumerate(zip(py, res)) if p['marks'] != j['marks'] or p['lw'] != j['lw'] or p['cant'] != j['cant'] or p['clean'] != j['clean']]
    print(f'{name}: {len(lines) - len(bad)}/{len(lines)} lines agree with the server')
    for i, p, j in bad[:5]: print('   ', i, 'server', p, '\n       ', name, j, [ (t['w'], t.get('n'), t.get('skel'), t.get('fit'), t.get('kept'), t.get('pw')) for t in lines[i]['TW']])
