import asyncio, os
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__))
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2); P = await c.new_page()
        await P.goto('http://127.0.0.1:8099/demo_pz200.html'); await P.wait_for_timeout(2500)
        f = await P.query_selector_all('.dk input[type=file]'); await f[0].set_input_files(os.path.join(H, 'take_shrem_l2.m4a')); await P.wait_for_timeout(300); await P.click('.dk [data-r=check]')
        await P.wait_for_function("()=>{const b=document.querySelector('.dk [data-r=busy]');return b&&b.hidden===true&&document.querySelector('.dk [data-r=say]').textContent}", timeout=300000)
        await P.click('.dk [data-r=strict]'); await P.wait_for_timeout(400)
        el = await P.query_selector('.dk [data-r=s4]'); await el.screenshot(path=os.path.join(H, '..', 'shots', 'strict_phone.png')); await b.close()
asyncio.run(main())
