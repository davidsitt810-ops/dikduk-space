"""The checker on a reader it has never heard. Each of his pesukim is the student's take; the hazzan is Rabbi Alouf's
recording of the same pasuk and the perek's other pesukim are the rival lines, as the site checks Tehillim. Through
the live server (/check) and the page's own rule (rule.summarize). Only his intact reading, so every word is right:
every ✕ is a false alarm, every "not sure" a word the checker could not confirm, every throat "plain" / vowel note /
shva note a claim to look at (a fault of the checker, or a real difference of his reading from the nikud).
usage: exam_voice.py <align dir> <audio> <name> [N=150] [seed=7]
  <audio>: the book file (perakim carry book_t0), or a per-perek file pattern with {n} (e.g. .../hbofPsa_{n:03d}.mp3)
writes exam_<name>.json next to this script and prints the summary"""
import sys, os, json, random, subprocess, time, collections
import requests
REPO = '/home/claude/dikduk-space'; sys.path.insert(0, REPO)
import rule
HERE = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(HERE)
AL, SRC, NAME = sys.argv[1:4]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 150; SEED = int(sys.argv[5]) if len(sys.argv) > 5 else 7
BASE = os.environ.get('DK_URL', 'http://127.0.0.1:7861')
IDX = json.load(open(os.path.join(S, 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))['perakim']
def perakim_of(spec):
    out = []
    for part in spec.split(','):
        a, _, b = part.partition('-'); out += list(range(int(a), int(b or a) + 1))
    return set(out)
ONLY = perakim_of(os.environ['PERAKIM']) if os.environ.get('PERAKIM') else None   # e.g. the held-out perakim
jobs = []
for f in sorted(os.listdir(AL)):
    if not f.endswith('.json'): continue
    A = json.load(open(os.path.join(AL, f), encoding='utf-8')); n = A['perek']
    if ONLY is not None and n not in ONLY: continue
    R = IDX.get(str(n))
    if not R or len(R['pesukim']) != len(A['pesukim']): continue
    for i, (p, q) in enumerate(zip(A['pesukim'], R['pesukim'])):
        if p['t0'] is None or q['t0'] is None or q['t1'] is None or len(p['words']) < 3 or any(w['t0'] is None for w in p['words']): continue
        if p['p'] < .45 or p['t1'] - p['t0'] > 30: continue      # the alignment itself is doubtful / too long for one take
        jobs.append((n, i))
random.seed(SEED); random.shuffle(jobs); jobs = jobs[:N]
print(f'{NAME}: {len(jobs)} pesukim', flush=True)
CACHE = {}
def align(n):
    if n not in CACHE: CACHE[n] = json.load(open(os.path.join(AL, f'{n}.json'), encoding='utf-8'))
    return CACHE[n]
def cut(n, a, b):
    A = align(n)
    if '{n' in SRC: path, off = SRC.format(n=n), 0.0
    else: path, off = SRC, A['book_t0']
    return subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, off + a):.3f}', '-i', path, '-t', f'{b - a:.3f}', '-ac', '1', '-ar', '16000', '-f', 'wav', '-'],
                          capture_output=True, timeout=120).stdout
# rows are kept as they come (exam_<name>.jsonl), so a stopped run picks up where it was
JL = os.path.join(HERE, f'exam_{NAME}.jsonl'); rows = []
if os.path.exists(JL):
    rows = [json.loads(l) for l in open(JL, encoding='utf-8') if l.strip()]
have = {(r['per'], r['ps']) for r in rows}; jl = open(JL, 'a', encoding='utf-8'); t_start = time.time()
def keep(r):
    rows.append(r); jl.write(json.dumps(r, ensure_ascii=False) + '\n'); jl.flush()
