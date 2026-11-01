"""The strict switch in the embed (and the lab page): check a take, read the words, switch strict on, read again.
On a clean take every 'not sure' becomes 'not clear' (✕) and nothing else moves; on an unclear take the marks stay and the
summary asks for a clearer take; off again restores the first view exactly; the switch is remembered on reload.
The takes: Rabbi Alouf's 23:1 (tools/take_alouf_23_1.wav) as it is, with a word cut out and with two words swapped (cut
at the server's own word times, made in a temp folder) and under noise (heard, but not clean: head median ~.65), his
23:2 with a swallowed shva, and 4 s of noise; a pizmon take
(tools/take_shrem_l2.m4a on pizmon 200 line 2) only when that file is there. The site's page is made by the test and
served on a free local port, with the embed and its api from the server under test. Only checks takes, saves nothing.
usage: t_strict_ui.py [base url, default http://127.0.0.1:7861]"""
import asyncio, os, sys, json, wave, shutil, tempfile, threading, http.server, urllib.parse
import numpy as np, requests
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); TMP = tempfile.mkdtemp(prefix='dk_strict_')
BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:7861').rstrip('/')
class Site(http.server.BaseHTTPRequestHandler):
    """a stand-in for the site: /demo.html?th=23&line=1 (or pz=…) -> a page with the embed on that line, pointed at BASE"""
    def do_GET(self):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
        b = ('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><body style="margin:0">'
             f'<div data-dikduk data-api="{BASE}" ' + ' '.join(f'data-{k}="{v}"' for k, v in q.items() if k in ('th', 'pz', 'line')) + f'></div><script src="{BASE}/embed.js"></script>').encode()
        self.send_response(200); self.send_header('content-type', 'text/html; charset=utf-8'); self.send_header('content-length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
SRV = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Site); threading.Thread(target=SRV.serve_forever, daemon=True).start(); SITE = f'http://127.0.0.1:{SRV.server_port}/'
def rd(p):
    with wave.open(p, 'rb') as w: return np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float32) / 32768
