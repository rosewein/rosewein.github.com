// 물길 갈래(waterways): 국토정보맵 「역사지도 → 종이지도」의 옛 지형도 조각을 구역마다 EPSG:5179 격자 그림으로 이어 붙여 내려받는다.
//
// 쓰는 곳: 이지의 크롬에서 https://map.ngii.go.kr/ms/map/NlipMap.do 를 열고 「역사지도」 → 「종이지도」에서 아무 판이나
// 「지도보기」로 한 번 띄운 뒤, 이 파일 내용을 그 탭의 자바스크립트로 넣는다(조각은 작업 공간에서 막혀 그 탭 안에서만 불러진다).
//
//   WT.init()                              지도·oldMap 레이어·타일 격자를 찾음
//   await WT.offset(판, 점들, 반경, 간격)    판을 지금 좌표에 맞추는 평행이동(dx, dy, m)을 찾음. 점들은 EPSG:5179 [x, y]
//                                          (지금 철도 선을 따라 찍은 점: 옛 판의 철도 기호는 검은 칸이 섞인 굵은 선이라 어두운 픽셀이 많다)
//   await WT.crop(이름, 판, [서, 남, 동, 북](경위도), m/px, dx, dy)
//                                          그 상자를 m/px 격자로 그린 PNG와 맞춤 정보 JSON을 내려받음(다운로드 폴더)
//
// 판 이름은 조각 주소의 판 부분이다: PC050K_1945(1:50,000 「1910 ~ 1930」), PT025K_1970·1980·1990(1:25,000 「○○년대」).
// 1960–1990년대 판은 지금 좌표보다 동쪽 약 184m·남쪽 약 311m 밀려 있다(roads 갈래 topo_probe.js). 그래서 지금 좌표 (x, y)의
// 색은 판의 (x + dx, y + dy)에서 읽는다.
(function () {
  const WT = window.WT = window.WT || {};
  WT.cfg = Object.assign({ targetRes: 2.1, conc: 3, gap: 60 }, WT.cfg || {});
  function allLayers(coll, out = []) { coll.getArray().forEach(l => { if (l.getLayers) allLayers(l.getLayers(), out); else out.push(l); }); return out; }
  WT.init = function () {
    WT.map = window.map; if (!WT.map || !window.ol) return "window.map 또는 window.ol이 없음";
    WT.proj = WT.map.getView().getProjection();
    WT.layer = allLayers(WT.map.getLayers()).find(l => l.get && l.get("name") === "oldMap");
    if (!WT.layer) return "oldMap 레이어가 없음(종이지도를 한 번 띄운 뒤 다시)";
    WT.src = WT.layer.getSource(); WT.tg = WT.src.getTileGrid(); WT.urlFn = WT.src.getTileUrlFunction();
    const res = WT.tg.getResolutions();
    WT.z = res.reduce((bi, r, i) => Math.abs(r - WT.cfg.targetRes) < Math.abs(res[bi] - WT.cfg.targetRes) ? i : bi, 0);
    WT.res = res[WT.z];
    return JSON.stringify({ proj: WT.proj.getCode(), z: WT.z, res: WT.res });
  };
  const cache = new Map();
  const edUrl = (ed, tc) => { const u = WT.urlFn(tc, 1, WT.proj); return u ? u.replace(/P[TC]0\d\dK_\d{4}/, ed) : null; };
  const tileOf = (x, y) => WT.tg.getTileCoordForCoordAndZ([x, y], WT.z);
  async function loadOne(url) {
    if (cache.has(url)) return cache.get(url);
    let img = null;
    try {
      const r = await fetch(url, { credentials: "same-origin" });
      if (r.ok) {
        const bmp = await createImageBitmap(await r.blob());
        const cv = new OffscreenCanvas(bmp.width, bmp.height), cx = cv.getContext("2d", { willReadFrequently: true });
        cx.drawImage(bmp, 0, 0); img = cx.getImageData(0, 0, bmp.width, bmp.height);
      } else WT.nBad = (WT.nBad || 0) + 1;
    } catch (e) { WT.lastErr = String(e); }
    cache.set(url, img); WT.nFetched = (WT.nFetched || 0) + 1;
    return img;
  }
  // 상자(EPSG:5179) 안 조각을 모두 불러 둔다
  WT.load = async function (ed, x0, y0, x1, y1) {
    const a = tileOf(x0, y0), b = tileOf(x1, y1), urls = [];
    for (let i = Math.min(a[1], b[1]); i <= Math.max(a[1], b[1]); i++)
      for (let j = Math.min(a[2], b[2]); j <= Math.max(a[2], b[2]); j++) urls.push(edUrl(ed, [WT.z, i, j]));
    const todo = [...new Set(urls)].filter(u => u && !cache.has(u)); let k = 0;
    async function worker() { while (k < todo.length) { const u = todo[k++]; await loadOne(u); await new Promise(r => setTimeout(r, WT.cfg.gap)); } }
    await Promise.all(Array.from({ length: WT.cfg.conc }, worker));
    return todo.length;
  };
  WT.px = function (ed, x, y) {
    const tc = tileOf(x, y), im = cache.get(edUrl(ed, tc));
    if (!im) return null;
    const ext = WT.tg.getTileCoordExtent(tc);
    const px = Math.floor((x - ext[0]) * im.width / (ext[2] - ext[0])), py = Math.floor((ext[3] - y) * im.height / (ext[3] - ext[1]));
    if (px < 0 || py < 0 || px >= im.width || py >= im.height) return null;
    const q = (py * im.width + px) * 4, d = im.data;
    return d[q + 3] < 128 ? null : [d[q], d[q + 1], d[q + 2]];
  };
  WT.dark = c => !!c && Math.max(c[0], c[1], c[2]) < 110;
  // 점들(지금 좌표)에서 판을 dx, dy만큼 옮겨 읽을 때 어두운 픽셀 비율이 가장 큰 이동을 찾는다
  WT.offset = async function (ed, pts, R = 600, step = 10) {
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    await WT.load(ed, Math.min(...xs) - R, Math.min(...ys) - R, Math.max(...xs) + R, Math.max(...ys) + R);
    const score = (dx, dy) => { let n = 0, v = 0; for (const p of pts) { const c = WT.px(ed, p[0] + dx, p[1] + dy); if (c) { v++; if (WT.dark(c)) n++; } } return v ? n / v : 0; };
    let best = [0, 0, score(0, 0)]; const base = best[2];
    for (let dx = -R; dx <= R; dx += step) for (let dy = -R; dy <= R; dy += step) { const s = score(dx, dy); if (s > best[2]) best = [dx, dy, s]; }
    return JSON.stringify({ ed, dx: best[0], dy: best[1], hit: +best[2].toFixed(3), hit0: +base.toFixed(3), n: pts.length });
  };
  // 상자를 m/px 격자로 그려 PNG로 내려받는다. 격자 (i, j)의 가운데 = (x0 + (i + .5)·m, y1 − (j + .5)·m), 그 색은 판의 (x + dx, y + dy)
  WT.crop = async function (name, ed, box, m, dx, dy) {
    const p0 = ol.proj.fromLonLat([box[0], box[1]], WT.proj), p1 = ol.proj.fromLonLat([box[2], box[3]], WT.proj);
    const x0 = Math.round(Math.min(p0[0], p1[0])), y0 = Math.round(Math.min(p0[1], p1[1])), x1 = Math.round(Math.max(p0[0], p1[0])), y1 = Math.round(Math.max(p0[1], p1[1]));
    await WT.load(ed, x0 + dx - 50, y0 + dy - 50, x1 + dx + 50, y1 + dy + 50);
    const W = Math.round((x1 - x0) / m), H = Math.round((y1 - y0) / m);
    const cv = document.createElement("canvas"); cv.width = W; cv.height = H;
    const cx = cv.getContext("2d"), out = cx.createImageData(W, H); let miss = 0;
    for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) {
      const c = WT.px(ed, x0 + (i + 0.5) * m + dx, y1 - (j + 0.5) * m + dy), q = (j * W + i) * 4;
      if (c) { out.data[q] = c[0]; out.data[q + 1] = c[1]; out.data[q + 2] = c[2]; out.data[q + 3] = 255; } else miss++;
    }
    cx.putImageData(out, 0, 0);
    const meta = { name, ed, box, crs: "EPSG:5179", x0, y0, x1, y1, m, W, H, dx, dy, miss, made: new Date().toISOString() };
    const save = (blob, fn) => { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = fn; document.body.appendChild(a); a.click(); a.remove(); };
    await new Promise(r => cv.toBlob(b => { save(b, `slm_water_${name}_${ed}.png`); r(); }, "image/png"));
    await new Promise(r => setTimeout(r, 400));
    save(new Blob([JSON.stringify(meta)], { type: "application/json" }), `slm_water_${name}_${ed}.json`);
    return JSON.stringify({ name, ed, W, H, miss });
  };
})();

