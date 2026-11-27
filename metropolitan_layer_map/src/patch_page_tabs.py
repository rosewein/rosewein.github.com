"""v1.0 index.html → v1.1 탭 구조(지도 / 읽는 법 / 자료 범위·출처). 한 번만 돌린 것(2026-11-27). python3 patch_page_tabs.py <입력> <출력>"""
import sys, re
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()

def cut(s, start, end_marker, inclusive=True):
    i = s.index(start); j = s.index(end_marker, i) + (len(end_marker) if inclusive else 0)
    return s[i:j], s[:i] + s[j:]

# 1) 조각 떼어 내기
header, s = cut(s, '<header class="band">', '</div></header>')
lede = re.search(r'<p class="lede">(.*?)</p>', header, re.S).group(1)
fig, s = cut(s, '<section class="fig" id="fig"', '</section>')
ctl, s = cut(s, '<div class="ctl">', '</div>')
ticks, s = cut(s, '<div class="ticks" id="ticks">', '</div>')
chips_start = s.index('<div class="chips" id="chips">')
legend_start = s.index('<div class="legend">')
legend_end = s.index('</div>', s.index('지도를 누르면', legend_start)) + 6
chips = s[chips_start:legend_start]
legend = s[legend_start:legend_end]
s = s[:chips_start] + s[legend_end:]
band, s = cut(s, '<section class="band"><div class="wrap">', '</div></section>')
notes = re.findall(r'  <p class="note">.*?</p>', band, re.S)
table = band[band.index('<table class="stack">'):band.index('</table>') + 8]
src_note = [n for n in notes if '>출처:' in n][0]
ver_note = [n for n in notes if re.search(r'>v1\.\d', n)][0]
read_notes = [n for n in notes if n not in (src_note, ver_note)]


sent = [x.strip() + ('' if x.strip().endswith('.') else '.') for x in re.split(r'(?<=다\.)\s+', lede.strip()) if x.strip()]
def pick(*keys):
    out = [x for x in sent if any(k in x for k in keys)]
    for x in out: sent.remove(x)
    return ' '.join(out)
intro = pick('겹쳐 본 지도입니다')
pick('레이어마다 자료가 닿는 범위')
joseon = pick('조선 후기 대로를')
bus = pick('광역버스는')
sw = pick('시외버스 노선과')
bnd = pick('경계는 HGIS에 자료가 없어서')
assert not sent, sent
txt = lambda n: re.sub(r'^\s*<p class="note">|</p>$', '', n.strip())
rail_n = txt([n for n in read_notes if n.strip().startswith('<p class="note">전철')][0])
bnd_n = txt([n for n in read_notes if '행정구역 경계는 시기마다' in n][0])
b75_n = txt([n for n in read_notes if '1975년 말 이후 경계는' in n][0])
blocks = [
  ('행정구역 경계의 자료와 보정', bnd_n),
  ('1975년 뒤 경계와 「바뀐 곳」 표시', b75_n),
  ('국철 선로와 철도 기호', '국철은 가는 선 위에 짧은 가로 눈금을 넣은 철도 기호로 그렸습니다. 경인선과 경부선 서울 구간은 HGIS의 시기별 선형이고, 1945년 뒤로는 1945년 선형을 이어 그렸습니다. 경부선 영등포 남쪽은 HGIS에 미완성 선형만 있어서 지금 선로 모양을 1905년 개통 때부터 그렸고, 서울 안 국철은 「서울 도시 연대지도」 정리값입니다. 서울 밖 경원·경의·경춘·중앙선 등의 1974년 전 모습은 아직 그리지 못했습니다.'),
  ('전철 선로와 역이 보이는 해', rail_n),
  ('조선 후기 대로의 근사선', joseon),
  ('광역버스 묶음선의 굵기', bus),
  ('시외버스 노선과 터미널', sw + ' 터미널·정류장 점을 누르면 그곳에서 나가던 방면과 기사에 함께 나온 행선지가 나옵니다.'),
]
read_html = ('  <p class="lead">' + intro + ' 레이어마다 자료가 닿는 범위와 비는 곳은 「자료 범위·출처」 탭의 표에 적었습니다.</p>\n  <div class="topics">\n'
  + '\n'.join(f'    <section class="topic"><h2>{h}</h2><p>{b}</p></section>' for h,b in blocks) + '\n  </div>')

# 2) 새 몸통
body = f'''<div class="app">
<header class="top">
  <h1>수도권 도시 연대지도</h1>
  <nav class="tabs" role="tablist" aria-label="보기">
    <button type="button" role="tab" id="tab-map" data-tab="map" aria-controls="pane-map" aria-selected="true">지도</button>
    <button type="button" role="tab" id="tab-read" data-tab="read" aria-controls="pane-read" aria-selected="false" tabindex="-1">읽는 법</button>
    <button type="button" role="tab" id="tab-data" data-tab="data" aria-controls="pane-data" aria-selected="false" tabindex="-1">자료 범위·출처</button>
  </nav>
</header>
<section class="pane pane-map" id="pane-map" role="tabpanel" aria-labelledby="tab-map">
<div class="mapwrap">
<div class="mapcol">
{fig}
{ctl}
{ticks}
</div>
<aside class="side" aria-label="레이어와 범례">
<h2 class="sh">레이어</h2>
{chips}<h2 class="sh">범례</h2>
{legend}
</aside>
</div>
</section>
<section class="pane pane-text" id="pane-read" role="tabpanel" aria-labelledby="tab-read" hidden><div class="tw">
{read_html}
</div></section>
<section class="pane pane-text" id="pane-data" role="tabpanel" aria-labelledby="tab-data" hidden><div class="tw">
  <h2>지금 자료로 닿는 범위</h2>
  {table}
  <h2 style="margin-top:32px">출처</h2>
{src_note.replace('<p class="note">출처: ', '<p class="note src">')}
{ver_note}
</div></section>
</div>
'''
i = s.index('<body>') + len('<body>')
j = s.index('<script src="https://cdnjs')
s = s[:i] + '\n' + body + '\n' + s[j:]

