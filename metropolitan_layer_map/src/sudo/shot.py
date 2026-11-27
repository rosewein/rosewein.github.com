import sys, threading, http.server, functools, json
from playwright.sync_api import sync_playwright
ROOT='/home/claude/sudo/page'; OUT='/home/claude/sudo/shots'
import os; os.makedirs(OUT,exist_ok=True)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=http.server.ThreadingHTTPServer(('127.0.0.1',8766),functools.partial(H,directory=ROOT))
threading.Thread(target=srv.serve_forever,daemon=True).start()
D3=open('/home/claude/vendor/node_modules/d3/dist/d3.min.js').read()
scenes=json.loads(sys.argv[1])
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for sc in scenes:
        ctx=b.new_context(viewport={'width':sc['w'],'height':sc['h']},device_scale_factor=sc.get('dpr',1),color_scheme='dark' if sc.get('dark') else 'light',is_mobile=sc.get('mobile',False),has_touch=sc.get('mobile',False))
        pg=ctx.new_page(); errs=[]
        pg.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
        pg.on('pageerror',lambda e: errs.append(str(e)))
        pg.route('**/cdnjs.cloudflare.com/**',lambda r: r.fulfill(body=D3,content_type='application/javascript'))
        pg.route('**/fonts.googleapis.com/**',lambda r: r.abort())
        pg.route('**/fonts.gstatic.com/**',lambda r: r.abort())
        pg.goto('http://127.0.0.1:8766/'+sc.get('page','index.html')); pg.wait_for_timeout(1200)
        if sc.get('js'): pg.evaluate(sc['js']); pg.wait_for_timeout(sc.get('wait',700))
        if sc.get('probe'): print(sc['name'],'probe:',pg.evaluate(sc['probe']))
        pg.screenshot(path=f"{OUT}/{sc['name']}.png",full_page=sc.get('full',False))
        print(sc['name'],'errors:',errs[:5])
        ctx.close()
    b.close()
