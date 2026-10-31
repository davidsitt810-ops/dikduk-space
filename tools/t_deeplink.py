"""/letters?c=ח and /letters#ק open that letter; ?c=ב&want=v picks the variant; a letter it does not check falls back."""
import asyncio, sys
from playwright.async_api import async_playwright
fails = []
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); P = await b.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        for q, want_c, want_v in (('?c=ח', 'ח', None), ('#ק', 'ק', None), ('?c=ב&want=v', 'ב', 'v'), ('?c=ג', None, None)):
            await P.goto('http://127.0.0.1:7861/letters' + q); await P.wait_for_timeout(1500)
            r = await P.evaluate("()=>({big: document.querySelector('#big') && !document.querySelector('#card').hidden ? document.querySelector('#big').textContent : null, seg: [...document.querySelectorAll('#seg button.on')].map(b => b.dataset.k)})")
            print(q, r)
            if want_c and r['big'] != want_c: fails.append((q, r))
            if want_v and want_v not in r['seg']: fails.append((q, 'variant', r))
        if errs: fails.append(('page errors', errs))
        await b.close()
    print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
asyncio.run(main())
