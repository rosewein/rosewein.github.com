#pragma once
/* 요약(care_summary)을 대시보드에 보일 글로 바꾼다. 웹앱의 src/time.js, src/ui/status.js 와 같은 규칙이다.
 * 화면·통신과 상관없는 순수 계산이라 PC 에서 시험한다(test/test_care_text.c). */
#include <stdbool.h>
#include <stdint.h>
#include <time.h>

#define CARE_MAX_GAPS 400

typedef enum { DIAPER_NONE, DIAPER_PEE, DIAPER_POO, DIAPER_BOTH } care_diaper_t;

/* care_summary() 에서 대시보드가 읽는 부분. 시각은 유닉스 초, 없으면 0 */
typedef struct {
    bool valid;                                  /* 한 번이라도 받았는가 */
    struct { time_t at, ended_at; int ml; bool feeding; } feed;       /* ml: 없으면 -1 */
    struct { time_t at; care_diaper_t type; } diaper;
    struct { time_t at; } poo;                   /* 대변·둘 다 중 가장 최근 */
    struct { time_t at, ended_at; } sleep;       /* at 만 있으면 자는 중 */
    struct { int count, ml; } today;
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
} care_view_t;

void care_build_view(const care_summary_t *summary, time_t now, care_view_t *view);

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
