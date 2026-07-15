# CineVerse 백엔드 API 명세서

작성 기준: 2026-07-09  
기준 코드: `app.main`, `app/api/*`, `app/schemas/*`, `app/services/*`  
Base URL: `http://127.0.0.1:8080`

## 0. 문서 범위

이 API 명세서는 현재 루트 백엔드 앱만 기준으로 작성했습니다.

| 항목 | 기준 |
| --- | --- |
| 포함 | `app/main.py`, `app/api/*`, `app/schemas/*`, `app/services/*` |
| 경로 검증 | `from app.main import app; app.openapi()` 기준 |
| 확인된 엔드포인트 수 | URL path 38개 / HTTP operation 39개 |

## 1. 기본 정보

| 항목 | 값 |
| --- | --- |
| Framework | FastAPI |
| 기본 Content-Type | `application/json` |
| 파일 업로드 Content-Type | `multipart/form-data` |
| API 문서 | `http://127.0.0.1:8080/docs` |
| 인증 방식 | `Authorization: Bearer <access_token>` |
| Refresh Token 저장 | HttpOnly cookie `refresh_token` |
| Refresh Cookie path | `/auth` |
| 정적 프로필 이미지 | `/profile_images/{filename}` |

프론트 로컬 CORS 허용 origin:

| Origin |
| --- |
| `http://localhost:5173` |
| `http://127.0.0.1:5173` |
| `http://localhost:5174` |
| `http://127.0.0.1:5174` |

## 2. 공통 규칙

대부분의 API는 HTTP 200으로 아래 형태를 반환합니다.

```json
{
  "state": "success",
  "message": "처리 메시지",
  "data": {}
}
```

일부 응답은 현재 코드상 `state` 대신 `status`를 사용합니다.

| API | 상황 | 위치 |
| --- | --- | --- |
| `POST /auth/register` | 성공, 비밀번호 누락 실패, 예외 에러 응답 | `app/api/auth.py` |
| `GET /db-test` | DB 연결 예외 실패 응답 | `app/main.py` |

| 상태값 | 의미 |
| --- | --- |
| `success` | 요청 처리 성공 |
| `failure` | 요청은 도달했지만 비즈니스 조건 실패 |
| `error` | 예외 또는 서버 내부 처리 실패 |

회원 전용 API에서 access token이 없거나 잘못되면 HTTP 401이 발생합니다.

```json
{
  "detail": {
    "state": "failure",
    "message": "로그인이 필요합니다.",
    "code": "LOGIN_REQUIRED"
  }
}
```

인증 실패 코드:

| code | 의미 |
| --- | --- |
| `LOGIN_REQUIRED` | Authorization 헤더 없음 |
| `ACCESS_TOKEN_EXPIRED` | access token 만료 |
| `INVALID_ACCESS_TOKEN` | token 서명 또는 형식 오류 |
| `INVALID_TOKEN_TYPE` | access token 타입이 아님 |
| `INVALID_TOKEN_PAYLOAD` | token payload에 사용자 정보 없음 |
| `INVALID_AUTH_SCHEME` | Bearer 방식이 아님 |

요청 검증 실패는 FastAPI 기본 HTTP 422 응답을 반환합니다.

## 3. 공통 타입

### 3.1 MovieCard

검색, 기본 추천, 좋아요, 최근 조회 목록에서 주로 사용하는 영화 카드입니다.

```ts
type MovieCard = {
  movie_id: number;
  title: string;
  poster_path: string | null;
  genres?: string[] | null;
  vote_average: number | null;
};
```

### 3.2 MovieDetail

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

### 3.3 ChatMovie

AI 서버가 내려주는 추천 영화 객체입니다. 구조는 AI 응답에 따라 달라질 수 있으므로 프론트에서는 필요한 필드만 방어적으로 사용합니다.

```ts
type ChatMovie = Record<string, unknown>;
```

## 4. 엔드포인트 요약

