"""How fast is this Mac? Times the checker on Rabbi Alouf's own audio against a running server (default
http://127.0.0.1:7860): a whole pasuk (23:1, /check) three times and six letter takes (/letter). Prints seconds.
With --mps it also starts a second server on port 7870 with DK_DEVICE=mps, times the same, and shows whether the
numbers (word scores, throat verdicts) came out the same.
  ~/dikduk/venv/bin/python ~/dikduk/app/mac/bench.py [--mps]"""
import sys, os, time, json, subprocess, io
import requests
BASE = next((a for a in sys.argv[1:] if a.startswith('http')), 'http://127.0.0.1:7860'); DIR = os.environ.get('DK_DIR') or os.path.expanduser('~/dikduk'); APP = os.environ.get('DK_APP') or os.path.join(DIR, 'app')
def cut(mp3, t0, t1):
    return subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t0:.3f}', '-i', mp3, '-t', f'{t1 - t0:.3f}', '-ac', '1', '-ar', '16000', '-f', 'wav', '-'], capture_output=True).stdout
def bench(base):
    out = {}
    # Tehillim 23:1 from the perek the server ships: its first line's times come from the server's own lyrics
    L = requests.get(base + '/lyrics', timeout=120).json()['s']['t23']; ev = [x.split(',') for x in L['t']['tehillim-023.mp3'].split(';') if x]
    t0 = int(ev[0][0]) / 10; t1 = int(ev[1][0]) / 10 if len(ev) > 1 else t0 + 8
    wav = cut(os.path.join(APP, 'static', 'tehillim', 'tehillim-023.mp3'), t0, t1)
    words = L['l'][int(ev[0][1])]
    ts = []; R = None
    for i in range(3):
        a = time.time(); r = requests.post(base + '/check', params={'words': words, 'ref': 'tehillim-023.mp3', 't0': t0, 't1': t1, 'pid': 't23'}, data=wav, timeout=600).json(); ts.append(time.time() - a); R = r
    out['check_s'] = [round(x, 2) for x in ts]; out['check_ms_server'] = R['take'].get('ms'); out['hskel'] = [w.get('hskel') for w in R['take']['words']]
    out['throat'] = [(th['c'], th['v']) for w in R['take']['words'] for th in w.get('throat', [])]
    tl = []; V = []
    for name, c in (('ayin-1.mp3', 'ע'), ('het-1.mp3', 'ח'), ('qof-1.mp3', 'ק'), ('tet-1.mp3', 'ט'), ('sadi-1.mp3', 'צ'), ('resh-1.mp3', 'ר')):
        data = open(os.path.join(APP, 'static', 'letters', name), 'rb').read()
        a = time.time(); j = requests.post(base + '/letter', params={'c': c}, data=data, timeout=120).json(); tl.append(time.time() - a); V.append((c, j.get('v')))
    out['letter_s'] = [round(x, 2) for x in tl]; out['letters'] = V
    return out
h = requests.get(BASE + '/health', timeout=120).json(); print('server', BASE, 'version', h['version'], 'device', h['device'], 'threads', h['threads'])
A = bench(BASE); print(json.dumps(A, ensure_ascii=False))
print(f"\nCPU: a pasuk check {min(A['check_s'])}–{max(A['check_s'])} s (first one includes the hazzan's line) · a letter {min(A['letter_s'])}–{max(A['letter_s'])} s")
if '--mps' in sys.argv:
    env = dict(os.environ); env.update({k: v for k, v in (l.strip().split('=', 1) for l in open(os.path.join(DIR, 'env')) if '=' in l and not l.startswith('#'))}); env['DK_DEVICE'] = 'mps'; env['DK_NO_WARM'] = '1'
    p = subprocess.Popen([os.path.join(DIR, 'venv', 'bin', 'uvicorn'), 'app:app', '--host', '127.0.0.1', '--port', '7870'], cwd=APP, env=env, stdout=open(os.path.join(DIR, 'logs', 'bench_mps.log'), 'w'), stderr=subprocess.STDOUT)
    try:
        for i in range(120):
            try: h2 = requests.get('http://127.0.0.1:7870/health', timeout=3).json(); break
            except Exception: time.sleep(3)
        print('\nMPS server device:', h2['device'])
        B = bench('http://127.0.0.1:7870'); print(json.dumps(B, ensure_ascii=False))
        print(f"MPS: a pasuk check {min(B['check_s'])}–{max(B['check_s'])} s · a letter {min(B['letter_s'])}–{max(B['letter_s'])} s")
        same = all(abs((a or 0) - (b or 0)) < .02 for a, b in zip(A['hskel'], B['hskel'])) and A['throat'] == B['throat'] and A['letters'] == B['letters']
        print('same verdicts and word scores (within .02):', same)
    finally:
        p.terminate()
