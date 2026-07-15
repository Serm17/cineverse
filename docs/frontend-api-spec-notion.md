# CineVerse 프론트엔드 API 연동 명세

> 작성 기준: 2026-07-15
> 기준 코드: `app/main.py`, `app/api/*`, `app/schemas/*`, `app/services/*`  
> 현재 OpenAPI: URL path 38개 / HTTP operation 39개

이 문서는 프론트엔드가 현재 백엔드에 바로 연동할 수 있도록 실제 요청 형식, 응답 필드, 인증 방식, 예외 사항을 한곳에 정리한 문서입니다.

## 빠른 찾기

- [1. 연동 전 필독](#1-연동-전-필독)
- [2. 공통 설정](#2-공통-설정)
- [3. 공통 타입](#3-공통-타입)
- [4. 전체 API 목록](#4-전체-api-목록)
- [5. Auth](#5-auth)
- [6. Movies](#6-movies)
- [7. User](#7-user)
- [8. Chat](#8-chat)
- [9. System](#9-system)
- [10. 프론트 체크리스트](#10-프론트-체크리스트)

---

## 1. 연동 전 필독

### 1.1 기본 주소

| 항목 | 값 |
| --- | --- |
| 로컬 Base URL | `http://127.0.0.1:8080` |
| Swagger | `http://127.0.0.1:8080/docs` |
| OpenAPI JSON | `http://127.0.0.1:8080/openapi.json` |
| 기본 요청 형식 | `application/json` |
| 파일 업로드 | `multipart/form-data` |
| 인증 헤더 | `Authorization: Bearer <access_token>` |

### 1.2 인증 표기

| 표기 | 의미 | 프론트 처리 |
| --- | --- | --- |
| 공개 | 토큰 없이 호출 | 별도 처리 없음 |
| 선택 | 토큰 없이도 호출 가능 | 로그인 상태면 access token 전송 |
| Access | access token 필수 | `Authorization` 헤더 전송 |
| Cookie | refresh cookie 사용 | `credentials: "include"` 또는 `withCredentials: true` |

### 1.3 현재 구현에서 반드시 알아둘 점

| 항목 | 현재 동작 | 프론트 처리 |
| --- | --- | --- |
| 비즈니스 실패 | 상당수 API가 HTTP 200 + `state: "failure"` 반환 | `response.ok`만 보지 말고 `state` 확인 |
| 회원가입 성공 | `state`가 아니라 `status: "success"` 사용 | `state ?? status`로 판정 |
| 랭킹 응답 | 공통 envelope 없이 배열을 바로 반환 | `Array.isArray(response)` 처리 |
| 1:1 캐릭터 채팅 | `POST /chat` 성공 시 항상 SSE | 일반 JSON 파싱 금지 |
| 기존 대화 이어가기 | 성공 시 항상 SSE이며 캐릭터가 필요함 | `content-type`을 먼저 확인 |
| 캐릭터 상세 경로 | 실제 경로가 `/chatcharcter/{character_name}` | 오타 경로 그대로 호출 |
| 채팅 추천 목록 경로 | 실제 경로가 `/user/chatai-reommended-movies` | 오타 경로 그대로 호출 |
| 영화 이미지 | `poster_path`/`poster_url`이 상대 경로 또는 전체 URL일 수 있음 | 이미지 URL 정규화 함수 사용 |
| Refresh cookie | cookie path가 `/auth`, `SameSite=Lax`, 개발 환경 `Secure=false` | 프론트/API의 host 표기를 통일 |

개발 중 `localhost`와 `127.0.0.1`을 섞으면 브라우저가 refresh cookie를 보내지 않을 수 있습니다. 프론트를 `http://127.0.0.1:5173`으로 열었다면 API도 `http://127.0.0.1:8080`으로 호출하는 방식으로 host를 맞추는 것을 권장합니다.

---

## 2. 공통 설정

### 2.1 허용된 로컬 Origin

| Origin |
| --- |
| `http://localhost:5173` |
| `http://127.0.0.1:5173` |
| `http://localhost:5174` |
| `http://127.0.0.1:5174` |

### 2.2 Axios 기본 인스턴스

```ts
import axios from "axios";

export const api = axios.create({
  baseURL: "http://127.0.0.1:8080",
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const accessToken = localStorage.getItem("access_token");

  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }

  return config;
});
```

`withCredentials`는 refresh cookie가 필요한 로그인, 재발급, 로그아웃에 필수입니다. 전역으로 켜 두면 API별로 빠뜨리는 실수를 줄일 수 있습니다.

### 2.3 공통 JSON 응답

대부분의 API는 아래 구조를 사용합니다.

```ts
type ApiState = "success" | "failure" | "error";

type ApiResponse<T> = {
  state: ApiState;
  message: string;
  data?: T;
  error?: string;
  detail?: string;
};
```

| 값 | 의미 | 권장 UI |
| --- | --- | --- |
| `success` | 정상 처리 | 결과 표시 |
| `failure` | 요청은 처리했지만 조건 불충족 | 안내/빈 상태 표시 |
| `error` | 서버 또는 외부 연동 오류 | 오류 안내 및 재시도 |

회원가입 일부 응답은 `state` 대신 `status`를 사용합니다.

```ts
function getApiState(response: {
  state?: string;
  status?: string;
}) {
  return response.state ?? response.status;
}
```

### 2.4 HTTP 오류 응답

`HTTPException`을 사용하는 API는 실제 4xx/5xx와 함께 오류 객체가 `detail` 안에 들어갑니다.

```json
{
  "detail": {
    "state": "failure",
    "message": "로그인이 필요합니다.",
    "code": "LOGIN_REQUIRED"
  }
}
```

반면 라우터 내부에서 예외를 잡아 JSON을 직접 반환하는 API는 HTTP 200일 수 있습니다. 두 형태를 모두 처리해야 합니다.

```ts
const body = error.response?.data;
const apiError = body?.detail ?? body;
```

### 2.5 요청 검증 실패

필수 필드 누락, 타입 오류, 길이 제한 위반은 FastAPI 기본 HTTP 422입니다.

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "email"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

### 2.6 Access token 오류 코드

| code | 의미 | 권장 처리 |
| --- | --- | --- |
| `LOGIN_REQUIRED` | access token 없음 | 로그인 화면 이동 |
| `ACCESS_TOKEN_EXPIRED` | access token 만료 | refresh 후 원 요청 1회 재시도 |
| `INVALID_ACCESS_TOKEN` | 서명 또는 형식 오류 | 토큰 제거 후 재로그인 |
| `INVALID_TOKEN_TYPE` | access token이 아닌 토큰 | 토큰 제거 후 재로그인 |
| `INVALID_TOKEN_PAYLOAD` | 사용자 정보가 없는 토큰 | 토큰 제거 후 재로그인 |
| `INVALID_AUTH_SCHEME` | Bearer 방식이 아님 | 헤더 구성 확인 |

### 2.7 토큰 갱신 흐름

1. 로그인 성공 시 `data.access_token`만 프론트 저장소에 저장합니다.
2. refresh token은 HttpOnly cookie이므로 JS에서 직접 읽지 않습니다.
3. Access API 호출 시 `Authorization: Bearer <token>`을 보냅니다.
4. HTTP 401 + `ACCESS_TOKEN_EXPIRED`이면 `POST /auth/refresh`를 호출합니다.
5. 새 access token을 저장하고 실패했던 요청을 한 번만 재시도합니다.
6. refresh가 실패하면 access token을 삭제하고 로그인 화면으로 이동합니다.

동시에 여러 요청이 401을 받으면 refresh 요청을 하나로 합치는 처리가 필요합니다. 무제한 재시도는 피해야 합니다.

### 2.8 캐시 정책

`/auth`, `/chat`, `/user`로 시작하는 응답에는 개인정보 캐시 방지를 위해 `Cache-Control: no-store` 계열 헤더가 추가됩니다.

---

## 3. 공통 타입

### 3.1 영화 목록 아이템

```ts
type MovieListItem = {
  movie_id: number;
  title: string;
  poster_path: string | null;
  vote_average: number | null;
  genres?: string[] | null;
  keyword?: string[] | null;
  cast?: string[] | null;
};
```

### 3.2 추천 영화 아이템

```ts
type RecommendedMovie = MovieListItem & {
  recommendation_score: number;
  reason: string;
  matched_preferences?: string[];
};
```

`matched_preferences`는 로그인 사용자의 개인화 추천에서만 내려올 수 있습니다.

### 3.3 영화 상세

```ts
type MovieDetail = {
  id: number;
  movie_id: number;
  tmdb_id: number | null;
  title: string;
  overview: string | null;
  genres: string[] | null;
  director: string | null;
  cast: string[] | null;
  keywords: string[] | null;
  year: number | null;
  language: string | null;
  vote_average: number | null;
  vote_count: number | null;
  audience_count: number | null;
  poster_path: string | null;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
};
```

### 3.4 캐릭터와 채팅방

```ts
type CharacterItem = {
  id: number;
  name: string;
  movie_title: string;
  profile_image: string | null;
};

type ChatRoom = {
  room_id: number;
  room_type: "general" | "character" | "group";
  characters: string[];
  created_at: string;
  updated_at: string;
};

type ChatMessage = {
  room_id: number;
  role: "user" | "assistant" | string;
  character: string | null;
  created_at: string;
  content: string;
  recommended_movies: Record<string, unknown>[];
};
```

### 3.5 사용자 선호

```ts
type PreferenceScore = {
  value: string;
  score: number;
};

type UserPreferences = {
  explicit_preferences: {
    genres: string[];
    actors: string[];
    keywords: string[];
  };
  learned_preferences: {
    genres: PreferenceScore[];
    actors: PreferenceScore[];
    keywords: PreferenceScore[];
  };
};
```

### 3.6 이미지 URL 처리

배우 이미지는 서버가 TMDB 전체 URL로 변환하지만 영화 포스터는 DB 값을 그대로 내려주는 API가 많습니다.

```ts
const TMDB_W500 = "https://image.tmdb.org/t/p/w500";

export function resolveMovieImage(path?: string | null) {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  return `${TMDB_W500}${path.startsWith("/") ? path : `/${path}`}`;
}
```

사용자 `profile_image`와 업로드 응답의 `user_profile`은 현재 API 서버의 전체 URL로 반환됩니다.

---

## 4. 전체 API 목록

### 4.1 Auth

| Method | Path | 인증 | 성공 HTTP | 설명 |
| --- | --- | --- | --- | --- |
| POST | `/auth/email-verification/request` | 공개 | 202 | 회원가입 인증번호 전송 |
| POST | `/auth/register` | 공개 | 200 | 인증번호 확인 후 회원가입 |
| POST | `/auth/password-reset/request` | 공개 | 202 | 비밀번호 재설정 메일 요청 |
| POST | `/auth/password-reset/confirm` | 공개 | 200 | 토큰으로 새 비밀번호 설정 |
| POST | `/auth/login` | Cookie | 200 | 로그인 및 refresh cookie 저장 |
| POST | `/auth/refresh` | Cookie | 200 | access token 재발급 |
| POST | `/auth/logout` | Cookie | 200 | refresh token 폐기 및 cookie 삭제 |

### 4.2 Movies

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| GET | `/movies/actors` | 공개 | 배우 목록 |
| POST | `/movies/actor/{actor_id}` | Access | 선호 배우 저장 |
| POST | `/movies/recommend` | 선택 | 기본/개인화 추천 |
| GET | `/movies/search` | 공개 | 영화 검색 |
| GET | `/movies/ranking` | 공개 | 실시간 랭킹 |
| GET | `/movies/{movie_id}` | 선택 | 영화 상세 및 선택적 행동 기록 |
| POST | `/movies/{movie_id}/like` | Access | 영화 좋아요 |
| GET | `/movies/today/recommend` | 공개 | 오늘의 AI 추천 |
| GET | `/movies/genre/{genre}` | 공개 | 장르별 영화 |
| POST | `/movies/ai-recommend` | 공개 | AI 서버 직접 추천 |

### 4.3 User

모든 User API는 access token이 필요합니다.

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/user` | 내 정보 |
| PATCH | `/user/profile_image` | 프로필 이미지 업로드/교체 |
| DELETE | `/user/delete/profile_image` | 프로필 이미지 삭제 |
| GET | `/user/preferences` | 명시적/학습된 선호 조회 |
| DELETE | `/user/preference/delete` | 명시적 선호 한 개 삭제 |
| GET | `/user/movies-like` | 좋아요 영화 |
| DELETE | `/user/movie-like/{movie_id}` | 영화 좋아요 삭제 |
| GET | `/user/recently-viewed` | 최근 상세 조회 영화 |
| GET | `/user/chatai-reommended-movies` | 채팅에서 추천받은 영화 |

### 4.4 Chat

| Method | Path | 인증 | 응답 | 설명 |
| --- | --- | --- | --- | --- |
| POST | `/chat/auto` | Access | JSON | 일반 AI 채팅 시작 |
| GET | `/chat/characters` | 공개 | JSON | 캐릭터 목록 |
| GET | `/chatcharcter/{character_name}` | 공개 | JSON | 캐릭터 단건 |
| POST | `/chat` | Access | SSE/JSON | 1:1 캐릭터 채팅 시작 |
| POST | `/chat/group` | Access | JSON | 그룹 채팅 시작 |
| GET | `/chat/rooms` | Access | JSON | 내 채팅방 목록 |
| GET | `/chat/rooms/{room_id}/messages` | Access | JSON | 메시지 목록 |
| POST | `/chat/rooms/{room_id}/messages` | Access | SSE/JSON | 기존 캐릭터 대화 이어가기 |
| DELETE | `/chat/rooms/{room_id}` | Access | JSON | 채팅방 삭제 |

### 4.5 System

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| GET | `/` | 공개 | API 실행 확인 |
| GET | `/health` | 공개 | 백엔드 상태 |
| GET | `/db-test` | 공개 | DB 연결 확인 |
| GET | `/ai-health` | 공개 | AI 서버 연결 확인 |

---

## 5. Auth

권장 화면 흐름:

```text
회원가입 화면
  └─ 인증번호 전송
       └─ 이메일로 받은 6자리 코드 입력
            └─ 회원가입

비밀번호 찾기
  └─ 재설정 메일 요청
       └─ 이메일 링크의 token 추출
            └─ 새 비밀번호 설정
```

### 5.1 회원가입 인증번호 전송

#### `POST /auth/email-verification/request`

인증: 공개  
성공 상태: HTTP 202

요청:

```json
{
  "email": "user@example.com"
}
```

성공:

```json
{
  "state": "success",
  "message": "인증번호를 이메일로 전송했습니다.",
  "data": {
    "expires_in_seconds": 300
  }
}
```

| HTTP | 상황 |
| --- | --- |
| 202 | 전송 성공 |
| 409 | 이미 가입된 이메일 |
| 429 | 재전송 제한 시간 내 재요청 |
| 503 | 이메일 발송 실패 |
| 500 | 인증번호 생성 실패 |
| 422 | 이메일 형식 오류 |

429 응답의 `detail.message`에 남은 초가 포함됩니다.

```json
{
  "detail": {
    "state": "failure",
    "message": "42초 후 다시 요청해주세요."
  }
}
```

### 5.2 회원가입

#### `POST /auth/register`

인증: 공개  
성공 상태: HTTP 200

요청:

```json
{
  "email": "user@example.com",
  "password": "password1234",
  "nickname": "무비러버",
  "verification_code": "123456"
}
```

| 필드 | 타입 | 필수 | 제한 |
| --- | --- | --- | --- |
| `email` | string | 예 | 이메일 형식 |
| `password` | string | 예 | 현재 스키마상 길이 제한 없음 |
| `nickname` | string | 예 | 현재 스키마상 길이 제한 없음 |
| `verification_code` | string | 예 | 숫자 6자리 |

성공:

```json
{
  "status": "success",
  "message": "회원가입 성공",
  "data": {
    "id": 1,
    "email": "user@example.com",
    "nickname": "무비러버"
  }
}
```

실패 예:

```json
{
  "state": "failure",
  "message": "회원가입 실패 - 이메일 중복"
}
```

인증번호가 틀렸거나 만료된 경우도 현재 HTTP 200입니다.

```json
{
  "state": "error",
  "message": "인증 에러",
  "error": "인증번호가 올바르지 않습니다.남은 입력 횟수 : 4회"
}
```

프론트는 이 API에서만 성공 키가 `status`임을 주의해야 합니다.

### 5.3 비밀번호 재설정 메일 요청

#### `POST /auth/password-reset/request`

인증: 공개  
성공 상태: HTTP 202

요청:

```json
{
  "email": "user@example.com"
}
```

응답:

```json
{
  "state": "success",
  "message": "가입된 이메일이면 비밀번호 재설정 링크가 전송됩니다."
}
```

가입되지 않은 이메일도 계정 존재 여부가 노출되지 않도록 같은 202 응답을 반환합니다.

| HTTP | 상황 |
| --- | --- |
| 202 | 요청 접수 |
| 503 | 이메일 발송 실패 |
| 500 | 재설정 토큰 생성 실패 |
| 422 | 이메일 형식 오류 |

메일 링크 형식:

```text
{FRONTEND_BASE_URL}/reset-password?token={token}
```

프론트의 재설정 페이지는 URL의 `token` query parameter를 읽어 다음 API에 전달해야 합니다.

### 5.4 새 비밀번호 설정

#### `POST /auth/password-reset/confirm`

인증: 공개  
성공 상태: HTTP 200

요청:

```json
{
  "token": "email-link-token",
  "new_password": "newPassword1234"
}
```

| 필드 | 제한 |
| --- | --- |
| `token` | 32~512자 |
| `new_password` | 8~128자 |

성공:

```json
{
  "state": "success",
  "message": "비밀번호가 변경되었습니다."
}
```

유효하지 않음, 만료, 이미 사용됨, 폐기된 링크는 HTTP 400입니다.

```json
{
  "detail": {
    "state": "failure",
    "message": "만료된 비밀번호 재설정 링크입니다."
  }
}
```

비밀번호가 변경되면 해당 사용자의 기존 refresh token이 모두 폐기됩니다.

### 5.5 로그인

#### `POST /auth/login`

인증: Cookie  
프론트 옵션: `credentials: "include"` / `withCredentials: true`

요청:

```json
{
  "email": "user@example.com",
  "password": "password1234"
}
```

성공:

```json
{
  "state": "success",
  "message": "로그인 성공",
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "email": "user@example.com",
    "nickname": "무비러버"
  }
}
```

성공 시 응답 헤더의 `Set-Cookie`로 HttpOnly `refresh_token`이 저장됩니다. 로그인 실패는 현재 HTTP 200입니다.

### 5.6 Access token 재발급

#### `POST /auth/refresh`

인증: Cookie  
요청 body: 없음  
프론트 옵션: `credentials: "include"` / `withCredentials: true`

성공:

```json
{
  "state": "success",
  "message": "토큰 재발급 성공",
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "email": "user@example.com"
  }
}
```

refresh cookie 없음, 만료, 폐기, 검증 실패는 현재 대부분 HTTP 200 + `state: "failure"`입니다.

### 5.7 로그아웃

#### `POST /auth/logout`

인증: Cookie  
요청 body: 없음  
프론트 옵션: `credentials: "include"` / `withCredentials: true`

성공:

```json
{
  "state": "success",
  "message": "로그아웃 성공",
  "data": {
    "detail": "클라이언트 쪽에서 access_token, refresh_token 삭제"
  }
}
```

서버는 DB refresh token을 폐기하고 cookie를 삭제합니다. 프론트도 저장한 access token을 직접 제거해야 합니다.

```ts
await api.post("/auth/logout");
localStorage.removeItem("access_token");
```

---

## 6. Movies

### 6.1 배우 목록

#### `GET /movies/actors`

인증: 공개

성공:

```json
{
  "state": "success",
  "message": "배우 조회 성공",
  "data": [
    {
      "actor_id": 1,
      "actor_name": "Leonardo DiCaprio",
      "profile_path": "https://image.tmdb.org/t/p/w500/profile.jpg"
    }
  ]
}
```

`profile_path`는 `string | null`이며 상대 TMDB 경로는 서버가 `w500` 전체 URL로 변환합니다.

### 6.2 선호 배우 저장

#### `POST /movies/actor/{actor_id}`

인증: Access  
요청 body: 없음

| Path | 타입 | 설명 |
| --- | --- | --- |
| `actor_id` | number | `GET /movies/actors`의 배우 ID |

성공:

```json
{
  "state": "success",
  "message": "선호 배우 저장 성공",
  "data": {
    "user_email": "user@example.com",
    "user_preferred_actors": ["Leonardo DiCaprio"]
  }
}
```

이미 선택한 배우이거나 배우 ID가 없으면 HTTP 200 + `state: "failure"`입니다.

### 6.3 기본/개인화 추천

#### `POST /movies/recommend?limit=12`

인증: 선택  
요청 body: 없음

| Query | 타입 | 기본값 | 제한 |
| --- | --- | --- | --- |
| `limit` | number | 12 | 1~30 |

비로그인은 인기·평점 기반 추천을, access token을 보낸 로그인 사용자는 학습된 취향을 반영한 추천을 받습니다.

성공:

```json
{
  "state": "success",
  "message": "영화 추천 API입니다.",
  "data": [
    {
      "movie_id": 1,
      "title": "Inception",
      "poster_path": "/poster.jpg",
      "genres": ["Action", "Sci-Fi"],
      "vote_average": 8.4,
      "recommendation_score": 9.231,
      "reason": "좋아하는 장르 'Action'와 잘 맞는 영화",
      "matched_preferences": ["genre:Action"]
    }
  ]
}
```

현재 키 이름은 `reson`이 아니라 `reason`입니다. `matched_preferences`는 비로그인 추천에는 없습니다.

### 6.4 영화 검색

#### `GET /movies/search`

인증: 공개

| Query | 타입 | 필수 | 기본값 | 제한 |
| --- | --- | --- | --- | --- |
| `keyword` | string | 예 | - | 1자 이상 |
| `page` | number | 아니오 | 1 | 1 이상 |
| `limit` | number | 아니오 | 20 | 1~50 |

제목, 줄거리, 감독, 언어, 배우, 장르, 키워드에서 검색합니다.

요청 예:

```http
GET /movies/search?keyword=인셉션&page=1&limit=20
```

성공:

```json
{
  "state": "success",
  "message": "검색 성공",
  "data": [
    {
      "movie_id": 1,
      "title": "Inception",
      "genres": ["Action", "Sci-Fi"],
      "keyword": ["dream"],
      "cast": ["Leonardo DiCaprio"],
      "poster_path": "/poster.jpg",
      "vote_average": 8.4
    }
  ]
}
```

결과가 없으면 HTTP 200 + `state: "failure"`이며, 현재 전체 건수/전체 페이지 값은 반환하지 않습니다.

### 6.5 실시간 영화 랭킹

#### `GET /movies/ranking?limit=10`

인증: 공개

| Query | 타입 | 기본값 | 제한 |
| --- | --- | --- | --- |
| `limit` | number | 10 | 1~100 |

성공 응답은 envelope이 없는 배열입니다.

```json
[
  {
    "id": 1,
    "title": "Inception",
    "poster_path": "/poster.jpg",
    "view_count": 15,
    "search_click_count": 3,
    "like_count": 2,
    "ranking_score": 20
  }
]
```

통계 row가 없는 영화도 포함하므로 카운트와 `ranking_score`는 `null`일 수 있습니다. 이 API의 영화 ID 키는 `movie_id`가 아니라 `id`입니다.

### 6.6 영화 상세

#### `GET /movies/{movie_id}?source=direct`

인증: 선택

| 위치 | 이름 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| Path | `movie_id` | number | - | DB 내부 영화 ID |
| Query | `source` | string | `direct` | `search`이면 검색 클릭, 그 외 일반 조회 |

비로그인도 조회할 수 있습니다. 로그인 사용자는 `view` 또는 `search_click` 행동과 취향 점수가 기록됩니다.

성공:

```json
{
  "state": "success",
  "message": "영화 조회 성공",
  "data": {
    "id": 1,
    "movie_id": 1,
    "tmdb_id": 27205,
    "title": "Inception",
    "overview": "A thief who steals corporate secrets...",
    "genres": ["Action", "Sci-Fi"],
    "director": "Christopher Nolan",
    "cast": ["Leonardo DiCaprio", "Joseph Gordon-Levitt"],
    "keywords": ["dream", "subconscious"],
    "year": 2010,
    "language": "en",
    "vote_average": 8.4,
    "vote_count": 37000,
    "audience_count": null,
    "poster_path": "/poster.jpg",
    "last_synced_at": "2026-07-14T00:00:00Z",
    "created_at": "2026-07-14T00:00:00Z",
    "updated_at": "2026-07-14T00:00:00Z"
  }
}
```

없는 영화는 HTTP 200 + `state: "failure"`입니다.

### 6.7 영화 좋아요

#### `POST /movies/{movie_id}/like`

인증: Access  
요청 body: 없음

성공:

```json
{
  "state": "success",
  "message": "좋아요 API 성공했습니다.",
  "user_id": 1,
  "movie_id": 10,
  "interaction_id": 99
}
```

이미 좋아요한 영화:

```json
{
  "state": "failure",
  "message": "이미 좋아요를 누른 영화입니다.",
  "user_id": 1,
  "movie_id": 10
}
```

좋아요 생성 시 영화 랭킹과 사용자 학습 취향 점수가 함께 갱신됩니다. 또한 현재 구현은 해당 영화의 장르·배우·키워드를 사용자 `preferred_*` 배열에도 추가합니다.

### 6.8 오늘의 AI 영화 추천

#### `GET /movies/today/recommend`

인증: 공개

성공:

```json
{
  "state": "success",
  "message": "오늘의 AI 추천 영화 조회 성공",
  "data": {
    "answer": "오늘은 몰입감 있는 SF의 세계로 떠나보세요.",
    "movies": [
      {
        "movie_id": 1,
        "tmdb_id": 27205,
        "title": "Inception",
        "year": 2010,
        "genres": "Action, Sci-Fi",
        "director": "Christopher Nolan",
        "cast": "Leonardo DiCaprio",
        "vote_average": 8.4,
        "overview": "짧게 줄인 줄거리",
        "poster_url": "/poster.jpg"
      }
    ]
  }
}
```

오늘 데이터가 DB에 있으면 캐시를 반환하고, 없으면 AI 서버 결과를 저장한 뒤 반환합니다. 최초 AI 응답과 DB 캐시 응답 사이에 추가 필드 차이가 생길 수 있으므로 `movies`의 불필요한 필드에는 의존하지 않는 것을 권장합니다. 캐시 응답의 `genres`와 `cast`는 배열이 아니라 쉼표로 연결된 문자열입니다.

### 6.9 장르별 영화

#### `GET /movies/genre/{genre}`

인증: 공개

| 위치 | 이름 | 타입 | 기본값 | 제한 |
| --- | --- | --- | --- | --- |
| Path | `genre` | string | - | DB에 저장된 장르명과 정확히 일치 |
| Query | `page` | number | 1 | 1 이상 |
| Query | `limit` | number | 20 | 1~50 |

성공:

```json
{
  "state": "success",
  "message": "장르별 영화 성공",
  "data": [
    {
      "movie_id": 1,
      "title": "Inception",
      "poster_path": "/poster.jpg",
      "vote_average": 8.4
    }
  ]
}
```

현재 서비스는 결과 없음에도 빈 배열을 반환하므로 성공 응답의 `data`가 빈 배열일 수 있습니다.

### 6.10 AI 서버 직접 추천

#### `POST /movies/ai-recommend`

인증: 공개

요청:

```json
{
  "user_id": 1,
  "prompt": "오늘 볼 영화 추천해줘",
  "genres": ["Action", "Drama"]
}
```

| 필드 | 타입 | 필수 | 기본값 |
| --- | --- | --- | --- |
| `user_id` | number | 예 | - |
| `prompt` | string \| null | 아니오 | `null` |
| `genres` | string[] | 아니오 | `[]` |

성공:

```json
{
  "state": "success",
  "message": "AI 영화 추천 성공",
  "data": {
    "answer": "추천 답변",
    "movies": []
  }
}
```

이 API는 access token을 사용하지 않고 request body의 `user_id`를 AI 서버에 전달합니다. `movies` 내부 구조는 외부 AI 응답에 따라 달라질 수 있습니다.

---

## 7. User

이 장의 모든 API는 `Authorization: Bearer <access_token>`이 필요합니다.

### 7.1 내 정보

#### `GET /user`

성공:

```json
{
  "state": "success",
  "message": "정보 조회 성공",
  "data": {
    "email": "user@example.com",
    "nickname": "무비러버",
    "profile_image": "http://127.0.0.1:8080/profile_images/profile_x.jpg"
  }
}
```

`profile_image`는 `string | null`입니다.

### 7.2 프로필 이미지 업로드/교체

#### `PATCH /user/profile_image`

Content-Type: `multipart/form-data`

| Form field | 타입 | 필수 | 제한 |
| --- | --- | --- | --- |
| `image` | File | 예 | JPEG, PNG, WebP / 최대 5MB |

브라우저에서 `FormData` 사용 시 `Content-Type` 헤더를 직접 지정하지 말고 boundary를 브라우저가 만들게 둡니다.

```ts
const formData = new FormData();
formData.append("image", file);

const response = await api.patch("/user/profile_image", formData);
```

성공:

```json
{
  "state": "success",
  "message": "이미지 수정 성공",
  "data": {
    "user_profile": "http://127.0.0.1:8080/profile_images/profile_x.jpg"
  }
}
```

형식/용량 검증 실패는 현재 HTTP 200 + `state: "failure"`입니다.

### 7.3 프로필 이미지 삭제

#### `DELETE /user/delete/profile_image`

요청 body: 없음

성공:

```json
{
  "state": "success",
  "message": "사용자 프로필 이미지 삭제 성공"
}
```

프로필 이미지가 없거나 서버 파일을 찾지 못하면 HTTP 200 + `state: "failure"`입니다.

### 7.4 내 선호 정보

#### `GET /user/preferences`

성공:

```json
{
  "state": "success",
  "message": "취향 조회 성공",
  "data": {
    "explicit_preferences": {
      "genres": ["Action", "Drama"],
      "actors": ["Leonardo DiCaprio"],
      "keywords": ["dream"]
    },
    "learned_preferences": {
      "genres": [
        {
          "value": "Action",
          "score": 4.8
        }
      ],
      "actors": [],
      "keywords": []
    }
  }
}
```

| 구분 | 의미 |
| --- | --- |
| `explicit_preferences` | User의 `preferred_*` 배열에 저장된 취향. 현재는 직접 선택뿐 아니라 영화 좋아요로도 추가됨 |
| `learned_preferences` | 조회, 검색 클릭, 좋아요 행동으로 누적된 취향 점수 |

학습 점수는 소수점 셋째 자리까지 반올림됩니다. 감독/언어 등 내부 학습값은 현재 이 응답에서 제외됩니다.

### 7.5 명시적 선호 한 개 삭제

#### `DELETE /user/preference/delete`

요청:

```json
{
  "preference_type": "genre",
  "preference_value": "Action"
}
```

허용 `preference_type`:

| 값 | 의미 |
| --- | --- |
| `genre` | 장르 |
| `actor` | 배우 |
| `keyword` | 키워드 |

성공:

```json
{
  "state": "success",
  "message": "사용자의 선호값 삭제 성공",
  "data": {
    "preferred_genres": [],
    "preferred_actors": ["Leonardo DiCaprio"],
    "preferred_keywords": ["dream"]
  }
}
```

이 API는 User의 `preferred_*` 배열 값만 삭제하며 학습된 점수 목록은 삭제하지 않습니다.

### 7.6 좋아요 영화

#### `GET /user/movies-like`

성공:

```json
{
  "state": "success",
  "message": "좋아요 누른 영화 조회 성공",
  "data": [
    {
      "movie_id": 1,
      "title": "Inception",
      "genres": ["Action", "Sci-Fi"],
      "keyword": ["dream"],
      "cast": ["Leonardo DiCaprio"],
      "poster_path": "/poster.jpg",
      "vote_average": 8.4
    }
  ]
}
```

좋아요가 없으면 현재 `data` 없이 `state: "failure"`를 반환합니다.

### 7.7 영화 좋아요 삭제

#### `DELETE /user/movie-like/{movie_id}`

| Path | 타입 | 설명 |
| --- | --- | --- |
| `movie_id` | number | DB 내부 영화 ID |

성공:

```json
{
  "state": "success",
  "message": "좋아요 누른 영화 삭제 성공"
}
```

삭제할 기록이 없으면:

```json
{
  "state": "failure",
  "message": "삭제할 좋아요 기록이 없습니다.",
  "data": {
    "movie_id": 1
  }
}
```

삭제 시 좋아요로 반영된 랭킹/학습 취향 점수가 함께 차감됩니다. 취소한 영화의 장르·배우·키워드가 다른 좋아요 영화에서도 사용되지 않으면 User의 `preferred_*` 배열에서도 제거됩니다. 현재 구현은 값의 최초 추가 경로를 구분하지 않으므로, 같은 값을 사용자가 직접 선택했더라도 다른 좋아요 영화가 사용하지 않으면 함께 제거될 수 있습니다.

### 7.8 최근 상세 조회 영화

#### `GET /user/recently-viewed?limit=5`

| Query | 타입 | 기본값 | 제한 |
| --- | --- | --- | --- |
| `limit` | number | 5 | 1~50 |

성공:

```json
{
  "state": "success",
  "message": "최근 조회한 영화 조회 성공",
  "data": [
    {
      "movie_id": 1,
      "title": "Inception",
      "genres": ["Action", "Sci-Fi"],
      "keyword": ["dream"],
      "cast": ["Leonardo DiCaprio"],
      "poster_path": "/poster.jpg",
      "vote_average": 8.4
    }
  ]
}
```

최근 조회가 없거나 내부 오류가 발생해도 이 API는 `data: []`를 포함합니다.

### 7.9 채팅에서 추천받은 영화

#### `GET /user/chatai-reommended-movies?limit=10`

경로에 `chatai`와 `reommended` 오타가 포함된 현재 실제 URL입니다.

| Query | 타입 | 기본값 | 제한 | 의미 |
| --- | --- | --- | --- | --- |
| `limit` | number | 10 | 1~50 | 조회할 assistant 메시지 수 |

성공:

```json
{
  "state": "success",
  "message": "ai가 추천한 영화 API 성공",
  "data": [
    {
      "tmdb_id": 27205,
      "title": "Inception",
      "poster_url": "/poster.jpg"
    }
  ]
}
```

`data`는 assistant 메시지의 `recommended_movies` snapshot을 최신순으로 모은 결과입니다. `tmdb_id` 기준으로 중복 제거하며 내부 필드는 AI 응답에 따라 달라질 수 있습니다. 추천 기록이 없어도 현재 구현은 성공 + 빈 배열을 반환합니다.

---

## 8. Chat

### 8.1 SSE 처리 규칙

아래 두 API는 성공 시 `text/event-stream`입니다.

- `POST /chat`
- `POST /chat/rooms/{room_id}/messages`

SSE 성공과 JSON 실패가 같은 URL에서 나올 수 있으므로 `content-type`을 먼저 확인합니다.

```ts
async function requestChatStream(
  path: string,
  body: Record<string, unknown>,
  accessToken: string,
  onToken: (token: string) => void,
) {
  const response = await fetch(`http://127.0.0.1:8080${path}`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(body),
  });

  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    return {
      kind: "json" as const,
      data: await response.json(),
    };
  }

  if (!response.ok || !response.body) {
    throw new Error("채팅 스트림 연결에 실패했습니다.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });

    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const event of events) {
      for (const line of event.split("\n")) {
        if (!line.startsWith("data:")) continue;

        const raw = line.slice(5).trim();
        if (raw === "[DONE]") {
          return { kind: "stream" as const };
        }

        try {
          const parsed = JSON.parse(raw);
          const token =
            typeof parsed === "string"
              ? parsed
              : (parsed.answer ?? "");
          if (token) onToken(token);
        } catch {
          if (raw) onToken(raw);
        }
      }
    }

    if (done) break;
  }

  return { kind: "stream" as const };
}
```

백엔드는 AI 서버에서 받은 `data: "문자열"`과 `data: {"answer":"..."}`를 파싱한 뒤, 프론트에는 답변 조각을 항상 JSON 문자열인 `data: "..."` 형식으로 정규화해 전달합니다. 답변 시작 부분의 `<|channel...>` 내부 제어 접두사는 제거하며, 종료 이벤트 `data: [DONE]`은 그대로 전달합니다. 따라서 프론트는 위 예시처럼 JSON 문자열을 우선 파싱하되, 이전 형식과의 호환을 위해 객체와 일반 문자열도 방어적으로 처리하는 것을 권장합니다.

### 8.2 일반 AI 채팅 시작

#### `POST /chat/auto`

인증: Access  
응답: JSON

요청:

```json
{
  "message": "오늘 볼 영화 추천해줘",
  "character": null
}
```

| 필드 | 타입 | 필수 | 제한 |
| --- | --- | --- | --- |
| `message` | string | 예 | 1자 이상 |
| `character` | string \| null | 아니오 | 활성 캐릭터 이름 또는 별칭 |

성공:

```json
{
  "state": "success",
  "message": "채팅 응답에 성공했습니다.",
  "data": {
    "room_id": 1,
    "answer": "오늘은 가볍게 볼 수 있는 영화를 추천할게요.",
    "character": null,
    "intent": "recommend",
    "movies": []
  }
}
```

`movies` 내부 구조는 AI 응답에 따라 달라집니다.

### 8.3 채팅 캐릭터 목록

#### `GET /chat/characters`

인증: 공개

성공:

```json
{
  "state": "success",
  "message": "채팅 캐릭터 조회 성공",
  "data": [
    {
      "id": 1,
      "name": "토니 스타크",
      "movie_title": "Iron Man",
      "profile_image": "https://example.com/profile.jpg"
    }
  ]
}
```

`profile_image`는 `string | null`입니다.

### 8.4 캐릭터 단건

#### `GET /chatcharcter/{character_name}`

인증: 공개

현재 라우터에 앞쪽 슬래시가 빠지고 `character` 철자가 틀려 실제 OpenAPI 경로가 위와 같이 생성됩니다. 권장 경로가 아니라 현재 호출 가능한 실제 경로입니다.

요청 예:

```ts
const name = encodeURIComponent("토니 스타크");
const response = await api.get(`/chatcharcter/${name}`);
```

성공:

```json
{
  "state": "success",
  "message": "캐릭터 정보 조회 성공",
  "data": {
    "id": 1,
    "name": "토니 스타크",
    "profile_image": "https://example.com/profile.jpg"
  }
}
```

정식 이름과 등록된 별칭을 모두 받을 수 있습니다. 단건 응답에는 `movie_title`이 없습니다.

### 8.5 1:1 캐릭터 채팅 시작

#### `POST /chat`

인증: Access  
성공 응답: `text/event-stream`

요청:

```json
{
  "message": "오늘 기분에 맞는 영화 추천해줘",
  "character": "토니 스타크"
}
```

| 필드 | 타입 | 필수 | 제한 |
| --- | --- | --- | --- |
| `message` | string | 예 | 1자 이상 |
| `character` | string | 예 | 1자 이상, 활성 캐릭터 이름/별칭 |

현재 요청 스키마에 `stream` 필드는 없습니다. 성공하면 항상 SSE이고, 스트림 종료 후 서버가 합친 assistant 답변을 저장합니다.

지원하지 않는 캐릭터 등 스트림 시작 전 실패는 HTTP 200 JSON입니다.

```json
{
  "state": "failure",
  "message": "지원하지 않는 캐릭터입니다.",
  "data": {
    "character": "없는 캐릭터"
  }
}
```

현재 SSE에는 새 `room_id`가 포함되지 않습니다. 스트림 종료 후 방 ID가 필요하면 `GET /chat/rooms`를 다시 조회해야 합니다.

### 8.6 그룹 캐릭터 채팅 시작

#### `POST /chat/group`

인증: Access  
응답: JSON

요청:

```json
{
  "characters": ["토니 스타크", "조커"],
  "message": "둘이서 오늘 볼 영화 하나 골라줘"
}
```

| 필드 | 타입 | 제한 |
| --- | --- | --- |
| `characters` | string[] | 서비스 검증 기준 2~5명 |
| `message` | string | 공백 문자열 불가 |

성공:

```json
{
  "state": "success",
  "message": "그룹 채팅 응답에 성공했습니다.",
  "data": {
    "room_id": 3,
    "intent": "recommend",
    "rounds": [
      {
        "round": 1,
        "label": "첫 번째 의견",
        "responses": [
          {
            "character": "토니 스타크",
            "answer": "기술과 상상력이 있는 영화가 좋겠어."
          }
        ]
      }
    ],
    "movies": []
  }
}
```

### 8.7 내 채팅방 목록

#### `GET /chat/rooms`

인증: Access

성공:

```json
{
  "state": "success",
  "message": "채팅방 목록 조회에 성공했습니다.",
  "data": [
    {
      "room_id": 1,
      "room_type": "general",
      "characters": [],
      "created_at": "2026-07-14T00:00:00Z",
      "updated_at": "2026-07-14T00:00:00Z"
    }
  ]
}
```

최신 `updated_at` 순이며 현재 pagination은 없습니다.

### 8.8 채팅 메시지 목록

#### `GET /chat/rooms/{room_id}/messages`

인증: Access

성공:

```json
{
  "state": "success",
  "message": "채팅 메시지 목록 조회에 성공했습니다.",
  "data": [
    {
      "room_id": 1,
      "role": "user",
      "character": null,
      "created_at": "2026-07-14T00:00:00Z",
      "content": "오늘 볼 영화 추천해줘",
      "recommended_movies": []
    },
    {
      "room_id": 1,
      "role": "assistant",
      "character": null,
      "created_at": "2026-07-14T00:00:01Z",
      "content": "오늘은 이 영화를 추천해요.",
      "recommended_movies": []
    }
  ]
}
```

메시지는 오래된 순이며 현재 pagination은 없습니다. 없는 방과 다른 사용자의 방은 동일하게 `state: "failure"`를 반환합니다.

### 8.9 기존 캐릭터 대화 이어가기

#### `POST /chat/rooms/{room_id}/messages`

인증: Access  
성공 응답: `text/event-stream`

요청:

```json
{
  "content": "다른 영화도 추천해줘",
  "character": "토니 스타크"
}
```

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `content` | string | 예 | 1자 이상 |
| `character` | string \| null | 아니오 | 새 캐릭터로 변경할 때 전달 |

현재 동작 제약:

| 방 상태 | 결과 |
| --- | --- |
| 1:1 방에 기존 캐릭터 있음 | SSE 성공 |
| 일반 방 + 요청에 `character` 제공 | 캐릭터 지정 후 SSE 성공 |
| 일반 방 + `character` 없음 | JSON failure |
| 그룹 방 | JSON failure |
| 방 없음/내 방 아님 | JSON failure |

일반 방에서 캐릭터 없이 JSON 일반 대화를 이어가는 기능과 그룹 방 이어가기는 현재 이 라우트에서 지원하지 않습니다.

### 8.10 채팅방 삭제

#### `DELETE /chat/rooms/{room_id}`

인증: Access

성공:

```json
{
  "state": "success",
  "message": "채팅방 삭제에 성공했습니다."
}
```

없는 방과 다른 사용자의 방은 동일하게 HTTP 200 + `state: "failure"`를 반환합니다.

---

## 9. System

### 9.1 API 실행 확인

#### `GET /`

```json
{
  "state": "success",
  "message": "CineVerse API is running"
}
```

### 9.2 백엔드 상태

#### `GET /health`

```json
{
  "state": "success",
  "message": "CineVerse"
}
```

### 9.3 DB 연결 확인

#### `GET /db-test`

성공:

```json
{
  "state": "success",
  "message": "PostgreSQL 연결 성공"
}
```

실패 시 이 API는 `state`가 아니라 `status: "failure"`를 사용합니다.

### 9.4 AI 서버 연결 확인

#### `GET /ai-health`

성공:

```json
{
  "state": "success",
  "message": "AI 서버 연결에 성공했습니다.",
  "ai_base_url": "http://210.109.15.251",
  "status_code": 200
}
```

AI 서버 timeout/연결 실패도 현재 HTTP 200 + `state: "error"`입니다.

---

## 10. 프론트 체크리스트

### 10.1 인증

- 로그인, refresh, logout 요청에 cookie 포함 옵션을 켰는가?
- access token을 회원 전용 요청의 Bearer 헤더에 넣었는가?
- HTTP 401 중 `ACCESS_TOKEN_EXPIRED`에서만 refresh 후 1회 재시도하는가?
- refresh 실패/로그아웃 시 프론트 access token을 삭제하는가?
- 로컬 개발에서 `localhost`와 `127.0.0.1`을 섞지 않았는가?

### 10.2 응답

- HTTP 200이어도 `state === "failure" | "error"`를 처리하는가?
- 회원가입의 `status` 키를 처리하는가?
- `HTTPException` 오류의 `detail` 래퍼를 처리하는가?
- 422 `detail[]`을 폼 필드 오류로 변환하는가?
- 랭킹 API의 raw array를 별도로 처리하는가?

### 10.3 영화/이미지

- `poster_path`와 `poster_url`의 상대/전체 URL을 모두 처리하는가?
- 오늘의 추천 `genres`/`cast`가 문자열일 수 있음을 처리하는가?
- 검색 결과의 키가 `keywords`가 아니라 `keyword`임을 반영했는가?
- 랭킹의 ID 키가 `movie_id`가 아니라 `id`임을 반영했는가?

### 10.4 채팅

- `POST /chat` 요청에서 `stream` 필드를 보내지 않는가?
- SSE/JSON을 `content-type`으로 분기하는가?
- `[DONE]`에서 로딩 상태를 종료하는가?
- 캐릭터 이름과 한글 path parameter를 `encodeURIComponent` 처리하는가?
- 새 1:1 SSE 방의 `room_id`가 필요하면 스트림 종료 후 방 목록을 갱신하는가?

### 10.5 현재 백엔드 정리 우선순위

프론트가 임시 분기 없이 연동하려면 백엔드에서 아래 항목을 우선 정리하는 것이 좋습니다.

1. `/chatcharcter/{name}`을 `/chat/character/{name}`으로 수정
2. `/user/chatai-reommended-movies` 경로 오타 수정
3. 모든 응답의 `state`와 HTTP status code 규칙 통일
4. `/movies/ranking`을 공통 envelope로 통일
5. 기존 채팅방 이어가기의 일반 JSON/그룹/SSE 정책 확정
6. SSE 시작 이벤트에 `room_id` 포함
7. OpenAPI response model 보강

경로 오타를 수정할 때는 프론트 배포와 동시에 바꾸거나, 일정 기간 기존 경로와 새 경로를 함께 제공하는 방식이 안전합니다.