### 4.1 Health

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/` | 없음 | API 실행 확인 |
| `GET` | `/health` | 없음 | 서버 상태 확인 |
| `GET` | `/db-test` | 없음 | PostgreSQL 연결 확인 |
| `GET` | `/ai-health` | 없음 | AI 서버 `/health` 연결 확인 |

### 4.2 Auth

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | 없음 | 회원가입 |
| `POST` | `/auth/login` | 없음 | 로그인, access token 반환, refresh cookie 저장 |
| `POST` | `/auth/refresh` | refresh cookie | access token 재발급 |
| `POST` | `/auth/logout` | refresh cookie | refresh token 폐기, cookie 삭제 |

### 4.3 Movies

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/movies/actors` | 없음 | 배우 목록 조회 |
| `POST` | `/movies/actor/{actor_id}` | 필요 | 선호 배우 저장 |
| `POST` | `/movies/recommend?limit=12` | 없음 | 기본 추천 영화 목록 |
| `GET` | `/movies/search?keyword=...&page=1&limit=20` | 없음 | 영화 검색 |
| `GET` | `/movies/ranking?limit=10` | 없음 | 실시간 영화 랭킹 |
| `GET` | `/movies/{movie_id}?source=direct` | 선택 | 영화 상세 조회, 로그인 사용자는 행동 기록 저장 |
| `POST` | `/movies/{movie_id}/like` | 필요 | 영화 좋아요 |
| `GET` | `/movies/today/recommend` | 없음 | 오늘의 AI 영화 추천 |
| `GET` | `/movies/genre/{genre}?page=1&limit=20` | 없음 | 장르별 영화 조회 |

### 4.4 User

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/user` | 필요 | 내 정보 조회 |
| `PATCH` | `/user/profile_image` | 필요 | 프로필 이미지 업로드/수정 |
| `DELETE` | `/user/delete/profile_image` | 필요 | 프로필 이미지 삭제 |
| `GET` | `/user/preferences` | 필요 | 내 선호 정보 조회 |
| `DELETE` | `/user/preference/delete` | 필요 | 선호 값 1개 삭제 |
| `GET` | `/user/movies-like` | 필요 | 좋아요 누른 영화 조회 |
| `DELETE` | `/user/movie-like/{movie_id}` | 필요 | 좋아요 삭제 |
| `GET` | `/user/recently-viewed?limit=5` | 필요 | 최근 상세 조회한 영화 조회 |
| `GET` | `/user/chatai-reommended-movies?limit=10` | 필요 | 채팅 AI가 추천했던 영화 조회 |

주의: `/user/chatai-reommended-movies`는 현재 코드에 있는 실제 경로명 기준입니다. `recommended`가 아니라 `reommended`로 오타가 포함되어 있습니다.

### 4.5 Chat

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/chat/auto` | 필요 | 일반 AI 채팅 시작 |
| `GET` | `/chat/characters` | 없음 | 채팅 가능 캐릭터 목록 조회 |
| `POST` | `/chat` | 필요 | 1대1 캐릭터 채팅 시작 |
| `POST` | `/chat/group` | 필요 | 그룹 캐릭터 채팅 시작 |
| `GET` | `/chat/rooms` | 필요 | 내 채팅방 목록 조회 |
| `GET` | `/chat/rooms/{room_id}/messages` | 필요 | 채팅방 메시지 목록 조회 |
| `POST` | `/chat/rooms/{room_id}/messages` | 필요 | 기존 채팅방 이어서 대화 |
| `DELETE` | `/chat/rooms/{room_id}` | 필요 | 채팅방 삭제 |

## 5. Health API

### 5.1 API 실행 확인

`GET /`

응답:

```json
{
  "state": "success",
  "message": "CineVerse API is running"
}
```

### 5.2 서버 상태 확인

`GET /health`

응답:

```json
{
  "state": "success",
  "message": "CineVerse"
}
```

### 5.3 DB 연결 확인

`GET /db-test`

응답:

```json
{
  "state": "success",
  "message": "PostgreSQL 연결 성공"
}
```

DB 연결 실패 응답:

