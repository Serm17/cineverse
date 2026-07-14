# CineVerse DB 명세서

작성 기준: 2026-07-14  
DB 기준: 루트 `app/models/*`, 루트 `alembic/versions/*`, 로컬 PostgreSQL `CineVerse` 직접 대조  
앱 DB URL: `.env`의 `DATABASE_URL`  
루트 Alembic head: `20260714_0011`  
현재 로컬 `alembic_version`: `20260714_0011`

## 1. 주의 사항

이 명세서는 루트 애플리케이션을 단일 기준으로 삼고, 실제 로컬 DB와 Alembic 메타데이터를 대조해 작성했습니다.

| 기준 자료 | 경로 |
| --- | --- |
| 루트 DB 모델 | `app/models/*` |
| 루트 Alembic | `alembic/versions/*` |
| 실제 DB 대조 | PostgreSQL `CineVerse` information_schema / pg_constraint / pg_indexes |
| 자동 정합성 검사 | `.venv/bin/alembic check` |

루트 ORM과 실제 로컬 DB에는 아래 비즈니스 테이블이 확인됩니다.

```text
actors
admin_audit_logs
character_aliases
characters
chat_messages
chat_rooms
daily_ai_recommendation_movies
daily_ai_recommendations
email_verification_codes
movie_actors
movie_genres
movie_stats
movies
password_reset_tokens
refresh_tokens
user_movie_interactions
user_preference_scores
users
```

루트 migration 흐름은 아래와 같습니다.

| revision | 파일 | 핵심 변경 |
| --- | --- | --- |
| `20260616_0001` | `20260616_0001_initial_schema.py` | 초기 사용자/영화/채팅/상호작용/통계/관리자 로그 |
| `25d8a2a18004` | `25d8a2a18004_add_refresh_tokens_table.py` | refresh token 테이블 |
| `20260702_0002` | `20260702_0002_add_recommended_movies_to_chat_messages.py` | `chat_messages.recommended_movies` JSONB |
| `20260703_0003` | `20260703_0003_sync_external_db_schema.py` | 선호 타입, 영화 장르 등 초기 통합 스키마 동기화 |
| `20260703_0004` | `20260703_0004_create_character_aliases.py` | `character_aliases` |
| `20260706_0007` | `20260706_0007_sync_external_profile_and_actors.py` | `users.profile_image`, `actors`, `movie_actors` |
| `20260709_0008` | `20260709_0008_create_daily_ai_recommendations.py` | `daily_ai_recommendations`, `daily_ai_recommendation_movies` |
| `20260714_0009` | `20260714_0009_create_password_reset_tokens.py` | `password_reset_tokens` |
| `20260714_0010` | `20260714_0010_create_email_verification_codes.py` | `email_verification_codes` |
| `20260714_0011` | `20260714_0011_add_revoked_at_to_password_reset_tokens.py` | 비밀번호 재설정 토큰 폐기 시각 |

정합성 메모:

- 실제 로컬 DB와 루트 Alembic은 모두 `20260714_0011` head입니다.
- `alembic/env.py`는 `Base.metadata`를 사용하며 모든 루트 ORM 모델을 autogenerate 검사에 포함합니다.
- `.venv/bin/alembic check` 결과 추가 upgrade operation이 없어 ORM과 실제 DB가 일치합니다.

현재 루트 앱 모델과 실제 DB의 차이:

| 항목 | 상태 |
| --- | --- | --- |
| ORM/DB 테이블 | 일치 |
| 컬럼 타입과 길이 | 일치 |
| 인덱스와 제약조건 | 일치 |

## 2. 테이블 요약

