"""The page on Tehillim 23:1 with three takes of Rabbi Alouf's own reading: intact, two words swapped, one skipped."""
import asyncio, os, sys, json
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:7861/'
async def run():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}); P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto(URL + '?th=23&line=1'); await P.wait_for_timeout(3000)
        for name in ('take_alouf_23_1.wav', 'take_alouf_23_1_swap.wav', 'take_alouf_23_1_skip.wav'):
            await P.set_input_files('#file', os.path.join(HERE, name)); await P.wait_for_timeout(300); await P.click('#check')
            await P.wait_for_function("()=>document.querySelector('#busy').hidden===true", timeout=240000); await P.wait_for_timeout(300)
            st = await P.evaluate("""()=>({say:document.querySelector('#say').textContent,words:[...document.querySelectorAll('#res .w')].map(w=>w.textContent.trim()),notes:[...document.querySelectorAll('#notes li')].map(l=>l.textContent),err:document.querySelector('#err').textContent,
              nums:document.querySelector('#nums').textContent.replace(/\\s+/g,' ').slice(-120)})""")
            print(name, '->', json.dumps(st, ensure_ascii=False))
            await P.click('#againLine'); await P.wait_for_timeout(300)
        print('errors:', errs); await b.close()
asyncio.run(run())