def wr(name, x):
    p = os.path.join(TMP, name)
    with wave.open(p, 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
    return p
def takes():
    """the tampered 23:1 takes, cut where the server puts the words (a plain check of the intact take)"""
    x = rd(os.path.join(HERE, 'take_alouf_23_1.wav')); W = json.load(open(os.path.join(HERE, '..', 'lyrics_tehillim.json'), encoding='utf-8'))['s']['t23']['l'][0]
    TW = requests.post(BASE + '/check', params={'words': W}, data=open(os.path.join(HERE, 'take_alouf_23_1.wav'), 'rb').read(), headers={'Content-Type': 'audio/wav'}, timeout=300).json()['take']['words']
    s = lambda i: int(TW[i]['t0'] * 16000); e = lambda i: int(TW[i]['t1'] * 16000)
    swap = lambda i: np.concatenate([x[:s(i)], x[s(i + 1):e(i + 1)], x[s(i):e(i)], x[e(i + 1):]])
    rng = np.random.default_rng(7)
    return {'skip': wr('take_alouf_23_1_skip.wav', np.concatenate([x[:s(1)], x[e(1):]])), 'swap': wr('take_alouf_23_1_swap.wav', swap(1)), 'swap01': wr('take_alouf_23_1_swap01.wav', swap(0)),
            'noisy': wr('take_alouf_23_1_noisy.wav', x + rng.normal(0, .05, len(x)).astype(np.float32)), 'noise': wr('take_noise.wav', rng.normal(0, .05, 16000 * 4).astype(np.float32))}
VIEW = """()=>({say: document.querySelector('.dk [data-r=say]').textContent, cls: document.querySelector('.dk [data-r=say]').className,
  w: [...document.querySelectorAll('.dk .dk-w')].map(b => [b.className.replace('dk-w','').replace('sel','').trim(), b.querySelector('small').textContent, [...b.querySelectorAll('b span')].map(s => s.className).join(',')]),
  notes: document.querySelector('.dk [data-r=notes]').textContent, strict: document.querySelector('.dk [data-r=strict]').checked})"""
fails = []
async def one(pw, page, take):   # page: the demo page's query (th / pz, line); take: a file
    b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}); P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
    got = {}
    async def on_resp(r):
        if '/job/' in r.url or r.url.split('?')[0].endswith('/check'):
            try:
                j = await r.json()
                if 'take' in j: got['j'] = j
                elif isinstance(j.get('result'), dict) and 'take' in j['result']: got['j'] = j['result']
            except Exception: pass
    P.on('response', on_resp)
    await P.goto(SITE + 'demo.html?' + page); await P.evaluate("()=>{try{localStorage.removeItem('dk.strict')}catch(e){}}"); await P.reload(); await P.wait_for_timeout(2500)
    files = await P.query_selector_all('.dk input[type=file]'); await files[0].set_input_files(take); await P.wait_for_timeout(300); await P.click('.dk [data-r=check]')
    await P.wait_for_function("()=>{const b=document.querySelector('.dk [data-r=busy]');return b&&b.hidden===true&&document.querySelector('.dk [data-r=say]').textContent}", timeout=300000)
    v0 = await P.evaluate(VIEW)
    await P.click('.dk [data-r=strict]'); await P.wait_for_timeout(300); v1 = await P.evaluate(VIEW)
    await P.click('.dk [data-r=strict]'); await P.wait_for_timeout(300); v2 = await P.evaluate(VIEW)
    await P.click('.dk [data-r=strict]'); await P.wait_for_timeout(200); await P.reload(); await P.wait_for_timeout(1500)
    kept = await P.evaluate("()=>document.querySelector('.dk [data-r=strict]').checked")
    j = got.get('j'); hs = sorted(t['hskel'] for t in j['take']['words'] if (t.get('n') or 0) >= 2 and t.get('hskel') is not None) if j else []
    if len(hs) >= 3: hs = hs[1:]
    hm = hs[(len(hs) - 1) // 2] if hs else None; clean = hm is not None and hm >= .7
    take = os.path.basename(take); print(f'\n== {take} on {page}: clean {clean} (head {hm})')
    for name, v in (('lenient', v0), ('strict', v1)):
        print(f'  {name:8s} [{v["cls"]}] {v["say"][:110]}'); print('           ', ' '.join(f'{m}:{l}' for m, l, _ in v['w']))
    if errs: fails.append((take, 'page errors', errs))
    if v2 != v0: fails.append((take, 'switching off did not restore the first view'))
    if not kept: fails.append((take, 'the switch was not remembered on reload'))
    m0 = [m for m, _, _ in v0['w']]; m1 = [m for m, _, _ in v1['w']]
    nospeech = 'did not hear any singing' in v0['say']; canthear = 'could not make out' in v0['say']
    if clean and not canthear and not nospeech:
        if 'unsure' in m1: fails.append((take, 'strict left a not-sure word on a clean take'))
        if any(a != b and not (a == 'unsure' and b == 'off') for a, b in zip(m0, m1)): fails.append((take, 'strict moved something other than not-sure', m0, m1))
        if 'not clear enough for a strict check' in v1['say']: fails.append((take, 'unclear banner on a clean take'))
    else:
        if m0 != m1: fails.append((take, 'strict changed marks on an unclear take', m0, m1))
        if not nospeech and not canthear and 'wrong' not in v0['cls'] and 'does not sound like this line' not in v0['say'] and 'not clear enough for a strict check' not in v1['say']:
            fails.append((take, 'no "not clear enough" on an unclear take', v1['say']))
    await b.close()
async def main():
    async with async_playwright() as pw:
        T = takes(); TH = os.path.join(HERE, 'take_shrem_l2.m4a')
        CASES = [('th=23&line=1', T['swap']), ('th=23&line=1', T['swap01']), ('th=23&line=1', os.path.join(HERE, 'take_alouf_23_1.wav')), ('th=23&line=1', T['skip']), ('th=23&line=1', T['noisy']),
                 ('th=23&line=2', os.path.join(HERE, 'take_alouf_23_2_shvadrop.wav')), ('th=23&line=1', T['noise'])] + ([('pz=200&line=2', TH)] if os.path.exists(TH) else [])
        if not os.path.exists(TH): print('(no tools/take_shrem_l2.m4a: the pizmon case is left out)')
        for page, take in CASES: await one(pw, page, take)
        # the lab page: the switch is there and toggles without errors (no take)
        b = await pw.chromium.launch(); P = await b.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto(BASE + '/'); await P.wait_for_timeout(2000); n = await P.evaluate("()=>!!document.getElementById('strict')")
        print('\nlab page: switch present', n, '| errors', errs)
        if not n or errs: fails.append(('lab page', n, errs))
        await b.close()
    shutil.rmtree(TMP, ignore_errors=True)
    print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
asyncio.run(main())