| 테이블 | 용도 | 주요 API/기능 |
| --- | --- | --- |
| `users` | 회원 계정, 프로필, 선호 배열 | Auth, User |
| `refresh_tokens` | refresh token hash 저장과 폐기 관리 | Auth |
| `password_reset_tokens` | 비밀번호 재설정용 일회성 token hash | Auth |
| `email_verification_codes` | 회원가입 이메일 인증 코드 hash | Auth |
| `movies` | 영화 원본/동기화 메타데이터 | Movies, Recommend, Chat |
| `movie_genres` | 영화-장르 정규화 테이블 | 검색, 장르별 조회 |
| `actors` | 배우 마스터 | 배우 목록, 선호 배우 |
| `movie_actors` | 영화-배우 N:M 연결 | 영화 데이터 확장 |
| `movie_stats` | 영화별 조회/검색/좋아요/랭킹 집계 | 랭킹, 추천 |
| `characters` | 채팅 캐릭터 설정 | Chat |
| `character_aliases` | 캐릭터 별칭 매핑 | Chat |
| `chat_rooms` | 사용자 채팅방 | Chat |
| `chat_messages` | 채팅 메시지와 추천 영화 snapshot | Chat, User 추천 이력 |
| `user_movie_interactions` | 조회, 검색 클릭, 좋아요 이벤트 | Movies, User, Ranking |
| `user_preference_scores` | 사용자 선호 점수 | 추천 계산용 |
| `daily_ai_recommendations` | 날짜별 AI 추천 문구 | 일일 추천 캐시 |
| `daily_ai_recommendation_movies` | 날짜별 AI 추천 영화 연결 | 일일 추천 캐시 |
| `admin_audit_logs` | 관리자 변경 감사 로그 | 관리자 기능 확장용 |

## 3. 관계 요약

| 관계 | 타입 | 삭제 정책 |
| --- | --- | --- |
| `users.id` -> `refresh_tokens.user_id` | 1:N | user 삭제 시 cascade |
| `users.id` -> `password_reset_tokens.user_id` | 1:N | user 삭제 시 cascade |
| `users.id` -> `chat_rooms.user_id` | 1:N | user 삭제 시 cascade |
| `users.id` -> `user_movie_interactions.user_id` | 1:N | user 삭제 시 cascade |
| `users.id` -> `user_preference_scores.user_id` | 1:N | user 삭제 시 cascade |
| `users.id` -> `admin_audit_logs.admin_user_id` | 1:N | user 삭제 시 set null |
| `movies.id` -> `movie_genres.movie_id` | 1:N | movie 삭제 시 cascade |
| `movies.id` -> `movie_actors.movie_id` | 1:N | movie 삭제 시 cascade |
| `movies.id` -> `movie_stats.movie_id` | 1:1 | movie 삭제 시 cascade |
| `movies.id` -> `characters.movie_id` | 1:N | movie 삭제 시 set null |
| `movies.id` -> `user_movie_interactions.movie_id` | 1:N | movie 삭제 시 cascade |
| `actors.id` -> `movie_actors.actor_id` | 1:N | actor 삭제 시 cascade |
| `characters.id` -> `character_aliases.character_id` | 1:N | character 삭제 시 cascade |
| `chat_rooms.id` -> `chat_messages.room_id` | 1:N | room 삭제 시 cascade |
| `daily_ai_recommendations.id` -> `daily_ai_recommendation_movies.daily_recommendation_id` | 1:N | recommendation 삭제 시 cascade |
| `movies.id` -> `daily_ai_recommendation_movies.movie_id` | 1:N | movie 삭제 시 cascade |

## 4. 테이블 상세

### 4.1 `users`

회원 계정, 로그인 정보, 프로필 이미지, 사용자의 명시/행동 기반 선호 배열을 저장합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | 사용자 PK |
| `email` | `varchar(255)` | NO |  | 로그인 이메일 |
| `password_hash` | `varchar(255)` | NO |  | bcrypt 해시 비밀번호 |
| `nickname` | `varchar(50)` | NO |  | 사용자 닉네임 |
| `preferred_genres` | `varchar[]` | YES |  | 선호 장르 배열 |
| `preferred_actors` | `varchar[]` | YES |  | 선호 배우 배열 |
| `preferred_keywords` | `varchar[]` | YES |  | 선호 키워드 배열 |
| `is_admin` | `boolean` | NO | `false` | 관리자 여부 |
| `created_at` | `timestamptz` | NO | `now()` | 생성 시각 |
| `updated_at` | `timestamptz` | NO | `now()` | 수정 시각 |
| `profile_image` | `varchar(300)` | YES |  | `/profile_images/...` 형태의 프로필 이미지 경로 |

키/인덱스:

| 이름 | 내용 |
| --- | --- |
| `users_pkey` | PK (`id`) |
| `ix_users_email` | UNIQUE INDEX (`email`) |

