"""a Tehillim perek whose sync data exists but whose audio is not on this server (94 locally): the page must say so,
disable the play buttons and check against the nikud only — no broken requests"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:7861/'
async def run():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}); P = await c.new_page()
        errs = []; P.on('pageerror', lambda e: errs.append(str(e))); bad = []
        P.on('response', lambda r: bad.append((r.status, r.url[-60:])) if r.status >= 400 else None)
        await P.goto(URL); await P.wait_for_timeout(1500)
        await P.click('#kindTh'); await P.fill('#pid', '94'); await P.click('#go'); await P.wait_for_timeout(2500)
        print('recs:', await P.evaluate("()=>document.querySelector('#recs').textContent.slice(0,120)"))
        print('play buttons disabled:', await P.evaluate("()=>[...document.querySelectorAll('.hear')].every(b=>b.disabled)"), 'lines:', await P.evaluate("()=>document.querySelectorAll('.ln').length"))
        await P.click('.ln[data-k="0"]'); await P.wait_for_timeout(1500)
        print('bad responses:', bad, 'page errors:', errs)
        await P.click('[data-change="s1"]'); await P.wait_for_timeout(300); await P.fill('#pid', '23'); await P.click('#go'); await P.wait_for_timeout(2000)
        print('perek 23 play buttons enabled:', await P.evaluate("()=>[...document.querySelectorAll('.hear')].some(b=>!b.disabled)"))
        await b.close()
asyncio.run(run())
