import asyncio, os
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--use-file-for-fake-audio-capture=' + os.path.join(HERE, 'fake_mic_het.wav'), '--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, permissions=['microphone'])
        pg = await ctx.new_page(); msgs = []
        pg.on('console', lambda m: msgs.append(m.text)); pg.on('pageerror', lambda e: msgs.append('ERR ' + str(e)))
        await pg.goto('http://127.0.0.1:7861/letters'); await pg.wait_for_timeout(2000)
        await pg.click('.tile[data-c="ח"]'); await pg.wait_for_timeout(500)
        await pg.click('#rec'); await pg.wait_for_timeout(3200)
        await pg.wait_for_selector('#out:not([hidden])', timeout=60000); await pg.wait_for_timeout(300)
        print('verdict:', await pg.inner_text('#verdict')); print('hist:', await pg.inner_text('#hist'))
        await pg.click('#labBtn'); await pg.wait_for_timeout(200); print('lab:', await pg.inner_text('#lab'))
        await pg.screenshot(path='shot_letters_4.png', full_page=True)
        # strict mode + another take
        await pg.check('#strict'); await pg.click('#rec'); await pg.wait_for_timeout(3200); await pg.wait_for_selector('#out:not([hidden])', timeout=60000); await pg.wait_for_timeout(300)
        print('verdict 2 (strict):', await pg.inner_text('#verdict'))
        print('console:', msgs[-5:])
        await b.close()
asyncio.run(main())