```json
{
  "status": "failure",
  "message": "BE2 DB연결 API 호출 실패",
  "error": "..."
}
```

### 5.4 AI 서버 연결 확인

`GET /ai-health`

응답:

```json
{
  "state": "success",
  "message": "AI 서버 연결에 성공했습니다.",
  "ai_base_url": "http://210.109.15.251",
  "status_code": 200
}
```

## 6. Auth API

### 6.1 회원가입

`POST /auth/register`

Request:

```json
{
  "email": "user@example.com",
  "password": "password1234",
  "nickname": "무비러버"
}
```

Success Response:

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

Failure Response:

```json
{
  "state": "failure",
  "message": "회원가입 실패 - 이메일 중복"
}
```

비밀번호 누락 실패 응답:

```json
{
  "status": "failure",
  "message": "비밀번호 입력해주세요"
}
```

### 6.2 로그인

`POST /auth/login`

Request:

```json
{
  "email": "user@example.com",
  "password": "password1234"
}
```

Success Response:

```json
{
  "state": "success",
  "message": "로그인 성공",
  "data": {
    "access_token": "<jwt>",
    "token_type": "bearer",
    "email": "user@example.com",
    "nickname": "무비러버"
  }
}
```

응답 시 `Set-Cookie: refresh_token=...; HttpOnly; Path=/auth; SameSite=lax`가 함께 내려갑니다.

### 6.3 Access Token 재발급

`POST /auth/refresh`

Cookie:

```http
Cookie: refresh_token=<refresh_jwt>
```

Success Response:

```json
{
  "state": "success",
  "message": "토큰 재발급 성공",
  "data": {
    "access_token": "<new_jwt>",
    "token_type": "bearer",
    "email": "user@example.com"
  }
}
```

### 6.4 로그아웃

`POST /auth/logout`

동작:

- refresh token hash row가 있으면 `refresh_tokens.revoked_at` 기록
- 브라우저의 `refresh_token` cookie 삭제

Success Response:

```json
{
  "state": "success",
  "message": "로그아웃 성공",
  "data": {
    "detail": "클라이언트 쪽에서 access_token, refresh_token 삭제"
  }
}
```

## 7. Movies API

### 7.1 배우 목록 조회

`GET /movies/actors`

Success Response:

```json
{
  "state": "success",
  "message": "배우 조회 성공",
  "data": [
    {
      "actor_id": 1,
      "actor_name": "Tom Hanks",
      "profile_path": "https://image.tmdb.org/t/p/w500/example.jpg"
    }
  ]
}
```

`profile_path`는 DB 값이 상대 경로이면 TMDB `w500` URL로 변환됩니다.

### 7.2 선호 배우 저장

`POST /movies/actor/{actor_id}`

Auth: 필요

Success Response:

```json
{
  "state": "success",
  "message": "선호 배우 저장 성공",
  "data": {
    "user_email": "user@example.com",
    "user_preferred_actors": ["Tom Hanks"]
  }
}
```

### 7.3 기본 추천 영화 목록

`POST /movies/recommend?limit=12`

Query:

| 이름 | 타입 | 기본값 | 제한 | 설명 |
| --- | --- | --- | --- | --- |
| `limit` | int | `12` | `1..30` | 반환 개수 |

