// 알밤케어 거실 화면 설정.
// supabaseUrl·supabaseAnonKey 는 Supabase 대시보드 > Project Settings > API 에 있다(프로젝트 baby_archive_AlbamWiki).
// anon key 는 공개돼도 되는 값이다(가족만 읽고 쓰게 하는 건 RLS가 맡는다). service_role 키는 절대 넣지 않는다.
window.ALBAM_CONFIG = {
  supabaseUrl: 'https://dkeiwryjvussejrevigh.supabase.co',
  supabaseAnonKey: 'sb_publishable_87W4Yg7J_a7vb9XnoSp4OA_OrX5krqY', // publishable(공개) 키

  // ── 화면 동작 (아직 정할 것의 임시값) ──
  nightStartHour: 21,        // 밤 화면 시작
  nightEndHour: 6,           // 밤 화면 끝
  nightWakeSeconds: 30,      // 밤에 터치하면 밝아져 있는 시간
  undoSeconds: 6,            // 저장 직후 [취소] 버튼이 떠 있는 시간
  voiceConfirmSeconds: 4,    // 음성 확인 화면에서 자동 저장까지
  pollSeconds: 20,           // 다른 기기 기록을 다시 읽는 주기
  shiftMinutes: 3,           // 번인 대비로 화면을 옮기는 주기
  // 대시보드 말풍선·표정: 지난 시간 ÷ 기준 시간이 가장 크고 1 이상인 항목 하나가 '급한 항목'(빨강)
  hungryMinutes: 'auto',     // 마지막 수유 후 이만큼(분) 지나면 "배고파요…". 'auto' = 최근 14일 수유 간격에서 자동
                             //   (4번 중 3번은 이보다 늦게 먹은 간격 = p25, 10분 단위. 기록이 적으면 180). 숫자로 적으면 그 값
  diaperMinutes: 180,        // 마지막 기저귀 후 이만큼 지나면 "기저귀 봐 주세요…"
  awakeMinutes: 120,         // 깬 뒤 이만큼 지나면 "졸려요…"
  defaultAmounts: [200, 230, 270], // 수유량 빠른 선택을 아직 못 받았을 때(평소엔 화면의 '수유량 설정' 값). 브레짜 180·210·240

  // 분유·기계: 수유량은 '완성량'으로 기록하고, 화면에 브레짜에서 고를 물 양을 같이 보여 준다.
  // 압타밀: 물 30ml 에 1스푼, 다 타면 약 33.3ml. 브레짜: 물 60~300ml, 30ml 단위
  // → 브레짜 180 = 200ml, 210 = 230ml, 240 = 270ml
  // 완성량은 10ml 단위로 반올림해 기록한다(roundMl)
  formula: { name: '압타밀', waterMlPerScoop: 30, mlPerScoop: 100 / 3, roundMl: 10 },
  machine: { name: '브레짜', minWaterMl: 60, maxWaterMl: 300, stepWaterMl: 30 },
  dailyReloadHour: 4,        // 24시간 켜 둘 때 하루 한 번 새로 고침하는 시각
  statsDays: 7,              // 통계 쪽에 보여 줄 날 수(오늘 포함)
  statsIdleSeconds: 60,      // 타임라인·통계 쪽에서 이만큼 안 만지면 대시보드로 돌아옴(시계 쪽은 그대로)
  theme: 'auto',             // 'auto' 해 뜬 동안 밝은 화면, 해 지면 어두운 화면 / 'light' / 'dark'
  location: { lat: 37.5665, lon: 126.978 },  // 해 뜨고 지는 시각을 셀 곳(서울)
};
