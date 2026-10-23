"""Direct /check against a server: pizmon 200 line 3 with the Shrem take (ref = the site's best recording, sync times
from /lyrics), then Tehillim 23:1 with Rabbi Alouf's own cut (ref = tehillim-023.mp3). Prints status, seconds, body.
usage: t_space_check.py <base_url> [pz|th|both]"""
import sys, os, json, time, requests
HERE = os.path.dirname(os.path.abspath(__file__)); B = sys.argv[1].rstrip('/'); what = sys.argv[2] if len(sys.argv) > 2 else 'both'
def sync_lines(s, f):
    ev = [tuple(map(int, x.split(','))) for x in s['t'][f].split(';') if x]; out = {}
    for i, (t, k) in enumerate(ev):
        if k < 0 or k in out: continue
        out[k] = (t / 10, ev[i + 1][0] / 10 if i + 1 < len(ev) else t / 10 + 8)
    return out
def post(params, path):
    t = time.time(); r = requests.post(B + '/check', params=params, data=open(path, 'rb').read(), timeout=900)
    dt = time.time() - t; print(f'  -> {r.status_code} in {dt:.0f} s; {r.headers.get("content-type")}; body: {r.text[:160]!r}')
    try: return r.json()
    except Exception: return None
def show(j):
    if not j or 'words' not in j: return
    print('  words:', ' '.join(f"{w}[skel {tw.get('skel')} hskel {tw.get('hskel')} pw {tw.get('pw')}]" for w, tw in zip(j['words'], j['take']['words'])))
    print('  throat:', [(t['c'], t.get('v')) for tw in j['take']['words'] for t in tw.get('throat', [])], '| fit:', [f.get('fit') for f in (j.get('fit') or [])][:12], '| ref:', bool(j.get('ref')), j.get('ref_err', '')[:80] if j.get('ref_err') else '')
    if j.get('vowels_nikud') is not None: print('  vowels vs nikud:', {k: [(d['you'], d['ref']) for d in v] for k, v in (j.get('vowels_nikud') or {}).items()})
L = requests.get(B + '/lyrics', timeout=120).json()
if what in ('pz', 'both'):
    s = L['s']['200']; b = s['b'] if s['b'] in s['t'] else list(s['t'])[0]; ln = sync_lines(s, b)
    words = s['l'][2]; t0, t1 = ln[2]; print(f'pizmon 200 line 3: "{words}" ref {b} {t0}-{t1}')
    for rep in (1, 2): show(post({'words': words, 'ref': b, 't0': t0, 't1': t1}, os.path.join(HERE, 'take_shrem_l2.m4a')))
if what in ('th', 'both'):
    s = L['s']['t23'] if 't23' in L['s'] else L['s'][[k for k in L['s'] if str(k).startswith('t') and k.endswith('23')][0]]
    th = json.load(open(os.path.join(HERE, '..', 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))['perakim']['23']['pesukim'][0]
    words = s['l'][0]; nik = (s.get('ln') or [None])[0]; print(f'Tehillim 23:1: "{words}" ref tehillim-023.mp3 {th["t0"]}-{th["t1"]}')
    for rep in (1, 2): show(post({'words': words, 'nikud': nik or '', 'ref': 'tehillim-023.mp3', 't0': th['t0'], 't1': th['t1']}, os.path.join(HERE, 'take_alouf_23_1.wav')))
