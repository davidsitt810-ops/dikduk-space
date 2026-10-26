"""Edge-case parity fuzz: the Python rule (rule.py, as t_parity.py uses it) against the page and embed JS
(cut out of index.html / embed.js, run in node). Compares marks, why, line_wrong, cant_hear, clean, and the noSpeech
expression, on synthetic boundary inputs that recorded data never covers."""
import json, os, sys, subprocess, random, itertools
HERE = os.path.dirname(os.path.abspath(__file__))
SPACE = os.path.join(HERE, '..', '..')
html = open(os.path.join(SPACE, 'static', 'index.html'), encoding='utf-8').read(); emb = open(os.path.join(SPACE, 'static', 'embed.js'), encoding='utf-8').read()
def grab(src, start, end): i = src.index(start); j = src.index(end, i); return src[i:j]
JS = {'page': grab(html, "let CLEAN=false;", "/* a throat letter's verdict"), 'embed': grab(emb, " let CLEAN = false;", " const VCLS")}
sys.path.insert(0, SPACE); import rule
ns = vars(rule)

random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
N_LINES = int(sys.argv[2]) if len(sys.argv) > 2 else 60000
NV = [None, 0, 1, 2, 3, 5]
SK = [None, 0.0, 0.1, 0.19, 0.2, 0.39, 0.4, 0.9, 1.0]
KP = [None, 0.0, 0.49, 0.5, 0.74, 0.75, 1.0]
PW = [None, 0.0, 0.79, 0.8, 0.94, 0.95, 1.0]
HS = [None, 0.0, 0.29, 0.3, 0.49, 0.5, 0.59, 0.6, 0.69, 0.7, 1.0]
DR = [None, None, -5.0, 0.0, 9.99, 10.0, 13.99, 14.0, 30.0, 30.0, 1e30]
SW = [None, None, 0.0, 7.99, 8.0, 11.99, 12.0, 20.0, 1e30]
FT = [None, 0.0, 0.14, 0.15, 0.19, 0.2, 0.49, 0.5, 1.0]
GP = [None, None, 0.0, 0.59, 0.6, 1.0]

def word(i, nw, mode):
    t = {}
    # sometimes leave keys out entirely (older server / missing field) rather than null
    def put(k, v):
        if v is None and random.random() < 0.3: return
        t[k] = v
    put('n', random.choice(NV)); put('skel', random.choice(SK)); put('kept', random.choice(KP)); put('pw', random.choice(PW)); put('hskel', random.choice(HS))
    put('drop', random.choice(DR))
    if mode == 'swap_on_last' or i < nw - 1: put('swap', random.choice(SW))
    else: put('swap', None)
    return t

lines = []
for L in range(N_LINES):
    nw = random.choice([0, 1, 1, 2, 2, 3, 3, 3, 4, 5, 6])
    mode = random.choice(['plain', 'plain', 'swap_on_last'])
    TW = [word(i, nw, mode) for i in range(nw)]
    r = random.random()
    if r < 0.35: F = None
    elif r < 0.40: F = []                       # fit_against returns [] when the hazzan words had no ids
    elif r < 0.45 and not os.environ.get('NO_SHORT_F'): F = [{'fit': random.choice(FT)} for _ in range(max(0, nw - 1))]   # shorter than TW
    elif r < 0.50: F = [{} if random.random() < .5 else {'fit': random.choice(FT)} for _ in range(nw)]  # entries without 'fit'
    else: F = [{'fit': random.choice(FT)} for _ in range(nw)]
    gap = random.choice(GP)
    phones = random.choice([None, [], ['a'], ['a'] * 3, ['a'] * 10]); dur = random.choice([None, 0, 2.0, 6.0, 7.0, 30.0])
    lines.append({'TW': TW, 'F': F, 'gap': gap, 'phones': phones, 'dur': dur})

