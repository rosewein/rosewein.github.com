"""시외버스 터미널·정류장과 나가는 방면 화살표 레이어(한 번만 돌림)"""
p='/home/claude/sudo/page/index.html'; s=open(p,encoding='utf-8').read()
def rep(a,b,n=1):
    global s
    assert s.count(a)==n,(a[:80],s.count(a)); s=s.replace(a,b)
rep("gSw=root.append('g'),","gSw=root.append('g'),gTm=root.append('g'),")
rep("bus:true,sw:true};","bus:true,sw:true,tm:true};")
rep('시외버스 1963–1990 · 신문 기사로 확인한 해만</button>',
    '시외버스 1963–1990 · 신문 기사로 확인한 해만</button>\n  <button class="chip" data-l="tm" aria-pressed="true"><i style="background:var(--bus4);border-radius:50%;width:10px;height:10px"></i>시외버스 터미널·정류장 · 나가던 방면</button>')
rep('<span><i class="sw" style="background:var(--nb);border-color:var(--rule)"></i>이웃 시·도와 북한(지금 경계)</span>',
    '<span><i class="sw" style="background:var(--bus4);border:1.5px solid var(--bg);border-radius:50%;width:10px;height:10px"></i><i class="sw" style="background:var(--bg);border:1.5px solid var(--bus4);border-radius:50%;width:10px;height:10px"></i>시외버스 터미널(채운 점)·정류장(빈 점)과 그곳에서 나가던 방면(화살표) — 신문 기사로 확인한 해 동안, 화살표 굵기는 그해까지 기사에 함께 나온 그 방면 행선지 수(1–2·3–7·8곳 넘음)</span>\n  <span><i class="sw" style="background:var(--nb);border-color:var(--rule)"></i>이웃 시·도와 북한(지금 경계)</span>')
rep("  drawSw();\n","  drawSw();\n  drawTm();\n")
rep("  gSw.selectAll('path').attr('d',e=>line(e.p));\n",
    "  gSw.selectAll('path').attr('d',e=>line(e.p));\n  gTm.selectAll('path.tl,path.tx').attr('d',a=>line(a.ln));\n  gTm.selectAll('path.th').attr('d',a=>line(a.hd)+'Z');\n  gTm.selectAll('circle').attr('cx',t=>proj(t.p)[0]).attr('cy',t=>proj(t.p)[1]);\n")
rep("  gSw.selectAll('circle').attr('r',Math.min(2.6,1.3+0.2*k)/k);\n",
    "  gSw.selectAll('circle').attr('r',Math.min(2.6,1.3+0.2*k)/k);\n  gTm.selectAll('circle').attr('r',Math.min(5,3.6+0.25*k)/k);\n")
