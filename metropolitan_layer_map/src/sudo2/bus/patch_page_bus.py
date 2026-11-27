"""index.html에 광역버스 레이어를 붙인다(한 번만 돌림)."""
import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import PAGE_HTML  # noqa: E402
p=PAGE_HTML; s=open(p,encoding='utf-8').read()
def rep(a,b,n=1):
    global s
    assert s.count(a)==n,(a[:70],s.count(a)); s=s.replace(a,b)
# 색: 붉은 한 색의 밝기 4단계
rep("--js:#2a7f72;--hwc:#59615b;--hwf:#fbfcf8;","--js:#2a7f72;--hwc:#59615b;--hwf:#fbfcf8;--bus1:#e9a89f;--bus2:#d46d5f;--bus3:#b53b2d;--bus4:#7f2218;")
rep("--js:#6cc7b8;--hwc:#a3aea6;--hwf:#18201c;color-scheme:dark}","--js:#6cc7b8;--hwc:#a3aea6;--hwf:#18201c;--bus1:#6a312b;--bus2:#a04a3f;--bus3:#de7262;--bus4:#ffa799;color-scheme:dark}",2)
rep(".card li{padding:3px 0;border-top:1px dashed var(--rule)}",".card li{padding:3px 0;border-top:1px dashed var(--rule)}\n.card a.bk{color:var(--ink);font-weight:600}\n.card li.hi a.bk{color:var(--bus3)}")
rep("gHW=root.append('g'),g38","gHW=root.append('g'),gBus=root.append('g'),g38")
rep("arb:true,js:true};","arb:true,js:true,bus:true};\nlet busHi=null;")
rep('<span class="chip none">광역버스 <em>자료 없음</em></span>','<button class="chip" data-l="bus" aria-pressed="true"><i style="background:var(--bus3);height:4px"></i>광역버스 · 2023년 9월 경기 노선</button>')
rep('  <span><i class="sw" style="background:var(--nb);border-color:var(--rule)"></i>이웃 시·도와 북한(지금 경계)</span>',
'''  <span><i class="sw" style="background:none;border:0;border-top:1.5px solid var(--bus1);height:0;width:18px"></i><i class="sw" style="background:none;border:0;border-top:2.5px solid var(--bus2);height:0;width:18px"></i><i class="sw" style="background:none;border:0;border-top:3.5px solid var(--bus3);height:0;width:18px"></i><i class="sw" style="background:none;border:0;border-top:4.5px solid var(--bus4);height:0;width:18px"></i>광역버스가 지나는 길(1–2·3–7·8–19·20개 넘는 노선, 2023년부터) — 서울로 들어가는 방향만, 정류소를 도로 위로 이은 근사선</span>
  <span><i class="sw" style="background:var(--nb);border-color:var(--rule)"></i>이웃 시·도와 북한(지금 경계)</span>''')
rep("지도를 누르면 시·군·구, 역, 택지 지구, 고속도로·자동차전용도로의 내력이 나옵니다.","지도를 누르면 시·군·구, 역, 택지 지구, 고속도로·자동차전용도로의 내력과 그 길을 지나는 광역버스 노선이 나옵니다.")
# 그리기
rep("  g38.append('path').attr('class','l38')",
"""  if(D.bus){const B=D.bus;
   gBus.selectAll('path.bl').data(B.ch).join('path').attr('class','bl').attr('fill','none').attr('stroke',c=>busCol(c.r.length)).attr('stroke-width',c=>busW(c.r.length)).attr('stroke-linecap','round').attr('stroke-linejoin','round').attr('vector-effect','non-scaling-stroke').attr('pointer-events','none');
   gBus.selectAll('circle').data(B.st).join('circle').attr('fill','var(--bg)').attr('stroke','var(--bus3)').attr('stroke-width',1.1).attr('vector-effect','non-scaling-stroke').attr('pointer-events','none');
   gBus.selectAll('path.bh').data(B.ch).join('path').attr('class','bh').attr('fill','none').attr('stroke','transparent').attr('stroke-width',10).attr('vector-effect','non-scaling-stroke').style('cursor','pointer')
     .on('click',(e,c)=>{e.stopPropagation();showBus(c)});}
  g38.append('path').attr('class','l38')""")
