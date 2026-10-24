"""the page with line 1 of Tehillim 23 picked and Rabbi Alouf's pasuk 2 uploaded: the verdict must be 'not this line'
(the rival evidence), and pasuk 1 uploaded on line 1 must not"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:7861/'
async def one(P, take):
    await P.set_input_files('#file', os.path.join(HERE, take)); await P.wait_for_timeout(300); await P.click('#check')
    await P.wait_for_function("()=>document.querySelector('#busy').hidden===true", timeout=180000)
    return await P.evaluate("""()=>({say:document.querySelector('#say').textContent, words:[...document.querySelectorAll('#res .w')].map(w=>w.className.replace('w','').trim()), lab:(document.querySelector('#nums').textContent.match(/clean take.*$/)||[''])[0]})""")
async def run():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}); P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto(URL); await P.wait_for_timeout(1500)
        await P.click('#kindTh'); await P.fill('#pid', '23'); await P.click('#go'); await P.wait_for_timeout(2500); await P.click('.ln[data-k="0"]'); await P.wait_for_timeout(300)
        r = await one(P, 'take_alouf_23_2.wav'); print('pasuk 2 on line 1:', json.dumps(r, ensure_ascii=False))
        await P.goto(URL); await P.wait_for_timeout(1500); await P.click('#kindTh'); await P.fill('#pid', '23'); await P.click('#go'); await P.wait_for_timeout(2500); await P.click('.ln[data-k="0"]'); await P.wait_for_timeout(300)
        r = await one(P, 'take_alouf_23_1.wav'); print('pasuk 1 on line 1:', json.dumps(r, ensure_ascii=False))
        await P.goto(URL); await P.wait_for_timeout(1500); await P.click('#kindTh'); await P.fill('#pid', '23'); await P.click('#go'); await P.wait_for_timeout(2500); await P.click('.ln[data-k="1"]'); await P.wait_for_timeout(300)
        r = await one(P, 'take_alouf_23_2.wav'); print('pasuk 2 on line 2:', json.dumps(r, ensure_ascii=False))
        print('errors:', errs); await b.close()
asyncio.run(run())