# the server
py = []; py_err = []
for k, l in enumerate(lines):
    try:
        clean = ns['clean_of'](l['TW']); marks, why, lw, cant = ns['marks_of'](l['TW'], l['F'], l['gap'], clean)
        take = {'words': l['TW'], 'gap': l['gap']}
        if l['phones'] is not None: take['phones'] = l['phones']
        if l['dur'] is not None: take['dur'] = l['dur']
        nosp = ns['no_speech_in'](take)
        py.append({'marks': marks, 'why': why, 'lw': lw, 'cant': cant, 'clean': clean, 'nosp': nosp})
    except Exception as e:
        py.append({'err': type(e).__name__ + ': ' + str(e)}); py_err.append((k, type(e).__name__, str(e)))
import tempfile; TMP = tempfile.mkdtemp(prefix='dk_fuzz_')
json.dump(lines, open(os.path.join(TMP, '_fz_lines.json'), 'w'))
print(len(lines), 'lines;', len(py_err), 'python exceptions')
ok=[p for p in py if 'err' not in p]
print('  coverage: cant_hear', sum(p['cant'] for p in ok), '| cant_hear with an off->unsure flip', sum(1 for p,l in zip(py,lines) if 'err' not in p and p['cant'] and any(ns['mark_of'](t, (l['F'][i] if l['F'] and i < len(l['F']) else None), p['clean'])=='off' for i,t in enumerate(l['TW']))),
      '| dropped', sum('dropped' in p['why'] for p in ok), '| swapped', sum('swapped' in p['why'] for p in ok), '| swapped&dropped', sum('swapped' in p['why'] and 'dropped' in p['why'] for p in ok),
      '| line_wrong', sum(p['lw'] for p in ok), '| clean', sum(p['clean'] for p in ok), '| nosp', sum(p['nosp'] for p in ok), '| 1-word', sum(len(l['TW'])==1 for l in lines), '| 0-word', sum(len(l['TW'])==0 for l in lines))
from collections import Counter
print('  python exception kinds:', Counter((e[1], e[2][:60]) for e in py_err).most_common(8))

failed = bool(py_err)
for name, js in JS.items():
    prog = js + """
const lines = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8')); const out = [];
for (const l of lines) { try { const HM = headMedian(l.TW); CLEAN = HM != null && HM >= .7; const r = marksOf(l.TW, l.F, l.gap);
  const take = {words: l.TW, gap: l.gap}; if (l.phones !== null) take.phones = l.phones; if (l.dur !== null) take.dur = l.dur;
  const noSpeech = (take.phones || []).length < Math.max(3, 0.5 * (take.dur || 0));
  out.push({marks: r.marks.map(m => m || ''), why: r.why, lw: r.lineWrong, cant: r.cantHear, clean: CLEAN, nosp: noSpeech}); }
  catch (e) { out.push({err: e.constructor.name + ': ' + e.message}); } }
process.stdout.write(JSON.stringify(out));"""
    fn = os.path.join(TMP, f'_fz_{name}.js'); open(fn, 'w').write(prog)
    res = json.loads(subprocess.run(['node', fn, os.path.join(TMP, '_fz_lines.json')], capture_output=True, text=True, check=True).stdout)
    js_err = [(i, r['err']) for i, r in enumerate(res) if 'err' in r]
    print(f'{name}: {len(js_err)} JS exceptions;', Counter(e[1][:70] for e in js_err).most_common(5))
    bad = []
    for i, (p, j) in enumerate(zip(py, res)):
        if 'err' in p or 'err' in j:
            if ('err' in p) != ('err' in j): bad.append((i, 'one side threw', p, j))
            continue
        for key in ('marks', 'why', 'lw', 'cant', 'clean', 'nosp'):
            if p[key] != j[key]: bad.append((i, key, p, j)); break
    print(f'{name}: {len(lines) - len(bad)}/{len(lines)} agree with the server;', Counter(b[1] for b in bad).most_common())
    failed = failed or bool(bad) or bool(js_err)
    shown = set()
    for i, key, p, j in bad:
        if key in shown: continue
        shown.add(key)
        print('   ---', key, 'line', i); print('   TW =', json.dumps(lines[i]['TW'], ensure_ascii=False)); print('   F =', lines[i]['F'], 'gap =', lines[i]['gap'], 'phones =', lines[i]['phones'], 'dur =', lines[i]['dur'])
        print('   server:', p); print('   ', name + ':', j)
sys.exit(1 if failed else 0)   # CI runs this: any disagreement or exception fails the push
