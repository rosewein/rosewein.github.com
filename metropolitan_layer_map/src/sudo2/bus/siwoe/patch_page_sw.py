"""시외버스(신문 기사로 확인한 해만) 레이어를 페이지에 더한다(한 번만 돌림)"""
import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import PAGE_HTML  # noqa: E402
p=PAGE_HTML; s=open(p,encoding='utf-8').read()
def rep(a,b,n=1):
    global s
    assert s.count(a)==n,(a[:80],s.count(a)); s=s.replace(a,b)
rep("gBus=root.append('g'),","gBus=root.append('g'),gSw=root.append('g'),")
rep("js:true,bus:true};","js:true,bus:true,sw:true};")
rep('광역버스 · 생긴 해부터 없어진 해까지</button>',
    '광역버스 · 생긴 해부터 없어진 해까지</button>\n  <button class="chip" data-l="sw" aria-pressed="true"><i style="background:none;border-radius:0;border-top:2px dashed var(--bus3);height:0"></i>시외버스 1963–1990 · 신문 기사로 확인한 해만</button>')
rep('<span><i class="sw" style="background:var(--nb);border-color:var(--rule)"></i>이웃 시·도와 북한(지금 경계)</span>',
    '<span><i class="sw" style="background:none;border:0;border-top:2px dashed var(--bus3);height:0;width:18px"></i>서울 시외버스 터미널·정류장에서 경기·인천으로 가던 시외버스 노선(1963–1990) — 신문 기사에 그 노선이 나온 해 사이만, 노선마다 한 줄, 서울 쪽 끝·경유지를 지금 도로 위로 이은 근사선</span>\n  <span><i class="sw" style="background:var(--nb);border-color:var(--rule)"></i>이웃 시·도와 북한(지금 경계)</span>')
# 그리기
rep("""     .on('click',(e,c)=>{e.stopPropagation();showBus(c)});}""",
"""     .on('click',(e,c)=>{e.stopPropagation();showBus(c)});}
  drawSw();""")
rep("  gBus.selectAll('path').attr('d',e=>line(e.p));\n",
    "  gBus.selectAll('path').attr('d',e=>line(e.p));\n  gSw.selectAll('path').attr('d',e=>line(e.p));\n  gSw.selectAll('circle').attr('cx',o=>proj(o.p[0])[0]).attr('cy',o=>proj(o.p[0])[1]);\n")
rep("  gBus.selectAll('circle').attr('r',Math.min(2.4,1.2+0.2*k)/k);\n",
    "  gBus.selectAll('circle').attr('r',Math.min(2.4,1.2+0.2*k)/k);\n  gSw.selectAll('circle').attr('r',Math.min(2.6,1.3+0.2*k)/k);\n")
rep("  gR0.style('display',on.r0?null:'none');\n",
    "  styleSw();\n  gR0.style('display',on.r0?null:'none');\n")
