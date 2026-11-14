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

/* 화면에서 부른다. 결과는 care_state() 로 본다. 비밀번호는 저장하지 않고 갱신 토큰만 저장한다 */
void care_login(const char *email, const char *password);
void care_logout(void);
