"""The line score (v5.1) in two copies — the server (rule.score_of) and the embed (embed.js scoreOf) — on 20,000 random
lines (parts present or missing, marks of every kind, the skip flag) must agree exactly. Exit 1 on any difference."""
import json, os, sys, random, subprocess, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
sys.path.insert(0, ROOT)
import rule
emb = open(os.path.join(ROOT, 'static', 'embed.js'), encoding='utf-8').read()
i = emb.index(' const SCORE_W'); j = emb.index(' const VCLS', i); JS = emb[i:j]
random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 3); N = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
cases = []
for _ in range(N):
    p = {k: (None if random.random() < .3 else round(random.random(), random.choice([1, 2, 3, 6]))) for k in ('throat', 'vowels', 'shva', 'clarity')}
    parts = {'skip': random.random() < .05, 'p': p, 'sure': round(random.random(), 4)}
    marks = [random.choice(['ok', 'ok', 'ok', 'unsure', 'off', '']) for _ in range(random.randint(0, 14))]
    cases.append({'parts': parts, 'marks': marks})
py = [rule.score_of(c['parts'], c['marks']) for c in cases]
py = [None if r['score'] is None else r for r in py]
tmp = tempfile.mkdtemp(prefix='dk_score_')
json.dump(cases, open(os.path.join(tmp, 'cases.json'), 'w'))
open(os.path.join(tmp, 't.js'), 'w', encoding='utf-8').write(JS + """
const cases = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
process.stdout.write(JSON.stringify(cases.map(c => scoreOf(c.parts, c.marks))));""")
js = json.loads(subprocess.run(['node', os.path.join(tmp, 't.js'), os.path.join(tmp, 'cases.json')], capture_output=True, text=True, check=True).stdout)
bad = [(k, py[k], js[k], cases[k]) for k in range(N) if py[k] != js[k]]
print(f'{N} lines: {N - len(bad)} agree' + (f'; first differences: {bad[:3]}' if bad else ''))
sys.exit(1 if bad else 0)
