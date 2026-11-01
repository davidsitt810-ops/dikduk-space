"""The shva note in the embed (phone size): Tehillim 23:2 with the short vowel of יְ in יְנַהֲלֵנִי cut out -> the
notes say "say a short “e” after the י (shva na) — a shva at the start of a word is said"; the intact take -> no shva
note. Screenshot to shots/shva_phone.png.
The site's page is tools/demo_th23_2.html, served by the test itself on a free local port (the embed and its api
pointed at the server under test). Only checks takes, saves nothing.
usage: t_shva_ui.py [base url, default http://127.0.0.1:7861]"""
import asyncio, os, sys, threading, http.server
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__)); fails = []
BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:7861').rstrip('/')
class Site(http.server.BaseHTTPRequestHandler):
    """a stand-in for the site: tools/<page>, pointed at BASE (a real local server: Chromium lets a loopback page call a loopback api)"""
    def do_GET(self):
        p = os.path.join(H, os.path.basename(self.path.split('?')[0]))
        if not p.endswith('.html') or not os.path.isfile(p): self.send_error(404); return
        b = open(p, encoding='utf-8').read().replace('http://127.0.0.1:7861', BASE).replace('src="embed.js"', f'src="{BASE}/embed.js"').encode()
        self.send_response(200); self.send_header('content-type', 'text/html; charset=utf-8'); self.send_header('content-length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
SRV = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Site); threading.Thread(target=SRV.serve_forever, daemon=True).start(); SITE = f'http://127.0.0.1:{SRV.server_port}/'
async def run(P, take):
    await P.goto(SITE + 'demo_th23_2.html'); await P.wait_for_timeout(2500)
    f = await P.query_selector_all('.dk input[type=file]'); await f[0].set_input_files(os.path.join(H, take)); await P.wait_for_timeout(300); await P.click('.dk [data-r=check]')
    await P.wait_for_function("()=>{const b=document.querySelector('.dk [data-r=busy]');return b&&b.hidden===true&&document.querySelector('.dk [data-r=say]').textContent}", timeout=300000)
    return await P.evaluate("()=>({say: document.querySelector('.dk [data-r=say]').textContent, notes: document.querySelector('.dk [data-r=notes]').textContent})")
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2); P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        v = await run(P, 'take_alouf_23_2_shvadrop.wav'); print('tampered:', v)
        if 'shva na' not in v['notes'] or 'start of a word' not in v['notes']: fails.append(('no shva note', v))
        os.makedirs(os.path.join(H, '..', 'shots'), exist_ok=True)
        el = await P.query_selector('.dk [data-r=s4]'); await el.screenshot(path=os.path.join(H, '..', 'shots', 'shva_phone.png'))
        v0 = await run(P, 'take_alouf_23_2.wav'); print('intact:', v0)
        if 'shva' in v0['notes']: fails.append(('shva note on the intact take', v0))
        if errs: fails.append(('page errors', errs))
        await b.close()
    print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
asyncio.run(main())
