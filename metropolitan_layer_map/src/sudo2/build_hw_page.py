# hw.json(구간 날짜를 붙인 선)과 hw_segments.SEG를 지도 data.json에 합침
import os as _os, sys as _sys  # paths.py 찾기: 이 파일 폴더에서 위로 올라감(저장소 src/, 작업 공간 $MLM_SUDO·$MLM_SUDO2)
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and not _os.path.isfile(_os.path.join(_d, 'paths.py')):
    _d = _os.path.dirname(_d)
_sys.path.insert(1, _d)
from paths import PAGE_DATA, SUDO2  # noqa: E402
import json,sys
sys.path.insert(0,SUDO2)
from hw_segments import SEG,SRC
P=PAGE_DATA
d=json.load(open(P)); h=json.load(open(f'{SUDO2}/hw.json'))
RN={'경부':'경부고속도로','경인':'경인고속도로','외곽':'수도권제1순환고속도로(옛 서울외곽순환고속도로)','서해안':'서해안고속도로','영동':'영동고속도로',
 '제2경인':'제2경인고속도로','중부':'중부고속도로','제2중부':'제2중부고속도로','중부내륙':'중부내륙고속도로','평택제천':'평택제천고속도로',
 '세종포천':'세종포천고속도로','서울양양':'서울양양고속도로','광주원주':'광주원주고속도로','공항':'인천국제공항고속도로','평택시흥':'평택시흥고속도로',
 '용인서울':'용인서울고속도로','오산화성':'오산화성고속도로','평택화성':'평택화성고속도로','수원광명':'수원광명고속도로','서울문산':'서울문산고속도로',
 '익산평택':'익산평택고속도로(서부내륙)','제2순환':'수도권제2순환고속도로','중앙':'중앙고속도로'}
WK={'외곽':'수도권제1순환고속도로','익산평택':'서부내륙고속도로'}
END={'END_N':'북쪽 지도 끝','END_S':'남쪽 지도 끝','END_E':'동쪽 지도 끝','END_W':'서쪽 지도 끝'}
BOXLAB={('제2순환','2017-03-23'):'인천–김포',('제2순환','2023-09-25'):'시화–남안산',('제2순환','2024-12-19'):'파주–양주'}
NEWS={('제2순환','2024-12-19'):['머니투데이방송 2024-12-18 기사','https://news.mtn.co.kr/news-detail/2024121811101058463'],
      ('익산평택','2024-12-10'):['정책브리핑(국토교통부) 보도','https://m.korea.kr/news/policyNewsView.do?newsId=148937177']}
NOTE={('중앙','1995-08-29'):'만종–남원주 사이는 처음 개통일을 찾지 못해 1995년 구간에 붙임(추정). 1998-07-10 이 사이 4차로 확장을 조기 개방했다는 건설교통부 보도자료 제목만 확인',
      ('제2경인','2001-10-18'):'석수–삼막은 1km 남짓이라 앞 구간(1995) 선과 겹쳐 지도에서는 1995년부터 보임',
      ('경인','1968-12-21'):'2017년 일반도로로 바뀐 인천 쪽 끝 구간은 지금 고속도로가 아니어서 그리지 않음',
      ('외곽','1997-11-03'):'국가기록원 연표의 착공 항목 괄호에는 1997-11-13 개통으로 적혀 있음. 건설교통부 1997년 8월 보도자료는 10월 말 개통 예정',
      ('외곽','2001-09-11'):'이날은 일산 방향 2개 차로만 임시 개방(건설교통부 보도자료). 양방향 개통은 2001-09-29로 적은 글도 있음(한국건설산업연구원)',
      ('경부','1968-12-21'):'연표에 「서울~인천간 및 서울~수원간 고속도로 개통」'}
sec={}
for rt,ss in SEG.items():
    rows=[]
    for dd,a,b,sk in ss:
        if a=='ALL': lab='지도 안 전 구간'
        elif a=='BOX': lab=BOXLAB.get((rt,dd),'일부 구간')
        else: lab=f"{END.get(a,a)}–{END.get(b,b)}"
        s=NEWS.get((rt,dd)) or ([SRC[sk][0],'https://ko.wikipedia.org/wiki/'+WK.get(rt,RN[rt].split('(')[0])] if sk=='wk' else SRC[sk])
        rows.append([dd,lab,s[0],s[1],NOTE.get((rt,dd),'')])
    sec[rt]=sorted(rows)
# 경부 한남–양재(OSM에서 trunk)는 build_art.py가 뽑아 hwx로 넘김
A=json.load(open(f'{SUDO2}/art.json'))
sec['경부']=[[r[0],('서울(반포)–수원신갈' if r[0]=='1968-12-21' else r[1])]+r[2:] for r in sec['경부']]
sec['경부'].append(['1969-12-26','한남대교(제3한강교)–반포','국가기록원 「고속도로 연표」','https://theme.archives.go.kr/next/gyeongbu/roadChronological01.do','연표에 「제3한강교 준공 개통(서울~부산간 고속도로 시작 기점)」. 한남–양재 구간은 지금 OSM에서 고속도로가 아닌 자동차전용도로로 표시됨'])
sec['경부'].sort()
d['hw']={'seg':[{'r':o['r'],'d':o['d'],'p':o['p']} for o in h['hw']]+A['hwx'],'sec':sec,'rn':RN}
d['art']={'seg':A['seg'],'base':A['base'],'sec':A['sec'],'rn':A['rn']}
json.dump(d,open(P,'w'),ensure_ascii=False,separators=(',',':'))
print(len(d['hw']['seg']),'segs',sum(len(v) for v in sec.values()),'sections',len(sec),'routes')