### 4.2 `refresh_tokens`

refresh token 원문은 저장하지 않고 SHA-256 hash만 저장합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NO | `gen_random_uuid()` | refresh token row PK |
| `user_id` | `bigint` | NO |  | `users.id` |
| `token_hash` | `varchar(255)` | NO |  | refresh token hash |
| `created_at` | `timestamptz` | NO | `now()` | 생성 시각 |
| `expires_at` | `timestamptz` | NO |  | 만료 시각 |
| `revoked_at` | `timestamptz` | YES |  | 로그아웃/폐기 시각 |
| `last_used_at` | `timestamptz` | YES |  | 마지막 재발급 사용 시각 |
| `user_agent` | `text` | YES |  | 로그인 요청의 User-Agent |

키/인덱스:

| 이름 | 내용 |
| --- | --- |
| `refresh_tokens_pkey` | PK (`id`) |
| `refresh_tokens_user_id_fkey` | FK (`user_id`) -> `users.id` ON DELETE CASCADE |
| `ix_refresh_tokens_token_hash` | UNIQUE INDEX (`token_hash`) |
| `ix_refresh_tokens_user_id` | INDEX (`user_id`) |

### 4.3 `movies`

TMDB 기반 영화 메타데이터와 검색/추천에 필요한 정보를 저장합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | 영화 PK |
| `tmdb_id` | `integer` | YES |  | TMDB 영화 ID |
| `title` | `varchar(300)` | NO |  | 영화 제목 |
| `overview` | `text` | YES |  | 줄거리 |
| `genres` | `varchar[]` | YES |  | 장르 배열 |
| `director` | `varchar(200)` | YES |  | 감독 |
| `cast` | `varchar[]` | YES |  | 주요 출연 배우 |
| `keywords` | `varchar[]` | YES |  | 검색/추천 키워드 |
| `year` | `integer` | YES |  | 개봉 연도 |
| `language` | `varchar(10)` | YES |  | 언어 코드 |
| `vote_average` | `double precision` | YES |  | TMDB 평균 평점 |
| `vote_count` | `integer` | YES |  | TMDB 투표 수 |
| `audience_count` | `bigint` | YES |  | 관객 수 |
| `poster_path` | `varchar(300)` | YES |  | 포스터 경로 또는 URL |
| `last_synced_at` | `timestamptz` | YES |  | 외부 데이터 동기화 시각 |
| `created_at` | `timestamptz` | NO | `now()` | 생성 시각 |
| `updated_at` | `timestamptz` | NO | `now()` | 수정 시각 |

키/인덱스:

| 이름 | 내용 |
| --- | --- |
| `movies_pkey` | PK (`id`) |
| `ix_movies_tmdb_id` | UNIQUE INDEX (`tmdb_id`) |
| `ix_movies_title` | INDEX (`title`) |

### 4.4 `movie_genres`

`movies.genres` 배열을 검색/집계하기 쉽게 영화-장르 row로 정규화한 테이블입니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | 장르 row PK |
| `movie_id` | `bigint` | NO |  | `movies.id` |
| `genre` | `varchar(50)` | NO |  | 단일 장르명 |

키/인덱스:

| 이름 | 내용 |
| --- | --- |
| `movie_genres_pkey` | PK (`id`) |
| `movie_genres_movie_id_fkey` | FK (`movie_id`) -> `movies.id` ON DELETE CASCADE |
| `uq_movie_genres_movie_genre` | UNIQUE (`movie_id`, `genre`) |
| `ix_movie_genres_movie_id` | INDEX (`movie_id`) |
| `ix_movie_genres_genre` | INDEX (`genre`) |

### 4.5 `actors`

배우 마스터 테이블입니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | 배우 PK |
| `tmdb_actor_id` | `integer` | YES |  | TMDB 배우 ID |
| `name` | `varchar(100)` | NO |  | 배우 이름 |
| `profile_path` | `varchar(300)` | YES |  | 프로필 이미지 경로 |
| `created_at` | `timestamptz` | NO | `now()` | 생성 시각 |
| `updated_at` | `timestamptz` | NO | `now()` | 수정 시각 |

키/인덱스:

