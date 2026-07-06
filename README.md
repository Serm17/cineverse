# CineVerse API 명세서

이 문서는 현재 `app/main.py`에 최종 등록된 API 기준으로 정리한 README입니다.

- 기본 주소: `http://127.0.0.1:8080`
- 실행 앱: `app.main:app`
- 인증 방식: `Authorization: Bearer <access_token>`
- Refresh Token 저장 위치: `refresh_token` HttpOnly Cookie
- 공통 응답 상태값: `state` 또는 `status`가 `success`, `failure`, `error` 중 하나로 반환됩니다.

## 실행

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

## 등록된 라우터

| 구분 | Prefix | 설명 |
| --- | --- | --- |
| 상태 확인 | 없음 | 서버, DB, AI 서버 연결 확인 |
| Auth | `/auth` | 회원가입, 로그인, 토큰 재발급, 로그아웃, 내 정보 조회 |
| Users | `/users` | 내 선호 정보 저장 및 조회 |
| Chat | `/chat` | AI 채팅, 채팅방 목록, 메시지 조회/전송, 채팅방 삭제 |

## 인증 규칙

로그인 성공 시 응답 본문으로 `access_token`이 반환되고, `refresh_token`은 HttpOnly Cookie에 저장됩니다.

회원 전용 API는 아래 헤더가 필요합니다.

```http
Authorization: Bearer <access_token>
```

Access Token이 만료되면 `POST /auth/refresh`를 호출해 새 Access Token을 발급받습니다. 이때 브라우저가 `/auth` 경로의 `refresh_token` 쿠키를 함께 보내야 합니다.

## 상태 확인 API

### GET `/health`

서버 실행 여부를 확인합니다.

#### Response

```json
{
  "message": "CineVerse"
}
```

### GET `/db-test`

PostgreSQL 연결 여부를 확인합니다.

#### Success Response

```json
{
  "status": "success",
  "message": "PostgreSQL 연결 성공"
}
```

#### Failure Response

```json
{
  "status": "failure",
  "message": "BE2 DB연결 API 호출 실패",
  "error": "error message"
}
```

### GET `/ai-health`

설정된 AI 서버의 `/health` 엔드포인트 연결 여부를 확인합니다.

#### Success Response

```json
{
  "state": "success",
  "message": "AI 서버 연결에 성공했습니다.",
  "ai_base_url": "http://210.109.15.251",
  "status_code": 200
}
```

#### Error Response

```json
{
  "state": "error",
  "message": "AI 서버에 연결할 수 없습니다.",
  "ai_base_url": "http://210.109.15.251",
  "error": "error message"
}
```

## Auth API

### POST `/auth/register`

회원가입을 처리합니다.

#### Request Body

```json
{
  "email": "user@example.com",
  "password": "password1234",
  "nickname": "cine"
}
```

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `email` | string | Y | 이메일 형식 |
| `password` | string | Y | 비밀번호 |
| `nickname` | string | Y | 닉네임 |

#### Success Response

```json
{
  "status": "success",
  "message": "회원가입 성공",
  "data": {
    "id": 1,
    "email": "user@example.com",
    "nickname": "cine"
  }
}
```

#### Failure Response

```json
{
  "status": "failure",
  "message": "회원가입 실패 - 이메일 중복"
}
```

### POST `/auth/login`

로그인을 처리하고 Access Token을 반환합니다. Refresh Token은 HttpOnly Cookie로 저장됩니다.

#### Request Body

```json
{
  "email": "user@example.com",
  "password": "password1234"
}
```

#### Success Response

```json
{
  "state": "success",
  "message": "로그인 성공",
  "data": {
    "access_token": "jwt.access.token",
    "token_type": "bearer",
    "email": "user@example.com",
    "nickname": "cine"
  }
}
```

#### Cookie

```http
Set-Cookie: refresh_token=<refresh_token>; HttpOnly; Path=/auth; SameSite=lax
```

#### Failure Response

```json
{
  "state": "failure",
  "message": "해당 이메일은 가입된 회원이 아닙니다."
}
```

```json
{
  "state": "failure",
  "message": "해당 회원의 비밀번호가 일치하지 않습니다."
}
```

### POST `/auth/refresh`

Refresh Token Cookie를 검증하고 새 Access Token을 발급합니다.

#### Request

별도 body는 없습니다. `/auth` 경로의 `refresh_token` Cookie가 필요합니다.

#### Success Response

```json
{
  "state": "success",
  "message": "토큰 재발급 성공",
  "data": {
    "access_token": "new.jwt.access.token",
    "token_type": "bearer",
    "email": "user@example.com"
  }
}
```

#### Failure Response

```json
{
  "state": "failure",
  "message": "refresh_token이 브라우저 내 쿠기에 없습니다."
}
```

```json
{
  "state": "failure",
  "message": "이미 로그아웃 처리된 refresh_token입니다."
}
```

### POST `/auth/logout`

Refresh Token을 폐기하고 브라우저 쿠키를 삭제합니다.

#### Request

별도 body는 없습니다. `refresh_token` Cookie가 있으면 DB에서 폐기 처리합니다.

#### Success Response

```json
{
  "state": "success",
  "message": "로그아웃 성공",
  "data": {
    "detail": "클라이언트 쪽에서 access_token, refresh_token 삭제"
  }
}
```

### GET `/auth/me`

현재 Access Token의 사용자 정보를 조회합니다.

#### Auth

필수

#### Success Response

```json
{
  "state": "success",
  "message": "정보 조회 성공",
  "data": {
    "email": "user@example.com"
  }
}
```

#### Auth Error Response

