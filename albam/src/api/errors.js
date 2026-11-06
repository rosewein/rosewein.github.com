// 통신 오류 종류. 화면은 이 둘만 구분하면 된다.

/** 로그인이 없거나 풀렸거나, 가족 계정이 아님 → 로그인 화면으로 */
export class AuthError extends Error {
  name = 'AuthError';
}

/** 연결이 안 됨(오프라인, 시간 초과, 서버 5xx) → 기기 안에 쌓아 두고 나중에 다시 */
export class NetworkError extends Error {
  name = 'NetworkError';
}
