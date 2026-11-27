"""광역버스: 노선마다 생긴 해부터 그리기, 인천·서울 면허 노선 더함(한 번만 돌림)"""
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
rep('광역버스 · 2023년 9월 경기 노선</button>','광역버스 · 노선이 생긴 해부터</button>')
rep("광역버스가 지나는 길(1–2·3–7·8–19·20개 넘는 노선, 2023년부터) — 서울로 들어가는 방향만, 정류소를 도로 위로 이은 근사선",
    "광역버스가 지나는 길(그해 다니던 노선 1–2·3–7·8–19·20개 넘음) — 노선마다 생긴 해부터, 서울로 들어가는 방향만, 지금 정류소를 도로 위로 이은 근사선")
# 그해 다니는 노선 수
rep("function busW(n){return 0.55+0.62*Math.sqrt(n)}",
"""function busW(n){return 0.55+0.62*Math.sqrt(n)}
function busY(i){const r=D.bus.rt[i];return r.y||r.d}
function busN(c){let n=0;for(const i of c.r)if(busY(i)<=Y)n++;return n}""")
rep("  gBus.style('display',on.bus&&Y>=2023?null:'none');\n",
"""  gBus.style('display',on.bus&&D.bus?null:'none');
  if(D.bus&&on.bus){
    gBus.selectAll('path.bl').each(function(c){const n=busN(c);c._n=n;d3.select(this).style('display',n>0?null:'none').attr('stroke-width',busW(Math.max(n,1))).attr('stroke',busHi!=null&&c.r.includes(busHi)?'var(--bus4)':busCol(n))});
    gBus.selectAll('path.bh').style('display',c=>c._n>0?null:'none');
    gBus.selectAll('circle').style('display',(p,i)=>busY(i)<=Y?null:'none');
  }
""")
rep("  gBus.selectAll('path.bl').attr('stroke-opacity',c=>ri==null||c.r.includes(ri)?1:.15).attr('stroke',c=>ri!=null&&c.r.includes(ri)?'var(--bus4)':busCol(c.r.length));",
    "  gBus.selectAll('path.bl').attr('stroke-opacity',c=>ri==null||c.r.includes(ri)?1:.15).attr('stroke',c=>ri!=null&&c.r.includes(ri)?'var(--bus4)':busCol(c._n||busN(c)));")
rep("""  const rs=c.r.map(i=>[i,B.rt[i]]).sort((a,b)=>a[1].n.localeCompare(b[1].n,'ko',{numeric:true}));
  const li=rs.map(([i,r])=>`<li data-ri="${i}"><a href="#" class="bk" data-ri="${i}">${esc(r.n)}</a> <small>${esc(r.o)} → ${esc(r.e)}${r.v&&r.v.length?' · 같이 센 변형 '+esc(r.v.join(', ')):''}</small></li>`).join('');
  card(`<h3>광역버스 ${c.r.length}개 노선이 지나는 길</h3><small>2023년 9월 경기도 버스운송관리시스템 노선 · 서울로 들어가는 방향만 · 번호를 누르면 그 노선만 진하게 보입니다</small><ul>${li}</ul><small>경로는 정류소 순서를 지금 OSM 도로 위 최단 경로로 이은 근사선이라 실제 운행 경로와 다를 수 있습니다. 출발 정류소는 서울에서 가장 먼 정류소로 잡았습니다. 인천·서울 면허 노선은 아직 넣지 않았습니다.</small>`);""",
"""  const HOW={'시·번호':'나무위키 개업 연도 분류','M·P 번호':'나무위키 개업 연도 분류','번호·지나는 시':'나무위키 개업 연도 분류(다른 시 문서)','문서 역사':'나무위키 노선 문서 역사 절','계열 문서':'나무위키 같은 계열 번호 문서(추정)'};
  const all=c.r.map(i=>[i,B.rt[i]]).sort((a,b)=>busY(a[0])-busY(b[0])||a[1].n.localeCompare(b[1].n,'ko',{numeric:true}));
  const now=all.filter(([i])=>busY(i)<=Y), later=all.filter(([i])=>busY(i)>Y);
  const yl=r=>r.y?`${r.y}년부터 · ${HOW[r.yh]||r.yh}`:`생긴 해 못 찾음 · 자료 시점 ${r.d}년부터 그림`;
  const li=now.map(([i,r])=>`<li data-ri="${i}"><a href="#" class="bk" data-ri="${i}">${esc(r.n)}</a> <small>${esc(r.reg)} · ${esc(r.o)} → ${esc(r.e)}<br>${esc(yl(r))}${r.ys?' 「'+esc(r.ys)+'」':''}${r.v&&r.v.length?' · 같이 센 변형 '+esc(r.v.join(', ')):''}</small></li>`).join('');
  card(`<h3>${Y}년에 광역버스 ${now.length}개 노선이 지나는 길</h3><small>서울로 들어가는 방향만 · 번호를 누르면 그 노선만 진하게 보입니다${later.length?` · 이 길에 뒤에 생기는 노선 ${later.length}개`:''}</small><ul>${li}</ul><small>경로는 지금(경기 2023년 9월·인천 2024년 8월·서울 2026년 11월) 정류소 순서를 OSM 도로 위 최단 경로로 이은 근사선이라, 생긴 해의 경로와 다를 수 있습니다. 그 사이 없어진 노선은 들어 있지 않습니다. 출발 정류소는 서울에서 가장 먼 정류소로 잡았습니다.</small>`);""")
