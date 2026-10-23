"""The booth end to end at phone size: start, a few tasks with injected recordings (no microphone in a headless
browser), the label chips, Save, Skip, then /takes and /score. usage: t_booth.py <base_url>"""
import asyncio, os, sys, json, base64, time, requests
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); B = sys.argv[1].rstrip('/'); OUT = os.path.join(HERE, '..', 'shots'); os.makedirs(OUT, exist_ok=True)
WAV = base64.b64encode(open(os.path.join(HERE, 'take_alouf_23_1.wav'), 'rb').read()).decode()
NAME = 'Test ' + time.strftime('%H%M')
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
        print('save without chip ->', await P.evaluate("()=>document.querySelector('#err').textContent"))
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
    S2 = requests.get(B + '/score', params={'set': 'david', 'who': WHO}).json(); print('own scoreboard (who):', S2['n'], 'takes', S2['totals'])
    print('wrong who ->', requests.get(B + '/score', params={'set': 'david', 'who': 'nope'}).json()['n'], 'takes')
    # the server side
    T = requests.get(B + '/takes', params={'set': 'david', 'name': NAME}).json(); print('takes:', T['n'], T['dir'], 'mirror', T['mirror'], [(j['task'], j['do'], j['labels']) for j in T['items']])
    for _ in range(60):
        S = requests.get(B + '/score', params={'set': 'david', 'name': NAME}).json()
        if not S['totals']['waiting']: break
        time.sleep(5)
    print('score totals:', S['totals'])
    for r in S['rows']: print(' ', r['task'], r['do'], r['labels'], r['state'], r.get('claims'))
    aud = requests.get(B + '/takes/audio/' + T['items'][0]['id']); print('audio:', aud.status_code, aud.headers.get('content-type'), len(aud.content), 'bytes')
asyncio.run(run())
