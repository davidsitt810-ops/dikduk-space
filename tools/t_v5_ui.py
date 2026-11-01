"""v5 in the embed, phone size, against a local server with DK_KEY=testkey123:
what-to-check switches, the hazzan-then-you button, hiding a note and sending it (/feedback), the tries history,
ask a hazzan -> an answer through the API -> the answer in the checker and on /hazzan, and the voice card from a
fake microphone (Rabbi Alouf's 23:1-2). usage: t_v5_ui.py"""
import asyncio, os, sys, json, requests
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__)); B = 'http://127.0.0.1:7861'; KEY = 'testkey123'; fails = []
DONE = "()=>{const b=document.querySelector('.dk [data-r=busy]');return b&&b.hidden===true&&document.querySelector('.dk [data-r=say]').textContent}"
async def check(P, take):
    if await P.evaluate("()=>!document.querySelector('.dk [data-r=s4]').hidden"): await P.click('.dk [data-r=againLine]'); await P.wait_for_timeout(400)
    f = await P.query_selector_all('.dk input[type=file]'); await f[0].set_input_files(os.path.join(H, take)); await P.wait_for_timeout(300)
    await P.evaluate("()=>{document.querySelector('.dk [data-r=say]').textContent=''}"); await P.click('.dk [data-r=check]'); await P.wait_for_function(DONE, timeout=300000)
notes = "()=>document.querySelector('.dk [data-r=notes]').textContent"
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--use-file-for-fake-audio-capture=' + os.path.join(H, 'vc_23_1_2.wav')])
        c = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2); P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto('http://127.0.0.1:8099/demo_th23_2.html'); await P.evaluate("()=>{localStorage.clear()}"); await P.reload(); await P.wait_for_timeout(2500)
        await check(P, 'take_alouf_23_2_shvadrop.wav'); n0 = await P.evaluate(notes); print('notes:', n0)
        if 'shva na' not in n0: fails.append(('no shva note to work with', n0))
        # what to check: vowels & shva off -> the note and the underline go; on -> back
        await P.click('.dk [data-r=nVow]'); n1 = await P.evaluate(notes); und = await P.evaluate("()=>document.querySelectorAll('.dk .dk-sv').length"); print('vowels off:', repr(n1), 'underlines', und)
        if 'shva' in n1 or und: fails.append(('vowels switch did not hide', n1, und))
        await P.click('.dk [data-r=nVow]'); n2 = await P.evaluate(notes)
        if 'shva na' not in n2: fails.append(('vowels switch did not restore', n2))
        await P.click('.dk [data-r=nLet]'); th = await P.evaluate("()=>document.querySelector('.dk [data-r=thP]').hidden"); await P.click('.dk [data-r=nLet]')
        if not th: fails.append('letters off left the throat table')
        both = await P.evaluate("()=>!document.querySelector('.dk [data-r=bothLine]').hidden"); print('hazzan-then-you button:', both)
        if not both: fails.append('no hazzan-then-you button')
        # hide the note, send it
        await P.click('.dk [data-r=notes] .dk-x'); n3 = await P.evaluate(notes); sh = await P.evaluate("()=>!document.querySelector('.dk [data-r=share]').hidden"); print('after hiding:', repr(n3), 'share prompt', sh)
        if 'shva' in n3 or not sh: fails.append(('hide/share', n3, sh))
        await P.click('.dk [data-r=shareYes]'); await P.wait_for_timeout(1500); sp = await P.evaluate("()=>document.querySelector('.dk [data-r=shareP]').textContent"); print('share:', sp)
        fb = requests.get(B + '/feedback', params={'key': KEY}).json(); print('feedback on server:', fb['n'], fb['items'][0].get('dismissed') if fb['n'] else None)
        if not fb['n'] or 'shva' not in json.dumps(fb['items'][0].get('dismissed'), ensure_ascii=False): fails.append(('feedback not kept', fb))
        # the same take again: the history line, and the hidden note is back for a new result
        await check(P, 'take_alouf_23_2_shvadrop.wav'); hist = await P.evaluate("()=>document.querySelector('.dk [data-r=hist]').textContent"); print('history:', hist)
        if '·' not in hist: fails.append(('no history', hist))
        el = await P.query_selector('.dk [data-r=s4]'); await el.screenshot(path=os.path.join(H, '..', 'shots', 'v5_result.png'))
        # ask a hazzan
        await P.click('.dk [data-r=askBtn]'); await P.fill('.dk [data-r=askNote]', 'Is my shva right in ינהלני?'); await P.click('.dk [data-r=askSend]'); await P.wait_for_timeout(1500)
        am = await P.evaluate("()=>document.querySelector('.dk [data-r=askMsg]').textContent"); qs = await P.evaluate("()=>document.querySelector('.dk [data-r=qs]').textContent"); print('ask:', am, '| panel:', qs[:80])
        L = requests.get(B + '/reviews', params={'key': KEY}).json(); print('reviews waiting:', L['waiting'])
        if not L['waiting']: fails.append(('review not kept', L))
        else:
            rid = L['items'][0]['id']; r = requests.post(B + f'/review/{rid}/reply', params={'key': KEY}, json={'text': 'Your shva in ינהלני is missing: say ye-na-ha-le-ni.', 'by': 'Test Hazzan'}); print('reply:', r.status_code)
            await P.reload(); await P.wait_for_timeout(2500); qs2 = await P.evaluate("()=>document.querySelector('.dk [data-r=qs]').textContent"); print('panel after the answer:', qs2[:160])
            if 'ye-na-ha-le-ni' not in qs2: fails.append(('answer not shown', qs2))
            H2 = await c.new_page(); await H2.goto(B + '/hazzan?key=' + KEY); await H2.wait_for_timeout(2000); hz = await H2.evaluate("()=>document.querySelector('#list').textContent"); print('/hazzan:', hz[:120].replace('\n', ' '))
            if 'ye-na-ha-le-ni' not in hz: fails.append('the hazzan page does not show it')
            await H2.screenshot(path=os.path.join(H, '..', 'shots', 'hazzan_page.png'), full_page=True); await H2.close()
        # the voice card: fake microphone = Rabbi Alouf's 23:1-2
        await P.click('.dk [data-r=vcOpen]'); await P.wait_for_timeout(1200); vt = await P.evaluate("()=>document.querySelector('.dk [data-r=vcText]').textContent"); print('vc text:', vt[:60])
        await P.click('.dk [data-r=vcRec]'); await P.wait_for_timeout(16500); await P.click('.dk [data-r=vcRec]')
        await P.wait_for_function("()=>document.querySelector('.dk [data-r=vcSay]').textContent", timeout=300000)
        vs = await P.evaluate("()=>document.querySelector('.dk [data-r=vcSay]').textContent"); vc = await P.evaluate("()=>localStorage.getItem('dk.vc')"); print('voice card:', vs, vc)
        if not vc and 'Not clear' not in vs: fails.append(('voice card not stored', vs))
        el = await P.query_selector('.dk [data-r=vc]'); await el.screenshot(path=os.path.join(H, '..', 'shots', 'v5_voicecard.png'))
        if errs: fails.append(('page errors', errs))
        await b.close()
    print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
asyncio.run(main())
