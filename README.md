# CineVerse Backend

CineVerse의 영화 탐색, 개인화 추천, 캐릭터 채팅, 회원 기능을 제공하는 FastAPI 백엔드입니다.

PostgreSQL에 영화·사용자·추천·채팅 데이터를 저장하며, 별도의 AI 서버와 TMDB API를 연동합니다.

## 주요 기능

- 이메일 인증 회원가입, JWT 로그인, 토큰 재발급 및 로그아웃
- 이메일 링크를 이용한 비밀번호 재설정
- 영화 검색, 상세 조회, 장르별 탐색, 실시간 랭킹 및 좋아요
- 좋아요·조회·검색 기록을 반영한 개인화 추천
- 오늘의 AI 영화 추천과 사용자 요청 기반 AI 추천
- 일반 AI 채팅, 캐릭터 1:1 실시간 채팅, 캐릭터 그룹 채팅
- 사용자 선호도, 좋아요, 최근 본 영화, AI 추천 이력 관리
- 관리자 권한 부여·회수와 변경 이력 감사 로그
- 관리자 TMDB 영화 검색·등록, 직접 입력 영화 등록, 영화 수정·삭제

## 기술 스택

| 구분 | 기술 |
| --- | --- |
| 언어 | Python 3.14+ |
| API | FastAPI, Uvicorn, Pydantic |
| 데이터베이스 | PostgreSQL, SQLAlchemy 2, Alembic, psycopg 3 |
| 인증 | JWT, python-jose, passlib/bcrypt, HttpOnly Cookie |
| 외부 연동 | AI 서버, TMDB API, SMTP |

## 빠른 시작

### 1. 준비 사항

기본 실행에는 다음 항목이 필요합니다.

- Python 3.14 이상
- PostgreSQL

사용할 기능에 따라 추가로 준비합니다.

- AI 추천·채팅: 연동할 AI 서버
- 영화 적재·예고편 조회: TMDB Access Token 또는 API Key
- 회원가입 이메일 인증·비밀번호 재설정: SMTP 계정

### 2. 가상환경과 패키지 설치

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

### 3. 환경변수 설정

예시 파일을 복사한 뒤 로컬 환경에 맞게 값을 변경합니다.

```bash
cp .env.example .env
```

`.env`에는 비밀정보가 들어가므로 Git에 커밋하지 않습니다.

현재 애플리케이션 시작에 필요한 값은 다음과 같습니다.

| 변수 | 예시 | 설명 |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://postgres:your-database-password@localhost:5432/CineVerse` | PostgreSQL 연결 주소 |
| `SECRET_KEY` | 충분히 긴 무작위 문자열 | Access/Refresh Token 서명 키 |
| `MAIL_HOST` | `smtp.gmail.com` | SMTP 서버 주소 |
| `MAIL_USERNAME` | `your-email@example.com` | SMTP 사용자명 |
| `MAIL_PASSWORD` | SMTP 앱 비밀번호 | SMTP 비밀번호 |
| `MAIL_FROM` | `your-email@example.com` | 발신 이메일 주소 |
| `FRONTEND_BASE_URL` | `http://localhost:5173` | 비밀번호 재설정 화면 주소 |
| `PASSWORD_RESET_EXPIRE_MINUTES` | `30` | 비밀번호 재설정 링크 유효 시간 |

기본값이 있거나 특정 기능에서 사용하는 값은 다음과 같습니다.

