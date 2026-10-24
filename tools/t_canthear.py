"""a take that is only noise: the page must say it could not make out the words, show no red word and no letter notes"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:7861/'
async def run():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}); P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto(URL); await P.wait_for_timeout(1500)
        await P.click('#kindTh'); await P.fill('#pid', '23'); await P.click('#go'); await P.wait_for_timeout(2500); await P.click('.ln[data-k="0"]'); await P.wait_for_timeout(300)
        await P.set_input_files('#file', os.path.join(HERE, 'take_noise.wav')); await P.wait_for_timeout(300); await P.click('#check')
        await P.wait_for_function("()=>document.querySelector('#busy').hidden===true", timeout=180000)
        st = await P.evaluate("""()=>({say:document.querySelector('#say').textContent, cls:document.querySelector('#say').className,
          words:[...document.querySelectorAll('#res .w')].map(w=>w.className.replace('w','').trim()), notes:document.querySelector('#notes').textContent, th:document.querySelector('#thP').hidden,
          nums:document.querySelector('#nums').textContent.slice(-80)})""")
        print(json.dumps(st, ensure_ascii=False, indent=1)); print('errors:', errs)
        await b.close()
asyncio.run(run())
