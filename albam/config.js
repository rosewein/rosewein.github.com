// 알밤케어 거실 화면 설정.
// supabaseUrl·supabaseAnonKey 는 Supabase 대시보드 > Project Settings > API 에 있다.
// anon key 는 공개돼도 되는 값이다(가족만 읽고 쓰게 하는 건 RLS가 맡는다). service_role 키는 절대 넣지 않는다.
// 비워 두면 첫 화면에서 직접 넣을 수 있고, 그 값은 이 기기에만 저장된다.
window.ALBAM_CONFIG = {
  supabaseUrl: '',
  supabaseAnonKey: '',

  // ── 화면 동작 (아직 정할 것의 임시값) ──
  nightStartHour: 21,        // 밤 화면 시작
  nightEndHour: 6,           // 밤 화면 끝
  nightWakeSeconds: 30,      // 밤에 터치하면 밝아져 있는 시간
  undoSeconds: 6,            // 저장 직후 [취소] 버튼이 떠 있는 시간
  voiceConfirmSeconds: 4,    // 음성 확인 화면에서 자동 저장까지
  pollSeconds: 20,           // 다른 기기 기록을 다시 읽는 주기
  shiftMinutes: 3,           // 번인 대비로 화면을 옮기는 주기
  hungryMinutes: 180,        // 마지막 수유 후 이만큼 지나면 캐릭터가 배고파함
  defaultAmounts: [180, 200, 220], // 수유량 빠른 선택을 아직 못 받았을 때(평소엔 화면의 '수유량 설정' 값)
  dailyReloadHour: 4,        // 24시간 켜 둘 때 하루 한 번 새로 고침하는 시각
};