Success Response:

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
      "recommendation_score": 9.321,
      "reson": "평점 높은 영화 추천"
    }
  ]
}
```

주의: 현재 응답 키는 코드 기준으로 `reason`이 아니라 `reson`입니다.

### 7.4 영화 검색

`GET /movies/search?keyword=인셉션&page=1&limit=20`

Query:

| 이름 | 타입 | 필수 | 기본값 | 제한 |
| --- | --- | --- | --- | --- |
| `keyword` | string | 예 | 없음 | min length 1 |
| `page` | int | 아니오 | `1` | `>= 1` |
| `limit` | int | 아니오 | `20` | `1..50` |

Success Response:

```json
{
  "state": "success",
  "message": "검색 성공",
  "data": [
    {
      "movie_id": 1,
      "title": "Inception",
      "genres": ["Action", "Sci-Fi"],
      "poster_path": "/poster.jpg",
      "vote_average": 8.4
    }
  ]
}
```

검색 대상: 제목, 줄거리, 감독, 언어, 배우 배열, 키워드 배열, 장르 테이블. 제목은 공백 제거 검색도 보정합니다.

### 7.5 실시간 영화 랭킹

`GET /movies/ranking?limit=10`

Query:

| 이름 | 타입 | 기본값 | 제한 |
| --- | --- | --- | --- |
| `limit` | int | `10` | `1..100` |

Response:

```json
[
  {
    "id": 1,
    "title": "Inception",
    "poster_path": "/poster.jpg",
    "view_count": 10,
    "search_click_count": 4,
    "like_count": 2,
    "ranking_score": 18
  }
]
```

정렬 기준: `ranking_score`, `view_count`, `like_count`, `search_click_count`, `vote_average`, `vote_count`, `id` 순입니다.

### 7.6 영화 상세 조회

`GET /movies/{movie_id}?source=direct`

Auth: 선택. 비회원도 조회 가능하며, 로그인 사용자는 행동 기록과 랭킹 점수가 저장됩니다.

Query:

| 이름 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `source` | string | `direct` | `search`이면 `search_click`, 그 외에는 `view`로 기록 |

Success Response:

```json
{
  "state": "success",
  "message": "영화 조회 성공",
  "data": {
    "id": 1,
    "movie_id": 1,
    "tmdb_id": 27205,
    "title": "Inception",
    "overview": "영화 줄거리",
    "genres": ["Action", "Sci-Fi"],
    "director": "Christopher Nolan",
    "cast": ["Leonardo DiCaprio"],
    "keywords": ["dream"],
    "year": 2010,
    "language": "en",
    "vote_average": 8.4,
    "vote_count": 36000,
    "audience_count": null,
    "poster_path": "/poster.jpg",
    "last_synced_at": null,
    "created_at": "2026-07-09T00:00:00Z",
    "updated_at": "2026-07-09T00:00:00Z"
  }
}
```

### 7.7 영화 좋아요

`POST /movies/{movie_id}/like`

Auth: 필요

Success Response:

```json
{
  "state": "success",
  "message": "좋아요 API 성공했습니다.",
  "user_id": 1,
  "movie_id": 1,
  "interaction_id": 10
}
```

동작:

- `user_movie_interactions`에 `action_type = like` 저장
- `movie_stats.like_count`, `movie_stats.ranking_score` 증가
- 영화 장르, 배우, 키워드를 사용자 선호 배열에 누적

### 7.8 오늘의 AI 영화 추천

`GET /movies/today/recommend`

Success Response:

```json
{
  "state": "success",
  "message": "오늘의 AI 추천 영화 조회 성공",
  "data": {
    "answer": "오늘은 몰입감 있는 영화를 추천할게요.",
    "movies": [
      {
        "movie_id": 1,
        "title": "Inception",
        "overview": "짧게 줄인 줄거리"
      }
    ]
  }
}
```

응답은 AI 서버 결과를 기반으로 하며 `movies` 내부 필드는 AI 응답에 따라 달라질 수 있습니다.

### 7.9 장르별 영화 조회

`GET /movies/genre/{genre}?page=1&limit=20`

Query:

| 이름 | 타입 | 기본값 | 제한 |
| --- | --- | --- | --- |
| `page` | int | `1` | `>= 1` |
| `limit` | int | `20` | `1..50` |

Success Response:

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

## 8. User API

모든 User API는 access token이 필요합니다.

### 8.1 내 정보 조회

`GET /user`

Success Response:

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

### 8.2 프로필 이미지 업로드/수정

`PATCH /user/profile_image`

Content-Type: `multipart/form-data`

Form Data:

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `image` | file | 예 | `jpeg`, `png`, `webp`, 최대 5MB |

Success Response:

```json
{
  "state": "success",
  "message": "이미지 수정 성공",
  "data": {
    "user_profile": "http://127.0.0.1:8080/profile_images/profile_x.jpg"
  }
}
```

### 8.3 프로필 이미지 삭제

`DELETE /user/delete/profile_image`

Success Response:

```json
{
  "state": "success",
  "message": "사용자 프로필 이미지 삭제 성공"
}
```

### 8.4 내 선호 정보 조회

`GET /user/preferences`

Success Response:

```json
{
  "state": "success",
  "message": "취향 조회 성공",
  "data": {
    "preferred_genres": ["Action"],
    "preferred_actors": ["Tom Hanks"],
    "preferred_keywords": ["space"]
  }
}
```

### 8.5 선호 값 삭제

`DELETE /user/preference/delete`

Request:

```json
{
  "preference_type": "genre",
  "preference_value": "Action"
}
```

허용 `preference_type`: `genre`, `actor`, `keyword`

Success Response:

```json
{
  "state": "success",
  "message": "사용자의 선호값 삭제 성공",
  "data": {
    "preferred_genres": [],
    "preferred_actors": ["Tom Hanks"],
    "preferred_keywords": ["space"]
  }
}
```

### 8.6 좋아요 누른 영화 조회

`GET /user/movies-like`

Success Response:

```json
{
  "state": "success",
  "message": "좋아요 누른 영화 조회 성공",
  "data": [
    {
      "movie_id": 1,
      "title": "Inception",
      "genres": ["Action", "Sci-Fi"],
      "poster_path": "/poster.jpg",
      "vote_average": 8.4
    }
  ]
}
```

### 8.7 좋아요 삭제

`DELETE /user/movie-like/{movie_id}`

Success Response:

```json
{
  "state": "success",
  "message": "좋아요 누른 영화 삭제 성공"
}
```

동작:

- 사용자의 해당 영화 `like` interaction 삭제
- `movie_stats.like_count`, `movie_stats.ranking_score` 감소

### 8.8 최근 조회 영화 조회

`GET /user/recently-viewed?limit=5`

Query:

| 이름 | 타입 | 기본값 | 제한 |
| --- | --- | --- | --- |
| `limit` | int | `5` | `1..50` |

Success Response:

```json
{
  "state": "success",
  "message": "최근 조회한 영화 조회 성공",
  "data": [
    {
      "movie_id": 1,
      "title": "Inception",
      "genres": ["Action", "Sci-Fi"],
      "poster_path": "/poster.jpg",
      "vote_average": 8.4
    }
  ]
}
```

### 8.9 채팅 AI 추천 영화 조회

`GET /user/chatai-reommended-movies?limit=10`

Query:

| 이름 | 타입 | 기본값 | 제한 |
| --- | --- | --- | --- |
| `limit` | int | `10` | `1..50` |

Success Response:

```json
{
  "state": "success",
  "message": "ai가 추천한 영화 API 성공",
  "data": [
    {
      "tmdb_id": 27205,
      "title": "Inception"
    }
  ]
}
```

`data`는 사용자의 채팅방 assistant 메시지 중 `recommended_movies` JSONB에 저장된 영화 snapshot을 최신순으로 모아 중복 `tmdb_id`를 제거한 목록입니다.

## 9. Chat API

### 9.1 일반 AI 채팅 시작

`POST /chat/auto`

Auth: 필요

Request:

```json
{
  "message": "오늘 볼 영화 추천해줘",
  "character": null
}
```

Success Response:

```json
{
  "state": "success",
  "message": "채팅 응답에 성공했습니다.",
  "data": {
    "room_id": 1,
    "answer": "추천 답변",
    "intent": "recommend",
    "movies": []
  }
}
```

### 9.2 채팅 가능 캐릭터 조회

`GET /chat/characters`

Success Response:

```json
{
  "state": "success",
  "message": "채팅 캐릭터 조회 성공",
  "data": [
    {
      "id": 1,
      "name": "Iron Man",
      "movie_title": "Iron Man",
      "profile_image": "https://example.com/profile.jpg"
    }
  ]
}
```

### 9.3 1대1 캐릭터 채팅 시작

`POST /chat`

Auth: 필요

Request:

```json
{
  "message": "너라면 어떤 영화를 추천해?",
  "character": "Iron Man"
}
```

Success Response:

```json
{
  "state": "success",
  "message": "채팅 응답에 성공했습니다.",
  "data": {
    "room_id": 1,
    "answer": "캐릭터 답변",
    "intent": "recommend",
    "movies": []
  }
}
```

### 9.4 그룹 캐릭터 채팅 시작

`POST /chat/group`

Auth: 필요

Request:

```json
{
  "characters": ["Iron Man", "Captain America"],
  "message": "둘이서 영화 하나 골라줘"
}
```

제약: `characters`는 2명 이상 5명 이하입니다.

Success Response:

```json
{
  "state": "success",
  "message": "그룹 채팅 응답에 성공했습니다.",
  "data": {
    "room_id": 1,
    "intent": "recommend",
    "rounds": [
      {
        "round": 1,
        "label": "토론",
        "responses": [
          {
            "character": "Iron Man",
            "answer": "답변"
          }
        ]
      }
    ],
    "movies": []
  }
}
```

### 9.5 내 채팅방 목록 조회

`GET /chat/rooms`

Auth: 필요

Success Response:

```json
{
  "state": "success",
  "message": "채팅방 목록 조회에 성공했습니다.",
  "data": [
    {
      "room_id": 1,
      "room_type": "general",
      "characters": [],
      "created_at": "2026-07-09T00:00:00Z",
      "updated_at": "2026-07-09T00:00:00Z"
    }
  ]
}
```

### 9.6 채팅방 메시지 목록 조회

`GET /chat/rooms/{room_id}/messages`

Auth: 필요

Success Response:

```json
{
  "state": "success",
  "message": "채팅 메시지 목록 조회에 성공했습니다.",
  "data": [
    {
      "room_id": 1,
      "role": "assistant",
      "character": "Iron Man",
      "created_at": "2026-07-09T00:00:00Z",
      "content": "추천 답변",
      "recommended_movies": []
    }
  ]
}
```

### 9.7 기존 채팅방 이어서 대화

`POST /chat/rooms/{room_id}/messages`

Auth: 필요

Request:

```json
{
  "content": "다른 영화도 있어?",
  "character": "Iron Man"
}
```

Success Response:

```json
{
  "state": "success",
  "message": "채팅 응답에 성공했습니다.",
  "data": {
    "room_id": 1,
    "answer": "이어서 답변",
    "intent": "recommend",
    "movies": []
  }
}
```

그룹 채팅방이면 그룹 채팅 응답 구조를 반환합니다.

### 9.8 채팅방 삭제

`DELETE /chat/rooms/{room_id}`

Auth: 필요

Success Response:

```json
{
  "state": "success",
  "message": "채팅방 삭제에 성공했습니다."
}
```

## 10. 현재 확인된 구현 메모

| 항목 | 내용 |
| --- | --- |
| 문서 범위 | 현재 루트 앱 기준 |
| 경로 대조 | `app.main` OpenAPI 기준 URL path 38개 / HTTP operation 39개 |
| 실패 응답 HTTP 코드 | 대부분 비즈니스 실패가 HTTP 200 + `state: failure`로 반환됨 |
| `state`/`status` 혼용 | `POST /auth/register` 일부 응답과 `GET /db-test` 예외 실패 응답은 `status`를 사용하므로 프론트에서 `state ?? status` 처리 권장 |
| `/user/chatai-reommended-movies` | 경로명에 오타가 포함된 상태로 구현됨 |
| `/movies/recommend` | 추천 이유 키가 `reson`으로 반환됨 |
| Optional Auth | `/movies/{movie_id}`는 토큰이 없어도 조회 가능하지만, 토큰이 있으면 검증 실패 시 401 발생 |
| 프로필 이미지 | 서버 로컬 `app/profile_images`에 저장되고 `/profile_images`로 static serving |
