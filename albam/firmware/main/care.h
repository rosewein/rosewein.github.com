#pragma once
/* 알밤보드 서버(Supabase)에서 요약을 읽어 온다. 웹앱의 src/api/supabase-rest.js 와 같은 HTTP 호출이다.
 *   로그인·토큰 갱신: POST /auth/v1/token      요약: POST /rest/v1/rpc/care_summary */
#include <stdbool.h>
#include <stdint.h>
#include "care_text.h"

typedef enum {
    CARE_STARTING,        /* 저장된 로그인으로 처음 읽는 중 */
    CARE_NEED_LOGIN,      /* 로그인한 적이 없거나 로그아웃함 */
    CARE_LOGGING_IN,
    CARE_LOGIN_FAILED,    /* 이메일이나 비밀번호가 다름 */
    CARE_LOGIN_OFFLINE,   /* 로그인하려는데 서버에 못 닿음 */
    CARE_NOT_FAMILY,      /* 가족 명단에 없는 계정 */
    CARE_OK,              /* 요약을 읽고 있음 */
    CARE_OFFLINE,         /* 로그인은 돼 있는데 지금 못 읽음(마지막 요약을 그대로 보여 준다) */
} care_state_t;

void care_start(void);
care_state_t care_state(void);
const char *care_email(void);

/* 문제를 찾을 때 보는 값: 읽은 횟수, 못 읽은 횟수와 마지막 까닭 */
typedef struct {
    int ok, fails, fails_in_a_row;
    int seconds_since_ok, seconds_since_error;   /* 없으면 -1 */
    char last_error[200];
} care_diag_t;
void care_diag(care_diag_t *out);

/* 요약이 *seen 뒤로 바뀌었으면 복사하고 true */
bool care_copy_summary(care_summary_t *out, uint32_t *seen);

/* ---- 기록하기 ----
 * 웹앱과 같은 서버 함수를 부른다: care_add_event(새 기록), care_update_event(다 먹음), care_set_sleep_end(깼어요),
 * care_cancel_event(취소). 한 번에 하나씩 하고, 끝나면 요약을 바로 다시 읽는다.
 * 연결이 안 되면 웹앱처럼 쌓아 두지 않고 "저장 못 했어요"로 끝난다. */
typedef enum {
    ACTION_IDLE,
    ACTION_BUSY,
    ACTION_SAVED,       /* 저장됨(취소도 여기) */
    ACTION_CONFIRM,     /* 비슷한 기록이 이미 있다 → 물어보고 force 로 다시 */
    ACTION_NOT_FOUND,   /* 먹이는 중인 수유·자는 중인 잠을 못 찾음 */
    ACTION_FAILED,
} care_action_status_t;

typedef struct {
    care_action_status_t status;
    care_action_t action;   /* 한 일. 새 기록이면 id 가 채워져 있다 */
    care_action_t existing; /* ACTION_CONFIRM: 이미 있는 기록(kind, at, ml, diaper) */
} care_action_result_t;

void care_do(const care_action_t *action);
void care_action_result(care_action_result_t *out);

/* ---- 오늘 기록 목록 ----
 * 목록 화면이 떠 있는 동안만(want) 요약과 함께 care_timeline(1일)을 읽는다 */
void care_want_timeline(bool want);
/* *seen 뒤로 바뀌었으면 복사하고 개수를, 그대로면 -1 을 준다. 아직 못 읽었으면 *seen 은 0 그대로 */
int care_copy_timeline(care_event_t *out, int max, uint32_t *seen);

/* 화면에서 부른다. 결과는 care_state() 로 본다. 비밀번호는 저장하지 않고 갱신 토큰만 저장한다 */
void care_login(const char *email, const char *password);
void care_logout(void);