| 변수 | 기본값·예시 | 설명 |
| --- | --- | --- |
| `AI_BASE_URL` | `http://localhost:8001` | 연동할 AI 서버 주소 |
| `TMDB_ACCESS_TOKEN` | TMDB Read Access Token | TMDB Bearer 인증. API Key보다 권장 |
| `TMDB_API_KEY` | TMDB v3 API Key | Access Token을 사용하지 않을 때 입력 |
| `ALGORITHM` | `HS256` | JWT 서명 알고리즘 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access Token 유효 시간 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `14` | Refresh Token 유효 기간 |
| `EMAIL_VERIFICATION_EXPIRE_MINUTES` | `5` | 이메일 인증번호 유효 시간 |
| `EMAIL_VERIFICATION_RESEND_SECONDS` | `60` | 인증번호 재전송 대기 시간 |
| `EMAIL_VERIFICATION_MAX_ATTEMPTS` | `5` | 인증번호 최대 검증 실패 횟수 |
| `MAIL_PORT` | `587` | SMTP 포트 |

기본 CORS 허용 주소는 다음과 같습니다.

- `http://localhost:5173`, `http://127.0.0.1:5173`
- `http://localhost:5174`, `http://127.0.0.1:5174`

`FRONTEND_BASE_URL`은 비밀번호 재설정 링크 생성에만 사용됩니다. 다른 프론트엔드 주소를 사용한다면 서버의 CORS 허용 주소도 맞춰야 합니다.

### 4. DB 마이그레이션

`DATABASE_URL`에 지정한 데이터베이스를 만든 뒤 최신 마이그레이션을 적용합니다.

```bash
.venv/bin/alembic upgrade head
```

현재 적용된 마이그레이션 확인:

```bash
.venv/bin/alembic current
```

### 5. 서버 실행

업로드 폴더는 애플리케이션 시작 시 자동 생성됩니다. Git에서 빈 하위 폴더를
유지해야 하는 경우에는 해당 폴더 안의 `.gitkeep` 파일을 남깁니다.

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

현재 프로필 이미지는 `app/uploads/images/user_profiles`에 저장되며
브라우저에서는 `/uploads/images/user_profiles/{파일명}`으로 접근합니다.
업로드 파일은 사용자가 제공한 원래 파일명을 그대로 사용하지 않고 서버에서
생성한 안전한 이름으로 저장해야 합니다. 운영 환경에서는 확장자뿐 아니라
MIME 타입과 파일 크기도 검증하고 업로드 폴더를 영속 볼륨으로 관리합니다.

서버가 실행되면 다음 주소를 사용할 수 있습니다.

| 용도 | 주소 |
| --- | --- |
| API | `http://127.0.0.1:8080` |
| Swagger UI | `http://127.0.0.1:8080/docs` |
| ReDoc | `http://127.0.0.1:8080/redoc` |

### 6. 연결 상태 확인

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/db-test
curl http://127.0.0.1:8080/ai-health
```

각 응답의 `state`와 `message`를 확인합니다. AI 서버를 실행하지 않았다면 `/ai-health`는 연결 실패를 반환할 수 있습니다.

## 프로젝트 구조

```text
.
├── app
│   ├── ai_client/       # AI 서버 HTTP·SSE 연동
│   ├── api/             # Auth, Movies, Chat, User, Admin API
│   ├── core/            # 환경설정, DB 세션, 인증·보안 공통 코드
│   ├── models/          # SQLAlchemy ORM 모델
│   ├── repositories/    # 데이터 접근 계층
│   ├── schemas/         # 요청·응답 Pydantic 스키마
│   ├── services/        # 기능별 서비스 로직
│   │   └── admin/       # 권한·영화 등록·수정·삭제 관리자 서비스
│   └── uploads/         # 사용자 업로드 파일 저장 루트
│       └── images/
│           └── user_profiles/
├── alembic/             # DB 마이그레이션
├── docs/                # API 및 DB 상세 문서
├── scripts/             # 데이터 적재·보정 도구
├── .env.example         # 환경변수 예시
└── pyproject.toml       # 패키지와 프로젝트 설정
```

## 데이터베이스 구성

현재 PostgreSQL에는 18개의 비즈니스 테이블이 있습니다.

| 영역 | 테이블 | 저장 내용 |
| --- | --- | --- |
| 사용자·인증 | `users`, `refresh_tokens`, `password_reset_tokens`, `email_verification_codes` | 계정, 프로필, 로그인 세션, 이메일 인증과 비밀번호 재설정 |
| 영화 | `movies`, `movie_genres`, `actors`, `movie_actors` | 영화·장르·배우와 영화-배우 관계 |
| 행동·추천 | `user_movie_interactions`, `user_preference_scores`, `movie_stats` | 사용자 행동 기록, 취향 점수, 영화 랭킹 통계 |
| 캐릭터 채팅 | `characters`, `character_aliases`, `chat_rooms`, `chat_messages` | 캐릭터 설정, 채팅방, 메시지와 추천 영화 기록 |
| 오늘의 추천 | `daily_ai_recommendations`, `daily_ai_recommendation_movies` | 날짜별 AI 추천 문구와 추천 영화 |
| 관리자 | `admin_audit_logs` | 관리자 변경 이력 저장용 테이블 |

주요 데이터 흐름은 다음과 같습니다.

```text
영화 조회·검색·좋아요
    -> user_movie_interactions
    -> movie_stats 랭킹 집계
    -> user_preference_scores 취향 학습

