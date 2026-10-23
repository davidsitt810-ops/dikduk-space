"""Screenshots of the lab page at iPhone size: the opening screen, a pizmon opened, a line picked, and the result
(the Shrem take uploaded). usage: shot.py <url> <prefix> [light]"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); URL = sys.argv[1]; PFX = sys.argv[2]; scheme = 'light' if len(sys.argv) > 3 else 'dark'
OUT = os.path.join(HERE, '..', 'shots'); os.makedirs(OUT, exist_ok=True)
async def run():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}, color_scheme=scheme, device_scale_factor=2)
        P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto(URL); await P.wait_for_timeout(2500); await P.screenshot(path=f'{OUT}/{PFX}-1-start.png', full_page=True)
        await P.fill('#pid', '200'); await P.click('#go'); await P.wait_for_timeout(2000); await P.screenshot(path=f'{OUT}/{PFX}-2-opened.png', full_page=True)
        await P.click('.ln[data-k="2"]'); await P.wait_for_timeout(600); await P.screenshot(path=f'{OUT}/{PFX}-3-line.png', full_page=True)
        await P.set_input_files('#file', os.path.join(HERE, 'take_shrem_l2.m4a')); await P.wait_for_timeout(500); await P.screenshot(path=f'{OUT}/{PFX}-4-recorded.png', full_page=True)
        await P.click('#check'); await P.wait_for_timeout(2500); await P.screenshot(path=f'{OUT}/{PFX}-5-checking.png', full_page=True)
        await P.wait_for_function("()=>document.querySelector('#busy').hidden===true", timeout=240000); await P.wait_for_timeout(500)
        await P.screenshot(path=f'{OUT}/{PFX}-6-result.png', full_page=True)
        print('errors:', errs); await b.close()
asyncio.run(run())