| 이름 | 내용 |
| --- | --- |
| `actors_pkey` | PK (`id`) |
| `ix_actors_tmdb_actor_id` | UNIQUE INDEX (`tmdb_actor_id`) |
| `ix_actors_name` | INDEX (`name`) |

### 4.6 `movie_actors`

영화와 배우의 N:M 관계, 배역명, 출연 순서를 저장합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | 연결 row PK |
| `movie_id` | `bigint` | NO |  | `movies.id` |
| `actor_id` | `bigint` | NO |  | `actors.id` |
| `character_name` | `varchar(150)` | YES |  | 영화 안 배역명 |
| `cast_order` | `integer` | YES |  | 출연 순서 |

키/인덱스:

| 이름 | 내용 |
| --- | --- |
| `movie_actors_pkey` | PK (`id`) |
| `fk_movie_actors_movie_id_movies` | FK (`movie_id`) -> `movies.id` ON DELETE CASCADE |
| `fk_movie_actors_actor_id_actors` | FK (`actor_id`) -> `actors.id` ON DELETE CASCADE |
| `uq_movie_actors_movie_actor` | UNIQUE (`movie_id`, `actor_id`) |
| `ix_movie_actors_movie_id` | INDEX (`movie_id`) |
| `ix_movie_actors_actor_id` | INDEX (`actor_id`) |

### 4.7 `movie_stats`

영화별 행동 집계와 랭킹 점수를 캐시합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `movie_id` | `bigint` | NO |  | `movies.id`, PK |
| `view_count` | `integer` | NO | `0` | 상세 조회 수 |
| `search_click_count` | `integer` | NO | `0` | 검색 결과 클릭 수 |
| `like_count` | `integer` | NO | `0` | 좋아요 수 |
| `ranking_score` | `integer` | NO | `0` | 랭킹 정렬 점수 |
| `created_at` | `timestamptz` | NO | `now()` | 생성 시각 |
| `updated_at` | `timestamptz` | NO | `now()` | 수정 시각 |

키/인덱스:

| 이름 | 내용 |
| --- | --- |
| `movie_stats_pkey` | PK (`movie_id`) |
| `movie_stats_movie_id_fkey` | FK (`movie_id`) -> `movies.id` ON DELETE CASCADE |
| `ix_movie_stats_ranking_score` | INDEX (`ranking_score`) |

### 4.8 `characters`

AI 캐릭터 채팅에 필요한 캐릭터 설정과 시스템 프롬프트를 저장합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | 캐릭터 PK |
| `movie_id` | `bigint` | YES |  | 연결 영화 `movies.id` |
| `name` | `varchar(100)` | NO |  | 캐릭터 이름 |
| `movie_title` | `varchar(200)` | NO |  | 캐릭터가 등장하는 영화 제목 |
| `actor` | `varchar(100)` | YES |  | 배우 이름 |
| `lang` | `varchar(10)` | NO |  | 언어 코드 |
| `system_prompt` | `text` | NO |  | 캐릭터 시스템 프롬프트 |
| `profile_image` | `varchar(300)` | YES |  | 캐릭터 프로필 이미지 |
| `is_active` | `boolean` | NO | `true` | 채팅 노출 여부 |
| `created_at` | `timestamptz` | NO | `now()` | 생성 시각 |
| `updated_at` | `timestamptz` | NO | `now()` | 수정 시각 |

키/인덱스:

| 이름 | 내용 |
| --- | --- |
| `characters_pkey` | PK (`id`) |
| `characters_movie_id_fkey` | FK (`movie_id`) -> `movies.id` ON DELETE SET NULL |
| `ix_characters_name` | INDEX (`name`) |

### 4.9 `character_aliases`

사용자가 입력한 별칭을 정식 캐릭터 이름으로 매핑합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | 별칭 row PK |
| `character_id` | `bigint` | NO |  | `characters.id` |
| `alias` | `varchar(100)` | NO |  | 별칭 |

키/인덱스:

| 이름 | 내용 |
| --- | --- |
| `character_aliases_pkey` | PK (`id`) |
| `character_aliases_character_id_fkey` | FK (`character_id`) -> `characters.id` ON DELETE CASCADE |
| `ix_character_aliases_alias` | UNIQUE INDEX (`alias`) |
| `ix_character_aliases_character_id` | INDEX (`character_id`) |