일반·캐릭터·그룹 채팅
    -> chat_rooms
    -> chat_messages
    -> 추천 영화가 있으면 JSONB 사본으로 함께 저장

오늘의 AI 추천
    -> daily_ai_recommendations
    -> daily_ai_recommendation_movies
    -> movies와 연결해 영화 카드 구성
```

DB 설계 원칙:

- Refresh Token과 인증·재설정 코드는 원문 대신 해시값을 저장합니다.
- 이미지 파일은 DB에 넣지 않고 프로필·포스터 경로만 저장합니다.
- 장르와 배우는 검색과 추천에 활용할 수 있도록 별도 테이블로 정규화합니다.
- 사용자 행동 원본과 행동을 분석한 취향 점수를 서로 다른 테이블에 저장합니다.
- 채팅 추천 영화는 대화 당시 화면을 복원할 수 있도록 메시지에 JSONB 사본으로 저장합니다.

컬럼, 인덱스, 제약조건, 삭제 정책은 [DB 스키마 명세](docs/db-schema-spec.md)에서 확인할 수 있습니다.

## 영화·캐릭터 데이터 준비

API를 실행하는 것만으로 영화와 캐릭터 데이터가 자동 생성되지는 않습니다. 필요한 경우 마이그레이션 후 적재 스크립트를 실행합니다.

### 영화 카탈로그 적재

`import_tmdb_popular_movies.py`는 영화와 함께 장르, 통계, 감독, 배우, 키워드를 동기화합니다. TMDB 인증 정보가 필요합니다.

먼저 적은 수량으로 미리 확인합니다. `--dry-run`은 DB를 변경하지 않습니다.

```bash
.venv/bin/python scripts/import_tmdb_popular_movies.py \
  --source catalog \
  --limit 20 \
  --cast-limit 10 \
  --dry-run
```

실제 카탈로그 적재 예시:

```bash
.venv/bin/python scripts/import_tmdb_popular_movies.py \
  --source catalog \
  --limit 12000 \
  --cast-limit 10
