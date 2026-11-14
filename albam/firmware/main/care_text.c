#include "care_text.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* 웹앱 config.js 와 같은 기준 */
#define DIAPER_MINUTES 180       /* 마지막 기저귀 뒤 이만큼 지나면 "기저귀 봐 주세요…" */
#define AWAKE_MINUTES 120        /* 깬 뒤 이만큼 지나면 "졸려요…" */
#define NIGHT_START_HOUR 21
#define NIGHT_END_HOUR 6
#define HUNGRY_FALLBACK 180
#define HUNGRY_MIN_SAMPLES 10
#define PERIOD_MIN_SAMPLES 6

/* 마지막 수유 시각으로 나누는 시간대: 낮, 저녁, 새벽. 저녁 수유 뒤에는 길게 자서 간격이 훨씬 길다 */
static const struct { int from, to; } PERIODS[] = { { 6, 18 }, { 18, 24 }, { 0, 6 } };

static struct tm local(time_t at)
{
    struct tm t;
    localtime_r(&at, &t);
    return t;
}

void care_clock(time_t at, char *out, size_t len)
{
    struct tm t = local(at);
    snprintf(out, len, "%02d:%02d", t.tm_hour, t.tm_min);
}

/* 며칠 전 날인가(달력 날 기준) */
static int days_before(time_t at, time_t now)
{
    struct tm a = local(at), n = local(now);
    a.tm_hour = n.tm_hour = 12;
    a.tm_min = a.tm_sec = n.tm_min = n.tm_sec = 0;
    double diff = difftime(mktime(&n), mktime(&a));
    return (int)((diff + (diff >= 0 ? 43200 : -43200)) / 86400);
}

void care_clock_on(time_t at, time_t now, bool day_only, char *out, size_t len)
{
    char clock[8], day[16];
    care_clock(at, clock, sizeof(clock));
    int before = days_before(at, now);
    if (before == 0) {
        snprintf(out, len, "%s", clock);
        return;
    }
    if (before == 1) {
        snprintf(day, sizeof(day), "어제");
    } else {
        struct tm t = local(at);
        snprintf(day, sizeof(day), "%d/%d", t.tm_mon + 1, t.tm_mday);
    }
    if (day_only) {
        snprintf(out, len, "%s", day);
    } else {
        snprintf(out, len, "%s %s", day, clock);
    }
}

care_ago_t care_ago(time_t from, time_t now)
{
    care_ago_t ago = { 0 };
    if (!from) {
        return ago;
    }
    long minutes = now > from ? (long)((now - from) / 60) : 0;
    ago.has = true;
    ago.hours = (int)(minutes / 60);
    ago.minutes = (int)(minutes % 60);
    return ago;
}

void care_ago_text(care_ago_t ago, bool ongoing, char *out, size_t len)
{
    const char *tail = ongoing ? "째" : "";
    if (!ago.has) {
        snprintf(out, len, "—");
    } else if (!ago.hours && !ago.minutes) {
        snprintf(out, len, "방금");
    } else if (!ago.hours) {
        snprintf(out, len, "%d분%s", ago.minutes, tail);
    } else if (!ago.minutes) {
        snprintf(out, len, "%d시간%s", ago.hours, tail);
    } else {
        snprintf(out, len, "%d시간 %d분%s", ago.hours, ago.minutes, tail);
    }
}

