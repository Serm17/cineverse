# CineVerse Backend

CineVerse 영화 추천/검색/채팅 서비스를 위한 FastAPI 백엔드입니다.

## 주요 기능

- JWT 기반 회원가입, 로그인, 토큰 재발급, 로그아웃
- 영화 검색, 상세 조회, 랭킹, 장르별 조회, 좋아요
- AI 서버 연동 일반 채팅, 그룹 채팅, 채팅방/메시지 조회
- 사용자 선호 정보, 좋아요 영화, 최근 조회 영화 조회
- TMDB 기반 영화/캐릭터 데이터 적재 및 키워드 백필 스크립트

## 기술 스택

- Python 3.14 이상
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Pydantic Settings
- python-jose JWT
- httpx

## 실행 준비

가상환경을 만든 뒤 의존성을 설치합니다.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e .
```

환경변수 예시 파일을 복사해 로컬 `.env`를 만듭니다.

```bash
cp .env.example .env
```

`.env`에는 실제 비밀키와 API 키를 넣고, Git에는 올리지 않습니다.

## 환경변수

| 이름 | 설명 | 예시 |
| --- | --- | --- |
| `SECRET_KEY` | JWT access/refresh token 서명 비밀키 | `change-me-to-a-long-random-secret` |
| `ALGORITHM` | JWT 서명 알고리즘 | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 만료 시간(분) | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh Token 만료 시간(일) | `14` |
| `BE2_BASE_URL` | BE2 서버 주소 | `http://127.0.0.1:8001` |
| `AI_BASE_URL` | AI 서버 주소 | `http://210.109.15.251` |
| `TMDB_API_KEY` | TMDB API 키 | `your-tmdb-api-key` |
| `DATABASE_URL` | 키워드 백필 스크립트용 DB URL | `postgresql://postgres:1234@localhost:5432/CineVerse` |

현재 앱의 기본 DB 연결 문자열은 [app/core/dependencies.py](/Users/apple/mainproject_musubi/app/core/dependencies.py)에 정의되어 있습니다.

## 서버 실행

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

기본 주소는 `http://127.0.0.1:8080`입니다.

## 상태 확인 API

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/` | API 실행 확인 |
| `GET` | `/health` | 서버 상태 확인 |
| `GET` | `/db-test` | PostgreSQL 연결 확인 |
| `GET` | `/ai-health` | AI 서버 `/health` 연결 확인 |

## Auth API

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | 없음 | 회원가입 |
| `POST` | `/auth/login` | 없음 | 로그인, access token 반환 및 refresh token cookie 저장 |
| `POST` | `/auth/refresh` | refresh cookie | access token 재발급 |
| `POST` | `/auth/logout` | refresh cookie | refresh token 폐기 및 cookie 삭제 |

로그인 후 회원 전용 API에는 아래 헤더를 보냅니다.

```http
Authorization: Bearer <access_token>
```

## Movies API

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/movies/recommend?limit=12` | 없음 | 추천 영화 목록 |
| `GET` | `/movies/search?keyword=...&page=1&limit=20` | 없음 | 영화 검색 |
| `GET` | `/movies/ranking?limit=10` | 없음 | 실시간 랭킹 |
| `GET` | `/movies/{movie_id}?source=direct` | 선택 | 영화 상세 조회, 로그인 사용자는 조회/검색 클릭 기록 저장 |
| `POST` | `/movies/{movie_id}/like` | 필요 | 영화 좋아요 |
| `GET` | `/movies/today/recommend` | 없음 | AI 오늘의 영화 추천 |
| `GET` | `/movies/genre/{genre}?page=1&limit=20` | 없음 | 장르별 영화 조회 |

## User API

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/user` | 필요 | 내 정보 조회 |
| `GET` | `/user/preferences` | 필요 | 내 선호 정보 조회 |
| `GET` | `/user/movies-like` | 필요 | 좋아요 누른 영화 조회 |
| `GET` | `/user/recently-viewed?limit=5` | 필요 | 최근 상세 조회한 영화 조회 |

## Chat API

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/chat/auto` | 필요 | 일반 AI 채팅 시작 |
| `GET` | `/chat/characters` | 없음 | 채팅 가능 캐릭터 조회 |
| `POST` | `/chat` | 필요 | 1대1 캐릭터 채팅 |
| `POST` | `/chat/group` | 필요 | 그룹 캐릭터 채팅 |
| `GET` | `/chat/rooms` | 필요 | 내 채팅방 목록 조회 |
| `GET` | `/chat/rooms/{room_id}/messages` | 필요 | 채팅방 메시지 조회 |
| `POST` | `/chat/rooms/{room_id}/messages` | 필요 | 기존 채팅방에서 이어서 대화 |
| `DELETE` | `/chat/rooms/{room_id}` | 필요 | 내 채팅방 삭제 |

현재 `POST /chat` 1대1 캐릭터 채팅은 실제 서비스 호출 전에 임시 응답을 반환하는 상태입니다.

## 데이터 스크립트

TMDB 인기 영화 적재:

```bash
.venv/bin/python scripts/import_tmdb_popular_movies.py
```

CineVerse 캐릭터와 연결 영화 적재:

```bash
.venv/bin/python scripts/import_cineverse_characters.py
```

로컬 DB의 영화 키워드 백필:

```bash
.venv/bin/python scripts/backfill_movie_keywords.py --merge-existing
```

백필 스크립트는 기본적으로 localhost PostgreSQL만 수정하도록 방어 로직이 들어 있습니다. 먼저 확인하려면 `--dry-run`을 사용합니다.

## 최근 작업 내역

- `/user` 라우터를 정리하고 내 정보, 선호 정보, 좋아요 영화, 최근 조회 영화 조회 API를 연결했습니다.
- 영화 검색/좋아요/최근 조회 응답에서 공통 영화 응답 형태를 사용하도록 `get_movie_result`와 `ShowMovie`, `ShowMovies` 스키마를 추가했습니다.
- 채팅방 삭제 API를 활성화하고 JWT 사용자 기준으로 본인 채팅방만 삭제하도록 확인 로직을 넣었습니다.
- 영화 상세 조회 시 로그인 사용자의 `view`, `search_click` 상호작용이 저장되도록 API 흐름을 정리했습니다.
- TMDB 캐릭터 적재 스크립트에서 영화 키워드를 함께 가져오도록 확장했습니다.
- 기존 영화 데이터의 빈 키워드를 로컬 메타데이터 기반으로 채우는 `scripts/backfill_movie_keywords.py`를 추가했습니다.
- 오늘의 AI 추천 요청 프롬프트가 짧은 답변을 요구하도록 조정했습니다.
- 개발 실행 호스트를 `127.0.0.1:8080` 기준으로 맞추고 CORS 허용 origin을 로컬 프론트 주소 중심으로 정리했습니다.

## Git 저장 규칙

- 실제 `.env`는 저장소에 올리지 않습니다.
- 환경변수 공유는 `.env.example`을 사용합니다.
- `.venv`, `outputs`, `external`, 캐시 파일은 Git에서 제외합니다.
