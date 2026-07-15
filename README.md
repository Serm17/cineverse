# CineVerse Backend

CineVerse의 영화 탐색, 개인화 추천, 캐릭터 채팅, 회원 인증을 담당하는 FastAPI 백엔드입니다. PostgreSQL에 영화·사용자·상호작용·채팅 데이터를 저장하고, 별도 AI 서버 및 TMDB 데이터와 연동합니다.

## 주요 기능

- 이메일 인증 기반 회원가입과 JWT 로그인, 토큰 재발급 및 로그아웃
- 이메일 링크를 이용한 비밀번호 재설정
- 영화 검색, 상세 조회, 장르별 탐색, 실시간 랭킹 및 좋아요
- 좋아요·조회·검색 이력을 반영한 사용자별 영화 추천
- 오늘의 AI 영화 추천과 프롬프트 기반 AI 추천
- 일반 AI 채팅, 캐릭터 1:1 SSE 스트리밍 채팅, 그룹 채팅
- 사용자 선호도, 좋아요 영화, 최근 조회 영화, AI 추천 이력 관리

## 기술 스택

| 구분 | 기술 |
| --- | --- |
| Language | Python 3.14+ |
| API | FastAPI, Uvicorn, Pydantic |
| Database | PostgreSQL, SQLAlchemy 2, Alembic, psycopg 3 |
| Authentication | JWT, python-jose, passlib/bcrypt, HttpOnly Cookie |
| External integration | httpx, TMDB API, SMTP |

## 프로젝트 구조

```text
.
├── app
│   ├── ai_client/       # AI 서버 HTTP·SSE 연동
│   ├── api/             # Auth, Movies, Chat, User 라우터
│   ├── core/            # 환경설정, DB 세션, 인증·보안 공통 코드
│   ├── models/          # SQLAlchemy ORM 모델
│   ├── repsitories/     # 데이터 접근 계층
│   ├── schemas/         # 요청·응답 Pydantic 스키마
│   └── services/        # 도메인 서비스
├── alembic/             # DB 마이그레이션
├── docs/                # API 및 DB 명세
├── scripts/             # TMDB 영화·장르·배우 데이터 동기화
├── .env.example
└── pyproject.toml
```

## 로컬 실행

### 1. 사전 준비

- Python 3.14 이상
- PostgreSQL
- 연동할 AI 서버
- 회원가입 및 비밀번호 재설정을 사용할 경우 SMTP 계정

### 2. 가상환경 및 패키지 설치

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

### 3. 환경변수 설정

```bash
cp .env.example .env
```

`.env`에 로컬 환경의 값을 입력합니다. 실제 비밀키와 API 키가 포함된 `.env`는 Git에 커밋하지 않습니다.

| 변수 | 필수 | 기본값·예시 | 설명 |
| --- | --- | --- | --- |
| `DATABASE_URL` | 필수 | `postgresql://postgres:1234@localhost:5432/CineVerse` | 애플리케이션 및 Alembic DB 주소 |
| `TMDB_ACCESS_TOKEN` | 선택 | TMDB API Read Access Token | TMDB 예고편 조회용 Bearer 인증 토큰 |
| `TMDB_API_KEY` | 선택 | TMDB v3 API Key | Access Token이 없을 때 사용하는 TMDB 인증 키 |
| `SECRET_KEY` | 필수 | 긴 무작위 문자열 | Access/Refresh Token 서명 키 |
| `ALGORITHM` | 선택 | `HS256` | JWT 서명 알고리즘 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 선택 | `60` | Access Token 만료 시간(분) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 선택 | `14` | Refresh Token 만료 시간(일) |
| `AI_BASE_URL` | 선택 | `http://210.109.15.251` | AI 서버 기본 주소 |
| `EMAIL_VERIFICATION_EXPIRE_MINUTES` | 선택 | `5` | 회원가입 인증번호 유효 시간(분) |
| `EMAIL_VERIFICATION_RESEND_SECONDS` | 선택 | `60` | 인증번호 재전송 대기 시간(초) |
| `EMAIL_VERIFICATION_MAX_ATTEMPTS` | 선택 | `5` | 인증번호 최대 검증 실패 횟수 |
| `MAIL_HOST` | 필수 | `smtp.example.com` | SMTP 호스트 |
| `MAIL_PORT` | 선택 | `587` | SMTP 포트 |
| `MAIL_USERNAME` | 필수 | SMTP 계정 | SMTP 사용자명 |
| `MAIL_PASSWORD` | 필수 | SMTP 앱 비밀번호 | SMTP 비밀번호 |
| `MAIL_FROM` | 필수 | `no-reply@example.com` | 발신 이메일 주소 |
| `FRONTEND_BASE_URL` | 필수 | `http://localhost:5173` | 비밀번호 재설정 화면의 프론트엔드 주소 |
| `PASSWORD_RESET_EXPIRE_MINUTES` | 필수 | `30` | 비밀번호 재설정 링크 유효 시간(분) |

