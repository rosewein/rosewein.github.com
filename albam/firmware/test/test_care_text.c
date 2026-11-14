/* care_text.c 시험. 웹앱 tests/unit/logic.test.mjs 와 같은 경우들이다.
 *   cc -I main test/test_care_text.c main/care_text.c -o /tmp/test_care_text && /tmp/test_care_text */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "care_text.h"

static time_t at(int day, int hour, int minute)
{
    struct tm t = { .tm_year = 126, .tm_mon = 10, .tm_mday = day, .tm_hour = hour, .tm_min = minute, .tm_isdst = -1 };
    return mktime(&t);
}

static void same(const char *got, const char *want)
{
    if (strcmp(got, want) != 0) {
        printf("실패: \"%s\" 이어야 하는데 \"%s\"\n", want, got);
        exit(1);
    }
}

static void add_gaps(care_summary_t *s, const int *minutes, int count, int first_hour, int wrap)
{
    for (int i = 0; i < count; i++) {
        s->gaps[s->gap_count].hour = first_hour + (wrap ? i % wrap : i);
        s->gaps[s->gap_count].minutes = minutes[i];
        s->gap_count++;
    }
}

int main(void)
{
    setenv("TZ", "KST-9", 1);
    tzset();
    char text[96];
    time_t now = at(6, 14, 0);   /* 2026-11-06 금 14:00 */

    /* 시각 */
    care_clock(at(6, 9, 5), text, sizeof(text));                       same(text, "09:05");
    care_clock_on(at(6, 9, 0), now, false, text, sizeof(text));        same(text, "09:00");
    care_clock_on(at(5, 9, 0), now, false, text, sizeof(text));        same(text, "어제 09:00");
    care_clock_on(at(5, 9, 0), now, true, text, sizeof(text));         same(text, "어제");
    care_clock_on(at(1, 9, 0), now, false, text, sizeof(text));        same(text, "11/1 09:00");
    care_clock_on(at(5, 23, 50), at(6, 0, 10), false, text, sizeof(text)); same(text, "어제 23:50");

    /* 서버가 주는 시각 글 */
    assert(care_parse_time("2026-11-06T05:00:00+00:00") == at(6, 14, 0));
    assert(care_parse_time("2026-11-06T14:00:00.123456+09:00") == at(6, 14, 0));
    assert(care_parse_time("2026-11-06T05:00:00Z") == at(6, 14, 0));
    assert(care_parse_time("2026-11-05 23:30:00-05:30") == at(6, 14, 0));
    assert(care_parse_time("1970-01-01T00:00:00+00:00") == 0 && care_parse_time("2024-02-29T12:00:00Z") == 1709208000);
    assert(care_parse_time(NULL) == 0 && care_parse_time("어제") == 0);

    /* 지난 시간 */
    care_ago_text(care_ago(now - 155 * 60, now), false, text, sizeof(text)); same(text, "2시간 35분");
    care_ago_text(care_ago(now - 35 * 60, now), false, text, sizeof(text));  same(text, "35분");
    care_ago_text(care_ago(now - 30, now), false, text, sizeof(text));       same(text, "방금");
    care_ago_text(care_ago(now - 120 * 60, now), false, text, sizeof(text)); same(text, "2시간");
    care_ago_text(care_ago(now - 12 * 60, now), true, text, sizeof(text));   same(text, "12분째");
    care_ago_text(care_ago(0, now), false, text, sizeof(text));              same(text, "—");

    /* 기저귀 세부 */
    care_summary_t d = { .valid = true };
    care_diaper_detail(&d, now, text, sizeof(text));                   same(text, "기록 없음");
    d.diaper.at = at(6, 12, 50); d.diaper.type = DIAPER_BOTH;
    care_diaper_detail(&d, now, text, sizeof(text));                   same(text, "12:50 · 소+대");
    d.diaper.type = DIAPER_PEE; d.poo.at = at(6, 9, 10);
    care_diaper_detail(&d, now, text, sizeof(text));                   same(text, "12:50 소변 · 대 09:10");
    d.poo.at = at(5, 9, 10);
    care_diaper_detail(&d, now, text, sizeof(text));                   same(text, "12:50 · 대 어제 09:10");
    d.poo.at = at(3, 9, 10);
    care_diaper_detail(&d, now, text, sizeof(text));                   same(text, "12:50 · 대 11/3 09:10");
    d.diaper.at = at(5, 22, 10); d.diaper.type = DIAPER_BOTH; d.poo.at = 0;
    care_diaper_detail(&d, now, text, sizeof(text));                   same(text, "어제 22:10 · 소+대");

    /* 배고파요 기준: 마지막 수유 시간대의 수유 간격 25% 값 */
    static care_summary_t s;
    const int day[] = { 220, 230, 240, 250, 260, 270, 280 }, evening[] = { 450, 480, 500, 520, 560, 600 }, dawn[] = { 250, 260, 270 };
    add_gaps(&s, day, 7, 8, 0);
    add_gaps(&s, evening, 6, 19, 3);
    add_gaps(&s, dawn, 3, 2, 0);
    s.feed.at = at(8, 10, 30); assert(care_hungry_minutes(&s) == 240);   /* 낮 간격 25% = 235 → 240 */
    s.feed.at = at(8, 20, 30); assert(care_hungry_minutes(&s) == 490);   /* 저녁 수유 뒤에는 길게 */
    s.feed.at = at(8, 3, 30);  assert(care_hungry_minutes(&s) == 250);   /* 새벽 간격이 적으면 전체 간격(25% = 250) */
    s.gap_count = 3;           assert(care_hungry_minutes(&s) == 180);   /* 전체가 10개 미만이면 180 */
    s.old_gap.n = 64; s.old_gap.p25 = 246; assert(care_hungry_minutes(&s) == 250);
    assert(care_hungry_minutes(NULL) == 180);

    /* 대시보드 글 */
    care_view_t v;
    care_summary_t c = { .valid = true, .feed = { .at = at(6, 11, 25), .ml = 200 }, .diaper = { .at = at(6, 12, 50), .type = DIAPER_PEE },
                         .sleep = { .at = at(6, 9, 0), .ended_at = at(6, 13, 20) }, .today = { 3, 570 },
                         .age = { true, 142, 4, 20, true, 3, 28 } };
    care_build_view(&c, now, &v);
    same(v.clock, "14:00"); same(v.today, "2026년 11월 6일 금요일"); same(v.total, "오늘 3회 · 570ml");
    same(v.age, "D+142 · 4개월 20일 · 교정 3개월 28일");
    same(v.words, "기분 좋아요"); same(v.prefix, "먹은 지"); same(v.label, "마지막 수유 11:25");
    assert(!v.urgent && v.mood == MOOD_NORMAL && v.ago.hours == 2 && v.ago.minutes == 35);
    same(v.feed.title, "수유"); same(v.feed.detail, "11:25 · 200ml");
    same(v.diaper.detail, "12:50 · 소변");
    same(v.sleep.title, "잠 · 깬 지"); same(v.sleep.detail, "09:00~13:20");

    c.feed.at = at(6, 10, 40);                     /* 200분 전: 기준 180분을 넘음 */
    care_build_view(&c, now, &v);
    same(v.words, "배고파요…"); assert(v.urgent && v.mood == MOOD_HUNGRY && v.feed.urgent && !v.diaper.urgent);

    c.feed.at = at(6, 13, 0); c.diaper.at = at(6, 10, 0);   /* 기저귀 240분 */
    care_build_view(&c, now, &v);
    same(v.words, "기저귀 봐 주세요…"); same(v.prefix, "기저귀 간 지"); same(v.label, "마지막 기저귀 10:00"); assert(v.diaper.urgent);

    c.sleep.at = at(6, 12, 40); c.sleep.ended_at = 0;       /* 자는 중이면 급한 것보다 잠 */
    care_build_view(&c, now, &v);
    same(v.words, "쿨쿨"); same(v.sleep.title, "잠 · 자는 중"); same(v.sleep.detail, "12:40~"); same(v.prefix, "잠든 지");
    assert(!v.urgent && v.mood == MOOD_SLEEP && v.sleep.ongoing && v.ago.hours == 1 && v.ago.minutes == 20);

    c.feed.at = at(6, 13, 48); c.feed.feeding = true;       /* 먹이는 중 */
    care_build_view(&c, now, &v);
    same(v.words, "냠냠"); same(v.feed.title, "수유 · 먹는 중"); same(v.feed.detail, "13:48~ · 200ml"); same(v.label, "먹이기 시작 13:48");

    care_build_view(NULL, now, &v);                         /* 아직 못 받음 */
    same(v.feed.detail, "기록 없음"); same(v.label, "수유 기록 없음"); same(v.prefix, ""); same(v.total, ""); assert(!v.ago.has && !v.urgent);

    c = (care_summary_t){ .valid = true, .feed = { .at = at(6, 21, 0), .ml = 200 } };
    care_build_view(&c, at(6, 22, 0), &v);                  /* 밤 */
    same(v.words, "쉿, 밤이에요"); assert(v.mood == MOOD_SLEEP);

    printf("care_text: 모두 통과\n");
    return 0;
}