```json
{
  "detail": {
    "state": "failure",
    "message": "로그인이 필요합니다.",
    "code": "LOGIN_REQUIRED"
  }
}
```

## Users API

### PUT `/users/me/preferences`

내 선호 정보를 저장합니다. 기존 `genre`, `actor`, `keyword` 선호값은 삭제 후 새 값으로 교체됩니다. 각 배열의 빈 문자열과 중복 값은 제거됩니다.

#### Auth

필수

#### Request Body

```json
{
  "genres": ["SF", "Action"],
  "actors": ["Tom Hardy"],
  "keywords": ["time travel", "space"]
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `genres` | string[] | N | `[]` | 선호 장르 |
| `actors` | string[] | N | `[]` | 선호 배우 |
| `keywords` | string[] | N | `[]` | 선호 키워드 |

#### Success Response

```json
{
  "state": "success",
  "message": "선호 정보 저장 성공",
  "data": {
    "genres": ["SF", "Action"],
    "actors": ["Tom Hardy"],
    "keywords": ["time travel", "space"]
  }
}
```

### GET `/users/me/preferences`

내 선호 정보를 조회합니다.

#### Auth

필수

#### Success Response

```json
{
  "state": "success",
  "message": "선호 정보 조회 성공",
  "data": {
    "genres": ["SF", "Action"],
    "actors": ["Tom Hardy"],
    "keywords": ["time travel", "space"]
  }
}
```

## Chat API

현재 채팅 API는 코드상 `user_id = 1`로 고정되어 있습니다. 추후 JWT 연동 시 `get_current_user` 의존성을 다시 활성화하면 로그인 사용자 기준으로 동작합니다.

AI 서버 호출 경로는 내부적으로 `POST {AI_BASE_URL}/chat/auto`를 사용합니다.

프론트 전달용 상세 명세는 [`docs/chat-auto-api.md`](docs/chat-auto-api.md)를 참고하세요.

### POST `/chat/auto`

새 일반 채팅방을 만들고 AI 응답을 생성합니다.

#### Request Body

```json
{
  "message": "오늘 볼 만한 영화 추천해줘"
}
```

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `message` | string | Y | 사용자 입력 메시지. 최소 1자 |

#### Success Response

```json
{
  "state": "success",
  "message": "채팅 응답에 성공했습니다.",
  "data": {
    "room_id": 1,
    "answer": "AI 답변",
    "intent": "recommend",
    "movies": []
  }
}
```

#### Failure Response

```json
{
  "state": "failure",
  "message": "내용을 입력해주세요."
}
```

### GET `/chat/rooms`

사용자의 채팅방 목록을 최신 수정순으로 조회합니다.

#### Success Response

```json
{
  "state": "success",
  "message": "채팅방 목록 조회에 성공했습니다.",
  "data": [
    {
      "room_id": 1,
      "room_type": "general",
      "characters": [],
      "created_at": "2026-07-01T10:00:00",
      "updated_at": "2026-07-01T10:00:00"
    }
  ]
}
```

### GET `/chat/rooms/{room_id}/messages`

채팅방의 메시지 목록을 생성 시간 오름차순으로 조회합니다.

#### Path Parameter

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `room_id` | integer | Y | 채팅방 ID |

#### Success Response

```json
{
  "state": "success",
  "message": "채팅 메시지 목록 조회에 성공했습니다.",
  "data": [
    {
      "room_id": 1,
      "role": "user",
      "character": null,
      "created_at": "2026-07-01T10:00:00",
      "content": "오늘 볼 만한 영화 추천해줘"
    },
    {
      "room_id": 1,
      "role": "assistant",
      "character": null,
      "created_at": "2026-07-01T10:00:02",
      "content": "AI 답변"
    }
  ]
}
```

#### Failure Response

```json
{
  "state": "failure",
  "message": "해당 채팅방이 존재하지 않습니다."
}
```

### POST `/chat/rooms/{room_id}/messages`

기존 채팅방에 사용자 메시지를 보내고 AI 응답을 이어서 생성합니다.

#### Path Parameter

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `room_id` | integer | Y | 채팅방 ID |

#### Request Body

```json
{
  "content": "비슷한 영화도 더 알려줘"
}
```

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `content` | string | Y | 사용자 입력 메시지. 최소 1자 |

#### Success Response

```json
{
  "state": "success",
  "message": "채팅 응답에 성공했습니다.",
  "data": {
    "room_id": 1,
    "answer": "AI 답변",
    "intent": "recommend",
    "movies": []
  }
}
```

#### Failure Response

```json
{
  "state": "failure",
  "message": "채팅방을 찾을 수 없습니다."
}
```

### DELETE `/chat/rooms/{room_id}`

채팅방을 삭제합니다. `ChatRoom` 모델의 관계 설정에 따라 해당 방의 메시지도 함께 삭제됩니다.

#### Path Parameter

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `room_id` | integer | Y | 채팅방 ID |

#### Success Response

```json
{
  "state": "success",
  "message": "채팅방 삭제에 성공했습니다."
}
```

#### Failure Response

```json
{
  "state": "failure",
  "message": "해당 채팅방이 존재하지 않습니다."
}
```

## 현재 비활성 API

`app/api/movies.py`에는 영화 관련 라우터가 작성되어 있지만, 현재 `app/main.py`에서 아래처럼 주석 처리되어 서버에 등록되지 않습니다.

```python
# from app.api.movies import router as movies_router
# app.include_router(movies_router)
```

따라서 현재 실행 서버 기준 API 명세에는 `/movies` 엔드포인트를 포함하지 않습니다.