```

대량 적재 전에는 DB를 백업하고 대상 `DATABASE_URL`을 다시 확인합니다. 운영 DB에서는 기존 영화 데이터를 삭제하는 `--replace-existing-data`를 사용하지 않습니다.

### 기타 데이터 관리 도구

| 스크립트 | 용도 | 미리 확인하는 방법 |
| --- | --- | --- |
| `import_cineverse_characters.py` | 지원 캐릭터를 TMDB 정보와 연결해 저장 | `--dry-run` 사용 |
| `backfill_movie_keywords.py` | 비어 있는 영화 키워드 보정 | `--dry-run` 사용 |
| `update_movie_titles_ko.py` | 영화를 TMDB 한국어 제목으로 갱신 | 기본 실행이 미리보기이며 저장 시 `--commit` 사용 |
| `render_api_spec_html.py` | 프론트엔드 API Markdown 문서를 HTML로 생성 | 생성된 HTML 변경 내용 확인 |

```bash
.venv/bin/python scripts/import_cineverse_characters.py --dry-run
.venv/bin/python scripts/backfill_movie_keywords.py --dry-run
.venv/bin/python scripts/update_movie_titles_ko.py
.venv/bin/python scripts/render_api_spec_html.py
```

## 인증 방식

로그인과 인증 흐름은 다음과 같습니다.

1. `POST /auth/login` 성공 시 Access Token은 응답 본문으로 반환됩니다.
2. Refresh Token은 `/auth` 경로의 HttpOnly Cookie로 저장됩니다.
3. 인증이 필요한 API에는 Access Token을 Bearer 헤더로 전송합니다.
4. `/auth/refresh`, `/auth/logout` 호출 시 브라우저가 Cookie를 전송하도록 credentials 옵션을 활성화합니다.

```http
Authorization: Bearer <access_token>
```

## API 요약

### 시스템

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/` | API 실행 확인 |
| `GET` | `/health` | 백엔드 상태 확인 |
| `GET` | `/db-test` | PostgreSQL 연결 확인 |
| `GET` | `/ai-health` | AI 서버 연결 확인 |

### 인증

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/auth/email-verification/request` | 없음 | 회원가입 인증번호 발송 |
| `POST` | `/auth/register` | 인증번호 | 회원가입 |
| `POST` | `/auth/password-reset/request` | 없음 | 비밀번호 재설정 링크 발송 |
| `POST` | `/auth/password-reset/confirm` | 재설정 토큰 | 새 비밀번호 저장 |
| `POST` | `/auth/login` | 없음 | 로그인 및 토큰 발급 |
| `POST` | `/auth/refresh` | Refresh Cookie | Access Token 재발급 |
| `POST` | `/auth/logout` | Refresh Cookie | Refresh Token 폐기 및 Cookie 삭제 |

### 영화

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/movies/actors` | 없음 | 배우 목록 조회 |
| `POST` | `/movies/actor/{actor_id}` | 필요 | 선호 배우 저장 |
| `POST` | `/movies/recommend?limit=12` | 선택 | 기본 또는 개인화 영화 추천 |
| `GET` | `/movies/search?keyword=...&page=1&limit=20` | 없음 | 영화 검색 |
| `GET` | `/movies/ranking?limit=10` | 없음 | 실시간 영화 랭킹 |
| `GET` | `/movies/{movie_id}?source=direct` | 선택 | 영화 상세 조회 및 회원 행동 기록 |
| `POST` | `/movies/{movie_id}/like` | 필요 | 영화 좋아요 |
| `GET` | `/movies/today/recommend` | 없음 | 오늘의 AI 추천 영화 |
| `GET` | `/movies/genre/{genre}?page=1&limit=20` | 없음 | 장르별 영화 조회 |
| `POST` | `/movies/ai-recommend` | 없음 | 사용자 요청 기반 AI 영화 추천 |

