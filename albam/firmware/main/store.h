#pragma once
#include <stdbool.h>
#include <stddef.h>

/* 꺼져도 남는 작은 값(와이파이 이름·비밀번호, 무선 업데이트 번호) */
void store_init(void);
bool store_get(const char *key, char *out, size_t len);
void store_set(const char *key, const char *value);
