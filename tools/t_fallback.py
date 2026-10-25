"""embed.js with several servers: dead first + live second -> uses the live one and a check works; live first -> same;
all dead -> the 'server down' pill and no page errors. Needs the local server on 7861 and the demo site on 8099."""
import asyncio, os, sys, json
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); TAKE = os.path.join(HERE, 'take_shrem_l2.m4a')
async def one(pw, name, expect_live):
    b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}); P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
    await P.goto(f'http://127.0.0.1:8099/{name}'); await P.wait_for_timeout(4000)
    pill = await P.evaluate("()=>document.querySelector('.dk [data-r=srv]').textContent"); print(name, '| pill:', pill, '| errors:', errs)
    ok = True
    if expect_live:
        files = await P.query_selector_all('.dk input[type=file]'); await files[0].set_input_files(TAKE); await P.wait_for_timeout(300); await P.click('.dk [data-r=check]')
        await P.wait_for_function("()=>{const b=document.querySelector('.dk [data-r=busy]');return b&&b.hidden===true&&document.querySelectorAll('.dk .dk-w').length>0}", timeout=180000)
        say = await P.evaluate("()=>document.querySelector('.dk [data-r=say]').textContent"); print('   check:', say[:70])
        ok = 'Ready' in pill and bool(say) and not errs
    else:
        ok = ('Ready' not in pill) and not errs
    await b.close(); return ok
async def main():
    async with async_playwright() as pw:
        r = [await one(pw, 'demo_fallback.html', True), await one(pw, 'demo_primary.html', True), await one(pw, 'demo_alldead.html', False)]
    print('ALL GOOD' if all(r) else 'FAIL', r); sys.exit(0 if all(r) else 1)
asyncio.run(main())
