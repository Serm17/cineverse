"""Import TMDB movies and their related catalog data into PostgreSQL.

Usage:
    TMDB_ACCESS_TOKEN=... .venv/bin/python scripts/import_tmdb_popular_movies.py

Movies, normalized genres, ranking-stat placeholders, actors, and movie/actor
relationships are synchronized together. Character data is never modified.

The script only allows local DB hosts by default so accidental production imports
fail fast. Use --dry-run first if you want to preview the TMDB rows.
"""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine, func, select, text
from sqlalchemy.dialects.postgresql import ARRAY, insert as pg_insert
from sqlalchemy.engine import URL, make_url


DEFAULT_DATABASE_URL = "postgresql://postgres:1234@localhost:5432/CineVerse"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
LOCAL_DB_HOSTS = {None, "", "localhost", "127.0.0.1", "::1"}
DEFAULT_LIMIT = 40
DEFAULT_LANGUAGE = "ko-KR"
DEFAULT_REGION = "KR"
DEFAULT_CAST_LIMIT = 10
SUPPORTED_ORIGINAL_LANGUAGES = {"en", "ko"}
UPSERT_BATCH_SIZE = 1000
TMDB_MAX_RETRIES = 5
TMDB_MAX_LIST_PAGE = 500
DEFAULT_CATALOG_START_YEAR = 1980

metadata = MetaData()