rep("  styleSw();\n","  styleSw();\n  styleTm();\n")
rep("function showJsPt(p){",
r"""// 시외버스 터미널·정류장: 기사로 확인한 해 동안 점, 그곳에서 나가던 방면은 화살표(굵기는 그해까지 기사에 나온 행선지 수)
let tmSel=null;
const tmOn=t=>t.a<=Y&&Y<=t.z, tmN=r=>r.ds.filter(d=>d[1]<=Y).length;
function tmCol(n){return n>=8?'var(--bus4)':n>=3?'var(--bus3)':'var(--bus2)'}
function drawTm(){
  if(!D.tm)return;
  const A=[];
  for(const t of D.tm)for(const r of t.dr){
    const L=9,H=1.7,W=1.1,cb=Math.cos(r.b),sb=Math.sin(r.b),pt=(f,s)=>[t.p[0]+(f*cb-s*sb)/88.2,t.p[1]+(f*sb+s*cb)/111];
    A.push({t,r,ln:[pt(0.6,0),pt(L-H*0.6,0)],hd:[pt(L,0),pt(L-H,W),pt(L-H,-W)]});
  }
  gTm.selectAll('path.tl').data(A).join('path').attr('class','tl').attr('fill','none').attr('stroke-linecap','butt').attr('vector-effect','non-scaling-stroke').attr('pointer-events','none');
  gTm.selectAll('path.th').data(A).join('path').attr('class','th').attr('stroke','none').attr('pointer-events','none');
  gTm.selectAll('path.tx').data(A).join('path').attr('class','tx').attr('fill','none').attr('stroke','transparent').attr('stroke-width',12).attr('vector-effect','non-scaling-stroke').style('cursor','pointer')
    .on('click',(e,a)=>{e.stopPropagation();showTm(a.t)});
  gTm.selectAll('circle').data(D.tm).join('circle').attr('stroke-width',1.6).attr('vector-effect','non-scaling-stroke').style('cursor','pointer')
    .on('click',(e,t)=>{e.stopPropagation();showTm(t)});
}
function styleTm(){
  gTm.style('display',on.tm&&D.tm?null:'none');
  if(!D.tm||!on.tm)return;
  const vis=a=>tmOn(a.t)&&tmN(a.r)>0, dim=a=>tmSel&&tmSel!==a.t;
  gTm.selectAll('path.tl').style('display',a=>vis(a)?null:'none').attr('stroke',a=>tmCol(tmN(a.r))).attr('stroke-width',a=>0.9+0.75*Math.sqrt(tmN(a.r))).attr('stroke-opacity',a=>dim(a)?.2:.95);
  gTm.selectAll('path.th').style('display',a=>vis(a)?null:'none').attr('fill',a=>tmCol(tmN(a.r))).attr('fill-opacity',a=>dim(a)?.2:.95);
  gTm.selectAll('path.tx').style('display',a=>vis(a)?null:'none');
  gTm.selectAll('circle').style('display',t=>tmOn(t)?null:'none').attr('fill',t=>t.k==='터미널'?'var(--bus4)':'var(--bg)').attr('stroke',t=>t.k==='터미널'?'var(--bg)':'var(--bus4)').attr('opacity',t=>tmSel&&tmSel!==t?.3:1);
}
function showTm(t){
  sel={t:'tm',v:t};tmSel=t;styleTm();
  const li=t.dr.map(r=>{const n=tmN(r);return `<li><b>${esc(r.nm)}</b> <small>· ${Y}년까지 기사에 나온 행선지 ${n}곳</small><br><small>${r.ds.map(d=>{const s=esc(d[0])+'('+(d[1]===d[2]?d[1]:d[1]+'–'+d[2])+')';return d[1]<=Y?s:'<span style="opacity:.45">'+s+'</span>'}).join(', ')}</small></li>`}).join('');
  card(`<h3>${esc(t.n)}</h3><small>시외버스 ${esc(t.k)} · 기사로 확인한 해 ${t.a}–${t.z}${t.sc?' · '+esc(t.sc):''}</small><p><small>${esc(t.nt)}</small></p><ul>${li}</ul><small>행선지는 이 ${esc(t.k)} 이름과 같은 문장에 나온 경기·강원·충청 지명을 모은 것이고, 괄호 안은 그 지명이 나온 기사의 해입니다(${t.a}년 전이나 ${t.z}년 뒤 기사는 앞뒤 해로 줄임). 화살표는 그 방면 행선지들의 평균 방위를 가리키는 도식이고, 실제 길이 아닙니다. 흐린 행선지는 ${Y}년보다 뒤 기사에 처음 나온 곳입니다. 근거: ${esc(t.src)}</small>`);
}
function showJsPt(p){""")
rep("if(swHi!=null){swHi=null;styleSw()}}","if(swHi!=null){swHi=null;styleSw()}if(tmSel){tmSel=null;styleTm()}}")
rep("""    ['바다','y','그림',""","""    ['시외버스 터미널','p','기사로 확인한 해만',`서울의 시외버스 터미널·정류장 ${(D.tm||[]).length}곳(신설동·종로5가·동마장·용산 남부·서울역 동자동·영등포·불광동 서부·신촌·상봉·동서울·서초 남부)을 기사에 나온 해 동안 점으로 찍고, 그곳에서 나가던 방면을 화살표로 그림. 화살표 굵기는 그해까지 그 터미널 이름과 같은 문장에 나온 그 방면 행선지 수`,'조선일보 기사(조선 뉴스 라이브러리 100, 1963–1999년 기사 본문). 기사 저작권은 조선일보에 있어 터미널 이름·해·행선지 지명만 옮김. 동서울·서초 남부가 지금도 영업 중이라는 것은 일반 지식','행선지는 같은 문장에 함께 나온 지명을 기계로 모은 뒤 엉뚱한 것(같은 문장에 다른 터미널 행선지가 나온 경우 등)을 사람이 덜어 낸 것이라, 노선 목록이 아니고 빠진 행선지도 많음. 터미널마다 문을 연 날·닫은 날을 모두 찾지는 못해 기사에 처음·마지막으로 나온 해로 둔 곳이 있음(신촌·불광동·상봉 등). 2000년 뒤 기사는 보지 않음'],
    ['바다','y','그림',""")
rep("노선을 누르면 기사 날짜가 나옴).</p>","노선을 누르면 기사 날짜가 나옴). 시외버스 터미널·정류장과 나가던 방면 — 같은 조선일보 기사(1963–1999), 터미널 점을 누르면 기사 날짜와 행선지가 나옴.</p>")
rep("그 길을 지나는 광역버스·시외버스 노선이 나옵니다.","그 길을 지나는 광역버스·시외버스 노선, 시외버스 터미널에서 나가던 방면이 나옵니다.")
open(p,'w',encoding='utf-8').write(s); print('ok')