rep("  gHW.selectAll('path').attr('d',e=>line(e.p));\n","  gHW.selectAll('path').attr('d',e=>line(e.p));\n  gBus.selectAll('path').attr('d',e=>line(e.p));\n  gBus.selectAll('circle').attr('cx',p=>proj(p)[0]).attr('cy',p=>proj(p)[1]);\n")
rep("  gR0.style('display',on.r0?null:'none');\n","  gBus.style('display',on.bus&&Y>=2023?null:'none');\n  gR0.style('display',on.r0?null:'none');\n")
rep("  gJs.selectAll('circle').attr('r',Math.min(2.6,1.4+0.25*k)/k);","  gJs.selectAll('circle').attr('r',Math.min(2.6,1.4+0.25*k)/k);\n  gBus.selectAll('circle').attr('r',Math.min(2.4,1.2+0.2*k)/k);")
rep("function closeCard(){$('card').classList.remove('on');sel=null}","function closeCard(){$('card').classList.remove('on');sel=null;if(busHi!=null)hiBus(null)}")
rep("function showJsPt(p){",
"""// 광역버스: 같은 노선 묶음이 지나는 도로 구간마다 한 선. 굵기·밝기는 노선 수
function busW(n){return 0.55+0.62*Math.sqrt(n)}
function busCol(n){return n>=20?'var(--bus4)':n>=8?'var(--bus3)':n>=3?'var(--bus2)':'var(--bus1)'}
function hiBus(ri){
  busHi=ri;
  gBus.selectAll('path.bl').attr('stroke-opacity',c=>ri==null||c.r.includes(ri)?1:.15).attr('stroke',c=>ri!=null&&c.r.includes(ri)?'var(--bus4)':busCol(c.r.length));
  gBus.selectAll('circle').style('opacity',(p,i)=>ri==null||i===ri?1:.15);
  document.querySelectorAll('#cardBody li[data-ri]').forEach(el=>el.classList.toggle('hi',+el.dataset.ri===ri));
}
function showBus(c){
  sel={t:'b',v:c};const B=D.bus;
  const rs=c.r.map(i=>[i,B.rt[i]]).sort((a,b)=>a[1].n.localeCompare(b[1].n,'ko',{numeric:true}));
  const li=rs.map(([i,r])=>`<li data-ri="${i}"><a href="#" class="bk" data-ri="${i}">${esc(r.n)}</a> <small>${esc(r.o)} → ${esc(r.e)}${r.v&&r.v.length?' · 같이 센 변형 '+esc(r.v.join(', ')):''}</small></li>`).join('');
  card(`<h3>광역버스 ${c.r.length}개 노선이 지나는 길</h3><small>2023년 9월 경기도 버스운송관리시스템 노선 · 서울로 들어가는 방향만 · 번호를 누르면 그 노선만 진하게 보입니다</small><ul>${li}</ul><small>경로는 정류소 순서를 지금 OSM 도로 위 최단 경로로 이은 근사선이라 실제 운행 경로와 다를 수 있습니다. 출발 정류소는 서울에서 가장 먼 정류소로 잡았습니다. 인천·서울 면허 노선은 아직 넣지 않았습니다.</small>`);
  document.querySelectorAll('#cardBody a.bk').forEach(a=>a.onclick=ev=>{ev.preventDefault();ev.stopPropagation();const i=+a.dataset.ri;hiBus(busHi===i?null:i)});
  hiBus(null);
}
function showJsPt(p){""")
# 범위 표
rep("    ['광역버스','n','없음','—','확인 못 함','지금 노선과 옛 노선 모두'],",
"""    ['광역버스','p','2023년 9월',`경기도 면허 노선 가운데 서울로 들어가는 M·G·P·네 자리 번호 ${(D.bus||{rt:[]}).rt.length}개(같은 번호·같은 출발지 변형은 하나로)를 서울로 들어가는 방향만 그림. 2023년부터 보임. 같은 도로를 지나는 노선 수로 굵기를 정함`,'노선·정류소 순서: 경기도 버스운송관리시스템(BMS) 「노선 경유정류소」「노선 정보 검증」(2023-09, 경기데이터드림·공공데이터포털, 이용허락범위 제한 없음). 정류소 좌표: 국토교통부 「전국 버스정류장 위치정보」(2026-11-09, 이용허락범위 제한 없음). 경로: © OpenStreetMap contributors(ODbL) 도로 위 최단 경로','노선이 생긴 해(옛 노선)를 아직 찾지 못해 2023년 모습만 있음. 인천·서울 면허 광역버스(서울 9401·9404·9408·9409·9707·9711 등)는 아직 없음. 2023년 9월 뒤 새로 생기거나 바뀐 노선은 빠짐'],""")
# 출처
rep("대로가 흐려지는 시점(1911년 도로규칙, 1938년 조선도로령) — 국가기록원 <a href=\"https://theme.archives.go.kr/next/koreaOfRecord/nationalHighway.do\">「추억의 일반국도 국도」</a>.</p>",
"대로가 흐려지는 시점(1911년 도로규칙, 1938년 조선도로령) — 국가기록원 <a href=\"https://theme.archives.go.kr/next/koreaOfRecord/nationalHighway.do\">「추억의 일반국도 국도」</a>. 광역버스 노선·정류소 순서 — 경기도 버스운송관리시스템 「노선 경유정류소」「노선 정보 검증」(2023-09, <a href=\"https://www.data.go.kr/data/15124068/fileData.do\">공공데이터포털</a>·경기데이터드림, 이용허락범위 제한 없음), 정류소 좌표 — 국토교통부 <a href=\"https://www.data.go.kr/data/15067528/fileData.do\">「전국 버스정류장 위치정보」</a>(2026-11-09, 이용허락범위 제한 없음), 경로 — © OpenStreetMap contributors(ODbL) 도로 위 최단 경로.</p>")
open(p,'w',encoding='utf-8').write(s); print('patched')