### 4. DB 마이그레이션

`DATABASE_URL`이 가리키는 PostgreSQL 데이터베이스를 만든 뒤 최신 마이그레이션을 적용합니다.

```bash
.venv/bin/alembic upgrade head
```

현재 마이그레이션 상태 확인:

```bash
.venv/bin/alembic current
```

### 5. TMDB 영화·배우 데이터 적재

`scripts/import_tmdb_popular_movies.py`는 다음 데이터를 한 트랜잭션에서 함께 동기화합니다.

- `movies`, `movie_genres`, `movie_stats`
- 영화별 주요 출연진의 `actors`, `movie_actors`
- 영화별 감독, 출연진 이름 배열, 키워드

`characters`, `character_aliases` 데이터는 변경하지 않습니다. 먼저 소량 dry-run으로 TMDB 연결과 결과를 확인합니다.

```bash
.venv/bin/python scripts/import_tmdb_popular_movies.py \
  --source catalog \
  --limit 20 \
  --cast-limit 10 \
  --dry-run
```

서비스용 카탈로그를 12,000편까지 적재하는 예시는 다음과 같습니다. `catalog` 모드는 1980년부터 현재까지 한국어·영어 원작 영화를 연도별로 고르게 수집하며, 같은 영화와 배우는 TMDB ID 기준으로 갱신합니다.

```bash
.venv/bin/python scripts/import_tmdb_popular_movies.py \
  --source catalog \
  --limit 12000 \
  --cast-limit 10
```

대량 적재 전에는 PostgreSQL 백업을 만들고, SSH 연결 종료에 대비해 `tmux` 같은 세션 관리 도구 안에서 실행하는 것을 권장합니다. 운영 DB에서는 기존 영화와 연관 데이터를 삭제하는 `--replace-existing-data`를 사용하지 않습니다. `--skip-extra-details`를 지정하면 배우 관계 동기화도 함께 생략됩니다.

### 6. 서버 실행

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

- API 기본 주소: `http://127.0.0.1:8080`
- Swagger UI: `http://127.0.0.1:8080/docs`
- ReDoc: `http://127.0.0.1:8080/redoc`

## 인증 방식

로그인에 성공하면 응답 본문으로 Access Token을 받고, Refresh Token은 `/auth` 경로의 HttpOnly Cookie에 저장됩니다. 인증이 필요한 API에는 다음 헤더를 전송합니다.

```http
Authorization: Bearer <access_token>
```

브라우저에서 `/auth/refresh`와 `/auth/logout`을 호출할 때는 Refresh Token Cookie가 전달되도록 credentials 옵션을 활성화해야 합니다.

## API 요약

### System

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/` | API 실행 확인 |
| `GET` | `/health` | 백엔드 상태 확인 |
| `GET` | `/db-test` | PostgreSQL 연결 확인 |
| `GET` | `/ai-health` | AI 서버 연결 확인 |

### Auth

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/auth/email-verification/request` | 없음 | 회원가입 인증번호 이메일 발송 |
| `POST` | `/auth/register` | 인증번호 | 회원가입 |
| `POST` | `/auth/password-reset/request` | 없음 | 비밀번호 재설정 링크 발송 |
| `POST` | `/auth/password-reset/confirm` | 재설정 토큰 | 새 비밀번호 저장 |
| `POST` | `/auth/login` | 없음 | 로그인 및 토큰 발급 |
| `POST` | `/auth/refresh` | Refresh Cookie | Access Token 재발급 |
| `POST` | `/auth/logout` | Refresh Cookie | Refresh Token 폐기 및 Cookie 삭제 |

