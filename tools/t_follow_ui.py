"""Live follow-along in the embed: a fake microphone plays Rabbi Alouf's 23:2 (looped); while recording, the line's
words light up (data-follow="1" forces it on this slow CPU server); after Stop the line is back to normal."""
import asyncio, os, sys
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__)); fails = []
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--use-file-for-fake-audio-capture=' + os.path.join(H, 'take_alouf_23_2.wav')])
        P = await (await b.new_context(viewport={'width': 390, 'height': 844})).new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto('http://127.0.0.1:8099/demo_follow.html'); await P.wait_for_timeout(3000)
        await P.click('.dk [data-r=recBtn]'); seen = []
        for _ in range(16):
            await P.wait_for_timeout(500); seen.append(await P.evaluate("()=>document.querySelectorAll('.dk [data-r=lineWords] .dk-fw.on').length"))
        await P.click('.dk [data-r=recBtn]'); await P.wait_for_timeout(500)
        after = await P.evaluate("()=>document.querySelectorAll('.dk [data-r=lineWords] .dk-fw').length")
        print('lit words over 8 s:', seen, '| spans after stop:', after)
        if max(seen) < 1: fails.append(('nothing lit', seen))
        if after: fails.append('line not restored after stop')
        if errs: fails.append(('page errors', errs))
        await b.close()
    print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
asyncio.run(main())
