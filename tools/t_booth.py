"""The booth end to end at phone size: start, a few tasks with injected recordings (no microphone in a headless
browser), the label chips, Save, Skip, then /takes and /score. It SAVES three takes on the server (under a name
"Test HHMMSS"): point it at a local or test server. The key (the server's DK_KEY) is sent to /takes and /score; a
server with no key set (a private machine) needs none. Screenshots go to shots/.
usage: t_booth.py <base_url> [key] [--real: allow a server that is not on this machine]"""
import asyncio, os, sys, json, base64, time, requests, urllib.parse
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
B = ARGS[0].rstrip('/'); KEY = ARGS[1] if len(ARGS) > 1 else None; OUT = os.path.join(HERE, '..', 'shots'); os.makedirs(OUT, exist_ok=True)
if urllib.parse.urlparse(B).hostname not in ('127.0.0.1', 'localhost', '::1') and '--real' not in sys.argv:
    sys.exit(f'{B} is not on this machine: this test files takes into its store (add --real if that is meant)')
K = {'key': KEY} if KEY else {}
WAV = base64.b64encode(open(os.path.join(HERE, 'take_alouf_23_1.wav'), 'rb').read()).decode()
NAME = 'Test ' + time.strftime('%H%M%S'); fails = []
async def inject(P):
    await P.evaluate("""(b64)=>{const bin=atob(b64);const u=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);SECS=5.9;setTake(new Blob([u],{type:'audio/wav'}));}""", WAV)
    await P.wait_for_timeout(300)
async def run():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark', device_scale_factor=2)
        P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto(B + '/record?set=david'); await P.wait_for_timeout(2500)
        print('title:', await P.evaluate("()=>document.querySelector('#title').textContent"), '| resume:', await P.evaluate("()=>document.querySelector('#resume').textContent"))
        await P.screenshot(path=f'{OUT}/booth-1-start.png', full_page=True)
        await P.fill('#name', NAME); await P.click('#begin'); await P.wait_for_timeout(500)
        print('task 1:', await P.evaluate("()=>document.querySelector('#prog').textContent+' | '+document.querySelector('#ask').textContent+' | '+document.querySelector('#where').textContent"))
        await P.screenshot(path=f'{OUT}/booth-2-task.png', full_page=True)
        await inject(P); await P.screenshot(path=f'{OUT}/booth-3-recorded.png', full_page=True)
        await P.click('#save'); await P.wait_for_timeout(1500)
        print('task 2:', await P.evaluate("()=>document.querySelector('#prog').textContent+' | '+document.querySelector('#ask').textContent"))
        await P.click('#skipBtn'); await P.wait_for_timeout(300)
        print('task 3:', await P.evaluate("()=>document.querySelector('#prog').textContent+' | '+document.querySelector('#ask').textContent"))
        await inject(P); await P.screenshot(path=f'{OUT}/booth-4-ayin.png', full_page=True)
        await P.click('.chip[data-w="Yes"]'); await P.click('#save'); await P.wait_for_timeout(1500)
        await P.click('#skipBtn'); await P.wait_for_timeout(300)   # d04
        print('task 5:', await P.evaluate("()=>document.querySelector('#prog').textContent+' | '+document.querySelector('#ask').textContent"))
        await inject(P); await P.click('#save'); await P.wait_for_timeout(300)
        e = await P.evaluate("()=>document.querySelector('#err').textContent"); print('save without chip ->', e)
        if not e: fails.append('Save went through on a skip task without the word tapped')
        await P.click('.chip[data-w="לא"]'); await P.screenshot(path=f'{OUT}/booth-5-skipq.png', full_page=True); await P.click('#save'); await P.wait_for_timeout(1500)
        print('task 6:', await P.evaluate("()=>document.querySelector('#prog').textContent+' | '+document.querySelector('#ask').textContent"))
        # reload: resumes where it was
        await P.goto(B + '/record?set=david'); await P.wait_for_timeout(1500)
        print('after reload:', await P.evaluate("()=>document.querySelector('#resume').textContent+' | '+document.querySelector('#begin').textContent"))
        # the pro set shows a whole perek
        await P.goto(B + '/record?set=pro'); await P.wait_for_timeout(1500); await P.fill('#name', NAME); await P.click('#begin'); await P.wait_for_timeout(500)
        print('pro task:', await P.evaluate("()=>document.querySelector('#ask').textContent.slice(0,60)+' | lines: '+document.querySelectorAll('#text .ps').length"))
        await P.screenshot(path=f'{OUT}/booth-6-pro.png', full_page=True)
        WHO = await P.evaluate("()=>localStorage.getItem('dk.rec.who')")
        print('page errors:', errs); await b.close()
        if errs: fails.append(('page errors', errs))
    S2 = requests.get(B + '/score', params={'set': 'david', 'who': WHO}).json(); print('own scoreboard (who):', S2['n'], 'takes', S2['totals'])
    if S2['n'] != 3: fails.append(('own scoreboard', S2['n'], 'takes, not 3'))
    nope = requests.get(B + '/score', params={'set': 'david', 'who': 'nope'}).json()['n']; print('wrong who ->', nope, 'takes')
    if nope: fails.append(('a wrong who sees takes', nope))
    # the server side (with the key: a public server refuses /takes and /score?name= without it)
    T = requests.get(B + '/takes', params={'set': 'david', 'name': NAME, **K}).json()
    if 'items' not in T: fails.append(('/takes', T)); print('/takes:', T)
    else:
        print('takes:', T['n'], T['dir'], 'mirror', T['mirror'], [(j['task'], j['do'], j['labels']) for j in T['items']])
        if T['n'] != 3: fails.append(('/takes', T['n'], 'takes, not 3'))
        for _ in range(60):
            S = requests.get(B + '/score', params={'set': 'david', 'name': NAME, **K}).json()
            if 'totals' not in S or not S['totals']['waiting']: break
            time.sleep(5)
        print('score totals:', S.get('totals') or S)
        if 'totals' not in S or S['totals']['waiting']: fails.append(('/score', S.get('totals') or S))
        for r in S.get('rows') or []: print(' ', r['task'], r['do'], r['labels'], r['state'], r.get('claims'))
        if T['items']:
            aud = requests.get(B + '/takes/audio/' + T['items'][0]['id'], params=K); print('audio:', aud.status_code, aud.headers.get('content-type'), len(aud.content), 'bytes')
            if aud.status_code != 200 or not (aud.headers.get('content-type') or '').startswith('audio/'): fails.append(('take audio', aud.status_code, aud.headers.get('content-type')))
    print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
asyncio.run(run())