### 4.10 `chat_rooms`

사용자의 일반, 캐릭터, 그룹 채팅방을 저장합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | 채팅방 PK |
| `user_id` | `bigint` | NO |  | `users.id` |
| `room_type` | `varchar(20)` | NO |  | `general`, `character`, `group` |
| `characters` | `varchar[]` | YES |  | 참여 캐릭터 이름 배열 |
| `created_at` | `timestamptz` | NO | `now()` | 생성 시각 |
| `updated_at` | `timestamptz` | NO | `now()` | 수정 시각 |

키/제약/인덱스:

| 이름 | 내용 |
| --- | --- |
| `chat_rooms_pkey` | PK (`id`) |
| `chat_rooms_user_id_fkey` | FK (`user_id`) -> `users.id` ON DELETE CASCADE |
| `ck_chat_rooms_room_type` | CHECK `room_type IN ('general', 'character', 'group')` |
| `ix_chat_rooms_user_id` | INDEX (`user_id`) |

### 4.11 `chat_messages`

채팅방의 사용자/assistant 메시지와 assistant가 추천한 영화 snapshot을 저장합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | 메시지 PK |
| `room_id` | `bigint` | NO |  | `chat_rooms.id` |
| `role` | `varchar(20)` | NO |  | `user`, `assistant` |
| `character_name` | `varchar(100)` | YES |  | assistant 캐릭터 이름 |
| `content` | `text` | NO |  | 메시지 본문 |
| `created_at` | `timestamptz` | NO | `now()` | 생성 시각 |
| `recommended_movies` | `jsonb` | YES |  | 추천 영화 snapshot |

키/제약/인덱스:

| 이름 | 내용 |
| --- | --- |
| `chat_messages_pkey` | PK (`id`) |
| `chat_messages_room_id_fkey` | FK (`room_id`) -> `chat_rooms.id` ON DELETE CASCADE |
| `ck_chat_messages_role` | CHECK `role IN ('user', 'assistant')` |
| `ix_chat_messages_room_id` | INDEX (`room_id`) |

### 4.12 `user_movie_interactions`

사용자의 영화 행동 이벤트를 누적 저장합니다. 랭킹, 최근 본 영화, 좋아요 목록, 선호도 학습의 원천입니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | interaction PK |
| `user_id` | `bigint` | NO |  | `users.id` |
| `movie_id` | `bigint` | NO |  | `movies.id` |
| `action_type` | `varchar(20)` | NO |  | `view`, `search_click`, `like` |
| `source` | `varchar(20)` | NO | `unknown` | 유입 경로 |
| `score_delta` | `integer` | NO |  | 랭킹/추천 반영 점수 |
| `created_at` | `timestamptz` | NO | `now()` | 기록 시각 |

키/제약/인덱스:

| 이름 | 내용 |
| --- | --- |
| `user_movie_interactions_pkey` | PK (`id`) |
| `user_movie_interactions_user_id_fkey` | FK (`user_id`) -> `users.id` ON DELETE CASCADE |
| `user_movie_interactions_movie_id_fkey` | FK (`movie_id`) -> `movies.id` ON DELETE CASCADE |
| `ck_user_movie_interactions_action_type` | CHECK `action_type IN ('view', 'search_click', 'like')` |
| `ck_user_movie_interactions_source` | CHECK `source IN ('direct', 'search', 'recommend', 'ranking', 'admin', 'unknown')` |
| `ix_user_movie_interactions_user_id` | INDEX (`user_id`) |
| `ix_user_movie_interactions_movie_id` | INDEX (`movie_id`) |
| `ix_user_movie_interactions_created_at` | INDEX (`created_at`) |

### 4.13 `user_preference_scores`

사용자별 선호 타입/값에 대한 누적 점수를 저장합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | 선호 점수 PK |
| `user_id` | `bigint` | NO |  | `users.id` |
| `preference_type` | `varchar(20)` | NO |  | 선호 타입 |
| `preference_value` | `varchar(200)` | NO |  | 선호 값 |
| `score` | `double precision` | NO | `0` | 누적 점수 |
| `created_at` | `timestamptz` | NO | `now()` | 생성 시각 |
| `updated_at` | `timestamptz` | NO | `now()` | 수정 시각 |

