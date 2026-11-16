#pragma once
/* 요약(care_summary)을 대시보드에 보일 글로 바꾼다. 웹앱의 src/time.js, src/ui/status.js 와 같은 규칙이다.
 * 화면·통신과 상관없는 순수 계산이라 PC 에서 시험한다(test/test_care_text.c). */
#include <stdbool.h>
#include <stdint.h>
#include <time.h>

#define CARE_MAX_GAPS 400
#define CARE_MAX_AMOUNTS 6
#define CARE_ID_LEN 40           /* 기록 id(uuid 글) */

typedef enum { DIAPER_NONE, DIAPER_PEE, DIAPER_POO, DIAPER_BOTH } care_diaper_t;

/* care_summary() 에서 대시보드가 읽는 부분. 시각은 유닉스 초, 없으면 0 */
typedef struct {
    bool valid;                                  /* 한 번이라도 받았는가 */
    struct { time_t at, ended_at; int ml; bool feeding; char id[CARE_ID_LEN]; } feed;   /* ml: 없으면 -1 */
    struct { time_t at; care_diaper_t type; } diaper;
    struct { time_t at; } poo;                   /* 대변·둘 다 중 가장 최근 */
    struct { time_t at, ended_at; char id[CARE_ID_LEN]; } sleep;   /* at 만 있으면 자는 중 */
    struct { int count, ml; } today;
    int amount_count;                            /* 수유량 빠른 선택(ml, 작은 것부터) */
    int amounts[CARE_MAX_AMOUNTS];
    struct { bool has; int day, months, days; bool corrected; int c_months, c_days; } age;
    int gap_count;                               /* 최근 14일 수유 간격 */
    struct { uint8_t hour; uint16_t minutes; } gaps[CARE_MAX_GAPS];
    struct { int n; double p25; } old_gap;       /* feed_gaps 가 없는 서버용 */
} care_summary_t;

typedef enum { MOOD_NORMAL, MOOD_HUNGRY, MOOD_SLEEP, MOOD_HAPPY } care_mood_t;   /* sprites.c 의 줄 순서 */
typedef enum { FOCUS_FEED, FOCUS_DIAPER, FOCUS_SLEEP } care_focus_t;

/* 지난 시간. has 가 아니면 "—", 둘 다 0 이면 "방금" */
typedef struct { bool has; int hours, minutes; } care_ago_t;

typedef struct {
    char title[32];      /* "수유", "잠 · 깬 지" */
    care_ago_t ago;
    bool ongoing;        /* 먹는 중·자는 중: "12분째" */
    char detail[64];     /* "11:25 · 200ml" */
    bool urgent;
} care_card_t;

/* 대시보드 한 장에 보일 글 전부 */
typedef struct {
    char clock[8];       /* "13:05" */
    char today[48];      /* "2026년 11월 7일 토요일" */
    char age[96];        /* "D+142 · 4개월 20일 · 교정 3개월 28일" */
    char total[48];      /* "오늘 3회 · 570ml" */
    care_mood_t mood;
    bool urgent;
    char words[40];      /* 말풍선 문구 */
    char prefix[32];     /* "먹은 지" */
    care_ago_t ago;
    char label[64];      /* "마지막 수유 11:25" */
    care_card_t feed, diaper, sleep;
    bool feeding, sleeping;   /* 먹이는 중, 자는 중: 칸을 누르면 [다 먹음], [깼어요] */
} care_view_t;

/* happy: 방금 저장했다(3초 동안 "고마워요!") */
void care_build_view(const care_summary_t *summary, time_t now, bool happy, care_view_t *view);

/* ---- 기록하기 ---- */

typedef enum {
    ACT_NONE,
    ACT_FEED,          /* 수유(지금 저장) */
    ACT_FEED_START,    /* 먹이기 시작 */
    ACT_FEED_FINISH,   /* 다 먹음: 먹이는 중인 수유에 끝을 넣는다 */
    ACT_DIAPER,
    ACT_SLEEP_START,   /* 잠들었어요 */
    ACT_SLEEP_END,     /* 깼어요: 자는 중인 잠에 끝을 넣는다 */
    ACT_UNDO,          /* 방금 한 것 되돌리기(undo_of 에 무엇을) */
} care_action_kind_t;

typedef struct {
    care_action_kind_t kind, undo_of;
    char id[CARE_ID_LEN];   /* 새 기록이면 비워 두면 만들어 준다 */
    time_t at;              /* 일어난 시각 */
    time_t started_at;      /* 다 먹음·깼어요: 시작한 시각(걸린 시간을 보여 주려고) */
    int ml;
    care_diaper_t diaper;
    bool force;             /* 비슷한 기록이 있어도 저장 */
} care_action_t;

/* 저장 뒤 알림 글: "수유 200ml", "기저귀 소변", "잠 시작 13:10", "수유 200ml · 12분", "잠 1시간 20분" */
void care_describe_action(const care_action_t *action, char *out, size_t len);
/* "1시간 30분", "15분", "2시간" */
void care_duration(long seconds, char *out, size_t len);

/* ---- 오늘 기록 목록 ---- */

#define CARE_MAX_EVENTS 96

/* care_timeline() 의 기록 하나 */
typedef struct {
    time_t at, ended_at;
    char kind[20];          /* feed, diaper, sleep, bath, temperature … */
    int ml;                 /* 없으면 -1 */
    bool has_value;
    double value;           /* 체온·체중·키 */
    care_diaper_t diaper;
    bool feeding;           /* 먹이는 중 */
    char note[72];          /* 약 이름·메모 등 */
} care_event_t;

/* 목록 한 줄(웹앱 src/ui/day-list.js 의 describeRow): "06:03" + "수유 200ml", "20:00~05:40" + "잠 9시간 40분" */
void care_describe_row(const care_event_t *event, time_t now, char *when, size_t when_len, char *what, size_t what_len);
/* 오늘(자정부터) 일어난 일인가. 자정을 넘겨 이어진 잠은 시작한 날에 둔다 */
bool care_is_today(time_t at, time_t now);

/* 분유 양(웹앱 src/formula.js). 브레짜는 물을 60~300ml, 30ml 단위로 고르고 압타밀은 물 30ml 에 1스푼(다 타면 약 33.3ml).
 * 그래서 브레짜 180 → 200ml, 210 → 230ml, 240 → 270ml */
int care_water_for(int ml);                    /* 완성량이 브레짜 한 칸과 딱 맞으면 그 물 양, 아니면 0 */
int care_step_machine(int ml, int direction);  /* 브레짜 한 칸 위/아래 양 */
int care_clamp_amount(int ml);                 /* 5~500 */

/* 아래는 시험하려고 내놓은 조각들 */
void care_clock(time_t at, char *out, size_t len);                               /* "13:05" */
void care_clock_on(time_t at, time_t now, bool day_only, char *out, size_t len); /* "어제 09:00", "11/8 09:00" */
care_ago_t care_ago(time_t from, time_t now);
int care_hungry_minutes(const care_summary_t *summary);                          /* "배고파요…" 기준(분) */
void care_diaper_detail(const care_summary_t *summary, time_t now, char *out, size_t len);
/* "2시간 35분", "방금", "—". ongoing 이면 "12분째" */
void care_ago_text(care_ago_t ago, bool ongoing, char *out, size_t len);
/* 서버가 주는 시각 글("2026-11-14T05:39:41.123+00:00")을 유닉스 초로. 못 읽으면 0 */
time_t care_parse_time(const char *text);
