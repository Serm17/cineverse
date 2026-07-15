"""Import CineVerse supported characters into the local PostgreSQL DB.

The script uses the fixed CineVerse character list as the source of truth and
uses TMDB only to enrich movie/actor/image fields when a match is found.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

from app.models.character import Character, CharacterAlias
from app.models.interactions import UserMovieInteraction
from app.models.movies import Movie
from app.models.users import User


DEFAULT_DATABASE_URL = "postgresql://postgres:1234@localhost:5432/CineVerse"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
LOCAL_DB_HOSTS = {None, "", "localhost", "127.0.0.1", "::1"}
DEFAULT_LANGUAGE = "ko-KR"
DEFAULT_REGION = "KR"


@dataclass(frozen=True)
class CharacterSeed:
    name: str
    movie_title: str
    tmdb_id: int | None = None
    aliases: tuple[str, ...] = ()
    credit_hints: tuple[str, ...] = ()
    movie_search_titles: tuple[str, ...] = ()
    actor_hint: str | None = None
    prompt_tone: str | None = None

    @property
    def all_movie_titles(self) -> tuple[str, ...]:
        return self.movie_search_titles or (self.movie_title,)


CINEVERSE_CHARACTERS: list[CharacterSeed] = [
    CharacterSeed("마석도", "범죄도시", credit_hints=("마석도", "Ma Seok-do"), actor_hint="마동석", prompt_tone="짧고 단호하게, 현장감 있게 말한다."),
    CharacterSeed("장첸", "범죄도시", credit_hints=("장첸", "Jang Chen"), actor_hint="윤계상", prompt_tone="차갑고 위협적인 어투를 유지한다."),
    CharacterSeed("강해상", "범죄도시2", credit_hints=("강해상", "Kang Hae-sang"), actor_hint="손석구", prompt_tone="거칠고 예측 불가능한 말투를 쓴다."),
    CharacterSeed("서도철", "베테랑", credit_hints=("서도철", "Seo Do-cheol"), actor_hint="황정민", prompt_tone="정의감 있고 직설적인 형사처럼 말한다."),
    CharacterSeed("조태오", "베테랑", credit_hints=("조태오", "Cho Tae-oh"), actor_hint="유아인", prompt_tone="오만하고 날 선 태도를 드러낸다."),
    CharacterSeed("차태식", "아저씨", credit_hints=("차태식", "Cha Tae-sik"), actor_hint="원빈", prompt_tone="과묵하고 절제된 보호자처럼 말한다."),
    CharacterSeed("고니", "타짜", credit_hints=("고니", "Goni"), actor_hint="조승우", prompt_tone="배짱 있고 능청스럽게 말한다."),
    CharacterSeed("고광렬", "타짜", credit_hints=("고광렬", "Go Gwang-ryeol"), actor_hint="유해진", prompt_tone="친근하고 구수한 말투를 쓴다."),
    CharacterSeed("강림", "신과함께-죄와 벌", credit_hints=("강림", "Gang-rim"), actor_hint="하정우", movie_search_titles=("신과함께-죄와 벌", "신과함께"), prompt_tone="침착하고 논리적인 저승차사처럼 말한다."),
    CharacterSeed("해원맥", "신과함께-죄와 벌", credit_hints=("해원맥", "Haewonmak"), actor_hint="주지훈", movie_search_titles=("신과함께-죄와 벌", "신과함께"), prompt_tone="시니컬하지만 정이 있는 말투를 쓴다."),
    CharacterSeed("우장훈", "내부자들", credit_hints=("우장훈", "Woo Jang-hoon"), actor_hint="조승우", prompt_tone="냉철한 검사처럼 핵심을 찌른다."),
    CharacterSeed("안옥윤", "암살", credit_hints=("안옥윤", "An Ok-yun"), actor_hint="전지현", prompt_tone="결연하고 담담한 독립군처럼 말한다."),
    CharacterSeed("석우", "부산행", credit_hints=("석우", "Seok-woo"), actor_hint="공유", prompt_tone="현실적이지만 가족을 지키려는 마음을 담아 말한다."),
    CharacterSeed("화림", "파묘", credit_hints=("화림", "Hwa-rim"), actor_hint="김고은", prompt_tone="예민하고 직감적인 무당처럼 말한다."),
    CharacterSeed("이순신", "명량", credit_hints=("이순신", "Yi Sun-sin", "Admiral Yi"), actor_hint="최민식", prompt_tone="무게감 있고 결연한 장군처럼 말한다."),
    CharacterSeed("토니 스타크", "아이언맨", aliases=("아이언맨", "아이언 맨"), credit_hints=("Tony Stark", "Iron Man"), actor_hint="Robert Downey Jr.", prompt_tone="재치 있고 자신감 넘치게 말한다."),
    CharacterSeed("스티브 로저스", "캡틴 아메리카: 퍼스트 어벤져", aliases=("캡틴 아메리카", "캡틴"), credit_hints=("Steve Rogers", "Captain America"), actor_hint="Chris Evans", movie_search_titles=("캡틴 아메리카: 퍼스트 어벤져", "Captain America: The First Avenger"), prompt_tone="정직하고 원칙 있는 리더처럼 말한다."),
    CharacterSeed("피터 파커", "스파이더맨: 홈커밍", aliases=("스파이더맨", "스파이더 맨"), credit_hints=("Peter Parker", "Spider-Man"), actor_hint="Tom Holland", movie_search_titles=("스파이더맨: 홈커밍", "Spider-Man: Homecoming"), prompt_tone="어색하지만 선한 청년처럼 말한다."),
    CharacterSeed("토르", "토르", tmdb_id=10195, credit_hints=("Thor",), actor_hint="Chris Hemsworth", prompt_tone="호쾌하고 신화적인 자신감으로 말한다."),
    CharacterSeed("로키", "토르", tmdb_id=10195, credit_hints=("Loki",), actor_hint="Tom Hiddleston", prompt_tone="교묘하고 장난기 있는 말투를 쓴다."),
    CharacterSeed("닥터 스트레인지", "닥터 스트레인지", aliases=("스트레인지",), credit_hints=("Stephen Strange", "Doctor Strange"), actor_hint="Benedict Cumberbatch", prompt_tone="냉철하고 신비로운 마법사처럼 말한다."),
    CharacterSeed("브루스 배너", "어벤져스", aliases=("헐크",), credit_hints=("Bruce Banner", "Hulk"), actor_hint="Mark Ruffalo", prompt_tone="이성적이지만 내면의 분노를 의식하며 말한다."),
    CharacterSeed("스타로드", "가디언즈 오브 갤럭시", credit_hints=("Peter Quill", "Star-Lord"), actor_hint="Chris Pratt", prompt_tone="능청스럽고 음악 취향을 드러내며 말한다."),
    CharacterSeed("데드풀", "데드풀", credit_hints=("Wade Wilson", "Deadpool"), actor_hint="Ryan Reynolds", prompt_tone="수다스럽고 장난스럽게 말한다."),
    CharacterSeed("타노스", "어벤져스: 인피니티 워", credit_hints=("Thanos",), actor_hint="Josh Brolin", prompt_tone="거대하고 숙명론적인 어조로 말한다."),
    CharacterSeed("브루스 웨인", "다크 나이트", aliases=("배트맨",), credit_hints=("Bruce Wayne", "Batman"), actor_hint="Christian Bale", prompt_tone="절제되고 어두운 신념을 담아 말한다."),
    CharacterSeed("조커", "조커", credit_hints=("Arthur Fleck", "Joker"), actor_hint="Joaquin Phoenix", prompt_tone="불안정하고 냉소적인 농담을 섞어 말한다."),
    CharacterSeed("할리 퀸", "수어사이드 스쿼드", aliases=("할리퀸",), credit_hints=("Harley Quinn",), actor_hint="Margot Robbie", prompt_tone="통통 튀고 위험한 에너지로 말한다."),
    CharacterSeed("슈퍼맨", "맨 오브 스틸", aliases=("클라크 켄트", "클락 켄트"), credit_hints=("Clark Kent", "Superman", "Kal-El"), actor_hint="Henry Cavill", prompt_tone="따뜻하고 영웅적인 책임감으로 말한다."),
    CharacterSeed("원더우먼", "원더우먼", tmdb_id=297762, aliases=("다이애나",), credit_hints=("Diana Prince", "Wonder Woman"), actor_hint="Gal Gadot", prompt_tone="강인하고 품위 있게 말한다."),
    CharacterSeed("해리포터", "해리 포터와 마법사의 돌", credit_hints=("Harry Potter",), actor_hint="Daniel Radcliffe", prompt_tone="용감하지만 겸손한 마법사처럼 말한다."),
    CharacterSeed("헤르미온느", "해리 포터와 마법사의 돌", credit_hints=("Hermione Granger",), actor_hint="Emma Watson", prompt_tone="똑똑하고 논리적으로 조언한다."),
    CharacterSeed("론 위즐리", "해리 포터와 마법사의 돌", credit_hints=("Ron Weasley",), actor_hint="Rupert Grint", prompt_tone="솔직하고 친구 같은 말투를 쓴다."),
    CharacterSeed("세베루스 스네이프", "해리 포터와 마법사의 돌", aliases=("스네이프",), credit_hints=("Severus Snape",), actor_hint="Alan Rickman", prompt_tone="차갑고 절제된 교수처럼 말한다."),
    CharacterSeed("알버스 덤블도어", "해리 포터와 마법사의 돌", aliases=("덤블도어",), credit_hints=("Albus Dumbledore",), actor_hint="Richard Harris", prompt_tone="온화하고 지혜롭게 말한다."),
    CharacterSeed("간달프", "반지의 제왕: 반지 원정대", credit_hints=("Gandalf",), actor_hint="Ian McKellen", prompt_tone="장엄하고 현명한 마법사처럼 말한다."),
    CharacterSeed("프로도", "반지의 제왕: 반지 원정대", credit_hints=("Frodo Baggins",), actor_hint="Elijah Wood", prompt_tone="선하지만 무거운 책임감을 느끼는 말투를 쓴다."),
    CharacterSeed("골룸", "반지의 제왕: 두 개의 탑", credit_hints=("Gollum", "Smeagol"), actor_hint="Andy Serkis", prompt_tone="집착과 불안을 섞어 독특하게 말한다."),
    CharacterSeed("네오", "매트릭스", credit_hints=("Neo", "Thomas Anderson"), actor_hint="Keanu Reeves", prompt_tone="차분하고 각성한 영웅처럼 말한다."),
    CharacterSeed("쿠퍼", "인터스텔라", credit_hints=("Cooper",), actor_hint="Matthew McConaughey", prompt_tone="현실적이고 가족을 생각하는 탐험가처럼 말한다."),
    CharacterSeed("코브", "인셉션", credit_hints=("Cobb", "Dom Cobb"), actor_hint="Leonardo DiCaprio", prompt_tone="집요하고 꿈과 현실을 구분하려 애쓰며 말한다."),
    CharacterSeed("폴 아트레이데스", "듄", credit_hints=("Paul Atreides",), actor_hint="Timothée Chalamet", prompt_tone="운명을 예감하는 젊은 지도자처럼 말한다."),
    CharacterSeed("오펜하이머", "오펜하이머", credit_hints=("J. Robert Oppenheimer", "Oppenheimer"), actor_hint="Cillian Murphy", prompt_tone="고뇌와 지성을 담아 신중하게 말한다."),
    CharacterSeed("존 윅", "존 윅", credit_hints=("John Wick",), actor_hint="Keanu Reeves", prompt_tone="짧고 조용하지만 단호하게 말한다."),
    CharacterSeed("에단 헌트", "미션 임파서블", credit_hints=("Ethan Hunt",), actor_hint="Tom Cruise", prompt_tone="임무 중심으로 빠르고 결단력 있게 말한다."),
    CharacterSeed("매버릭", "탑건: 매버릭", credit_hints=("Maverick", "Pete Mitchell"), actor_hint="Tom Cruise", prompt_tone="자유롭고 자신감 있는 파일럿처럼 말한다."),
    CharacterSeed("잭 스패로우", "캐리비안의 해적: 블랙 펄의 저주", tmdb_id=22, credit_hints=("Jack Sparrow",), actor_hint="Johnny Depp", prompt_tone="능청스럽고 해적다운 비유를 섞어 말한다."),
    CharacterSeed("엘사", "겨울왕국", credit_hints=("Elsa",), actor_hint="Idina Menzel", prompt_tone="차분하고 우아하지만 감정을 숨기지 않는다."),
    CharacterSeed("슈렉", "슈렉", credit_hints=("Shrek",), actor_hint="Mike Myers", prompt_tone="툴툴대지만 따뜻한 마음을 드러낸다."),
    CharacterSeed("우디", "토이 스토리", credit_hints=("Woody",), actor_hint="Tom Hanks", prompt_tone="믿음직하고 친구를 먼저 생각하며 말한다."),
]


class TMDBClient:
    def __init__(self) -> None:
        access_token = os.getenv("TMDB_ACCESS_TOKEN")
        api_key = os.getenv("TMDB_API_KEY")
        if not access_token and not api_key:
            raise SystemExit("TMDB_ACCESS_TOKEN 또는 TMDB_API_KEY 환경변수가 필요합니다.")

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
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CineVerse 지원 캐릭터 50명을 characters 테이블에 저장합니다.")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help=f"TMDB 언어 코드 (기본값: {DEFAULT_LANGUAGE})")
    parser.add_argument("--region", default=DEFAULT_REGION, help=f"TMDB 지역 코드 (기본값: {DEFAULT_REGION})")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 TMDB 매칭 결과만 출력합니다.")
    parser.add_argument("--allow-non-local-db", action="store_true", help="localhost가 아닌 DB URL도 허용합니다.")
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
        raise SystemExit(f"로컬 DB만 허용됩니다. 현재 DB host={url.host!r}.")


def image_url(path: str | None) -> str | None:
    if not path or not path.strip():
        return None

    image_path = path.strip()
    if image_path.startswith(("http://", "https://")):
        return image_path

    if not image_path.startswith("/"):
        image_path = f"/{image_path}"
    return f"{TMDB_IMAGE_BASE_URL}{image_path}"


def truncate(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    return value[:max_length]


def normalize_text(value: str | None) -> str:
    return (value or "").casefold().replace(" ", "").replace("-", "").replace(":", "")


def parse_year(release_date: str | None) -> int | None:
    if not release_date or len(release_date) < 4:
        return None
    year_text = release_date[:4]
    return int(year_text) if year_text.isdigit() else None


def unique_names(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        name = item.strip()
        if not name or name in seen:
            continue
        result.append(name)
        seen.add(name)
    return result


def fetch_genre_map(tmdb: TMDBClient, language: str) -> dict[int, str]:
    payload = tmdb.get("/genre/movie/list", {"language": language})
    return {genre["id"]: genre["name"] for genre in payload.get("genres", [])}


def search_movie(tmdb: TMDBClient, seed: CharacterSeed, language: str, region: str) -> dict[str, Any] | None:
    if seed.tmdb_id is not None:
        return {"id": seed.tmdb_id}

    for title in seed.all_movie_titles:
        payload = tmdb.get(
            "/search/movie",
            {
                "query": title,
                "language": language,
                "region": region,
                "include_adult": "false",
                "page": 1,
            },
        )
        results = payload.get("results", [])
        if not results:
            continue

        target_titles = {normalize_text(title), normalize_text(seed.movie_title)}
        exact = [
            movie for movie in results
            if normalize_text(movie.get("title")) in target_titles
            or normalize_text(movie.get("original_title")) in target_titles
        ]
        return (exact or results)[0]
    return None


def fetch_movie_details(tmdb: TMDBClient, tmdb_id: int, language: str) -> dict[str, Any]:
    return tmdb.get(f"/movie/{tmdb_id}", {"language": language})


def fetch_movie_credits(tmdb: TMDBClient, tmdb_id: int, language: str) -> dict[str, Any]:
    return tmdb.get(f"/movie/{tmdb_id}/credits", {"language": language})


def fetch_movie_keywords(tmdb: TMDBClient, tmdb_id: int) -> list[str]:
    try:
        payload = tmdb.get(f"/movie/{tmdb_id}/keywords")
    except RuntimeError as exc:
        print(f"[warn] keywords 생략: tmdb_id={tmdb_id} ({exc})")
        return []

    return unique_names([keyword.get("name", "") for keyword in payload.get("keywords", [])])


def find_cast_member(seed: CharacterSeed, credits: dict[str, Any]) -> dict[str, Any] | None:
    cast = credits.get("cast", [])
    actor_hint = normalize_text(seed.actor_hint)
    if actor_hint:
        for member in cast:
            if normalize_text(member.get("name")) == actor_hint:
                return member

    hints = [seed.name, *seed.aliases, *seed.credit_hints]
    normalized_hints = [normalize_text(hint) for hint in hints if hint]
    for member in cast:
        character_text = normalize_text(member.get("character"))
        if any(hint and hint in character_text for hint in normalized_hints):
            return member
    return None


def get_director(credits: dict[str, Any]) -> str | None:
    directors = [
        crew.get("name", "")
        for crew in credits.get("crew", [])
        if crew.get("job") == "Director"
    ]
    return truncate(", ".join(unique_names(directors)), 200)


def build_system_prompt(seed: CharacterSeed) -> str:
    tone = seed.prompt_tone or "캐릭터의 성격과 말투를 살려 자연스럽게 대화한다."
    aliases = f" 별칭은 {', '.join(seed.aliases)}이다." if seed.aliases else ""
    return (
        f"너는 영화 '{seed.movie_title}'의 캐릭터 '{seed.name}'이다.{aliases} "
        f"한국어로 답하고, 사용자의 질문에 캐릭터성을 유지해 응답한다. {tone}"
    )


def build_movie_row(
    movie: dict[str, Any],
    details: dict[str, Any],
    credits: dict[str, Any],
    genre_map: dict[int, str],
    keywords: list[str],
) -> dict[str, Any]:
    genre_names = [
        genre_map[genre_id]
        for genre_id in movie.get("genre_ids", [])
        if genre_id in genre_map
    ]
    if not genre_names:
        genre_names = [genre.get("name", "") for genre in details.get("genres", []) if genre.get("name")]

    return {
        "tmdb_id": int(movie["id"]),
        "title": truncate(details.get("title") or movie.get("title") or movie.get("original_title"), 300),
        "overview": details.get("overview") or movie.get("overview") or None,
        "genres": unique_names(genre_names) or None,
        "director": get_director(credits),
        "cast": unique_names([member.get("name", "") for member in credits.get("cast", [])])[:10] or None,
        "keywords": unique_names(keywords) or None,
        "year": parse_year(details.get("release_date") or movie.get("release_date")),
        "language": truncate(details.get("original_language") or movie.get("original_language"), 10),
        "vote_average": details.get("vote_average") or movie.get("vote_average"),
        "vote_count": details.get("vote_count") or movie.get("vote_count"),
        "audience_count": None,
        "poster_path": truncate(image_url(details.get("poster_path") or movie.get("poster_path")), 300),
        "last_synced_at": datetime.now(UTC),
    }


def upsert_movie(db, row: dict[str, Any]) -> Movie:
    movie = db.scalar(select(Movie).where(Movie.tmdb_id == row["tmdb_id"]))
    if movie is None:
        movie = Movie(**row)
        db.add(movie)
        db.flush()
        return movie

    for key, value in row.items():
        if value is not None:
            setattr(movie, key, value)
    db.flush()
    return movie


def upsert_character(db, seed: CharacterSeed, movie: Movie | None, cast_member: dict[str, Any] | None) -> Character:
    character = db.scalar(select(Character).where(Character.name == seed.name))
    if character is None:
        character = Character(name=seed.name)
        db.add(character)

    profile_path = cast_member.get("profile_path") if cast_member else None
    actor = cast_member.get("name") if cast_member else seed.actor_hint

    character.movie_id = movie.id if movie else None
    character.movie_title = seed.movie_title
    character.actor = truncate(actor, 100)
    character.lang = "ko"
    character.system_prompt = build_system_prompt(seed)
    character.profile_image = truncate(image_url(profile_path) or (image_url(movie.poster_path) if movie else None), 300)
    character.is_active = True
    db.flush()
    return character


def upsert_character_aliases(db, character: Character, aliases: tuple[str, ...]) -> None:
    for alias in dict.fromkeys(alias.strip() for alias in aliases if alias.strip()):
        alias_row = db.scalar(select(CharacterAlias).where(CharacterAlias.alias == alias))
        if alias_row is None:
            db.add(CharacterAlias(character_id=character.id, alias=alias))
            continue

        alias_row.character_id = character.id


def import_characters(args: argparse.Namespace) -> None:
    database_url = normalize_database_url(args.database_url)
    ensure_local_database(database_url, args.allow_non_local_db)

    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    tmdb = TMDBClient()
    try:
        genre_map = fetch_genre_map(tmdb, args.language)
        rows: list[
            tuple[
                CharacterSeed,
                dict[str, Any] | None,
                dict[str, Any] | None,
                dict[str, Any] | None,
                dict[str, Any] | None,
                list[str],
            ]
        ] = []

        for index, seed in enumerate(CINEVERSE_CHARACTERS, start=1):
            movie = search_movie(tmdb, seed, args.language, args.region)
            details = credits = cast_member = None
            keywords: list[str] = []
            if movie:
                tmdb_id = int(movie["id"])
                details = fetch_movie_details(tmdb, tmdb_id, args.language)
                credits = fetch_movie_credits(tmdb, tmdb_id, args.language)
                keywords = fetch_movie_keywords(tmdb, tmdb_id)
                cast_member = find_cast_member(seed, credits)

            rows.append((seed, movie, details, credits, cast_member, keywords))
            actor_text = cast_member.get("name") if cast_member else seed.actor_hint or "-"
            movie_text = details.get("title") if details else (movie.get("title") if movie else "-")
            print(f"[fetch] {index:02d}/50 {seed.name} | movie={movie_text} | actor={actor_text}")

        if args.dry_run:
            print("[dry-run] DB 저장 없이 TMDB 매칭 확인 완료")
            return

        with SessionLocal() as db:
            for seed, movie_payload, details, credits, cast_member, keywords in rows:
                movie_model = None
                if movie_payload and details and credits:
                    movie_model = upsert_movie(db, build_movie_row(movie_payload, details, credits, genre_map, keywords))
                character = upsert_character(db, seed, movie_model, cast_member)
                upsert_character_aliases(db, character, seed.aliases)
            db.commit()

        print(f"[done] characters 테이블에 {len(rows)}명 저장/갱신 완료")
    finally:
        tmdb.close()


def main() -> None:
    load_local_env()
    args = parse_args()
    import_characters(args)


if __name__ == "__main__":
    main()
