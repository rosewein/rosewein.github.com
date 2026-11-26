// 궁궐 레이어 시안 코드(2026-11-26, 옛 지도 갈래). 빌드에는 들어가지 않는다.
// 넣을 때: template.html의 drawJoseon() 앞에 이 함수를 두고, 그룹을 const gJoseon 줄 다음에
//   const gPalace = root.insert("g", () => gNew.node()), gPalaceTop = root.append("g");
// 로 만들고, render()의 drawOld(); 다음과 확대(zoom) 처리의 sizeJoseon(); 다음에 drawPalace();를 부른다.
// build.py DATA에 "palaces": data/palace_geo.json, 색 변수: 밝은 --palace #22d65a / --palace-2 #0f7a33, 어두운 #45ff7d / #b9ffcf (이지가 형광초록으로 정함)
  // ── 시안: 궁궐 레이어 ──────────────────────────────────────────
  const PAL = DATA.palaces;
  // 궁마다 [처음 해, 끝 해, 상태, 한 줄 설명]. 상태: 궁(쓰임) / 훼손(헐리거나 다른 쓰임) / 복원
  const PAL_PH = {
    gbg: [[1868, 1914, "궁", "법궁 · 1896년 임금이 떠난 뒤 비어 있음"], [1915, 1989, "훼손", "공진회(1915) · 조선총독부 청사(1926–1996)"], [1990, 2100, "복원", "복원 사업(1990–)"]],
    cdg: [[1610, 1916, "궁", "1907년부터 순종 거처"], [1917, 1919, "훼손", "내전 큰불(1917)"], [1920, 2100, "궁", "내전 다시 지음(1920)"]],
    cgg: [[1834, 1908, "궁", ""], [1909, 1983, "훼손", "동·식물원 · 창경원(1911–1983)"], [1984, 2100, "복원", "창경궁으로 되돌림(1983)"]],
    ghg: [[1832, 1864, "궁", ""], [1865, 1987, "훼손", "전각 대부분 헐림(1865–) · 경성중학교(1910)"], [1988, 2100, "복원", "흥화문 되옮김(1988) · 일부 복원"]],
    gug: [[1897, 1932, "궁", "대한제국 황궁 · 1907년 덕수궁"], [1933, 2006, "훼손", "공원으로 엶(1933)"], [2007, 2100, "복원", "복원 사업(2007–)"]],
  };
  const palPhase = (id, y) => (PAL_PH[id] || []).find(p => y >= p[0] && y <= p[1]);
  function drawPalace() {
    gPalace.selectAll("*").remove(); gPalaceTop.selectAll("*").remove();
    if (!PAL) return;
    const y = year < 1899 ? 1898 : year, k = kNow;
    let defs = svg.select("defs"); if (defs.empty()) defs = svg.append("defs");
    if (defs.select("#palHatch").empty()) {
      const pt = defs.append("pattern").attr("id", "palHatch").attr("width", 6).attr("height", 6).attr("patternUnits", "userSpaceOnUse").attr("patternTransform", "rotate(45)");
      pt.append("rect").attr("width", 6).attr("height", 6).attr("fill", "var(--palace)").attr("fill-opacity", .10);
      pt.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 6).attr("stroke", "var(--palace)").attr("stroke-width", 2).attr("stroke-opacity", .55);
      defs.append("marker").attr("id", "palArrow").attr("viewBox", "0 0 10 10").attr("refX", 9).attr("refY", 5).attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto-start-reverse")
        .append("path").attr("d", "M0,0L10,5L0,10z").attr("fill", "var(--palace-2)");
    }
    PAL.areas.forEach(a => {
      const ph = palPhase(a.id, y); if (!ph) return;
      gPalace.append("path").datum(a.geom).attr("d", path)
        .attr("fill", ph[2] === "훼손" ? "url(#palHatch)" : "var(--palace)").attr("fill-opacity", ph[2] === "궁" ? .42 : ph[2] === "복원" ? .18 : 1)
        .attr("stroke", "var(--palace-2)").attr("stroke-width", 1.3 / k).attr("stroke-dasharray", ph[2] === "복원" ? `${4 / k} ${3 / k}` : null);
      const c = projection(a.c);
      const t = gPalaceTop.append("text").attr("x", c[0]).attr("y", c[1]).attr("text-anchor", "middle").attr("font-size", 11.5 / k)
        .attr("font-weight", 600).attr("fill", "var(--palace-2)").attr("paint-order", "stroke").attr("stroke", "var(--paper)").attr("stroke-width", 3 / k);
      t.append("tspan").text(a.name.replace(/\(.*\)/, ""));
      if (ph[3]) t.append("tspan").attr("x", c[0]).attr("dy", 13 / k).attr("font-size", 9.5 / k).attr("font-weight", 400).text(ph[3]);
    });
    // 옮겨 간 건물: 옮긴 해부터 6년 동안 화살표
    PAL.moves.filter(m => m.to && y >= m.y && y <= m.y + 6).forEach(m => {
      const a = projection(m.from.p), b = projection(m.to.p);
      gPalaceTop.append("path").attr("d", `M${a[0]},${a[1]}L${b[0]},${b[1]}`).attr("fill", "none").attr("stroke", "var(--palace-2)")
        .attr("stroke-width", 1.6 / k).attr("stroke-dasharray", `${5 / k} ${3 / k}`).attr("marker-end", "url(#palArrow)");
      gPalaceTop.append("circle").attr("cx", a[0]).attr("cy", a[1]).attr("r", 3 / k).attr("fill", "var(--paper)").attr("stroke", "var(--palace-2)").attr("stroke-width", 1.4 / k);
      gPalaceTop.append("text").attr("x", (a[0] + b[0]) / 2).attr("y", (a[1] + b[1]) / 2 - 5 / k).attr("text-anchor", "middle").attr("font-size", 10 / k)
        .attr("fill", "var(--palace-2)").attr("paint-order", "stroke").attr("stroke", "var(--paper)").attr("stroke-width", 3 / k).text(`${m.y} ${m.what}`);
    });
    // 임금 거처
    const r = PAL.residence.find(r => y >= +r.from.slice(0, 4) && y < +r.to.slice(0, 4));
    if (r) {
      const p = projection(r.at.p);
      gPalaceTop.append("path").attr("d", d3.symbol(d3.symbolStar, 150 / (k * k))()).attr("transform", `translate(${p[0]},${p[1] - 22 / k})`)
        .attr("fill", "var(--palace)").attr("stroke", "var(--paper)").attr("stroke-width", 1.2 / k);
      gPalaceTop.append("text").attr("x", p[0] + 9 / k).attr("y", p[1] - 18 / k).attr("font-size", 10 / k).attr("font-weight", 600).attr("fill", "var(--palace-2)")
        .attr("paint-order", "stroke").attr("stroke", "var(--paper)").attr("stroke-width", 3 / k).text(`${r.who}(${(r.title_y && r.title_y[String(y)]) || r.title}) 거처`);
    }
  }