허용 `preference_type`:

| 값 |
| --- |
| `genre` |
| `actor` |
| `director` |
| `keyword` |
| `language` |
| `character` |

키/제약/인덱스:

| 이름 | 내용 |
| --- | --- |
| `user_preference_scores_pkey` | PK (`id`) |
| `user_preference_scores_user_id_fkey` | FK (`user_id`) -> `users.id` ON DELETE CASCADE |
| `ck_user_preference_scores_preference_type` | CHECK 허용 타입 |
| `uq_user_preference_scores_value` | UNIQUE (`user_id`, `preference_type`, `preference_value`) |
| `ix_user_preference_scores_user_id` | INDEX (`user_id`) |

### 4.14 `daily_ai_recommendations`

날짜별 AI 추천 문구를 저장하는 테이블입니다. 루트의 `DailyAiRecommendation` ORM 모델과 `20260709_0008` migration이 관리합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | 일일 추천 PK |
| `recommend_date` | `date` | NO |  | 추천 날짜 |
| `answer` | `text` | NO |  | AI 추천 문구 |
| `created_at` | `timestamptz` | NO | `now()` | 생성 시각 |

키/인덱스:

| 이름 | 내용 |
| --- | --- |
| `daily_ai_recommendations_pkey` | PK (`id`) |
| `ix_daily_ai_recommendations_recommend_date` | UNIQUE INDEX (`recommend_date`) |

### 4.15 `daily_ai_recommendation_movies`

날짜별 AI 추천과 영화의 연결 테이블입니다. 한 날짜 추천 안에서 영화 순서를 저장하며, 루트의 `DailyAiRecommendationMovie` ORM 모델이 관리합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `daily_recommendation_id` | `bigint` | NO |  | `daily_ai_recommendations.id` |
| `movie_id` | `bigint` | NO |  | `movies.id` |
| `display_order` | `integer` | NO |  | 노출 순서 |

키/제약/인덱스:

| 이름 | 내용 |
| --- | --- |
| `daily_ai_recommendation_movies_pkey` | PK (`daily_recommendation_id`, `movie_id`) |
| `daily_ai_recommendation_movies_daily_recommendation_id_fkey` | FK (`daily_recommendation_id`) -> `daily_ai_recommendations.id` ON DELETE CASCADE |
| `daily_ai_recommendation_movies_movie_id_fkey` | FK (`movie_id`) -> `movies.id` ON DELETE CASCADE |
| `ck_daily_ai_recommendation_movies_display_order` | CHECK `display_order >= 1 AND display_order <= 3` |
| `uq_daily_ai_recommendation_movies_order` | UNIQUE (`daily_recommendation_id`, `display_order`) |

### 4.16 `admin_audit_logs`

관리자 변경 작업 감사 로그입니다. 루트의 `AdminAuditLog` ORM 모델이 테이블 구조를 관리합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | NO | sequence | 감사 로그 PK |
| `admin_user_id` | `bigint` | YES |  | 작업 관리자 `users.id` |
| `target_table` | `varchar(100)` | NO |  | 변경 대상 테이블 |
| `target_id` | `bigint` | YES |  | 변경 대상 row id |
| `action` | `varchar(50)` | NO |  | 작업 종류 |
| `before_data` | `text` | YES |  | 변경 전 데이터 |
| `after_data` | `text` | YES |  | 변경 후 데이터 |
| `created_at` | `timestamptz` | NO | `now()` | 기록 시각 |

키/인덱스:

| 이름 | 내용 |
| --- | --- |
| `admin_audit_logs_pkey` | PK (`id`) |
| `admin_audit_logs_admin_user_id_fkey` | FK (`admin_user_id`) -> `users.id` ON DELETE SET NULL |

### 4.17 `password_reset_tokens`