# 3) CSS
css = '''
/* 탭 구조: 지도 탭은 화면을 꽉 채우고, 레이어·범례는 오른쪽 판 */
.app{display:flex;flex-direction:column;min-height:100vh;min-height:100dvh}
body[data-tab=map] .app{height:100vh;height:100dvh;min-height:560px}
header.top{flex:none;display:flex;flex-wrap:wrap;align-items:flex-end;gap:4px 28px;padding:10px max(2vw,14px) 0;border-bottom:1px solid var(--rule);background:var(--bg)}
header.top h1{font-size:clamp(20px,2.2vw,26px);margin:0 0 9px}
.tabs{display:flex}
.tabs button{font:500 15px var(--body);color:var(--ink2);background:none;border:0;border-bottom:2px solid transparent;padding:8px 14px 10px;margin-bottom:-1px;cursor:pointer}
.tabs button[aria-selected=true]{color:var(--ink);border-bottom-color:var(--ink)}
.pane[hidden]{display:none!important}
.pane-map{flex:1;min-height:0;display:flex}
.mapwrap{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 320px}
.mapcol{display:flex;flex-direction:column;min-height:0;min-width:0}
.mapcol .fig{flex:1;height:auto;min-height:320px;border-top:0}
.mapcol .ctl{padding:8px 16px 0}
.mapcol .ticks{margin:0 24px 8px 72px}
.side{border-left:1px solid var(--rule);overflow-y:auto;padding:4px 16px 16px;background:var(--bg)}
.side .sh{font:600 13px/1.2 var(--body);color:var(--ink2);margin:14px 0 8px;letter-spacing:.02em}
.side .chips{padding:0;gap:6px}
.side .chip{min-height:34px;padding:4px 10px;font-size:13px;width:100%;justify-content:flex-start;text-align:left}
.side .legend{flex-direction:column;gap:7px;padding:0;font-size:12.5px;line-height:1.45}
.side .legend span{align-items:flex-start}.side .legend .sw{margin-top:3px;flex:none}
.pane-text{padding:28px max(3vw,16px) 56px}
.tw{max-width:1480px;margin:0 auto}
.pane-text .lead{font-size:18px;line-height:1.7;color:var(--ink);max-width:62ch;margin:0 0 28px}
.topics{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,30em),1fr));gap:28px 48px}
.topic h2{font:600 17px/1.3 var(--body);margin:0 0 8px}
.topic p{margin:0;font-size:15.5px;line-height:1.75;color:var(--ink2)}
.cols .note,.pane-text .note{max-width:none}
.note.src{column-width:34em;column-gap:48px}
@media(max-width:900px){
  body[data-tab=map] .app{height:auto;min-height:0}
  .mapwrap{display:block}
  .mapcol .fig{flex:none;height:clamp(380px,64svh,680px)}
  .side{border-left:0;overflow:visible;padding:4px max(4vw,16px) 24px}
  .side .chips{gap:8px}.side .chip{width:auto}
  .side .legend{flex-direction:row;flex-wrap:wrap;gap:6px 18px}
  header.top{gap:0 12px}
}
'''
s = s.replace('</style>', css + '</style>', 1)

# 4) 숨은 탭에서 지도 크기가 0일 때는 다시 그리지 않음
a = "function layout(){\n  if(!D)return;"
assert s.count(a) == 1
s = s.replace(a, "function layout(){\n  if(!D||!fig.clientWidth||!fig.clientHeight)return;")

# 5) 탭 바꾸기
tabjs = '''<script>
{
const TABS=['map','read','data'];
function showTab(t,push){
  if(!TABS.includes(t))t='map';
  document.body.dataset.tab=t;
  for(const k of TABS){document.getElementById('pane-'+k).hidden=k!==t;const b=document.getElementById('tab-'+k);b.setAttribute('aria-selected',k===t?'true':'false');b.tabIndex=k===t?0:-1}
  if(push){try{history.replaceState(null,'',t==='map'?location.pathname+location.search:'#'+t)}catch(e){}}
  window.scrollTo(0,0);
}
const tb=[...document.querySelectorAll('.tabs [role=tab]')];
tb.forEach((b,i)=>{b.onclick=()=>showTab(b.dataset.tab,true);b.onkeydown=e=>{const d=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0;if(!d)return;const n=tb[(i+d+tb.length)%tb.length];n.focus();showTab(n.dataset.tab,true)}});
showTab(location.hash.slice(1),false);
}
</script>
</body>'''
s = s.replace('</body>', tabjs, 1)
open(dst, 'w', encoding='utf-8').write(s)
print('ok', len(read_notes), 'read notes')
