"""An exam over a list of takes cut from recordings (a jobs file: bench/lt_jobs.py) — for a reader outside Tehillim,
where exam_voice.py's index of Rabbi Alouf does not reach. Each take goes to the server as a pointed line with its
rival lines and no hazzan; the server's whole answer is kept (exam_<name>.full.jsonl, as exam_voice.py FULLOUT=1), so
bench/replay.py reads it like any other exam: the correct reading, the five planted kinds, any rule.

usage: exam_items.py <jobs.json> <name>      env: DK_URL (the server), DK_LAB_V (where the exam is kept),
       DEGRADE=phone|noisy|<parts>, N=<the first N jobs only>. A stopped run goes on where it ended."""
import sys, os, json, subprocess, time, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
JOBS, NAME = sys.argv[1:3]; BASE = os.environ.get('DK_URL', 'http://127.0.0.1:7861'); OUT = os.environ.get('DK_LAB_V') or '.'
jobs = json.load(open(JOBS, encoding='utf-8'))['items']
if os.environ.get('N'): jobs = jobs[:int(os.environ['N'])]
DG = None
if os.environ.get('DEGRADE'):
    import degrade as DGM
    DG = DGM.parts(os.environ['DEGRADE'])
P = os.path.join(OUT, f'exam_{NAME}.full.jsonl'); have = set()
if os.path.exists(P):
    for l in open(P, encoding='utf-8'):
        try: r = json.loads(l); have.add((r['per'], r['ps']))
        except ValueError: pass
fl = open(P, 'a', encoding='utf-8'); t_start = time.time(); errs = 0
print(f'{NAME}: {len(jobs)} takes ({len(have)} already there)', flush=True)
for n, j in enumerate(jobs, 1):
    if (j['per'], j['ps']) in have: continue
    wav = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, j["t0"] - .25):.3f}', '-i', j['file'], '-t', f'{j["t1"] - j["t0"] + .5:.3f}', '-ac', '1', '-ar', '16000', '-f', 'wav', '-'], capture_output=True, timeout=120).stdout
    if DG: wav = DGM.degrade(wav, j['per'] * 1000 + j['ps'], DG)
    try:
        r = requests.post(BASE + '/check', params={'words': j['words'], 'nikud': j['nikud'], 'alts': j['alts']}, data=wav, headers={'Content-Type': 'application/octet-stream'}, timeout=900); out = r.json()
        if r.status_code != 200: errs += 1; print('  error', j['id'], str(out)[:120], flush=True); continue
    except Exception as e:
        errs += 1; print('  error', j['id'], str(e)[:120], flush=True); continue
    fl.write(json.dumps({'per': j['per'], 'ps': j['ps'], 'id': j['id'], 'nikud': j['nikud'], 'dur': round(j['t1'] - j['t0'] + .5, 2), 'out': out}, ensure_ascii=False) + '\n'); fl.flush()
    if n % 10 == 0: print(f'  {n}/{len(jobs)}  [{int(time.time() - t_start)} s]', flush=True)
fl.close(); print(f'== {NAME}: done, {errs} errors [{int(time.time() - t_start)} s]')