### Movies

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/movies/actors` | 없음 | 배우 목록 조회 |
| `POST` | `/movies/actor/{actor_id}` | 필요 | 선호 배우 저장 |
| `POST` | `/movies/recommend?limit=12` | 선택 | 비회원 기본 추천 또는 회원 맞춤 추천 |
| `GET` | `/movies/search?keyword=...&page=1&limit=20` | 없음 | 영화 검색 |
| `GET` | `/movies/ranking?limit=10` | 없음 | 실시간 영화 랭킹 |
| `GET` | `/movies/{movie_id}?source=direct` | 선택 | 영화 상세 조회 및 회원 행동 기록 |
| `POST` | `/movies/{movie_id}/like` | 필요 | 영화 좋아요 |
| `GET` | `/movies/today/recommend` | 없음 | 오늘의 AI 추천 영화 |
| `GET` | `/movies/genre/{genre}?page=1&limit=20` | 없음 | 장르별 영화 조회 |
| `POST` | `/movies/ai-recommend` | 없음 | 프롬프트·장르 기반 AI 영화 추천 |

### Chat

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/chat/auto` | 필요 | 일반 AI 채팅 시작 |
| `GET` | `/chat/characters` | 없음 | 활성 캐릭터 목록 조회 |
| `POST` | `/chat` | 필요 | 캐릭터 1:1 SSE 스트리밍 채팅 시작 |
| `POST` | `/chat/group` | 필요 | 캐릭터 그룹 채팅 시작 |
| `GET` | `/chat/rooms` | 필요 | 내 채팅방 목록 조회 |
| `GET` | `/chat/rooms/{room_id}/messages` | 필요 | 채팅방 메시지 조회 |
| `POST` | `/chat/rooms/{room_id}/messages` | 필요 | 기존 채팅방에서 SSE 스트리밍 대화 계속 |
| `DELETE` | `/chat/rooms/{room_id}` | 필요 | 내 채팅방 삭제 |

`POST /chat`과 `POST /chat/rooms/{room_id}/messages`의 응답 타입은 `text/event-stream`입니다.

### User

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/user` | 필요 | 내 정보 조회 |
| `PATCH` | `/user/profile_image` | 필요 | 프로필 이미지 등록·변경 |
| `DELETE` | `/user/delete/profile_image` | 필요 | 프로필 이미지 삭제 |
| `GET` | `/user/preferences` | 필요 | 직접 설정·자동 학습 선호 정보 조회 |
| `DELETE` | `/user/preference/delete` | 필요 | 선호 항목 삭제 |
| `GET` | `/user/movies-like` | 필요 | 좋아요 영화 조회 |
| `DELETE` | `/user/movie-like/{movie_id}` | 필요 | 영화 좋아요 삭제 |
| `GET` | `/user/recently-viewed?limit=5` | 필요 | 최근 조회 영화 조회 |
| `GET` | `/user/chatai-reommended-movies?limit=10` | 필요 | AI 채팅 추천 영화 이력 조회 |

요청·응답 스키마와 상태 코드는 실행 중인 [Swagger UI](http://127.0.0.1:8080/docs)에서 확인할 수 있습니다. 협업용 상세 문서는 [`docs/backend-api-spec.md`](docs/backend-api-spec.md), [`docs/frontend-api-spec-notion.md`](docs/frontend-api-spec-notion.md), [`docs/db-schema-spec.md`](docs/db-schema-spec.md)를 참고하세요.

## 문서

- [백엔드 API 명세](docs/backend-api-spec.md)
- [프론트엔드 연동 API 명세](docs/frontend-api-spec-notion.md)
- [캐릭터 상세 API 명세](docs/frontend-character-detail-api-spec.md)
- [DB 스키마 명세](docs/db-schema-spec.md)

## Git 저장 규칙

- `.env`, API 키, 토큰, SMTP 비밀번호 등 비밀정보는 커밋하지 않습니다.
- 팀에서 공유할 환경변수 이름과 예시는 `.env.example`에만 기록합니다.
- 가상환경, 캐시, 로컬 출력물과 업로드 파일은 저장소에 포함하지 않습니다.
- `external/`, `outputs/`, `.venv/`, `.vscode/`, `app/profile_images/`는 로컬 전용 폴더로 Git 추적에서 제외합니다.
- 운영 적재에 사용하는 `scripts/import_tmdb_popular_movies.py`는 서버에서도 같은 절차를 재현할 수 있도록 Git으로 관리합니다.