static int compare_doubles(const void *a, const void *b)
{
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

/* 25% 값(Postgres percentile_cont 와 같은 선형 보간) */
static double p25(double *values, int count)
{
    qsort(values, count, sizeof(double), compare_doubles);
    double i = (count - 1) * 0.25;
    int lo = (int)i;
    int hi = lo + 1 < count ? lo + 1 : count - 1;
    return values[lo] + (values[hi] - values[lo]) * (i - lo);
}

static int round10(double minutes)
{
    return (int)((minutes + 5) / 10) * 10;
}

int care_hungry_minutes(const care_summary_t *s)
{
    static double values[CARE_MAX_GAPS];
    if (!s || s->gap_count < HUNGRY_MIN_SAMPLES) {
        return s && s->old_gap.p25 > 0 && s->old_gap.n >= HUNGRY_MIN_SAMPLES ? round10(s->old_gap.p25) : HUNGRY_FALLBACK;
    }
    /* 마지막 수유와 같은 시간대에서 시작한 간격만. 그 시간대 기록이 적으면 전체 */
    if (s->feed.at) {
        int hour = local(s->feed.at).tm_hour;
        for (size_t p = 0; p < sizeof(PERIODS) / sizeof(PERIODS[0]); p++) {
            if (hour < PERIODS[p].from || hour >= PERIODS[p].to) {
                continue;
            }
            int count = 0;
            for (int i = 0; i < s->gap_count; i++) {
                if (s->gaps[i].hour >= PERIODS[p].from && s->gaps[i].hour < PERIODS[p].to) {
                    values[count++] = s->gaps[i].minutes;
                }
            }
            if (count >= PERIOD_MIN_SAMPLES) {
                return round10(p25(values, count));
            }
        }
    }
    for (int i = 0; i < s->gap_count; i++) {
        values[i] = s->gaps[i].minutes;
    }
    return round10(p25(values, s->gap_count));
}

void care_diaper_detail(const care_summary_t *s, time_t now, char *out, size_t len)
{
    static const char *const SHORT[] = { "", "소변", "대변", "소+대" };
    if (!s || !s->diaper.at) {
        snprintf(out, len, "기록 없음");
        return;
    }
    char at[24], poo[24];
    care_clock_on(s->diaper.at, now, false, at, sizeof(at));
    /* 소변 뒤에 대변이 따로 있었으면 그 시각도. 대변이 오늘이 아니면 자리가 없어 '소변'을 뺀다 */
    if (s->diaper.type == DIAPER_PEE && s->poo.at) {
        care_clock_on(s->poo.at, now, false, poo, sizeof(poo));
        snprintf(out, len, "%s%s 대 %s", at, days_before(s->poo.at, now) == 0 ? " 소변 ·" : " ·", poo);
        return;
    }
    snprintf(out, len, "%s · %s", at, SHORT[s->diaper.type]);
}

time_t care_parse_time(const char *text)
{
    int year, month, day, hour, minute, second, used = 0;
    if (!text || sscanf(text, "%d-%d-%d%*1[T ]%d:%d:%d%n", &year, &month, &day, &hour, &minute, &second, &used) != 6) {
        return 0;
    }
    /* 초 뒤의 소수는 버리고, 시간대(+09:00, +0900, +09, Z)를 읽는다 */
    const char *p = text + used;
    while (*p == '.' || (*p >= '0' && *p <= '9')) {
        p++;
    }
    long offset = 0;
    if (*p == '+' || *p == '-') {
        int h = 0, m = 0;
        if (sscanf(p + 1, "%2d:%2d", &h, &m) < 2) {
            sscanf(p + 1, "%2d%2d", &h, &m);
        }
        offset = (h * 3600L + m * 60L) * (*p == '-' ? -1 : 1);
    }
    /* 달력 날짜 → 1970-01-01 부터의 날 수 */
    year -= month <= 2;
    long era = (year >= 0 ? year : year - 399) / 400;
    long yoe = year - era * 400;
    long doy = (153 * (month + (month > 2 ? -3 : 9)) + 2) / 5 + day - 1;
    long days = era * 146097 + yoe * 365 + yoe / 4 - yoe / 100 + doy - 719468;
    return (time_t)(days * 86400LL + hour * 3600L + minute * 60L + second - offset);
}

static double minutes_since(time_t at, time_t now)
{
    return at ? difftime(now, at) / 60.0 : -1;
}

void care_duration(long seconds, char *out, size_t len)
{
    long minutes = seconds > 0 ? (seconds + 30) / 60 : 0;
    long h = minutes / 60, m = minutes % 60;
    if (!h) {
        snprintf(out, len, "%ld분", m);
    } else if (m) {
        snprintf(out, len, "%ld시간 %ld분", h, m);
    } else {
        snprintf(out, len, "%ld시간", h);
    }
}

void care_describe_action(const care_action_t *a, char *out, size_t len)
{
    static const char *const DIAPER[] = { "", "소변", "대변", "소변+대변" };
    char extra[32];
    switch (a->kind) {
    case ACT_FEED:
    case ACT_FEED_START:
        snprintf(out, len, "수유 %dml%s", a->ml, a->kind == ACT_FEED_START ? " · 먹이기 시작" : "");
        break;
    case ACT_FEED_FINISH:
        care_duration((long)difftime(a->at, a->started_at), extra, sizeof(extra));
        snprintf(out, len, "수유 %dml · %s", a->ml, extra);
        break;
    case ACT_DIAPER:
        snprintf(out, len, "기저귀 %s", DIAPER[a->diaper]);
        break;
    case ACT_SLEEP_START:
        care_clock(a->at, extra, sizeof(extra));
        snprintf(out, len, "잠 시작 %s", extra);
        break;
    case ACT_SLEEP_END:
        care_duration((long)difftime(a->at, a->started_at), extra, sizeof(extra));
        snprintf(out, len, "잠 %s", extra);
        break;
    default:
        out[0] = '\0';
        break;
    }
}

/* 물 양 → 완성량(10ml 단위 반올림). 210 → 233.3 → 230 */
static int ml_for_water(int water)
{
    return (int)((water / 30.0 * (100.0 / 3.0)) / 10.0 + 0.5) * 10;
}

int care_water_for(int ml)
{
    int water = (int)(ml / (100.0 / 3.0) * 30.0 / 30.0 + 0.5) * 30;
    int back = ml_for_water(water);
    return water >= 60 && water <= 300 && back - ml <= 1 && ml - back <= 1 ? water : 0;
}

int care_step_machine(int ml, int direction)
{
    /* 칸에 맞는 양이면 그 칸의 물 양에서, 아니면(220) 물 양을 거꾸로 셈해서 가까운 위/아래 칸으로 */
    int exact = care_water_for(ml);
    double steps = (exact ? exact : ml / (100.0 / 3.0) * 30.0) / 30.0;
    int n = direction > 0 ? (int)(steps + 0.02) + 1 : (int)(steps - 0.02 + 0.999999) - 1;
    int water = n * 30;
    water = water < 60 ? 60 : water > 300 ? 300 : water;
    return ml_for_water(water);
}

int care_clamp_amount(int ml)
{
    return ml < 5 ? 5 : ml > 500 ? 500 : ml;
}

void care_build_view(const care_summary_t *s, time_t now, bool happy, care_view_t *v)
{
    static const care_summary_t EMPTY = { .feed = { .ml = -1 } };
    static const char *const WEEKDAY[] = { "일요일", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일" };
    if (!s || !s->valid) {
        s = &EMPTY;
    }
    memset(v, 0, sizeof(*v));

    struct tm t = local(now);
    care_clock(now, v->clock, sizeof(v->clock));
    snprintf(v->today, sizeof(v->today), "%d년 %d월 %d일 %s", t.tm_year + 1900, t.tm_mon + 1, t.tm_mday, WEEKDAY[t.tm_wday]);
    if (s->age.has) {
        int n = snprintf(v->age, sizeof(v->age), "D+%d · %d개월 %d일", s->age.day, s->age.months, s->age.days);
        if (s->age.corrected && n > 0 && n < (int)sizeof(v->age)) {
            snprintf(v->age + n, sizeof(v->age) - n, " · 교정 %d개월 %d일", s->age.c_months, s->age.c_days);
        }
    }
    if (s->valid) {
        snprintf(v->total, sizeof(v->total), "오늘 %d회 · %dml", s->today.count, s->today.ml);
    }

    bool feeding = s->feed.at && s->feed.feeding && !s->feed.ended_at;
    bool sleeping = s->sleep.at && !s->sleep.ended_at;
    bool night = t.tm_hour >= NIGHT_START_HOUR || t.tm_hour < NIGHT_END_HOUR;

    /* 말풍선과 표정이 따를 항목: 먹이는 중 > 자는 중 > 급한 항목 > 밤 > 평온.
     * 급한 항목: 지난 시간 ÷ 기준 시간이 가장 크고 1 이상인 것 하나 */
    care_focus_t focus = FOCUS_FEED;
    const char *words = "기분 좋아요";
    v->mood = MOOD_NORMAL;
    v->feeding = feeding;
    v->sleeping = sleeping;
    if (happy) {
        v->mood = MOOD_HAPPY;
        focus = sleeping ? FOCUS_SLEEP : FOCUS_FEED;
        words = "고마워요!";
    } else if (feeding) {
        words = "냠냠";
    } else if (sleeping) {
        v->mood = MOOD_SLEEP;
        focus = FOCUS_SLEEP;
        words = "쿨쿨";
    } else {
        static const char *const URGENT_WORDS[] = { "배고파요…", "기저귀 봐 주세요…", "졸려요…" };
        const double minutes[] = { minutes_since(s->feed.at, now), minutes_since(s->diaper.at, now),
                                   s->sleep.ended_at ? minutes_since(s->sleep.ended_at, now) : -1 };
        const double limits[] = { care_hungry_minutes(s), DIAPER_MINUTES, AWAKE_MINUTES };
        double worst = 0;
        for (int i = 0; i < 3; i++) {
            double ratio = minutes[i] < 0 ? 0 : minutes[i] / limits[i];
            if (ratio >= 1 && ratio > worst) {
                worst = ratio;
                focus = (care_focus_t)i;
                v->urgent = true;
            }
        }
        if (v->urgent) {
            v->mood = MOOD_HUNGRY;
            words = URGENT_WORDS[focus];
        } else if (night) {
            v->mood = MOOD_SLEEP;
            words = "쉿, 밤이에요";
        }
    }
    snprintf(v->words, sizeof(v->words), "%s", words);

    char clock[24], clock2[24];

    /* 수유 칸 */
    snprintf(v->feed.title, sizeof(v->feed.title), feeding ? "수유 · 먹는 중" : "수유");
    v->feed.ago = care_ago(s->feed.at, now);
    v->feed.ongoing = feeding;
    v->feed.urgent = v->urgent && focus == FOCUS_FEED;
    if (!s->feed.at) {
        snprintf(v->feed.detail, sizeof(v->feed.detail), "기록 없음");
    } else {
        char ml[24] = "";
        if (s->feed.ml >= 0) {
            snprintf(ml, sizeof(ml), " · %dml", s->feed.ml);
        }
        if (feeding) {
            care_clock(s->feed.at, clock, sizeof(clock));
            snprintf(v->feed.detail, sizeof(v->feed.detail), "%s~%s", clock, ml);
        } else {
            care_clock_on(s->feed.at, now, false, clock, sizeof(clock));
            snprintf(v->feed.detail, sizeof(v->feed.detail), "%s%s", clock, ml);
        }
    }

    /* 기저귀 칸 */
    snprintf(v->diaper.title, sizeof(v->diaper.title), "기저귀");
    v->diaper.ago = care_ago(s->diaper.at, now);
    v->diaper.urgent = v->urgent && focus == FOCUS_DIAPER;
    care_diaper_detail(s, now, v->diaper.detail, sizeof(v->diaper.detail));

    /* 잠 칸: 자는 중이면 잠든 뒤, 아니면 깬 뒤 */
    v->sleep.urgent = v->urgent && focus == FOCUS_SLEEP;
    if (sleeping) {
        snprintf(v->sleep.title, sizeof(v->sleep.title), "잠 · 자는 중");
        v->sleep.ago = care_ago(s->sleep.at, now);
        v->sleep.ongoing = true;
        care_clock(s->sleep.at, clock, sizeof(clock));
        snprintf(v->sleep.detail, sizeof(v->sleep.detail), "%s~", clock);
    } else if (s->sleep.ended_at) {
        snprintf(v->sleep.title, sizeof(v->sleep.title), "잠 · 깬 지");
        v->sleep.ago = care_ago(s->sleep.ended_at, now);
        care_clock(s->sleep.at, clock, sizeof(clock));
        care_clock(s->sleep.ended_at, clock2, sizeof(clock2));
        snprintf(v->sleep.detail, sizeof(v->sleep.detail), "%s~%s", clock, clock2);
    } else {
        snprintf(v->sleep.title, sizeof(v->sleep.title), "잠");
        snprintf(v->sleep.detail, sizeof(v->sleep.detail), "기록 없음");
    }

    /* 말풍선: 고른 항목의 앞말 / 지난 시간 / 이름표. 앞말이 있어야 큰 숫자가 무엇의 시간인지 바로 읽힌다 */
    time_t from = 0;
    const char *prefix = "", *what = "", *none = "";
    if (focus == FOCUS_FEED) {
        from = s->feed.at;
        prefix = feeding ? "먹는 중" : "먹은 지";
        what = feeding ? "먹이기 시작" : "마지막 수유";
        none = "수유 기록 없음";
    } else if (focus == FOCUS_DIAPER) {
        from = s->diaper.at;
        prefix = "기저귀 간 지";
        what = "마지막 기저귀";
        none = "기저귀 기록 없음";
    } else {
        from = sleeping ? s->sleep.at : s->sleep.ended_at;
        prefix = sleeping ? "잠든 지" : "깬 지";
        what = sleeping ? "잠든 시각" : "깬 시각";
        none = "잠 기록 없음";
    }
    v->ago = care_ago(from, now);
    if (from) {
        care_clock_on(from, now, false, clock, sizeof(clock));
        snprintf(v->label, sizeof(v->label), "%s %s", what, clock);
    } else {
        snprintf(v->label, sizeof(v->label), "%s", none);
    }
    /* "방금"·기록 없음에는 앞말을 안 붙인다 */
    if (v->ago.has && (v->ago.hours || v->ago.minutes)) {
        snprintf(v->prefix, sizeof(v->prefix), "%s", prefix);
    }
}
