"""지도 화면 찍기(작업 공간용): python3 src/shot.py <index.html 폴더> <장면 json> <출력 폴더>

작업 공간은 cdnjs·구글 폰트에 접속하지 못하므로, npm으로 받은 d3·topojson과 지도 글꼴(fontsource)을 가로채 넣는다.
준비: mkdir -p $SLM_VENDOR && cd $SLM_VENDOR && npm i d3@7.8.5 topojson@3.0.2 @fontsource/hahmlet @fontsource/ibm-plex-sans-kr @fontsource/ibm-plex-mono
      (SLM_VENDOR 기본값 /home/claude/vendor, 브라우저는 /usr/bin/google-chrome, 파이썬 playwright 필요)
장면 json: [{"name":..., "w":1280, "h":900, "dark":false, "mobile":false, "js":"...", "after":["덧씌울.js"],
            "clip":"map|stagechips|page|full", "wait":700, "probe":"화면에서 값을 뽑을 JS 식"}]
js 안에서 쓸 수 있는 도우미: Y(연도), chip(레이어, 켜기여부), cam(단추 id). 움직임 줄이기(reduced motion)로 찍어 화면 전환이 바로 끝난다
"""
import json, sys, os, threading, http.server, functools, time
from playwright.sync_api import sync_playwright

ROOT, SCEN, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
VEND = os.path.join(os.environ.get("SLM_VENDOR", "/home/claude/vendor"), "node_modules")
FONTS = os.path.join(VEND, "@fontsource")
FONT_CSS = os.path.join(OUT, "_fonts.css")
os.makedirs(OUT, exist_ok=True)
# 지도가 쓰는 굵기만 모아 글꼴 CSS를 만든다(파일 주소는 아래 작은 서버의 /__fonts/로)
with open(FONT_CSS, "w") as fo:
    for pkg, ws in {"hahmlet": [300, 500, 700], "ibm-plex-sans-kr": [400, 500, 600], "ibm-plex-mono": [400, 500]}.items():
        for w in ws:
            fo.write(open(f"{FONTS}/{pkg}/{w}.css").read().replace("url(./files/", f"url(http://127.0.0.1:8765/__fonts/{pkg}/files/") + "\n")

class H(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, p):
        if p.startswith("/__fonts/"):
            return os.path.join(FONTS, p[len("/__fonts/"):].split("?")[0])
        return super().translate_path(p)
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*"); super().end_headers()
    def log_message(self, *a): pass

srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), functools.partial(H, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()

HELP = """
window.Y = (y) => { const s = document.getElementById('year'); s.value = y; s.dispatchEvent(new Event('input')); };
window.chip = (k, on) => { const c = document.querySelector(`.chip[data-layer="${k}"]`); if (!c) return; const now = c.getAttribute('aria-pressed') === 'true'; if (now !== on) c.click(); };
window.cam = (id) => document.getElementById(id).click();
0;
"""

def route(r):
    u = r.request.url
    if "cdnjs.cloudflare.com" in u and "d3.min.js" in u:
        return r.fulfill(path=f"{VEND}/d3/dist/d3.min.js", content_type="application/javascript")
    if "cdnjs.cloudflare.com" in u and "topojson" in u:
        return r.fulfill(path=f"{VEND}/topojson/dist/topojson.min.js", content_type="application/javascript")
    if "fonts.googleapis.com" in u:
        return r.fulfill(path=FONT_CSS, content_type="text/css")
    if u.startswith("http://127.0.0.1:8765/"):
        return r.continue_()
    return r.abort()

scen = json.load(open(SCEN))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for s in scen:
        ctx = b.new_context(viewport={"width": s.get("w", 1280), "height": s.get("h", 900)},
                            device_scale_factor=s.get("dpr", 2 if s.get("mobile") else 1),
                            is_mobile=s.get("mobile", False), has_touch=s.get("mobile", False),
                            color_scheme="dark" if s.get("dark") else "light", reduced_motion="reduce")
        pg = ctx.new_page()
        pg.route("**/*", route)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://127.0.0.1:8765/index.html", wait_until="load")
        pg.evaluate("document.fonts.ready")
        pg.evaluate(HELP)
        if s.get("js"): pg.evaluate("() => {" + s["js"] + "}")
        pg.wait_for_timeout(s.get("wait", 700))
        for f in s.get("after", []):
            pg.evaluate("() => {" + open(f).read() + "}")
            pg.wait_for_timeout(s.get("after_wait", 900))
        out = os.path.join(OUT, s["name"] + ".png")
        clip = s.get("clip", "map")
        if clip == "map":
            pg.locator(".stage").screenshot(path=out)
        elif clip == "stagechips":
            box = pg.evaluate("(() => { const a = document.querySelector('.stage').getBoundingClientRect(); const c = document.querySelector('.chips').parentElement.getBoundingClientRect(); return {x:0, y:a.top + scrollY, width: innerWidth, height: c.bottom - a.top}; })()")
            pg.screenshot(path=out, clip=box, full_page=True)
        elif clip == "page":
            pg.screenshot(path=out)
        else:
            pg.screenshot(path=out, full_page=True)
        info = pg.evaluate(s["probe"]) if s.get("probe") else None
        print(s["name"], "errors:", errs[:3], "probe:", json.dumps(info, ensure_ascii=False) if info is not None else "")
        ctx.close()
    b.close()
srv.shutdown()
