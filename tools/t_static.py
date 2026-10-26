"""The files the live pages are made of parse: every <script> in static/*.html and static/embed.js (node --check) and
the JSON files the server and the pages read. The Space serves static/ from GitHub main within a minute of a push,
so a syntax error there breaks the live pages before anyone rebuilds anything. usage: t_static.py"""
import os, re, sys, json, glob, subprocess, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
TMP = tempfile.mkdtemp(prefix='dk_static_'); fails = []
def node_check(code, name):
    p = os.path.join(TMP, re.sub(r'\W+', '_', name) + '.js'); open(p, 'w', encoding='utf-8').write(code)
    r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
    if r.returncode: fails.append(f'{name}: ' + (r.stderr.strip().splitlines() or ['?'])[-1])
    return not r.returncode
n = 0
for f in sorted(glob.glob(os.path.join(ROOT, 'static', '*.html'))):
    src = open(f, encoding='utf-8').read()
    for i, m in enumerate(re.finditer(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', src, re.S)):
        node_check(m.group(1), f'{os.path.basename(f)} script {i + 1}'); n += 1
node_check(open(os.path.join(ROOT, 'static', 'embed.js'), encoding='utf-8').read(), 'embed.js'); n += 1
for f in [os.path.join(ROOT, 'static', 'scripts.json'), os.path.join(ROOT, 'static', 'letters.json'), os.path.join(ROOT, 'lyrics_tehillim.json'),
          os.path.join(ROOT, 'throat_models.json'), os.path.join(ROOT, 'throat_models_v2.json')]:
    try: json.load(open(f, encoding='utf-8')); n += 1
    except Exception as e: fails.append(f'{os.path.relpath(f, ROOT)}: {e}')
# every letter example the letters page offers is in the repo
L = json.load(open(os.path.join(ROOT, 'static', 'letters.json'), encoding='utf-8'))
for x in L.get('letters', []):
    for exs in (x.get('examples') or {}).values():
        for e in exs:
            if not os.path.exists(os.path.join(ROOT, 'static', 'letters', e['audio'])): fails.append(f"static/letters/{e['audio']} missing (letters.json names it)")
print(f'{n} scripts and files checked;', 'all parse' if not fails else f'{len(fails)} problems:')
for f in fails: print('  ' + f)
sys.exit(1 if fails else 0)