movies_table = Table(
    "movies",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("tmdb_id", Integer),
    Column("title", String(300)),
    Column("overview", Text),
    Column("genres", ARRAY(String)),
    Column("director", String(200)),
    Column("cast", ARRAY(String)),
    Column("keywords", ARRAY(String)),
    Column("year", Integer),
    Column("language", String(10)),
    Column("vote_average", Float),
    Column("vote_count", Integer),
    Column("audience_count", BigInteger),
    Column("poster_path", String(300)),
    Column("last_synced_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)

movie_stats_table = Table(
    "movie_stats",
    metadata,
    Column("movie_id", BigInteger, primary_key=True),
    Column("view_count", Integer),
    Column("search_click_count", Integer),
    Column("like_count", Integer),
    Column("ranking_score", Integer),
)

movie_genres_table = Table(
    "movie_genres",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("movie_id", BigInteger, nullable=False),
    Column("genre", String(50), nullable=False),
)

actors_table = Table(
    "actors",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("tmdb_actor_id", Integer),
    Column("name", String(100)),
    Column("profile_path", String(300)),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)

movie_actors_table = Table(
    "movie_actors",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("movie_id", BigInteger, nullable=False),
    Column("actor_id", BigInteger, nullable=False),
    Column("character_name", String(150)),
    Column("cast_order", Integer),
)


@dataclass(frozen=True)
class CastCredit:
    tmdb_actor_id: int
    name: str
    profile_path: str | None
    character_name: str | None
    cast_order: int | None


@dataclass(frozen=True)
class MovieExtras:
    director: str | None
    cast_names: list[str]
    keywords: list[str]
    cast_credits: list[CastCredit]
    credits_loaded: bool


@dataclass(frozen=True)
class ImportCounts:
    movies: int
    movie_stats: int
    movie_genres: int
    actors: int
    movie_actors: int


class TMDBClient:
    def __init__(self) -> None:
        access_token = os.getenv("TMDB_ACCESS_TOKEN")
        api_key = os.getenv("TMDB_API_KEY")
        if not access_token and not api_key:
            raise SystemExit(
                "TMDB_ACCESS_TOKEN 또는 TMDB_API_KEY 환경변수가 필요합니다. "
                "예: TMDB_ACCESS_TOKEN=... .venv/bin/python scripts/import_tmdb_popular_movies.py"
            )

        headers = {"accept": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        self._api_key = None if access_token else api_key
        self._client = httpx.Client(base_url=TMDB_BASE_URL, headers=headers, timeout=20.0)

    def close(self) -> None:
        self._client.close()

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_params = dict(params or {})
        if self._api_key:
            request_params["api_key"] = self._api_key

        last_error: str | None = None
        for attempt in range(TMDB_MAX_RETRIES):
            try:
                response = self._client.get(path, params=request_params)
            except httpx.RequestError as exc:
                last_error = str(exc)
                if attempt == TMDB_MAX_RETRIES - 1:
                    break
                wait_seconds = float(2**attempt)
                print(f"[warn] TMDB 네트워크 재시도 대기: seconds={wait_seconds:g}, path={path}")
                time.sleep(wait_seconds)
                continue

            if response.status_code != 429 and response.status_code < 500:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise RuntimeError(f"TMDB 요청 실패: {path} ({response.status_code}) {response.text}") from exc
                return response.json()

            if attempt == TMDB_MAX_RETRIES - 1:
                break

            retry_after = response.headers.get("Retry-After")
            try:
                wait_seconds = float(retry_after) if retry_after else float(2**attempt)
            except ValueError:
                wait_seconds = float(2**attempt)
            print(f"[warn] TMDB 재시도 대기: status={response.status_code}, seconds={wait_seconds:g}, path={path}")
            time.sleep(wait_seconds)

        if last_error is not None:
            raise RuntimeError(f"TMDB 네트워크 요청 실패: {path} ({last_error})")
        raise RuntimeError(f"TMDB 요청 실패: {path} ({response.status_code}) {response.text}")


def load_local_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            os.environ.setdefault(key, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TMDB 영화와 관련 장르·배우 데이터를 PostgreSQL에 동기화합니다.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"가져올 영화 수 (기본값: {DEFAULT_LIMIT})")
    parser.add_argument(
        "--source",
        choices=("popular", "catalog"),
        default="popular",
        help="popular는 현재 인기순, catalog는 연도·원어별로 고르게 수집합니다. (기본값: popular)",
    )
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help=f"TMDB 응답 언어 (기본값: {DEFAULT_LANGUAGE})")
    parser.add_argument("--region", default=DEFAULT_REGION, help=f"인기 영화 지역 코드 (기본값: {DEFAULT_REGION})")
    parser.add_argument(
        "--start-year",
        type=int,
        default=DEFAULT_CATALOG_START_YEAR,
        help=f"catalog 수집 시작 연도 (기본값: {DEFAULT_CATALOG_START_YEAR})",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=datetime.now(UTC).year,
        help="catalog 수집 종료 연도 (기본값: 현재 연도)",
    )
    parser.add_argument(
        "--min-vote-count",
        type=int,
        default=20,
        help="catalog 영화의 최소 TMDB 투표 수 (기본값: 20)",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="저장할 PostgreSQL URL. 기본값은 DATABASE_URL 또는 로컬 CineVerse DB입니다.",
    )
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 가져올 데이터만 미리 확인합니다.")
    parser.add_argument(
        "--skip-extra-details",
        action="store_true",
        help="감독/출연진/키워드와 actors/movie_actors 동기화를 건너뜁니다.",
    )
    parser.add_argument(
        "--cast-limit",
        type=int,
        default=DEFAULT_CAST_LIMIT,
        help=f"영화별로 actors/movie_actors에 저장할 주요 출연진 수 (기본값: {DEFAULT_CAST_LIMIT})",
    )
    parser.add_argument(
        "--allow-non-local-db",
        action="store_true",
        help="localhost가 아닌 DB URL도 허용합니다. 로컬 적재에서는 사용하지 않는 것을 권장합니다.",
    )
    parser.add_argument(
        "--replace-existing-data",
        action="store_true",
        help="기존 movies 데이터를 삭제한 뒤 새 기준으로 다시 저장하고 movie_stats를 0으로 초기화합니다.",
    )
    return parser.parse_args()


def normalize_database_url(raw_url: str) -> URL:
    url = make_url(raw_url)
    if url.drivername == "postgresql":
        return url.set(drivername="postgresql+psycopg")
    return url


def ensure_local_database(url: URL, allow_non_local_db: bool) -> None:
    if allow_non_local_db:
        return

    if url.host not in LOCAL_DB_HOSTS:
        raise SystemExit(
            f"로컬 DB만 허용됩니다. 현재 DB host={url.host!r}. "
            "정말 원격 DB에 넣어야 한다면 --allow-non-local-db를 명시하세요."
        )


def truncate(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    return value[:max_length]


def tmdb_image_url(path: str | None) -> str | None:
    if not path or not path.strip():
        return None

    image_path = path.strip()
    if image_path.startswith(("http://", "https://")):
        return image_path

    if not image_path.startswith("/"):
        image_path = f"/{image_path}"
    return f"{TMDB_IMAGE_BASE_URL}{image_path}"


def unique_names(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        name = item.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def parse_year(release_date: str | None) -> int | None:
    if not release_date or len(release_date) < 4:
        return None
    year_text = release_date[:4]
    return int(year_text) if year_text.isdigit() else None


def is_korean_or_english_title(title: str | None) -> bool:
    # 서비스 화면에서는 한국어/영어 제목만 보여주기 위해 제목 문자 범위를 검사한다.
    # 한글, 영문, 숫자, 공백, 일반적인 제목용 문장부호만 허용한다.
    if not title or not title.strip():
        return False

    has_letter_or_number = False
    allowed_punctuation = set(".,:;!?/\\'\"()[]{}+-&·…#@%°_")

    for char in title.strip():
        code = ord(char)

        if char.isspace() or char in allowed_punctuation:
            continue

        if "0" <= char <= "9" or "A" <= char <= "Z" or "a" <= char <= "z":
            has_letter_or_number = True
            continue

        if 0xAC00 <= code <= 0xD7A3 or 0x1100 <= code <= 0x11FF or 0x3130 <= code <= 0x318F:
            has_letter_or_number = True
            continue

        return False

    return has_letter_or_number


def is_supported_original_movie(movie: dict[str, Any]) -> bool:
    # 19금/adult 영화는 서비스 기본 영화 목록에서 제외한다.
    if movie.get("adult"):
        return False

    # 원문 언어가 영어/한국어인 영화만 저장한다.
    if movie.get("original_language") not in SUPPORTED_ORIGINAL_LANGUAGES:
        return False

    # 저장 제목은 original_title을 사용하므로, 원제 자체도 한글/영문 범위인지 확인한다.
    return is_korean_or_english_title(movie.get("original_title"))


def fetch_genre_map(tmdb: TMDBClient, language: str) -> dict[int, str]:
    payload = tmdb.get("/genre/movie/list", {"language": language})
    return {genre["id"]: genre["name"] for genre in payload.get("genres", [])}


def fetch_popular_movies(tmdb: TMDBClient, limit: int, language: str, region: str) -> list[dict[str, Any]]:
    movies: list[dict[str, Any]] = []
    page = 1

    while len(movies) < limit:
        params: dict[str, Any] = {"language": language, "page": page}
        if region:
            params["region"] = region

        payload = tmdb.get("/movie/popular", params)
        results = payload.get("results", [])
        if not results:
            break

        for movie in results:
            if is_supported_original_movie(movie):
                movies.append(movie)
                if len(movies) >= limit:
                    break

        if page >= payload.get("total_pages", page):
            break
        page += 1

    return movies[:limit]


def fetch_catalog_movies(
    tmdb: TMDBClient,
    limit: int,
    language: str,
    region: str,
    start_year: int,
    end_year: int,
    min_vote_count: int,
) -> list[dict[str, Any]]:
    """Collect a balanced catalog by round-robin over year/language slices."""
    movies: list[dict[str, Any]] = []
    seen_tmdb_ids: set[int] = set()
    slices = [
        {"year": year, "original_language": original_language, "page": 1}
        for year in range(end_year, start_year - 1, -1)
        for original_language in sorted(SUPPORTED_ORIGINAL_LANGUAGES)
    ]

    while slices and len(movies) < limit:
        next_slices: list[dict[str, Any]] = []
        for source_slice in slices:
            params: dict[str, Any] = {
                "language": language,
                "page": source_slice["page"],
                "include_adult": "false",
                "include_video": "false",
                "sort_by": "popularity.desc",
                "primary_release_year": source_slice["year"],
                "with_original_language": source_slice["original_language"],
                "vote_count.gte": min_vote_count,
            }
            if region:
                params["region"] = region

            payload = tmdb.get("/discover/movie", params)
            for movie in payload.get("results", []):
                raw_tmdb_id = movie.get("id")
                if not isinstance(raw_tmdb_id, int) or raw_tmdb_id in seen_tmdb_ids:
                    continue
                if not is_supported_original_movie(movie):
                    continue
                seen_tmdb_ids.add(raw_tmdb_id)
                movies.append(movie)
                if len(movies) >= limit:
                    break

            total_pages = min(int(payload.get("total_pages") or 1), TMDB_MAX_LIST_PAGE)
            if source_slice["page"] < total_pages:
                next_slices.append({**source_slice, "page": source_slice["page"] + 1})

            if len(movies) >= limit:
                break

        print(f"[catalog] {len(movies)}/{limit}개 목록 수집 완료")
        slices = next_slices

    if len(movies) < limit:
        print(f"[warn] 조건에 맞는 catalog 영화가 목표보다 적습니다: requested={limit}, fetched={len(movies)}")
    return movies


def choose_original_title(movie: dict[str, Any]) -> str:
    # 번역 제목이 아니라 TMDB 원제(original_title)를 저장한다.
    # fetch_popular_movies에서 adult 제외, 원문 언어 en/ko, 제목 문자 범위를 이미 필터링한다.
    tmdb_id = int(movie["id"])
    return truncate(movie.get("original_title"), 300) or f"TMDB {tmdb_id}"


def fetch_movie_extras(tmdb: TMDBClient, tmdb_id: int, language: str, cast_limit: int) -> MovieExtras:
    try:
        details = tmdb.get(
            f"/movie/{tmdb_id}",
            {
                "language": language,
                "append_to_response": "credits,keywords",
            },
        )
    except RuntimeError as exc:
        print(f"[warn] 상세 출연진/키워드 생략: tmdb_id={tmdb_id} ({exc})")
        return MovieExtras(None, [], [], [], False)

    credits = details.get("credits") or {}
    directors = [
        crew_member.get("name", "")
        for crew_member in credits.get("crew", [])
        if crew_member.get("job") == "Director"
    ]
    director = truncate(", ".join(unique_names(directors)), 200) or None

    cast_credits: list[CastCredit] = []
    seen_actor_ids: set[int] = set()
    for default_order, cast_member in enumerate(credits.get("cast", [])):
        raw_actor_id = cast_member.get("id")
        name = (cast_member.get("name") or "").strip()
        if not isinstance(raw_actor_id, int) or not name or raw_actor_id in seen_actor_ids:
            continue

        seen_actor_ids.add(raw_actor_id)
        raw_order = cast_member.get("order")
        cast_credits.append(
            CastCredit(
                tmdb_actor_id=raw_actor_id,
                name=truncate(name, 100) or f"TMDB Actor {raw_actor_id}",
                profile_path=truncate(tmdb_image_url(cast_member.get("profile_path")), 300),
                character_name=truncate((cast_member.get("character") or "").strip() or None, 150),
                cast_order=raw_order if isinstance(raw_order, int) else default_order,
            )
        )
        if len(cast_credits) >= cast_limit:
            break

    keyword_payload = details.get("keywords") or {}
    keywords = unique_names([keyword.get("name", "") for keyword in keyword_payload.get("keywords", [])])

    return MovieExtras(
        director=director,
        cast_names=[credit.name for credit in cast_credits],
        keywords=keywords,
        cast_credits=cast_credits,
        credits_loaded=True,
    )


def build_movie_rows(
    tmdb: TMDBClient,
    source_movies: list[dict[str, Any]],
    genre_map: dict[int, str],
    language: str,
    skip_extra_details: bool,
    cast_limit: int,
) -> tuple[list[dict[str, Any]], dict[int, list[CastCredit]]]:
    synced_at = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    cast_credits_by_movie: dict[int, list[CastCredit]] = {}
    seen_tmdb_ids: set[int] = set()

    for index, movie in enumerate(source_movies, start=1):
        tmdb_id = int(movie["id"])
        if tmdb_id in seen_tmdb_ids:
            continue
        seen_tmdb_ids.add(tmdb_id)

        extras = MovieExtras(None, [], [], [], False)

        if not skip_extra_details:
            extras = fetch_movie_extras(tmdb, tmdb_id, language, cast_limit)
            if extras.credits_loaded:
                # 키가 있고 빈 리스트인 경우도 "출연진 0명"이라는 정상 응답이므로
                # 기존 movie_actors 관계를 비우는 동기화 대상으로 취급한다.
                cast_credits_by_movie[tmdb_id] = extras.cast_credits

        genre_names = [
            genre_map[genre_id]
            for genre_id in movie.get("genre_ids", [])
            if genre_id in genre_map
        ]

        rows.append(
            {
                "tmdb_id": tmdb_id,
                "title": choose_original_title(movie),
                "overview": movie.get("overview") or None,
                "genres": genre_names or None,
                "director": extras.director,
                "cast": extras.cast_names or None,
                "keywords": extras.keywords or None,
                "year": parse_year(movie.get("release_date")),
                "language": truncate(movie.get("original_language"), 10),
                "vote_average": movie.get("vote_average"),
                "vote_count": movie.get("vote_count"),
                "audience_count": None,
                "poster_path": truncate(tmdb_image_url(movie.get("poster_path")), 300),
                "last_synced_at": synced_at,
            }
        )

        if index % 10 == 0 or index == len(source_movies):
            print(f"[fetch] {index}/{len(source_movies)}개 변환 완료")

    return rows, cast_credits_by_movie


def batched(items: list[Any], size: int = UPSERT_BATCH_SIZE):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def affected_row_count(result, fallback: int) -> int:
    rowcount = result.rowcount
    return rowcount if rowcount is not None and rowcount >= 0 else fallback


def load_id_map(connection, table: Table, external_column, external_ids: list[int]) -> dict[int, int]:
    result: dict[int, int] = {}
    for batch in batched(external_ids):
        rows = connection.execute(
            select(table.c.id, external_column).where(external_column.in_(batch))
        )
        result.update({int(external_id): int(row_id) for row_id, external_id in rows if external_id is not None})
    return result


def sync_movie_genres(connection, movie_id_by_tmdb_id: dict[int, int], rows: list[dict[str, Any]]) -> int:
    imported_movie_ids = list(movie_id_by_tmdb_id.values())
    for batch in batched(imported_movie_ids):
        connection.execute(movie_genres_table.delete().where(movie_genres_table.c.movie_id.in_(batch)))

    genre_rows: list[dict[str, Any]] = []
    for row in rows:
        movie_id = movie_id_by_tmdb_id.get(int(row["tmdb_id"]))
        if movie_id is None:
            continue
        for genre in row.get("genres") or []:
            genre_rows.append({"movie_id": movie_id, "genre": truncate(genre, 50)})

    inserted_count = 0
    for batch in batched(genre_rows):
        stmt = pg_insert(movie_genres_table).values(batch).on_conflict_do_nothing(
            index_elements=[movie_genres_table.c.movie_id, movie_genres_table.c.genre]
        )
        result = connection.execute(stmt)
        inserted_count += affected_row_count(result, len(batch))
    return inserted_count


def sync_movie_actors(
    connection,
    movie_id_by_tmdb_id: dict[int, int],
    cast_credits_by_movie: dict[int, list[CastCredit]],
) -> tuple[int, int]:
    if not cast_credits_by_movie:
        return 0, 0

    actor_rows_by_tmdb_id: dict[int, dict[str, Any]] = {}
    for credits in cast_credits_by_movie.values():
        for credit in credits:
            existing = actor_rows_by_tmdb_id.get(credit.tmdb_actor_id)
            if existing is None:
                actor_rows_by_tmdb_id[credit.tmdb_actor_id] = {
                    "tmdb_actor_id": credit.tmdb_actor_id,
                    "name": credit.name,
                    "profile_path": credit.profile_path,
                }
            elif not existing["profile_path"] and credit.profile_path:
                existing["profile_path"] = credit.profile_path

    actor_rows = list(actor_rows_by_tmdb_id.values())
    changed_actor_count = 0
    for batch in batched(actor_rows):
        stmt = pg_insert(actors_table).values(batch)
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[actors_table.c.tmdb_actor_id],
            set_={
                "name": excluded.name,
                "profile_path": func.coalesce(excluded.profile_path, actors_table.c.profile_path),
                "updated_at": func.now(),
            },
        )
        result = connection.execute(stmt)
        changed_actor_count += affected_row_count(result, len(batch))

    actor_id_by_tmdb_id = load_id_map(
        connection,
        actors_table,
        actors_table.c.tmdb_actor_id,
        list(actor_rows_by_tmdb_id),
    )

    synchronized_movie_ids = [
        movie_id_by_tmdb_id[tmdb_movie_id]
        for tmdb_movie_id in cast_credits_by_movie
        if tmdb_movie_id in movie_id_by_tmdb_id
    ]
    for batch in batched(synchronized_movie_ids):
        connection.execute(movie_actors_table.delete().where(movie_actors_table.c.movie_id.in_(batch)))

    relationship_rows: list[dict[str, Any]] = []
    for tmdb_movie_id, credits in cast_credits_by_movie.items():
        movie_id = movie_id_by_tmdb_id.get(tmdb_movie_id)
        if movie_id is None:
            continue
        for credit in credits:
            actor_id = actor_id_by_tmdb_id.get(credit.tmdb_actor_id)
            if actor_id is None:
                continue
            relationship_rows.append(
                {
                    "movie_id": movie_id,
                    "actor_id": actor_id,
                    "character_name": credit.character_name,
                    "cast_order": credit.cast_order,
                }
            )

    relationship_count = 0
    for batch in batched(relationship_rows):
        stmt = pg_insert(movie_actors_table).values(batch)
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[movie_actors_table.c.movie_id, movie_actors_table.c.actor_id],
            set_={
                "character_name": excluded.character_name,
                "cast_order": excluded.cast_order,
            },
        )
        result = connection.execute(stmt)
        relationship_count += affected_row_count(result, len(batch))

    return changed_actor_count, relationship_count


def upsert_movies(
    database_url: URL,
    rows: list[dict[str, Any]],
    cast_credits_by_movie: dict[int, list[CastCredit]],
    update_extra_details: bool,
    replace_existing_data: bool,
) -> ImportCounts:
    engine = create_engine(database_url)

    with engine.begin() as connection:
        if replace_existing_data:
            # movies 데이터만 지운다. movie_stats는 FK CASCADE로 같이 정리된다.
            # characters.movie_id는 FK SET NULL 설정에 따라 연결만 해제된다.
            connection.execute(text("DELETE FROM movies"))

        changed_count = 0
        for start in range(0, len(rows), UPSERT_BATCH_SIZE):
            batch = rows[start : start + UPSERT_BATCH_SIZE]
            stmt = pg_insert(movies_table).values(batch)
            excluded = stmt.excluded
            update_columns = {
                "title": excluded.title,
                "overview": func.coalesce(excluded.overview, movies_table.c.overview),
                "genres": func.coalesce(excluded.genres, movies_table.c.genres),
                "year": func.coalesce(excluded.year, movies_table.c.year),
                "language": func.coalesce(excluded.language, movies_table.c.language),
                "vote_average": func.coalesce(excluded.vote_average, movies_table.c.vote_average),
                "vote_count": func.coalesce(excluded.vote_count, movies_table.c.vote_count),
                "poster_path": func.coalesce(excluded.poster_path, movies_table.c.poster_path),
                "last_synced_at": excluded.last_synced_at,
                "updated_at": func.now(),
            }

            if update_extra_details:
                update_columns.update(
                    {
                        "director": func.coalesce(excluded.director, movies_table.c.director),
                        "cast": func.coalesce(excluded.cast, movies_table.c.cast),
                        "keywords": func.coalesce(excluded.keywords, movies_table.c.keywords),
                    }
                )

            stmt = stmt.on_conflict_do_update(
                index_elements=[movies_table.c.tmdb_id],
                set_=update_columns,
            )
            result = connection.execute(stmt)
            changed_count += affected_row_count(result, len(batch))
            print(f"[save] {min(start + len(batch), len(rows))}/{len(rows)}개 저장/갱신 완료")

        movie_id_by_tmdb_id = load_id_map(
            connection,
            movies_table,
            movies_table.c.tmdb_id,
            [int(row["tmdb_id"]) for row in rows],
        )
        genre_count = sync_movie_genres(connection, movie_id_by_tmdb_id, rows)
        actor_count, movie_actor_count = sync_movie_actors(
            connection,
            movie_id_by_tmdb_id,
            cast_credits_by_movie,
        )

        # 새로 저장된 movies 전체에 대해 ranking 통계 row를 0으로 생성한다.
        stats_result = connection.execute(
            text(
                """
                INSERT INTO movie_stats (
                    movie_id,
                    view_count,
                    search_click_count,
                    like_count,
                    ranking_score
                )
                SELECT
                    m.id,
                    0,
                    0,
                    0,
                    0
                FROM movies m
                LEFT JOIN movie_stats s ON s.movie_id = m.id
                WHERE s.movie_id IS NULL
                RETURNING movie_id
                """
            )
        )
        stats_count = len(stats_result.fetchall())

    return ImportCounts(
        movies=changed_count,
        movie_stats=stats_count,
        movie_genres=genre_count,
        actors=actor_count,
        movie_actors=movie_actor_count,
    )


def print_preview(rows: list[dict[str, Any]]) -> None:
    for row in rows[:5]:
        print(
            f"- {row['tmdb_id']} | {row['title']} | "
            f"{', '.join(row['genres'] or [])} | {row['year'] or '-'}"
        )


def main() -> None:
    load_local_env()
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit은 1 이상이어야 합니다.")
    if args.cast_limit < 1:
        raise SystemExit("--cast-limit은 1 이상이어야 합니다.")
    if args.start_year > args.end_year:
        raise SystemExit("--start-year는 --end-year보다 클 수 없습니다.")
    if args.min_vote_count < 0:
        raise SystemExit("--min-vote-count는 0 이상이어야 합니다.")

    database_url = normalize_database_url(args.database_url)
    ensure_local_database(database_url, args.allow_non_local_db)

    tmdb = TMDBClient()
    try:
        genre_map = fetch_genre_map(tmdb, args.language)
        if args.source == "catalog":
            source_movies = fetch_catalog_movies(
                tmdb,
                args.limit,
                args.language,
                args.region,
                args.start_year,
                args.end_year,
                args.min_vote_count,
            )
        else:
            source_movies = fetch_popular_movies(tmdb, args.limit, args.language, args.region)
        rows, cast_credits_by_movie = build_movie_rows(
            tmdb,
            source_movies,
            genre_map,
            args.language,
            args.skip_extra_details,
            args.cast_limit,
        )
    finally:
        tmdb.close()

    if not rows:
        print("가져온 영화가 없습니다.")
        return

    print_preview(rows)
    if args.dry_run:
        print(f"[dry-run] DB 저장 없이 {len(rows)}개 영화 확인 완료")
        return

    counts = upsert_movies(
        database_url,
        rows,
        cast_credits_by_movie,
        update_extra_details=not args.skip_extra_details,
        replace_existing_data=args.replace_existing_data,
    )
    print(f"[done] movies 테이블에 {counts.movies}개 영화 저장/갱신 완료")
    print(f"[done] movie_genres 테이블에 {counts.movie_genres}개 장르 관계 동기화 완료")
    print(f"[done] movie_stats 테이블에 {counts.movie_stats}개 통계 row 생성 완료")
    if args.skip_extra_details:
        print("[done] --skip-extra-details 지정으로 actors/movie_actors 동기화를 건너뜀")
    else:
        print(f"[done] actors 테이블에 {counts.actors}개 배우 저장/갱신 완료")
        print(f"[done] movie_actors 테이블에 {counts.movie_actors}개 출연 관계 동기화 완료")


if __name__ == "__main__":
    main()
