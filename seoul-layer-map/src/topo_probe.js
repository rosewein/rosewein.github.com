// 큰 도로 갈래(roads): 국토정보맵 「역사지도 → 종이지도」의 옛 1:25,000 지형도에서
// 지금 큰 도로 링크 자리에 길이 그려져 있는지 판마다 잰다.
//
// 쓰는 곳: 이지의 크롬에서 https://map.ngii.go.kr/ms/map/NlipMap.do 를 열고 왼쪽 「역사지도」 → 「종이지도」,
// 지형도(25K)와 판을 고르고 「지도보기」를 한 번 눌러 지형도를 띄운 뒤 이 파일 내용을 그 탭의 자바스크립트로 넣는다
// (지형도 조각은 작업 공간에서 막혀 있고 같은 출처인 그 탭 안에서만 불러진다).
//
//   TP.init()                         지도·지형도 레이어(oldMap)·타일 격자를 찾음
//   await TP.loadRoads()              GitHub roads 브랜치의 data/majorroads.json을 받아 25m 점으로 나눔
//   await TP.run(판, 링크들)          판 하나를 잼(링크 생략 시 전부). TP.status()로 진행을 봄
//   TP.codes()                        링크마다 판별 있음·없음을 한 글자로(majorroads.json 순서)
//   await TP.show(판, [이름], [x, y]) 화면을 그 판으로 바꾸고 길을 판의 자리에 맞춰 겹침(눈으로 볼 때)
//   await TP.offset(판, x, y)         판을 지금 좌표에 맞추는 데 필요한 평행이동을 찾음(맞춤 확인용)
//
// 2026-11-27에 맞춘 것(옛 지형도 채팅):
// - 조각 레이어 이름은 「oldMap」, 좌표계 EPSG:5179, 가장 큰 확대 단계 10(2.117m/px). 판은 조각 주소의
//   PT025K_1980 부분만 바꿔 부르면 된다.
// - 1960–1990년대 판은 지금 좌표보다 동쪽으로 약 184m, 남쪽으로 약 311m 밀려 있다. 옛 지도가 베셀(동경) 측지계로
//   그려진 것을 좌표 변환 없이 세계측지계 자리에 놓은 만큼이다(pyproj로 계산한 차이 +184·−311m, 큰 도로 점이
//   붉은 길 위에 가장 많이 떨어지는 평행이동을 찾으면 1990년대 판 +180·−320, 1980년대 +180·−310, 1970년대 +190·−290).
//   2000년대 판은 세계측지계로 맞음(찾은 이동 −10·0). 그래서 판마다 dx·dy를 더해 읽는다.
// - 판마다 길 색이 다르다. 1970–1990년대 판은 큰길이 붉은 띠(시가지 분홍 칠과 r/g 비율로 가름), 고속도로는
//   어두운 붉은 갈색 띠. 2000년대 판부터는 수치지도 식으로 일반 도로가 주황, 고속도로가 파랑(2000)·하늘색(2015).
//   1960년대 판은 갈색 두 줄이고 서울 일부 도엽만 있어 아직 재지 않는다.
// - 길 무늬: 그 판의 길 색 띠(너비 6–60m)나, 양옆이 어두운 선·분홍 칠·길 색인 흰 띠(4–30m)가 선 가운데에서
//   22m 안에 있으면 그 점에 길이 있다고 본다. 같은 단면을 선에서 110m 옆으로 옮긴 두 줄(대조)도 센다.
(function () {
  const TP = window.TP = window.TP || {};
  TP.cfg = Object.assign({
    roadsUrl: "https://raw.githubusercontent.com/rosewein/rosewein.github.com/roads/seoul-layer-map/data/majorroads.json",
    targetRes: 2.1, step: 25, endTrim: 15, W: 45, TOL: 22, CTRL: 110, conc: 3, gap: 60, cacheMax: 600,
    // 있음: 길 무늬 점 비율 ≥ ON이고 대조보다 DIFF 넘게 많음. 없음: 비율 ≤ OFF
    ON: 0.6, DIFF: 0.3, OFF: 0.3,
  }, TP.cfg || {});
  // 판마다 평행이동(m)과 길 색 무리
  TP.ED = {
    PT025K_1960: { dx: 184, dy: -311, band: "D" }, PT025K_1970: { dx: 184, dy: -311, band: "R" },
    PT025K_1980: { dx: 184, dy: -311, band: "R" }, PT025K_1990: { dx: 184, dy: -311, band: "R" },
    PT025K_2000: { dx: 0, dy: 0, band: "OX" }, PT025K_2011: { dx: 0, dy: 0, band: "OX" },
    PT025K_2013: { dx: 0, dy: 0, band: "OX" }, PT025K_2015: { dx: 0, dy: 0, band: "OX" },
  };
  TP.EDS = ["PT025K_1970", "PT025K_1980", "PT025K_1990", "PT025K_2000"];

  function allLayers(coll, out = []) { coll.getArray().forEach(l => { if (l.getLayers) allLayers(l.getLayers(), out); else out.push(l); }); return out; }
  TP.init = function () {
    TP.map = window.map; if (!TP.map || !window.ol) return "window.map 또는 window.ol이 없음";
    TP.view = TP.map.getView(); TP.proj = TP.view.getProjection();
    TP.layer = allLayers(TP.map.getLayers()).find(l => l.get && l.get("name") === "oldMap");
    if (!TP.layer) return "oldMap 레이어가 없음(종이지도를 한 번 띄운 뒤 다시)";
    TP.src = TP.layer.getSource(); TP.tg = TP.src.getTileGrid(); TP.urlFn = TP.src.getTileUrlFunction();
    const res = TP.tg.getResolutions();
    TP.z = res.reduce((bi, r, i) => Math.abs(r - TP.cfg.targetRes) < Math.abs(res[bi] - TP.cfg.targetRes) ? i : bi, 0);
    TP.res = res[TP.z];
    return JSON.stringify({ proj: TP.proj.getCode(), z: TP.z, res: TP.res });
  };

  // ---------- 조각 ----------
  const cache = new Map();
  const edUrl = (ed, tc) => { const u = TP.urlFn(tc, 1, TP.proj); return u ? u.replace(/PT025K_\d{4}/, ed) : null; };
  const tileOf = (x, y) => TP.tg.getTileCoordForCoordAndZ([x, y], TP.z);
  async function loadOne(url) {
    if (cache.has(url)) { const c = cache.get(url); c.t = performance.now(); return c.img; }
    let img = null;
    try {
      const r = await fetch(url, { credentials: "same-origin" });
      if (r.ok) {
        const bmp = await createImageBitmap(await r.blob());
        const cv = new OffscreenCanvas(bmp.width, bmp.height), cx = cv.getContext("2d", { willReadFrequently: true });
        cx.drawImage(bmp, 0, 0); img = cx.getImageData(0, 0, bmp.width, bmp.height);
      } else TP.nBad = (TP.nBad || 0) + 1;
    } catch (e) { TP.lastErr = String(e); }
    cache.set(url, { img, t: performance.now() });
    if (cache.size > TP.cfg.cacheMax) [...cache.entries()].sort((a, b) => a[1].t - b[1].t).slice(0, cache.size - TP.cfg.cacheMax).forEach(([k]) => cache.delete(k));
    TP.nFetched = (TP.nFetched || 0) + 1;
    return img;
  }
  async function loadMany(urls) {
    const todo = [...new Set(urls)].filter(u => u && !cache.has(u)); let i = 0;
    async function worker() { while (i < todo.length) { const u = todo[i++]; await loadOne(u); await new Promise(r => setTimeout(r, TP.cfg.gap)); } }
    await Promise.all(Array.from({ length: TP.cfg.conc }, worker));
  }
  function pxAt(ed, x, y) {
    const tc = tileOf(x, y), c = cache.get(edUrl(ed, tc));
    if (!c || !c.img) return null;
    const ext = TP.tg.getTileCoordExtent(tc), im = c.img;
    const px = Math.floor((x - ext[0]) * im.width / (ext[2] - ext[0])), py = Math.floor((ext[3] - y) * im.height / (ext[3] - ext[1]));
    if (px < 0 || py < 0 || px >= im.width || py >= im.height) return null;
    const k = (py * im.width + px) * 4, d = im.data;
    return d[k + 3] < 128 ? null : [d[k], d[k + 1], d[k + 2]];
  }

  // ---------- 색 무리 ----------
  // R 붉은 길(옛 판, 붉은 갈색 고속도로 포함) O 주황 길 X 파랑·하늘색 고속도로(2000년대 판부터) D 어두운 선
  // W 바탕 B 물 G 초록 P 분홍 시가지 칠 o 그 밖 _ 빈 곳
  TP.cls = function (c) {
    if (!c) return "_";
    const [r, g, b] = c, mx = Math.max(r, g, b), mn = Math.min(r, g, b), s = mx - mn;
    if (r > 120 && r / (g + 1) > 2.05 && r / (b + 1) > 2.05) return "R";
    if (r > 210 && g > 135 && g < 190 && b < 140 && r - b > 90 && r - g > 45) return "O";
    if (r < 120 && b > 150 && b - r > 90 && g > 95) return "X";
    if (mx < 135 && s < 110) return "D";
    if (mn > 195) return "W";
    if (b > r + 20 && b >= g) return "B";
    if (g > r + 10 && g > b) return "G";
    if (r > 160 && r - g >= 40 && r - g <= 110) return "P";
    return "o";
  };
  function sigs(prof, band) {
    const res = TP.res, n = prof.length, mid = (n - 1) / 2, TOL = TP.cfg.TOL / res;
    const q = prof.replace(new RegExp("[" + band + "]", "g"), "#");
    const runs = []; let i = 0; while (i < n) { let j = i; while (j < n && q[j] === q[i]) j++; runs.push([q[i], i, j]); i = j; }
    let sb = false, ss = false;
    for (let a = 0; a < runs.length; a++) {
      const [c, s0, e0] = runs[a], w = (e0 - s0) * res;
      if (Math.abs((s0 + e0) / 2 - mid) > TOL) continue;
      if (c === "#" && w >= 6 && w <= 60) sb = true;
      if (c === "W" && w >= 4 && w <= 30 && a > 0 && a < runs.length - 1 && "DP#".includes(runs[a - 1][0]) && "DP#".includes(runs[a + 1][0])) ss = true;
    }
    return [sb, ss];
  }
  function profile(ed, x, y, nx, ny, off) {
    const e = TP.ED[ed], res = TP.res, m = Math.round(TP.cfg.W / res); let s = "", nv = 0;
    for (let t = -m; t <= m; t++) { const d = off + t * res, c = TP.cls(pxAt(ed, x + e.dx + nx * d, y + e.dy + ny * d)); if (c !== "_") nv++; s += c; }
    return nv < s.length * 0.8 ? null : s;
  }

  // ---------- 길 ----------
  TP.segKey = sg => sg.g[0].join(",") + "|" + sg.g[sg.g.length - 1].join(",");
  TP.loadRoads = async function (url) {
    const d = await (await fetch(url || TP.cfg.roadsUrl)).json();
    TP.segs = d.segs.map((sg, i) => {
      const pts = sg.g.map(p => ol.proj.transform(p, "EPSG:4326", TP.proj)), samp = [], L = []; let tot = 0;
      for (let k = 1; k < pts.length; k++) { const l = Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]); L.push(l); tot += l; }
      const e = Math.min(TP.cfg.endTrim, tot / 4);
      for (let s = e; s <= tot - e + 1e-6; s += TP.cfg.step) {
        let acc = 0, k = 0; while (k < L.length - 1 && acc + L[k] < s) { acc += L[k]; k++; }
        const f = L[k] ? (s - acc) / L[k] : 0, a = pts[k], b = pts[k + 1];
        samp.push([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, -(b[1] - a[1]) / (L[k] || 1), (b[0] - a[0]) / (L[k] || 1)]);
      }
      return { i, key: TP.segKey(sg), n: sg.n, c: sg.c, o: sg.o || null, len: tot, pts, samp };
    });
    return TP.segs.length + "개 링크, 점 " + TP.segs.reduce((a, s) => a + s.samp.length, 0) + "개";
  };

  // ---------- 재기 ----------
  TP.out = TP.out || {};
  TP.status = () => JSON.stringify(TP.prog || {});
  // 결과: TP.out[판][키] = [점, 읽힌 점, 띠, 흰 띠, 둘 중 하나, 대조 읽힌 단면, 대조 띠, 대조 흰 띠, 대조 둘 중 하나]
  TP.run = async function (ed, segs) {
    const e = TP.ED[ed], C = TP.cfg.CTRL, W = TP.cfg.W; TP.out[ed] = TP.out[ed] || {};
    segs = (segs || TP.segs).filter(s => s.samp.length);
    segs.sort((a, b) => { const ta = tileOf(a.samp[0][0], a.samp[0][1]), tb = tileOf(b.samp[0][0], b.samp[0][1]); return (ta[1] - tb[1]) || (ta[2] - tb[2]); });
    TP.prog = { ed, done: 0, total: segs.length, running: true, t0: Date.now() };
    for (let a = 0; a < segs.length; a += 20) {
      if (TP.stop) { TP.stop = false; break; }
      const batch = segs.slice(a, a + 20), urls = [];
      batch.forEach(s => s.samp.forEach(([x, y, nx, ny]) => [-C - W, -W, 0, W, C + W].forEach(d => urls.push(edUrl(ed, tileOf(x + e.dx + nx * d, y + e.dy + ny * d))))));
      await loadMany(urls);
      batch.forEach(s => {
        let nv = 0, nb = 0, ns = 0, na = 0, cv = 0, cb = 0, cs = 0, ca = 0;
        s.samp.forEach(([x, y, nx, ny]) => {
          const p = profile(ed, x, y, nx, ny, 0);
          if (p) { nv++; const q = sigs(p, e.band); nb += q[0]; ns += q[1]; na += q[0] || q[1]; }
          [-C, C].forEach(off => { const pc = profile(ed, x, y, nx, ny, off); if (pc) { cv++; const r = sigs(pc, e.band); cb += r[0]; cs += r[1]; ca += r[0] || r[1]; } });
        });
        TP.out[ed][s.key] = [s.samp.length, nv, nb, ns, na, cv, cb, cs, ca];
      });
      TP.prog.done = Math.min(segs.length, a + 20);
    }
    TP.prog.running = false; TP.prog.ms = Date.now() - TP.prog.t0; return TP.prog;
  };
  // 판 하나의 상태: 1 있음, 0 없음, 2 모름
  TP.state = function (r) {
    if (!r || r[1] < Math.max(2, 0.6 * r[0])) return 2;
    const p = r[4] / r[1], c = r[5] ? r[8] / r[5] : 0;
    return p >= TP.cfg.ON && p - c >= TP.cfg.DIFF ? 1 : p <= TP.cfg.OFF ? 0 : 2;
  };
  // 링크마다 TP.EDS 판 상태 넷을 한 글자로(3진수 81가지). majorroads.json 링크 순서.
  // 크롬 확장의 결과 창은 =·&·? 같은 글자가 든 출력을 막고 한 번에 1,000자 남짓만 보여 주므로, 영숫자와 한글 19자만 쓰고 950자씩 꺼낸다
  TP.ALPH = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz가나다라마바사아자차카타파하거너더러머";
  TP.codes = function (from = 0, to = 1e9) {
    return TP.segs.slice(from, to).map(s => TP.ALPH[TP.EDS.reduce((acc, ed, i) => acc + TP.state(TP.out[ed] && TP.out[ed][s.key]) * 3 ** i, 0)]).join("");
  };

  // ---------- 눈으로 보기·맞춤 확인 ----------
  TP.setEdition = function (code) {
    const s2 = document.querySelector("select#old_select2"); s2.value = code; s2.dispatchEvent(new Event("change", { bubbles: true }));
    const b = [...document.querySelectorAll("button")].filter(b => /지도\s*보기/.test(b.textContent) && b.offsetParent && b.className !== "on");
    if (b[0]) b[0].click();
    return code + (b[0] ? " 누름" : " 단추 없음");
  };
  // 새 벡터 레이어는 이 누리집 지도에서 그려지지 않아, 이미 있는 「vectorLayer」에 선을 더한다
  TP.show = async function (ed, names, center, res) {
    TP.setEdition(ed); await new Promise(r => setTimeout(r, 2500));
    const e = TP.ED[ed]; if (center) { TP.view.setCenter([center[0] + e.dx, center[1] + e.dy]); TP.view.setResolution(res || 2.1167); }
    const src = TP.map.getLayers().getArray().find(l => l.get("name") === "vectorLayer").getSource();
    const st = new ol.style.Style({ stroke: new ol.style.Stroke({ color: "rgba(0,90,255,0.95)", width: 1.5, lineDash: [6, 8] }) });
    const want = new Set([].concat(names || []));
    const fs = TP.segs.filter(s => want.has(s.n)).map(s => { const f = new ol.Feature({ geometry: new ol.geom.LineString(s.pts.map(p => [p[0] + e.dx, p[1] + e.dy])) }); f.setStyle(st); return f; });
    src.addFeatures(fs); await new Promise(r => setTimeout(r, 2500)); return ed + " " + fs.length;
  };
  // 큰 도로 점이 그 판의 길 색 위에 떨어지는 비율이 가장 큰 평행이동(m)을 찾는다
  TP.offset = async function (ed, cx, cy, R = 1500, S = 400, step = 10) {
    const pts = []; TP.segs.forEach(s => s.samp.forEach(p => { if (Math.abs(p[0] - cx) < R && Math.abs(p[1] - cy) < R) pts.push(p); }));
    const urls = []; for (let x = cx - R - S; x <= cx + R + S + 541; x += 500) for (let y = cy - R - S; y <= cy + R + S + 541; y += 500) urls.push(edUrl(ed, tileOf(x, y)));
    await loadMany(urls);
    const band = new RegExp("[" + TP.ED[ed].band + "]");
    let best = [-1, 0, 0], at0 = 0;
    for (let dx = -S; dx <= S; dx += step) for (let dy = -S; dy <= S; dy += step) {
      let n = 0, v = 0; for (const p of pts) { const c = pxAt(ed, p[0] + dx, p[1] + dy); if (c) { v++; if (band.test(TP.cls(c))) n++; } }
      const f = v ? n / v : 0; if (!dx && !dy) at0 = f; if (f > best[0]) best = [f, dx, dy];
    }
    return { ed, n: pts.length, best, at0 };
  };
  TP._sigs = sigs; TP._px = pxAt; TP._load = loadMany; TP._edUrl = edUrl; TP._tileOf = tileOf; TP._profile = profile;
})();
