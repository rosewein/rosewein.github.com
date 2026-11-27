// 큰 도로 갈래(roads): 국토정보맵 「역사지도 → 종이지도」의 옛 1:25,000 지형도에서
// 지금 큰 도로 링크 자리에 길이 그려져 있는지 판마다 잰다.
//
// 쓰는 곳: 이지의 크롬에서 https://map.ngii.go.kr/ms/map/NlipMap.do 를 열고 「역사지도 → 종이지도」로
// 1:25,000 지형도를 한 번 띄운 뒤, 이 파일 내용을 그 탭의 자바스크립트로 넣는다(지형도 조각은
// 작업 공간에서 막혀 있고 같은 출처인 그 탭 안에서만 불러진다).
//
//   TP.init()                         지도·지형도 레이어·타일 격자를 찾아 요약을 돌려줌
//   TP.setEdition("PT025K_1990")      판 바꾸기(숨은 select에 값을 넣고 「지도보기」를 누름)
//   await TP.loadRoads()              GitHub roads 브랜치의 data/majorroads.json을 받아 25m 점으로 나눔
//   TP.overlay(["호암로"])            그 길을 붉은 선으로 겹치고 화면을 맞춤(눈으로 볼 때)
//   TP.run("PT025K_1980", {names})    판 하나를 잼(비동기, TP.status()로 진행을 봄)
//   TP.dump("PT025K_1980", 0, 800)    결과를 짧은 JSON 글자로 꺼냄
//   TP.sample(x, y, ed)               한 점의 색과 분류(문턱 맞출 때)
//
// 재는 방법(시안): 점마다 길에 수직인 단면을 ±W m 읽어 픽셀을 색 무리로 나누고,
//   sig1 = 검은 테두리 – 속(흰·붉은·노란 등) – 검은 테두리, 속 너비 F1–F2 m, 가운데가 선에서 TOL m 안
//   sig2 = 붉은·노란 띠 하나, 너비 F1–F2 m, 가운데가 선에서 TOL m 안
// 를 센다. 같은 단면을 선에서 CTRL m 옆으로 옮긴 두 줄(대조)도 같이 세어, 그 동네에 길 무늬가
// 원래 얼마나 많은지(시가지 칠, 나란한 길)를 함께 남긴다. 있다·없다의 문턱은 결과를 받아
// src/majorroads_topo.py에서 정한다(개통일을 아는 길로 맞춤).
(function () {
  const TP = window.TP = window.TP || {};
  TP.cfg = Object.assign({
    roadsUrl: "https://raw.githubusercontent.com/rosewein/rosewein.github.com/roads/seoul-layer-map/data/majorroads.json",
    editions: ["PT025K_1960", "PT025K_1970", "PT025K_1980", "PT025K_1990", "PT025K_2000", "PT025K_2011", "PT025K_2013", "PT025K_2015"],
    targetRes: 2.5,   // 단면을 읽을 해상도(m/px)에 가장 가까운 확대 단계를 고름
    step: 25,         // 선 위 점 간격(m)
    endTrim: 15,      // 링크 양 끝(교차로)은 빼고 잼(m)
    W: 45,            // 단면 반쪽 길이(m)
    TOL: 22,          // 길 무늬 가운데가 선에서 이만큼 안이면 있음(m, 옛 판 위치 어긋남 몫)
    F1: 4, F2: 40,    // 속 너비(m)
    K1: 1, K2: 4,     // 검은 테두리 두께(px)
    CTRL: 110,        // 대조 단면을 옮길 거리(m)
    conc: 3,          // 동시에 부르는 조각 수
    gap: 60,          // 조각 부르기 사이 쉬는 시간(ms)
    cacheMax: 220,    // 메모리에 둘 조각 수
  }, TP.cfg || {});

  // ---------- 지도·레이어 찾기 ----------
  function allLayers(coll, out = []) {
    coll.getArray().forEach(l => { if (l.getLayers) allLayers(l.getLayers(), out); else out.push(l); });
    return out;
  }
  function srcUrlSample(src) {
    try { const u = src.getUrls && src.getUrls(); if (u && u.length) return u[0]; } catch (e) {}
    try { const f = src.getTileUrlFunction(); const tg = src.getTileGrid(); const z = Math.min(3, tg.getMaxZoom());
      const c = tg.getTileCoordForCoordAndZ(ol.extent.getCenter(tg.getExtent()), z); return f(c, 1, TP.proj); } catch (e) {}
    return "";
  }
  TP.init = function () {
    TP.map = window.map; if (!TP.map || !window.ol) return "window.map 또는 window.ol이 없음";
    TP.view = TP.map.getView(); TP.proj = TP.view.getProjection();
    const ls = allLayers(TP.map.getLayers());
    TP.layer = ls.find(l => l.getSource && /PT025K|PT050K|PT/.test(srcUrlSample(l.getSource())) && l.getVisible()) ||
               ls.find(l => l.getSource && /PT025K/.test(srcUrlSample(l.getSource())));
    if (!TP.layer) return "PT025K 조각 레이어를 찾지 못함. 레이어: " + ls.map(l => srcUrlSample(l.getSource ? l.getSource() : {}) || "?").join(" | ");
    TP.src = TP.layer.getSource(); TP.tg = TP.src.getTileGrid(); TP.urlFn = TP.src.getTileUrlFunction();
    const res = TP.tg.getResolutions();
    TP.z = res.reduce((bi, r, i) => Math.abs(r - TP.cfg.targetRes) < Math.abs(res[bi] - TP.cfg.targetRes) ? i : bi, 0);
    TP.res = res[TP.z];
    const ts = ol.size ? ol.size.toSize(TP.tg.getTileSize(TP.z)) : [256, 256];
    TP.tileSize = ts;
    return JSON.stringify({ proj: TP.proj.getCode(), z: TP.z, res: TP.res, resolutions: res, tileSize: ts,
      origin: TP.tg.getOrigin ? TP.tg.getOrigin(TP.z) : null, sampleUrl: srcUrlSample(TP.src),
      extent: TP.tg.getExtent && TP.tg.getExtent(), olVersion: ol.VERSION || "?" });
  };

  // ---------- 판 바꾸기(화면, 눈으로 볼 때) ----------
  TP.setEdition = function (code, scaleCode = "PT025K") {
    const s1 = document.querySelector("select#old_select1"), s2 = document.querySelector("select#old_select2");
    if (s1 && s1.value !== scaleCode) { s1.value = scaleCode; s1.dispatchEvent(new Event("change", { bubbles: true })); }
    if (!s2) return "select#old_select2 없음";
    s2.value = code; s2.dispatchEvent(new Event("change", { bubbles: true }));
    const btn = [...document.querySelectorAll("button, a, input[type=button]")].find(b => /지도\s*보기/.test(b.textContent || b.value || ""));
    if (btn) btn.click();
    return "판 " + code + (btn ? " · 지도보기 누름" : " · 지도보기 단추를 못 찾음") + " · 옵션: " + [...s2.options].map(o => o.value + "=" + o.textContent.trim()).join(", ");
  };

  // ---------- 조각 불러오기 ----------
  const cache = new Map();   // url -> {img: ImageData|null, t}
  function edUrl(ed, tc) {
    const u = TP.urlFn(tc, 1, TP.proj);
    return u ? u.replace(/PT025K_\d{4}/, ed) : null;
  }
  async function loadOne(url) {
    if (cache.has(url)) { const c = cache.get(url); c.t = performance.now(); return c.img; }
    let img = null;
    try {
      const r = await fetch(url, { credentials: "same-origin" });
      if (r.ok) {
        const bmp = await createImageBitmap(await r.blob());
        const cv = new OffscreenCanvas(bmp.width, bmp.height), cx = cv.getContext("2d", { willReadFrequently: true });
        cx.drawImage(bmp, 0, 0); img = cx.getImageData(0, 0, bmp.width, bmp.height);
      }
    } catch (e) { img = null; }
    cache.set(url, { img, t: performance.now() });
    if (cache.size > TP.cfg.cacheMax) {
      const old = [...cache.entries()].sort((a, b) => a[1].t - b[1].t).slice(0, cache.size - TP.cfg.cacheMax);
      old.forEach(([k]) => cache.delete(k));
    }
    TP.nFetched = (TP.nFetched || 0) + 1;
    return img;
  }
  async function loadMany(urls) {
    const todo = [...new Set(urls)].filter(u => u && !cache.has(u));
    let i = 0;
    async function worker() { while (i < todo.length) { const u = todo[i++]; await loadOne(u); await new Promise(r => setTimeout(r, TP.cfg.gap)); } }
    await Promise.all(Array.from({ length: TP.cfg.conc }, worker));
  }
  function tileOf(x, y) {
    const tc = TP.tg.getTileCoordForCoordAndZ([x, y], TP.z);
    return tc;
  }
  function pxAt(ed, x, y) {
    const tc = tileOf(x, y), url = edUrl(ed, tc), c = cache.get(url);
    if (!c || !c.img) return null;
    const ext = TP.tg.getTileCoordExtent(tc), im = c.img;
    const sx = im.width / (ext[2] - ext[0]), sy = im.height / (ext[3] - ext[1]);
    const px = Math.floor((x - ext[0]) * sx), py = Math.floor((ext[3] - y) * sy);
    if (px < 0 || py < 0 || px >= im.width || py >= im.height) return null;
    const k = (py * im.width + px) * 4, d = im.data;
    if (d[k + 3] < 128) return null;   // 투명 = 그 판에 도엽 없음
    return [d[k], d[k + 1], d[k + 2]];
  }

  // ---------- 색 무리 ----------
  // k 검정, w 바탕(흰), r 붉은·주황·분홍, y 노랑, b 파랑, g 초록, n 갈색(등고선), o 그 밖
  TP.cls = function (c) {
    if (!c) return "_";
    const [r, g, b] = c, mx = Math.max(r, g, b), mn = Math.min(r, g, b), s = mx - mn;
    if (mx < 95 && s < 45) return "k";
    if (mn > 205 && s < 28) return "w";
    if (b > r + 25 && b >= g) return "b";
    if (g > r + 12 && g > b + 5) return "g";
    if (r > 150 && g > 140 && b < 120 && Math.abs(r - g) < 45) return "y";
    if (r > 140 && r - g > 45 && r - b > 35) return "r";
    if (r > 110 && r - b > 40 && r - g > 15 && r - g <= 45) return "n";
    return "o";
  };
  TP.sample = function (x, y, ed) { const c = pxAt(ed || TP.edNow, x, y); return { rgb: c, cls: TP.cls(c) }; };

  // 단면 글자(가운데가 선 자리)에서 길 무늬 찾기
  function sigs(prof, res) {
    const n = prof.length, mid = (n - 1) / 2, F1 = TP.cfg.F1 / res, F2 = TP.cfg.F2 / res, TOL = TP.cfg.TOL / res;
    const runs = []; let i = 0;
    while (i < n) { let j = i; while (j < n && prof[j] === prof[i]) j++; runs.push([prof[i], i, j]); i = j; }
    let s1 = false, s2 = false, s3 = false;
    for (let a = 0; a < runs.length; a++) {
      const [ca, ia, ja] = runs[a];
      if (!s1 && ca === "k" && ja - ia >= TP.cfg.K1 && ja - ia <= TP.cfg.K2 + 2) {
        // 테두리 다음부터 속(k·b·g·_ 아닌 것)이 이어지다 다시 k
        let b = a + 1, fs = ja, fe = ja;
        while (b < runs.length && !"kbg_".includes(runs[b][0])) { fe = runs[b][2]; b++; }
        if (b < runs.length && runs[b][0] === "k" && runs[b][2] - runs[b][1] <= TP.cfg.K2 + 2) {
          const w = fe - fs, c = (fs + fe) / 2;
          if (w >= F1 && w <= F2 && Math.abs(c - mid) <= TOL) s1 = true;
        }
      }
      if (!s2 && (ca === "r" || ca === "y")) {
        const w = ja - ia, c = (ia + ja) / 2;
        if (w >= F1 && w <= F2 && Math.abs(c - mid) <= TOL) s2 = true;
      }
      // sig3: 붉은 시가지 칠 속을 지나는 흰 길(양옆이 칠이나 테두리)
      if (!s3 && ca === "w" && a > 0 && a < runs.length - 1 && "krno".includes(runs[a - 1][0]) && "krno".includes(runs[a + 1][0])) {
        const w = ja - ia, c = (ia + ja) / 2;
        if (w >= F1 && w <= F2 && Math.abs(c - mid) <= TOL) s3 = true;
      }
    }
    return [s1, s2, s3];
  }
  function profile(ed, x, y, nx, ny, off) {
    const res = TP.res, W = TP.cfg.W, m = Math.round(W / res);
    let s = "", nv = 0;
    for (let t = -m; t <= m; t++) {
      const d = off + t * res, c = TP.cls(pxAt(ed, x + nx * d, y + ny * d));
      if (c !== "_") nv++; s += c;
    }
    return nv < s.length * 0.8 ? null : s;
  }

  // ---------- 길 불러오기 ----------
  function toMap(lonlat) { return ol.proj.transform(lonlat, "EPSG:4326", TP.proj); }
  TP.segKey = sg => sg.g[0].join(",") + "|" + sg.g[sg.g.length - 1].join(",");
  TP.loadRoads = async function (url) {
    const d = await (await fetch(url || TP.cfg.roadsUrl)).json();
    TP.segs = d.segs.map((sg, i) => {
      const pts = sg.g.map(toMap), samp = [];
      const L = []; let tot = 0;
      for (let k = 1; k < pts.length; k++) { const l = Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]); L.push(l); tot += l; }
      const e = Math.min(TP.cfg.endTrim, tot / 4);
      for (let s = e; s <= tot - e + 1e-6; s += TP.cfg.step) {
        let acc = 0, k = 0; while (k < L.length - 1 && acc + L[k] < s) { acc += L[k]; k++; }
        const f = L[k] ? (s - acc) / L[k] : 0, a = pts[k], b = pts[k + 1];
        const dx = (b[0] - a[0]) / (L[k] || 1), dy = (b[1] - a[1]) / (L[k] || 1);
        samp.push([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, -dy, dx]);
      }
      return { i, key: TP.segKey(sg), n: sg.n, c: sg.c, o: sg.o || null, oh: sg.oh || null, hb: sg.hb || null, len: tot, pts, samp };
    });
    return TP.segs.length + "개 링크, 점 " + TP.segs.reduce((a, s) => a + s.samp.length, 0) + "개";
  };

  // ---------- 겹쳐 보기 ----------
  TP.overlay = function (names, color = "rgba(230,30,30,0.85)") {
    if (TP.vec) TP.map.removeLayer(TP.vec);
    const want = new Set([].concat(names || []));
    const feats = TP.segs.filter(s => !want.size || want.has(s.n)).map(s => new ol.Feature({ geometry: new ol.geom.LineString(s.pts), name: s.n }));
    TP.vec = new ol.layer.Vector({ source: new ol.source.Vector({ features: feats }),
      style: new ol.style.Style({ stroke: new ol.style.Stroke({ color, width: 2, lineDash: [6, 6] }) }) });
    TP.vec.setZIndex && TP.vec.setZIndex(9999);
    TP.map.addLayer(TP.vec);
    if (feats.length) TP.view.fit(TP.vec.getSource().getExtent(), { size: TP.map.getSize(), padding: [40, 40, 40, 40], maxZoom: 99 });
    return feats.length + "개 링크를 겹침";
  };
  TP.fitBox = function (x0, y0, x1, y1) { TP.view.fit([x0, y0, x1, y1], { size: TP.map.getSize() }); };

  // ---------- 재기 ----------
  TP.out = TP.out || {};
  TP.status = () => JSON.stringify(TP.prog || {});
  TP.run = function (ed, opt = {}) {
    const want = opt.names ? new Set(opt.names) : null;
    const segs = TP.segs.filter(s => (!want || want.has(s.n)) && (!opt.only || opt.only(s)));
    // 조각 순서로 정렬해 캐시를 덜 버리게
    segs.sort((a, b) => { const ta = tileOf(...a.samp[0] || a.pts[0]), tb = tileOf(...b.samp[0] || b.pts[0]);
      return (ta[1] - tb[1]) || (ta[2] - tb[2]); });
    TP.edNow = ed; TP.out[ed] = TP.out[ed] || {};
    TP.prog = { ed, done: 0, total: segs.length, fetched: 0, started: Date.now(), running: true };
    (async () => {
      const B = 25;
      for (let a = 0; a < segs.length; a += B) {
        if (TP.stop) { TP.stop = false; break; }
        const batch = segs.slice(a, a + B), urls = [];
        const C = TP.cfg.CTRL, W = TP.cfg.W;
        batch.forEach(s => s.samp.forEach(([x, y, nx, ny]) => {
          [-C - W, -W, 0, W, C + W].forEach(d => urls.push(edUrl(ed, tileOf(x + nx * d, y + ny * d))));
        }));
        await loadMany(urls);
        batch.forEach(s => {
          let nv = 0, n1 = 0, n2 = 0, n3 = 0, na = 0, cv = 0, c1 = 0, c2 = 0, c3 = 0, ca = 0;
          s.samp.forEach(([x, y, nx, ny]) => {
            const p = profile(ed, x, y, nx, ny, 0);
            if (p) { nv++; const q = sigs(p, TP.res); n1 += q[0]; n2 += q[1]; n3 += q[2]; na += q[0] || q[1] || q[2]; }
            [-C, C].forEach(off => { const pc = profile(ed, x, y, nx, ny, off);
              if (pc) { cv++; const r = sigs(pc, TP.res); c1 += r[0]; c2 += r[1]; c3 += r[2]; ca += r[0] || r[1] || r[2]; } });
          });
          TP.out[ed][s.key] = [s.samp.length, nv, n1, n2, n3, na, cv, c1, c2, c3, ca];
        });
        TP.prog.done = Math.min(segs.length, a + B); TP.prog.fetched = TP.nFetched || 0;
      }
      TP.prog.running = false; TP.prog.ms = Date.now() - TP.prog.started;
    })();
    return "시작: " + ed + ", 링크 " + segs.length + "개";
  };
  // 결과 꺼내기: {키: [점, 읽힌 점, sig1, sig2, sig3, 셋 중 하나, 대조 읽힌 단면, 대조 sig1, sig2, sig3, 셋 중 하나]}
  TP.dump = function (ed, from = 0, to = 1e9) {
    const ks = Object.keys(TP.out[ed] || {}).sort().slice(from, to), o = {};
    ks.forEach(k => o[k] = TP.out[ed][k]);
    return JSON.stringify({ ed, z: TP.z, res: TP.res, cfg: TP.cfg, n: Object.keys(TP.out[ed] || {}).length, from, rows: o });
  };
  // 한 링크의 단면 글자를 보기(문턱 맞출 때)
  TP.profiles = function (name, ed, k = 5) {
    const s = TP.segs.find(s => s.n === name); if (!s) return "없음";
    return s.samp.slice(0, k).map(([x, y, nx, ny]) => { const p = profile(ed, x, y, nx, ny, 0); return (p || "(빈 곳)") + " " + (p ? sigs(p, TP.res).map(Number).join("") : ""); }).join("\n");
  };
  TP._sigs = sigs;
})();
