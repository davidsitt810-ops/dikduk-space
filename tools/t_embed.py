"""The site-native embed (embed.js) on the demo site, against the local server: mounts, loads the line, takes an uploaded
file, renders words, throat rows and notes without page errors. Usage: python3 t_embed.py [demo url] [take.wav]"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8099/site_demo.html'
TAKE = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'take_shrem_l2.m4a')
async def run():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        c = await b.new_context(viewport={'width': 390, 'height': 844})
        P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto(URL); await P.wait_for_timeout(2500)
        print('version:', await P.evaluate("()=>window.Dikduk&&window.Dikduk.version"))
        print('hero:', await P.evaluate("()=>document.querySelector('.dk [data-r=hero]')?.textContent.trim().slice(0,80)"))
        files = await P.query_selector_all('.dk input[type=file]'); print('file inputs:', len(files))
        await files[0].set_input_files(TAKE); await P.wait_for_timeout(500)
        await P.click('.dk [data-r=check]')
        await P.wait_for_function("()=>{const b=document.querySelector('.dk [data-r=busy]');return b&&b.hidden===true&&document.querySelectorAll('.dk .dk-w').length>0}", timeout=180000)
        st = await P.evaluate("""()=>({say:document.querySelector('.dk [data-r=say]').textContent,
          words:[...document.querySelectorAll('.dk .dk-w')].map(w=>w.querySelector('b').textContent+' '+w.className.replace('dk-w','').trim()+' '+w.querySelector('small').textContent),
          notes:document.querySelector('.dk [data-r=notes]')?.textContent.trim(),
          th:[...document.querySelectorAll('.dk [data-r=th] .dk-tr, .dk .dk-tr')].map(t=>t.textContent.replace(/\\s+/g,' ').trim().slice(0,120))})""")
        print(json.dumps(st, ensure_ascii=False, indent=1))
        os.makedirs(os.path.join(HERE, '..', 'shots'), exist_ok=True)
        await P.screenshot(path=os.path.join(HERE, '..', 'shots', 'embed-demo.png'), full_page=True)
        print('errors:', errs)
        await b.close()
asyncio.run(run())
