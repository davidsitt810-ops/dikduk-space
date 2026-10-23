# The real lab page against the real server (local): pizmon 200, line 3 (והעדה לחובי בטבעו בים), the take = another
# hazzan (Shrem) singing that line, uploaded as an m4a (what an iPhone records). Reads the marks and the sentence.
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:7861/'
async def run():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        c = await b.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
        P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto(URL); await P.wait_for_timeout(1500)
        print('server pill:', await P.evaluate("()=>document.querySelector('#srv').textContent"))
        await P.fill('#pid', '200'); await P.click('#go'); await P.wait_for_timeout(2500)
        print('recordings:', await P.evaluate("()=>document.querySelector('#recSel')?[...document.querySelectorAll('#recSel option')].map(o=>o.textContent):document.querySelector('#recs').textContent"))
        print('lines:', await P.evaluate("()=>[...document.querySelectorAll('.ln')].slice(0,4).map(b=>b.textContent)"))
        await P.click('.ln[data-k="2"]'); await P.wait_for_timeout(300)
        await P.set_input_files('#file', os.path.join(HERE, 'take_shrem_l2.m4a')); await P.wait_for_timeout(300)
        await P.click('#check')
        await P.wait_for_function("()=>document.querySelector('#busy').hidden===true", timeout=120000)
        st = await P.evaluate("""()=>({err:document.querySelector('#err').textContent,say:document.querySelector('#say').textContent,
          words:[...document.querySelectorAll('#res .w')].map(w=>w.querySelector('b').textContent+' '+w.className.replace('w','').trim()+' '+w.querySelector('small').textContent),
          th:[...document.querySelectorAll('#th .tr')].map(t=>t.textContent.replace(/\\s+/g,' ').trim()),notes:document.querySelector('#notes').textContent,ph:document.querySelector('#ph').textContent.slice(0,200)})""")
        print(json.dumps(st, ensure_ascii=False, indent=1))
        await P.evaluate("()=>{document.querySelector('#lab').open=true;document.querySelector('#detP').open=true;}"); await P.click('#saveV'); await P.wait_for_timeout(300)
        print('scorecard:', await P.evaluate("()=>document.querySelector('#sc').textContent"))
        await P.screenshot(path=os.path.join(HERE, '..', 'shots', 'live-200.png'), full_page=True)
        print('vowel panel:', await P.evaluate("()=>document.querySelector('#vwP').hidden?'hidden':document.querySelector('#vw').textContent.replace(/\\s+/g,' ').trim().slice(0,300)"))
        # v4: a Tehillim perek (Rabbi Alouf), the take = a cut of his own pasuk when the audio is on the server
        await P.click('[data-change="s1"]'); await P.wait_for_timeout(300)
        await P.fill('#pid', 't23'); await P.click('#go'); await P.wait_for_timeout(2500)
        print('tehillim title:', await P.evaluate("()=>document.querySelector('#ptitle').textContent"))
        print('tehillim lines:', await P.evaluate("()=>[...document.querySelectorAll('.ln')].slice(0,2).map(b=>b.textContent)"))
        await P.click('.ln[data-k="0"]'); await P.wait_for_timeout(300)
        take = os.path.join(HERE, 'take_alouf_23_1.wav')
        if os.path.exists(take):
            await P.set_input_files('#file', take); await P.wait_for_timeout(300); await P.click('#check')
            await P.wait_for_function("()=>document.querySelector('#busy').hidden===true", timeout=180000)
            st = await P.evaluate("""()=>({err:document.querySelector('#err').textContent,say:document.querySelector('#say').textContent,
              words:[...document.querySelectorAll('#res .w')].map(w=>w.querySelector('b').textContent+' '+w.className.replace('w','').trim()+' '+w.querySelector('small').textContent),
              th:[...document.querySelectorAll('#th .tr')].map(t=>t.textContent.replace(/\\s+/g,' ').trim()),
              vw:document.querySelector('#vwP').hidden?'hidden':document.querySelector('#vw').textContent.replace(/\\s+/g,' ').trim().slice(0,400)})""")
            print('tehillim check:', json.dumps(st, ensure_ascii=False, indent=1))
            await P.screenshot(path=os.path.join(HERE, '..', 'shots', 'live-t23.png'), full_page=True)
        print('errors:', errs)
        await b.close()
asyncio.run(run())
