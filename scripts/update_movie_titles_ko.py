"""Update movie titles to Korean localized TMDB titles when available."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

from app.core.dependencies import SQLALCHEMY_DATABASE_URL


TMDB_BASE_URL = "https://api.themoviedb.org/3"


def load_local_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def has_hangul(value: str | None) -> bool:
    return any("가" <= char <= "힣" for char in value or "")


def tmdb_auth() -> tuple[dict[str, str], dict[str, str]]:
    access_token = os.getenv("TMDB_ACCESS_TOKEN")
    api_key = os.getenv("TMDB_API_KEY")
    if not access_token and not api_key:
        raise SystemExit("TMDB_ACCESS_TOKEN 또는 TMDB_API_KEY 환경변수가 필요합니다.")

    headers = {"accept": "application/json"}
    params: dict[str, str] = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    else:
        params["api_key"] = api_key or ""
    return headers, params


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="movies.title을 TMDB 한국어 제목으로 갱신합니다.")
    parser.add_argument("--commit", action="store_true", help="실제로 DB를 업데이트합니다. 없으면 dry-run입니다.")
    parser.add_argument("--language", default="ko-KR", help="TMDB 언어 코드")
    return parser.parse_args()


def main() -> None:
    load_local_env()
    args = parse_args()
    headers, auth_params = tmdb_auth()

    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    with engine.connect() as conn:
        movies = conn.execute(
            text("SELECT id, tmdb_id, title FROM movies WHERE tmdb_id IS NOT NULL ORDER BY id ASC")
        ).mappings().all()

    updates: list[tuple[int, int, str, str]] = []
    with httpx.Client(base_url=TMDB_BASE_URL, headers=headers, timeout=20.0) as client:
        for movie in movies:
            response = client.get(
                f"/movie/{movie['tmdb_id']}",
                params={**auth_params, "language": args.language},
            )
            response.raise_for_status()
            ko_title = (response.json().get("title") or "").strip()
            if ko_title and has_hangul(ko_title) and ko_title != movie["title"]:
                updates.append((movie["id"], movie["tmdb_id"], movie["title"], ko_title))

    print(f"candidates={len(updates)}")
    for movie_id, tmdb_id, old_title, ko_title in updates:
        print(f"{movie_id} | {tmdb_id} | {old_title} -> {ko_title}")

    if not args.commit:
        print("dry-run: DB는 수정하지 않았습니다.")
        return

    with engine.begin() as conn:
        for movie_id, _tmdb_id, _old_title, ko_title in updates:
            conn.execute(
                text(
                    """
                    UPDATE movies
                    SET title = :title,
                        updated_at = now(),
                        last_synced_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": movie_id, "title": ko_title},
            )

    print(f"updated={len(updates)}")


if __name__ == "__main__":
    main()