// ---- 2026-11-27 덧붙임: 크롬이 파일마다 저장 위치를 물어서, 구역 이미지를 한 파일(slm_water_bundle.json)로 묶어 받는다 ----
// 쓰는 법(국토정보맵 종이지도 화면에서, WT.init() 뒤):
//   WT.Z = { jamsil: [127.055,37.495,127.125,37.545], jeoja: [127.010,37.525,127.050,37.545], yeouido: [126.895,37.510,126.955,37.545], nanji: [126.860,37.555,126.905,37.585] };
//   WT.OFF = { PC050K_1945: { w: [-80,-330], e: [-80,-315] }, PT025K_1970: [160,-335], PT025K_1980: [190,-310], PT025K_1990: [185,-320] };
//   for (const z in WT.Z) for (const ed in WT.OFF) await WT.cropUrl(z, ed, 4);   // 한 번에 45초를 넘기면 구역별로 나눠 부른다
//   WT.bundle();   // 다운로드 폴더에 slm_water_bundle.json(16장, 약 70 MB)
// 어긋남 재기: WT.offset(ed, 점들, 600, 20)으로 거칠게 찾고 WT.fine(ed, 점들, dx, dy)로 5 m 간격 다시. 점은 1914년 이전 개통·현존 철도(data/rail.json)
(function () {
  const WT = window.WT;
  WT.off = (ed, z) => { const o = WT.OFF[ed]; return Array.isArray(o) ? o : (WT.Z[z][2] <= 127.0 ? o.w : o.e); };
  WT.fine = function (ed, pts, cx, cy, R = 40, step = 5) {
    const score = (dx, dy) => { let n = 0, v = 0; for (const p of pts) { const c = WT.px(ed, p[0] + dx, p[1] + dy); if (c) { v++; if (WT.dark(c)) n++; } } return v ? n / v : 0; };
    let best = [cx, cy, score(cx, cy)];
    for (let dx = cx - R; dx <= cx + R; dx += step) for (let dy = cy - R; dy <= cy + R; dy += step) { const s = score(dx, dy); if (s > best[2]) best = [dx, dy, s]; }
    return { dx: best[0], dy: best[1], hit: +best[2].toFixed(3) };
  };
  WT.grid = async function (ed, box, m, dx, dy) {
    const p0 = ol.proj.fromLonLat([box[0], box[1]], WT.proj), p1 = ol.proj.fromLonLat([box[2], box[3]], WT.proj);
    const x0 = Math.round(Math.min(p0[0], p1[0])), y0 = Math.round(Math.min(p0[1], p1[1])), x1 = Math.round(Math.max(p0[0], p1[0])), y1 = Math.round(Math.max(p0[1], p1[1]));
    await WT.load(ed, x0 + dx - 50, y0 + dy - 50, x1 + dx + 50, y1 + dy + 50);
    const W = Math.round((x1 - x0) / m), H = Math.round((y1 - y0) / m), px = new Uint8Array(W * H * 3);
    for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) { const c = WT.px(ed, x0 + (i + 0.5) * m + dx, y1 - (j + 0.5) * m + dy) || [255, 255, 255], q = (j * W + i) * 3; px[q] = c[0]; px[q + 1] = c[1]; px[q + 2] = c[2]; }
    return { x0, y0, x1, y1, m, W, H, px };
  };
  WT.B = WT.B || {};
  WT.cropUrl = async function (name, ed, m) {
    const o = WT.off(ed, name), g = await WT.grid(ed, WT.Z[name], m, o[0], o[1]);
    const cv = document.createElement("canvas"); cv.width = g.W; cv.height = g.H;
    const cx = cv.getContext("2d"), im = cx.createImageData(g.W, g.H);
    for (let k = 0, q = 0; k < g.W * g.H; k++, q += 3) { im.data[4 * k] = g.px[q]; im.data[4 * k + 1] = g.px[q + 1]; im.data[4 * k + 2] = g.px[q + 2]; im.data[4 * k + 3] = 255; }
    cx.putImageData(im, 0, 0);
    WT.B[name + "|" + ed] = { name, ed, box: WT.Z[name], crs: "EPSG:5179", x0: g.x0, y0: g.y0, x1: g.x1, y1: g.y1, m, W: g.W, H: g.H, dx: o[0], dy: o[1], png: cv.toDataURL("image/png") };
    return g.W + "x" + g.H;
  };
  WT.bundle = function () {
    const meta = { made: new Date().toISOString(), src: "국토정보맵 역사지도 종이지도(NGII), 타일 z" + WT.z + " 해상도 " + WT.res.toFixed(3) + " m", offsetsMeasuredOn: "1914년 이전 개통·현존 철도선(경부·경인·경원) 표본점과 지형도 검은 선의 겹침", items: Object.values(WT.B) };
    const blob = new Blob([JSON.stringify(meta)], { type: "application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "slm_water_bundle.json"; document.body.appendChild(a); a.click(); a.remove();
    return +(blob.size / 1048576).toFixed(1) + " MB";
  };
})();
