"""Import popular TMDB movies into the local PostgreSQL movies table.

Usage:
    TMDB_ACCESS_TOKEN=... .venv/bin/python scripts/import_tmdb_popular_movies.py

The script only allows local DB hosts by default so accidental production imports
fail fast. Use --dry-run first if you want to preview the TMDB rows.
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine, func, text
from sqlalchemy.dialects.postgresql import ARRAY, insert as pg_insert
from sqlalchemy.engine import URL, make_url


DEFAULT_DATABASE_URL = "postgresql://postgres:1234@localhost:5432/CineVerse"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
LOCAL_DB_HOSTS = {None, "", "localhost", "127.0.0.1", "::1"}
DEFAULT_LIMIT = 40
DEFAULT_LANGUAGE = "ko-KR"
DEFAULT_REGION = "KR"
MAX_CAST_COUNT = 10
SUPPORTED_ORIGINAL_LANGUAGES = {"en", "ko"}

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

        response = self._client.get(path, params=request_params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"TMDB 요청 실패: {path} ({response.status_code}) {response.text}") from exc

        return response.json()


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
    parser = argparse.ArgumentParser(description="TMDB 인기 영화 40개를 로컬 movies 테이블에 저장합니다.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"가져올 영화 수 (기본값: {DEFAULT_LIMIT})")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help=f"TMDB 응답 언어 (기본값: {DEFAULT_LANGUAGE})")
    parser.add_argument("--region", default=DEFAULT_REGION, help=f"인기 영화 지역 코드 (기본값: {DEFAULT_REGION})")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="저장할 PostgreSQL URL. 기본값은 DATABASE_URL 또는 로컬 CineVerse DB입니다.",
    )
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 가져올 데이터만 미리 확인합니다.")
    parser.add_argument(
        "--skip-extra-details",
        action="store_true",
        help="감독/출연진/키워드 추가 요청을 건너뜁니다.",
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


def choose_original_title(movie: dict[str, Any]) -> str:
    # 번역 제목이 아니라 TMDB 원제(original_title)를 저장한다.
    # fetch_popular_movies에서 adult 제외, 원문 언어 en/ko, 제목 문자 범위를 이미 필터링한다.
    tmdb_id = int(movie["id"])
    return truncate(movie.get("original_title"), 300) or f"TMDB {tmdb_id}"


def fetch_movie_extras(tmdb: TMDBClient, tmdb_id: int, language: str) -> tuple[str | None, list[str], list[str]]:
    director = None
    cast: list[str] = []
    keywords: list[str] = []

    try:
        credits = tmdb.get(f"/movie/{tmdb_id}/credits", {"language": language})
        directors = [
            crew_member.get("name", "")
            for crew_member in credits.get("crew", [])
            if crew_member.get("job") == "Director"
        ]
        director = truncate(", ".join(unique_names(directors)), 200)
        cast = unique_names([cast_member.get("name", "") for cast_member in credits.get("cast", [])])[:MAX_CAST_COUNT]
    except RuntimeError as exc:
        print(f"[warn] credits 생략: tmdb_id={tmdb_id} ({exc})")

    try:
        keyword_payload = tmdb.get(f"/movie/{tmdb_id}/keywords")
        keywords = unique_names([keyword.get("name", "") for keyword in keyword_payload.get("keywords", [])])
    except RuntimeError as exc:
        print(f"[warn] keywords 생략: tmdb_id={tmdb_id} ({exc})")

    return director, cast, keywords


def build_movie_rows(
    tmdb: TMDBClient,
    popular_movies: list[dict[str, Any]],
    genre_map: dict[int, str],
    language: str,
    skip_extra_details: bool,
) -> list[dict[str, Any]]:
    synced_at = datetime.now(UTC)
    rows: list[dict[str, Any]] = []

    for index, movie in enumerate(popular_movies, start=1):
        tmdb_id = int(movie["id"])
        director = None
        cast: list[str] = []
        keywords: list[str] = []

        if not skip_extra_details:
            director, cast, keywords = fetch_movie_extras(tmdb, tmdb_id, language)

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
                "director": director,
                "cast": cast or None,
                "keywords": keywords or None,
                "year": parse_year(movie.get("release_date")),
                "language": truncate(movie.get("original_language"), 10),
                "vote_average": movie.get("vote_average"),
                "vote_count": movie.get("vote_count"),
                "audience_count": None,
                "poster_path": truncate(movie.get("poster_path"), 300),
                "last_synced_at": synced_at,
            }
        )

        if index % 10 == 0 or index == len(popular_movies):
            print(f"[fetch] {index}/{len(popular_movies)}개 변환 완료")

    return rows


def upsert_movies(
    database_url: URL,
    rows: list[dict[str, Any]],
    update_extra_details: bool,
    replace_existing_data: bool,
) -> tuple[int, int]:
    engine = create_engine(database_url)

    stmt = pg_insert(movies_table).values(rows)
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

    with engine.begin() as connection:
        if replace_existing_data:
            # movies 데이터만 지운다. movie_stats는 FK CASCADE로 같이 정리된다.
            # characters.movie_id는 FK SET NULL 설정에 따라 연결만 해제된다.
            connection.execute(text("DELETE FROM movies"))

        result = connection.execute(stmt)

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
                """
            )
        )

    return result.rowcount or 0, stats_result.rowcount or 0


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

    database_url = normalize_database_url(args.database_url)
    ensure_local_database(database_url, args.allow_non_local_db)

    tmdb = TMDBClient()
    try:
        genre_map = fetch_genre_map(tmdb, args.language)
        popular_movies = fetch_popular_movies(tmdb, args.limit, args.language, args.region)
        rows = build_movie_rows(tmdb, popular_movies, genre_map, args.language, args.skip_extra_details)
    finally:
        tmdb.close()

    if not rows:
        print("가져온 영화가 없습니다.")
        return

    print_preview(rows)
    if args.dry_run:
        print(f"[dry-run] DB 저장 없이 {len(rows)}개 영화 확인 완료")
        return

    changed_count, stats_count = upsert_movies(
        database_url,
        rows,
        update_extra_details=not args.skip_extra_details,
        replace_existing_data=args.replace_existing_data,
    )
    print(f"[done] 로컬 movies 테이블에 {changed_count}개 영화 저장/갱신 완료")
    print(f"[done] 로컬 movie_stats 테이블에 {stats_count}개 통계 row 생성 완료")


if __name__ == "__main__":
    main()