### 채팅

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/chat/auto` | 필요 | 일반 AI 채팅 시작 |
| `GET` | `/chat/characters` | 없음 | 활성 캐릭터 목록 조회 |
| `GET` | `/chatcharcter/{character_name}` | 없음 | 캐릭터 단건 조회 |
| `POST` | `/chat` | 필요 | 캐릭터 1:1 실시간 채팅 시작 |
| `POST` | `/chat/group` | 필요 | 캐릭터 그룹 채팅 시작 |
| `GET` | `/chat/rooms` | 필요 | 내 채팅방 목록 조회 |
| `GET` | `/chat/rooms/{room_id}/messages` | 필요 | 채팅방 메시지 조회 |
| `POST` | `/chat/rooms/{room_id}/messages` | 필요 | 기존 채팅방에서 대화 계속 |
| `DELETE` | `/chat/rooms/{room_id}` | 필요 | 내 채팅방 삭제 |

`POST /chat`과 `POST /chat/rooms/{room_id}/messages`는 `text/event-stream` 형식으로 답변을 실시간 전송합니다.

### 사용자

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

### 관리자

모든 관리자 API에는 유효한 Access Token과 `users.is_admin = true`인 계정이
필요합니다. 영화 API의 `{movie_id}`는 TMDB ID가 아니라 `movies.id`입니다.

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/admin/check` | 관리자 | 현재 계정의 관리자 권한 확인 |
| `GET` | `/admin/tmdb-movies-search?query=...&page=1` | 관리자 | TMDB 영화 검색 및 내부 DB 등록 여부 확인 |
| `POST` | `/admin/tmdb-movies-register/{tmdb_id}` | 관리자 | TMDB 상세정보·장르·배우와 함께 영화 등록 |
| `POST` | `/admin/movie` | 관리자 | TMDB에 없는 영화 직접 등록 |
| `PATCH` | `/admin/movie/{movie_id}` | 관리자 | 내부 영화 ID 기준 부분 수정 |
| `DELETE` | `/admin/movie/{movie_id}` | 관리자 | 내부 영화 ID 기준 삭제 |
| `PATCH` | `/admin/users/admin-role` | 관리자 | 이메일로 관리자 권한 부여·회수 |

관리자 등록·수정·삭제와 권한 변경은 `admin_audit_logs`에 실행 관리자와
변경 전후 정보를 기록합니다. TMDB 영화의 배우 정보는 `movies.cast`,
`actors`, `movie_actors`의 일관성을 위해 수정 API에서 직접 변경할 수 없습니다.

요청·응답 형식과 상태 코드는 실행 중인 [Swagger UI](http://127.0.0.1:8080/docs) 또는 아래 상세 문서에서 확인할 수 있습니다.

## 운영 배포 전 확인

- `.env.example`의 예시 비밀정보를 실제 값으로 교체합니다.
- 충분히 길고 예측하기 어려운 `SECRET_KEY`를 사용합니다.
- 배포 전에 DB를 백업하고 `.venv/bin/alembic upgrade head`를 실행합니다.
- 서비스 프론트엔드 주소만 CORS에 허용합니다.
- HTTPS 환경에서는 Refresh Token Cookie에 `Secure` 설정을 적용합니다.
- Uvicorn의 `--reload` 옵션은 로컬 개발에서만 사용합니다.
- `app/uploads/`는 운영 환경에서 영속 볼륨과 별도 백업이 필요합니다.
- 문서 업로드 기능을 추가하더라도 저작권·계약 문서는 `/uploads` 정적 경로에
  그대로 공개하지 말고 권한 검사를 거치는 별도 다운로드 API를 사용합니다.

## 상세 문서

- [백엔드 API 명세](docs/backend-api-spec.md)
- [프론트엔드 연동 API 명세](docs/frontend-api-spec-notion.md)
- [캐릭터 상세 API 명세](docs/frontend-character-detail-api-spec.md)
- [DB 스키마 명세](docs/db-schema-spec.md)

## Git 저장 규칙

- `.env`, API 키, 토큰, SMTP 비밀번호 같은 비밀정보는 커밋하지 않습니다.
- 공유할 환경변수 이름과 예시는 `.env.example`에만 기록합니다.
- 가상환경, 캐시, 로컬 출력물과 업로드 파일은 저장소에 포함하지 않습니다.
- `external/`, `outputs/`, `.venv/`, `.vscode/`, `app/uploads/`의 실제 업로드 파일은 로컬 전용입니다.
- `scripts/`의 데이터 적재·보정 도구는 실행 절차를 재현할 수 있도록 Git으로 관리합니다.
