"""v5.7 on the lab page: the too-noisy line and Learn my voice. A fresh browser (its own student id) on Tehillim 23:1:
learning off -> no panel, no student id sent; on -> the panel, and each check goes with the id; Rabbi Alouf's take as
recorded is kept (1 of 30), the same take with the noise 5 dB under is not (and shows the noise line, with no vowel
notes), as recorded again -> 2 of 30 and no noise line; after a reload the switch and the id are remembered (the next
take: 3 of 30); Forget my takes needs a second tap and then the count is 0; learning off again -> no id sent. (The
switch and the panel are in step 4, with the take's result.)
TRAINED_ID=<id> (a student whose head is made on this server) adds: the panel for a made head, switched off and on
again (never forgotten). Needs the local v5.7 server on 7861."""
import asyncio, os, sys, json
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); URL = os.environ.get('DK_URL', 'http://127.0.0.1:7861/')
fails = []
def need(ok, *what):
    if not ok: fails.append(what)
    print('  ', 'ok ' if ok else 'BAD', *what)

async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}); P = await c.new_page()
        errs = []; P.on('pageerror', lambda e: errs.append(str(e))); sent = []; got = {}
        P.on('request', lambda r: sent.append(r.url) if '/check' in r.url else None)
        async def on_resp(r):
            if '/job/' in r.url or urlparse(r.url).path.endswith('/check'):
                try:
                    j = await r.json(); j = j.get('result') if isinstance(j.get('result'), dict) else j
                    if isinstance(j, dict) and 'take' in j: got['j'] = j
                except Exception: pass
        P.on('response', on_resp)
        async def check(name):
            if await P.evaluate("()=>!document.querySelector('#s4').hidden"): await P.click('#againLine'); await P.wait_for_timeout(300)
            got.pop('j', None); n0 = len(sent)
            await P.set_input_files('#file', os.path.join(HERE, name)); await P.wait_for_timeout(300); await P.click('#check')
            await P.wait_for_function("()=>document.querySelector('#busy').hidden===true&&document.querySelector('#say').textContent", timeout=300000)
            await P.wait_for_timeout(1200)
            v = await P.evaluate("""()=>({say:document.querySelector('#say').textContent, noisy:document.querySelector('#noisy').hidden?null:document.querySelector('#noisy').textContent,
               me:document.querySelector('#meP').hidden?null:document.querySelector('#meTxt').textContent, btns:[...document.querySelectorAll('#meBtns button')].map(x=>x.textContent),
               vow:[...document.querySelectorAll('#notes li')].map(l=>l.textContent).filter(t=>/where the (hazzan|nikud)/.test(t))})""")
            q = parse_qs(urlparse(sent[-1]).query) if len(sent) > n0 else {}
            return v, got.get('j'), q
        await P.goto(URL + '?th=23&line=1'); await P.wait_for_timeout(3000)
        print('learning off (a fresh browser):')
        need(await P.evaluate("()=>document.querySelector('#meP').hidden&&!document.querySelector('#learn').checked"), 'no panel, the switch off')
        v, j, q = await check('take_alouf_23_1.wav')
        need('student' not in q and 'enroll' not in q, 'no student id sent', sorted(q))
        need(v['noisy'] is None, 'no noise line on the take as recorded')
        print('learning on:')
        await P.click('#learn'); await P.wait_for_timeout(1500)
        me = await P.evaluate("()=>document.querySelector('#meP').hidden?null:document.querySelector('#meTxt').textContent")
        need(me is not None and '0 of 30' in me, 'the panel, 0 of 30', me)
        sid = await P.evaluate("()=>localStorage.getItem('dk.student')")
        v, j, q = await check('take_alouf_23_1.wav')
        need(q.get('student') == [sid] and q.get('enroll') == ['1'], 'the id and enroll sent', q.get('student'), q.get('enroll'))
        need(j is not None and j.get('student_kept') is True and (j.get('student') or {}).get('kept') == 1, 'the server kept it', j and j.get('student_kept'), j and j.get('student'))
        need(v['me'] is not None and '1 of 30' in v['me'], 'the panel says 1 of 30', v['me'])
        need('Forget my takes' in v['btns'], 'Forget my takes offered', v['btns'])
        v, j, q = await check('take_alouf_23_1_noisier.wav')
        need(j is not None and not j.get('student_kept'), 'the noisy take not kept')
        need(v['noisy'] is not None and 'vowels were not checked' in v['noisy'], 'the noise line, vowels not checked', v['noisy'])
        need(not v['vow'], 'no vowel notes on it', v['vow'])
        need(v['me'] is not None and '1 of 30' in v['me'], 'still 1 of 30', v['me'])
        v, j, q = await check('take_alouf_23_1.wav')
        need(v['noisy'] is None and v['me'] is not None and '2 of 30' in v['me'], 'as recorded again: no noise line, 2 of 30', v['noisy'], v['me'])
        print('a reload:')
        await P.reload(); await P.wait_for_timeout(3500)
        v, j, q = await check('take_alouf_23_1.wav')
        st = await P.evaluate("()=>({on:document.querySelector('#learn').checked, sid:localStorage.getItem('dk.student')})")
        need(st['on'] and st['sid'] == sid and q.get('student') == [sid], 'the switch and the id remembered', st, q.get('student'))
        need(v['me'] is not None and '3 of 30' in v['me'], 'the next take: 3 of 30', v['me'])
        print('forget:')
        await P.click('#meBtns button:has-text("Forget my takes")'); await P.wait_for_timeout(800)
        t = await P.evaluate("()=>[...document.querySelectorAll('#meBtns button')].map(x=>x.textContent)")
        need(any('Tap again' in x for x in t), 'a second tap asked for', t)
        await P.click('#meBtns button:has-text("Tap again")'); await P.wait_for_timeout(2500)
        me = await P.evaluate("()=>document.querySelector('#meTxt').textContent")
        need('0 of 30' in me, 'forgotten: 0 of 30', me)
        print('learning off again:')
        await P.click('#learn'); await P.wait_for_timeout(500)
        need(await P.evaluate("()=>document.querySelector('#meP').hidden"), 'no panel')
        v, j, q = await check('take_alouf_23_1.wav')
        need('student' not in q, 'no student id sent', sorted(q))
        tid = os.environ.get('TRAINED_ID')
        if tid:
            print(f'a made head ({tid}):')
            await P.evaluate("id=>{localStorage.setItem('dk.student',id);localStorage.setItem('dk.learn','1');}", tid); await P.reload(); await P.wait_for_timeout(3500)
            v, j, q = await check('take_alouf_23_1.wav')
            need(j is not None and (j.get('student') or {}).get('heard_with_own') is True and not j.get('student_kept'), 'heard with his own head, nothing more kept', j and j.get('student'))
            me = await P.evaluate("()=>({t:document.querySelector('#meTxt').textContent,b:[...document.querySelectorAll('#meBtns button')].map(x=>x.textContent)})")
            need('heard with your own voice model' in me['t'] and 'Switch it off' in me['b'] and 'Forget my voice' in me['b'], 'the made-head panel', me)
            await P.click('#meBtns button:has-text("Switch it off")'); await P.wait_for_timeout(1500)
            me = await P.evaluate("()=>({t:document.querySelector('#meTxt').textContent,b:[...document.querySelectorAll('#meBtns button')].map(x=>x.textContent)})")
            need('switched off' in me['t'] and 'Switch it on' in me['b'], 'switched off', me)
            v, j, q = await check('take_alouf_23_1.wav')
            need(j is not None and (j.get('student') or {}).get('heard_with_own') is False, 'off: heard with the shipped head', j and j.get('student'))
            await P.click('#meBtns button:has-text("Switch it on")'); await P.wait_for_timeout(1500)
            me = await P.evaluate("()=>document.querySelector('#meTxt').textContent")
            need('heard with your own voice model' in me, 'on again', me)
            v, j, q = await check('take_alouf_23_1.wav')
            need(j is not None and (j.get('student') or {}).get('heard_with_own') is True, 'on: heard with his own head', j and j.get('student'))
        need(not errs, 'no page errors', errs)
        await b.close()
    print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
asyncio.run(main())
