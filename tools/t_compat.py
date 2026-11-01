"""The new pages (v4.9 embed, booth, letters) against an OLDER server (v4.8, what the Mac runs until update.sh): a
check renders, the strict switch works, no shva notes (the old server sends none), no page errors; letters deep link."""
import asyncio, os, sys
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__)); fails = []; B = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:7863'
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}); P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto('http://127.0.0.1:8099/demo_old.html'); await P.wait_for_timeout(3000)
        pill = await P.evaluate("()=>document.querySelector('.dk [data-r=srv]').textContent"); print('pill:', pill)
        f = await P.query_selector_all('.dk input[type=file]'); await f[0].set_input_files(os.path.join(H, 'take_alouf_23_2_shvadrop.wav')); await P.wait_for_timeout(300); await P.click('.dk [data-r=check]')
        await P.wait_for_function("()=>{const b=document.querySelector('.dk [data-r=busy]');return b&&b.hidden===true&&document.querySelector('.dk [data-r=say]').textContent}", timeout=300000)
        v = await P.evaluate("()=>({say: document.querySelector('.dk [data-r=say]').textContent, notes: document.querySelector('.dk [data-r=notes]').textContent, words: document.querySelectorAll('.dk .dk-w').length})"); print('check:', v)
        if not v['words']: fails.append(('no words rendered', v))
        if 'shva' in v['notes']: fails.append(('a shva note from an old server?', v))
        await P.click('.dk [data-r=strict]'); await P.wait_for_timeout(300); v2 = await P.evaluate("()=>document.querySelector('.dk [data-r=say]').textContent"); print('strict:', v2)
        await P.goto(B + '/letters?c=ח'); await P.wait_for_timeout(2000)
        big = await P.evaluate("()=>document.querySelector('#big') && !document.querySelector('#card').hidden ? document.querySelector('#big').textContent : null"); print('letters ?c=ח ->', big)
        if big != 'ח': fails.append(('deep link', big))
        if errs: fails.append(('page errors', errs))
        await b.close()
    print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
asyncio.run(main())