rep("function showJsPt(p){",
r"""// 시외버스: 신문 기사로 확인한 노선(서울 터미널·정류장–경기·인천). 노선마다 한 줄, 기사에 나온 해 사이만
let swHi=null;
const swOn=o=>o.y<=Y&&Y<=o.z;
function drawSw(){
  if(!D.sw)return;
  gSw.selectAll('path.sl').data(D.sw).join('path').attr('class','sl').attr('fill','none').attr('stroke','var(--bus3)').attr('stroke-width',1.7).attr('stroke-dasharray','5 3').attr('stroke-linejoin','round').attr('vector-effect','non-scaling-stroke').attr('pointer-events','none');
  gSw.selectAll('circle').data(D.sw).join('circle').attr('fill','var(--bg)').attr('stroke','var(--bus3)').attr('stroke-width',1.2).attr('vector-effect','non-scaling-stroke').attr('pointer-events','none');
  gSw.selectAll('path.sh').data(D.sw).join('path').attr('class','sh').attr('fill','none').attr('stroke','transparent').attr('stroke-width',10).attr('vector-effect','non-scaling-stroke').style('cursor','pointer')
    .on('click',(e,o)=>{e.stopPropagation();showSw(e)});
}
function styleSw(){
  gSw.style('display',on.sw&&D.sw?null:'none');
  if(!D.sw||!on.sw)return;
  gSw.selectAll('path,circle').style('display',o=>swOn(o)?null:'none');
  gSw.selectAll('path.sl').attr('stroke',o=>swHi===o?'var(--bus4)':'var(--bus3)').attr('stroke-width',o=>swHi===o?2.6:1.7).attr('stroke-opacity',o=>swHi==null||swHi===o?1:.25);
}
function showSw(e){
  // 누른 자리에서 화면으로 9px 안에 지나는, 그해 보이는 노선을 모두 보여 준다(같은 길을 여러 노선이 같이 씀)
  const [mx,my]=d3.pointer(e,svg.node());
  const near=o=>{let m=1e9;const q=o.p.map(c=>T.apply(proj(c)));for(let i=1;i<q.length;i++){const [ax,ay]=q[i-1],[bx,by]=q[i];const dx=bx-ax,dy=by-ay,L=dx*dx+dy*dy;let t=L?((mx-ax)*dx+(my-ay)*dy)/L:0;t=Math.max(0,Math.min(1,t));m=Math.min(m,Math.hypot(ax+t*dx-mx,ay+t*dy-my))}return m};
  const L=D.sw.map((o,i)=>[i,o,near(o)]).filter(([i,o,d])=>swOn(o)&&d<9).sort((a,b)=>a[1].y-b[1].y);
  if(!L.length)return;
  sel={t:'sw',v:e};
  const li=L.map(([i,o])=>`<li data-si="${i}"><a href="#" class="bk" data-si="${i}">${esc(o.n)}</a> <small>${o.y===o.z?o.y+'년 기사':o.y+'–'+o.z+'년 기사'} · 그린 끝 ${esc(o.o)} → ${esc(o.e)}<br>${esc(o.nt||'')}<br>근거: ${esc(o.src)}</small></li>`).join('');
  card(`<h3>${Y}년, 이 길을 지나던 시외버스 ${L.length}개 노선</h3><small>신문 기사에 노선이 나온 해 사이만 그림 · 이름을 누르면 그 노선만 진하게 보입니다</small><ul>${li}</ul><small>1960–80년대 시외버스는 노선 목록이 남아 있지 않아, 조선일보 기사(조선 뉴스 라이브러리 100)에 서울 쪽 종점·정류장과 경기·인천 쪽 끝이 함께 나온 노선만 넣었습니다. 기사에 나온 첫해와 마지막 해 사이에만 보이므로, 실제로는 더 일찍 생기거나 더 늦게까지 다녔을 수 있습니다. 경로는 기사에 나온 곳을 지금 도로 위 최단 경로로 이은 근사선이라 그때 길과 다를 수 있습니다.</small>`);
  document.querySelectorAll('#cardBody a.bk[data-si]').forEach(a=>a.onclick=ev=>{ev.preventDefault();ev.stopPropagation();const o=D.sw[+a.dataset.si];swHi=swHi===o?null:o;styleSw();document.querySelectorAll('#cardBody li[data-si]').forEach(el=>el.classList.toggle('hi',D.sw[+el.dataset.si]===swHi))});
  swHi=null;styleSw();
}
function showJsPt(p){""")
rep("function closeCard(){$('card').classList.remove('on');sel=null;if(busHi!=null)hiBus(null)}",
    "function closeCard(){$('card').classList.remove('on');sel=null;if(busHi!=null)hiBus(null);if(swHi!=null){swHi=null;styleSw()}}")
# 범위 표
rep("""    ['바다','y','그림',""","""    ['시외버스','p','기사로 확인한 해만',`1963–1990년 서울의 시외버스 터미널·정류장(종로5가·신설동·용두동·동마장·용산·동자동·불광동·신촌 등)에서 경기·인천으로 가던 노선 ${(D.sw||[]).length}개. 신문 기사에 서울 쪽 끝과 경기·인천 쪽 끝이 함께 나온 노선만, 기사에 나온 첫해부터 마지막 해까지 노선마다 한 줄로 그림(광역버스와 달리 노선 수로 굵기를 정하지 않음)`,'조선일보 기사(조선 뉴스 라이브러리 100, 1963–1990년 기사 본문). 기사 저작권은 조선일보에 있어 사실(노선의 두 끝·해)만 옮김. 경로: © OpenStreetMap contributors(ODbL), 지명 자리: 국토교통부 「전국 버스정류장 위치정보」','노선 목록·면허 기록(교통부·경기도·서울시 고시)은 보지 못함. 기사에 나온 해 사이만 보여 실제 운행 기간보다 짧음. 경로는 기사에 나온 곳을 지금 도로 위 최단 경로로 이은 근사선. 다른 신문(동아·경향·매일경제)은 아직 찾지 않음'],
    ['바다','y','그림',""")
rep("1970–80년대 시외버스 등은 빠짐)","1970–80년대 시외버스는 아래 「시외버스」 줄에서 따로 그림)")
rep("경로 — © OpenStreetMap contributors(ODbL) 도로 위 최단 경로.</p>",
    "경로 — © OpenStreetMap contributors(ODbL) 도로 위 최단 경로. 1963–1990년 시외버스 노선과 해 — 조선일보 기사(<a href=\"https://newslibrary.chosun.com/\">조선 뉴스 라이브러리 100</a>, 기사 저작권은 조선일보에 있어 노선의 두 끝과 해만 옮김; 노선을 누르면 기사 날짜가 나옴).</p>")
rep("그 길을 지나는 광역버스 노선이 나옵니다.","그 길을 지나는 광역버스·시외버스 노선이 나옵니다.")
open(p,'w',encoding='utf-8').write(s); print('ok')
