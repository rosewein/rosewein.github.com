import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from paths import RAW as _RAW, D as _D, W as _W  # 경로는 src/paths.py 한곳에서 정한다
OUT = str(_W("nodelink", "_")).rsplit("/", 1)[0]  # 중간 파일(격자·gpkg·요약)
SITE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "site")
import asyncio, sys
from playwright.async_api import async_playwright
D3=open(str(_W("vendor","node_modules","d3","dist","d3.min.js"))).read()  # npm install d3 (WORK/vendor 안)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--allow-file-access-from-files"])
        for name,w,h,theme,js in [("desk",1366,900,"light",""),("dark",1366,900,"dark","document.getElementById('slider').value=16;document.getElementById('slider').dispatchEvent(new Event('input'))"),("phone",390,844,"light","")]:
            pg=await b.new_page(viewport={"width":w,"height":h}, color_scheme=theme)
            logs=[]; pg.on("console", lambda m: logs.append(m.text)); pg.on("pageerror", lambda e: logs.append("ERR "+str(e)))
            async def route(r):
                u=r.request.url
                if "cdnjs" in u: await r.fulfill(body=D3, content_type="application/javascript")
                elif "fonts.g" in u: await r.fulfill(body="", content_type="text/css")
                else: await r.continue_()
            await pg.route("**/*", route)
            await pg.goto("http://127.0.0.1:8765/index.html"); await pg.wait_for_timeout(2500)
            if js: await pg.evaluate(js); await pg.wait_for_timeout(800)
            await pg.screenshot(path=f"/tmp/shot_{name}.png", full_page=(name!="phone"))
            print(name, logs[:5])
        await b.close()
asyncio.run(main())