비밀번호 재설정 링크에 사용하는 일회성 token hash를 저장합니다. 정상 사용은 `used_at`, 발송 실패나 다른 토큰 무효화는 `revoked_at`으로 구분합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NO | `gen_random_uuid()` | 재설정 토큰 PK |
| `user_id` | `bigint` | NO |  | 대상 사용자 `users.id` |
| `token_hash` | `varchar(255)` | NO |  | 원문을 저장하지 않은 SHA-256 hash |
| `created_at` | `timestamptz` | NO | `now()` | 생성 시각 |
| `expires_at` | `timestamptz` | NO |  | 만료 시각 |
| `used_at` | `timestamptz` | YES |  | 정상 사용 완료 시각 |
| `revoked_at` | `timestamptz` | YES |  | 사용 전 폐기 시각 |

### 4.18 `email_verification_codes`

회원가입 전에 이메일 기준으로 발급한 인증 코드 hash와 입력 실패 횟수를 저장합니다.

| 컬럼 | 타입 | Null | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NO | `gen_random_uuid()` | 인증 코드 PK |
| `email` | `varchar(255)` | NO |  | 인증 대상 이메일 |
| `purpose` | `varchar(30)` | NO | `signup` | 인증 목적 |
| `code_hash` | `varchar(255)` | NO |  | bcrypt 인증 코드 hash |
| `created_at` | `timestamptz` | NO | `now()` | 생성 시각 |
| `expires_at` | `timestamptz` | NO |  | 만료 시각 |
| `verified_at` | `timestamptz` | YES |  | 인증 완료 시각 |
| `attempt_count` | `integer` | NO | `0` | 입력 실패 횟수 |

## 5. 주요 데이터 흐름

### 5.1 로그인과 토큰

1. `POST /auth/login` 성공 시 `users`에서 회원을 확인합니다.
2. access token은 응답 body로 반환합니다.
3. refresh token 원문은 HttpOnly cookie로 내려줍니다.
4. DB에는 `refresh_tokens.token_hash`만 저장합니다.
5. `POST /auth/logout` 또는 만료 시 `revoked_at`, `expires_at`으로 유효성을 판단합니다.

### 5.2 영화 상세 조회와 랭킹

1. 로그인 사용자가 `GET /movies/{movie_id}`를 호출하면 `user_movie_interactions`에 `view` 또는 `search_click` 기록이 저장됩니다.
2. `movie_stats`의 `view_count`, `search_click_count`, `ranking_score`가 증가합니다.
3. `GET /movies/ranking`은 `movie_stats`와 `movies`를 조합해 점수순으로 조회합니다.

### 5.3 좋아요

1. `POST /movies/{movie_id}/like`는 중복 좋아요를 확인합니다.
2. `user_movie_interactions.action_type = like`를 저장합니다.
3. `movie_stats.like_count`, `movie_stats.ranking_score`를 증가시킵니다.
4. 영화의 장르, 배우, 키워드를 `users.preferred_*` 배열에 누적합니다.
5. `DELETE /user/movie-like/{movie_id}`는 like interaction을 삭제하고 집계 값을 감소시킵니다.

### 5.4 채팅

1. 채팅 시작 시 `chat_rooms`가 생성됩니다.
2. 사용자 메시지와 assistant 응답이 `chat_messages`에 저장됩니다.
3. assistant 응답에 추천 영화가 있으면 `chat_messages.recommended_movies` JSONB에 snapshot으로 저장합니다.
4. `/user/chatai-reommended-movies`는 이 JSONB snapshot을 사용자별로 모아 보여줍니다.

## 6. 운영/정리 메모

| 항목 | 메모 |
| --- | --- |
| Migration 정합성 | 루트와 로컬 DB 모두 `20260714_0011`이며 `alembic check`를 통과합니다. |
| Timestamp 자동 갱신 | `updated_at`은 대부분 `server_default=now()`만 있고 자동 `on update` 트리거는 확인되지 않습니다. 수정 시 코드에서 직접 갱신해야 합니다. |
| 배열 컬럼 | `users.preferred_*`, `movies.genres`, `movies.cast`, `movies.keywords`, `chat_rooms.characters`는 PostgreSQL ARRAY 타입입니다. |
| 추천 snapshot | `chat_messages.recommended_movies`는 정규화 테이블이 아니라 JSONB snapshot입니다. |
| 프로필 이미지 | 파일은 DB에 바이너리로 저장하지 않고 경로만 `users.profile_image`에 저장합니다. |