# 범위 표
import re
i=s.index("    ['광역버스','p','2023년 9월',"); j=s.index("\n",i)
s=s[:i]+"""    ['광역버스','p','생긴 해부터',`서울로 들어가는 광역버스 ${(D.bus||{rt:[]}).rt.length}개(경기 면허 M·G·P·네 자리 번호, 인천 면허 광역·M, 서울 면허 9xxx)를 서울로 들어가는 방향만 그림. 노선마다 나무위키에서 찾은 생긴 해부터 보이고, 못 찾은 노선은 자료 시점부터 보임. 그해 다니던 노선 수로 굵기를 정함`,'노선·정류소 순서: 경기도 BMS 「노선 경유정류소」「노선 정보 검증」(2023-09, 이용허락범위 제한 없음), 인천광역시 BIS 「노선별경유노드 현황」(2024-08, 이용허락범위 제한 없음)과 「시내버스 노선현황」(2024-08-31, 공공누리 출처표시), 서울시 「버스노선별 정류장별 승하차 인원」(2026-11, 공공누리 제1유형). 정류소 좌표: 국토교통부 「전국 버스정류장 위치정보」(2026-11-09, 이용허락범위 제한 없음), 인천 교차로 노드: 국가교통정보센터 표준노드링크(2024-11-29). 생긴 해: 나무위키 「YYYY년 개업한 버스 노선」 분류와 노선 문서(CC BY-NC-SA 2.0 KR). 경로: © OpenStreetMap contributors(ODbL)','지금 노선의 지금 경로를 생긴 해까지 거슬러 그리므로 옛 경로·옛 번호, 그 사이 없어진 노선(신분당선 개통 뒤 줄어든 분당·용인 노선 등)은 없음. 생긴 해를 못 찾은 노선은 자료 시점부터 보임']"""+s[j:]
rep("광역버스 노선·정류소 순서 — 경기도 버스운송관리시스템 「노선 경유정류소」「노선 정보 검증」(2023-09, <a href=\"https://www.data.go.kr/data/15124068/fileData.do\">공공데이터포털</a>·경기데이터드림, 이용허락범위 제한 없음),",
    "광역버스 노선·정류소 순서 — 경기도 버스운송관리시스템 「노선 경유정류소」「노선 정보 검증」(2023-09, <a href=\"https://www.data.go.kr/data/15124068/fileData.do\">공공데이터포털</a>·경기데이터드림, 이용허락범위 제한 없음), 인천광역시 버스정보시스템 <a href=\"https://www.data.go.kr/data/15134389/fileData.do\">「노선별경유노드 현황」</a>(2024-08, 이용허락범위 제한 없음)과 <a href=\"https://www.incheon.go.kr/traffic/TR060002/2205815\">「시내버스 노선현황」</a>(2024-08-31, 공공누리 출처표시), 서울시 「버스노선별 정류장별 승하차 인원 정보」(서울 열린데이터광장, 공공누리 제1유형), 인천 교차로 노드 — 국가교통정보센터 표준노드링크(2024-11-29), 노선이 생긴 해 — 나무위키 「YYYY년 개업한 버스 노선」 분류와 노선 문서(CC BY-NC-SA 2.0 KR),")
rep("광역버스는 2023년 9월 경기도 노선을 서울로 들어가는 방향만 도로 위로 이어, 같은 길을 지나는 노선 수로 굵기를 정했습니다.",
    "광역버스는 서울로 들어가는 경기·인천·서울 면허 노선을 서울 방향만 도로 위로 이어, 노선마다 생긴 해부터 그해 같은 길을 다니던 노선 수로 굵기를 정했습니다.")
open(p,'w',encoding='utf-8').write(s); print('patched2')