for done, (n, i) in enumerate(jobs, 1):
    if (n, i) in have: continue
    A = align(n); R = IDX[str(n)]; p = A['pesukim'][i]; q = R['pesukim'][i]
    wav = cut(n, p['t0'] - .25, p['t1'] + .25)
    alts = '|'.join(x['text'] for k, x in enumerate(R['pesukim']) if k != i and x.get('text'))
    try:
        r = requests.post(BASE + '/check', params={'words': q['text'], 'nikud': q['nikud'], 'ref': R['file'], 't0': q['t0'], 't1': q['t1'], 'alts': alts},
                          data=wav, headers={'Content-Type': 'application/octet-stream'}, timeout=900)
        out = r.json()
        if r.status_code != 200: keep({'per': n, 'ps': i, 'err': out.get('err', r.status_code)}); continue
    except Exception as e:
        keep({'per': n, 'ps': i, 'err': str(e)[:200]}); continue
    sm = rule.summarize(out)
    keep({'per': n, 'ps': i, 'words': out['words'], 'dur': round(p['t1'] - p['t0'] + .5, 2), 'align_p': p['p'], 'marks': sm['marks'], 'why': sm['why'],
                 'line_wrong': sm['line_wrong'], 'cant_hear': sm['cant_hear'], 'no_speech': sm['no_speech'], 'clean': sm['clean'], 'head': rule.head_median(out['take']['words']),
                 'throat': sm['throat'], 'vowels': sm['vowels'], 'shva': sm['shva'], 'rival': sm['rival'], 'gap': sm['gap'],
                 'strict': rule.strict_of(sm['marks'], sm['why'], sm['clean'], sm['cant_hear'])[0]})
    if done % 10 == 0: print(f'  {done}/{len(jobs)}  [{int(time.time() - t_start)} s]', flush=True)
jl.close(); want = set(jobs); rows = [r for r in rows if (r['per'], r['ps']) in want]
json.dump(rows, open(os.path.join(HERE, f'exam_{NAME}.json'), 'w', encoding='utf-8'), ensure_ascii=False)

ok = [r for r in rows if 'err' not in r]
W = sum(len(r['marks']) for r in ok); C = collections.Counter(m for r in ok for m in r['marks'])
CL = [r for r in ok if r['clean']]; Wc = sum(len(r['marks']) for r in CL); Cc = collections.Counter(m for r in CL for m in r['marks'])
St = collections.Counter(m for r in CL for m in r['strict'])
pct = lambda a, b: f'{100 * a / b:.1f}%' if b else '-'
print(f'\n== {NAME}: {len(ok)} takes ({len(rows) - len(ok)} errors), clean {len(CL)} ({pct(len(CL), len(ok))}), line called wrong {sum(r["line_wrong"] for r in ok)}, can\'t hear {sum(r["cant_hear"] for r in ok)}')
print(f'  all words {W}: ✕ {C["off"]} ({pct(C["off"], W)}), not sure {C["unsure"]} ({pct(C["unsure"], W)}), ✓ {C["ok"]} ({pct(C["ok"], W)})')
print(f'  on clean takes {Wc}: ✕ {Cc["off"]} ({pct(Cc["off"], Wc)}), not sure {Cc["unsure"]} ({pct(Cc["unsure"], Wc)}); strict ✕ {St["off"]} ({pct(St["off"], Wc)})')
for c in 'עח':
    th = collections.Counter(t['v'] for r in ok for t in r['throat'] if t['c'] == c); n_ = sum(th.values())
    hz = collections.Counter(t['hazzan'] for r in ok for t in r['throat'] if t['c'] == c)
    print(f'  {c} (n={n_}): throat {pct(th["throat"], n_)}, unsure {pct(th["unsure"], n_)}, plain {pct(th["plain"], n_)}   | the hazzan on the same letters: ' + ', '.join(f'{k} {v}' for k, v in hz.most_common()))
nv = sum(len(r['vowels']) for r in ok); ns = sum(len(r['shva']) for r in ok)
print(f'  vowel notes {nv} ({pct(nv, Wc)} of clean words): ' + ', '.join(f'{a}->{b} {k}' for (a, b), k in collections.Counter((v['ref'], v['you']) for r in ok for v in r['vowels']).most_common(6)))
print(f'  shva notes {ns}: ' + ', '.join(f'{k} {v}' for k, v in collections.Counter((s['want'], s['you'], s['rule']) for r in ok for s in r['shva']).most_common(6)))
fa = [(r['per'], r['ps'] + 1, r['words'][k], r['why'][k], round(r['head'] or 0, 2)) for r in ok for k, m in enumerate(r['marks']) if m == 'off']
print(f'  false alarms ({len(fa)}):', *fa[:25], sep='\n    ')
