"""Backfill movies.keywords from the currently stored movie metadata.

Usage:
    .venv/bin/python scripts/backfill_movie_keywords.py --merge-existing

This is intentionally local-DB only by default. It is a pragmatic fallback for
seeded movies that have titles, genres, and overviews but no TMDB keyword data.
"""

from __future__ import annotations

import argparse
import os
from typing import Any

from sqlalchemy import String, bindparam, create_engine, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import make_url


DEFAULT_DATABASE_URL = "postgresql://postgres:1234@localhost:5432/CineVerse"
LOCAL_DB_HOSTS = {None, "", "localhost", "127.0.0.1", "::1"}
MAX_GENERATED_KEYWORDS = 14

GENRE_KEYWORDS = {
    "가족": ["가족", "우정", "성장", "따뜻한 이야기"],
    "공포": ["공포", "긴장감", "오컬트", "생존"],
    "드라마": ["드라마", "인물 서사", "감정선", "갈등"],
    "모험": ["모험", "여정", "팀워크", "위험한 임무"],
    "미스터리": ["미스터리", "비밀", "불길한 사건", "추적"],
    "범죄": ["범죄", "수사", "조직범죄", "부패"],
    "스릴러": ["스릴러", "긴장감", "추격", "위기"],
    "애니메이션": ["애니메이션", "가족 영화", "캐릭터", "상상력"],
    "액션": ["액션", "추격", "격투", "전투"],
    "역사": ["역사", "시대극", "실화 기반", "한국사"],
    "전쟁": ["전쟁", "전투", "희생", "리더십"],
    "코미디": ["코미디", "유머", "통쾌함", "가벼운 분위기"],
    "판타지": ["판타지", "마법", "신화", "운명"],
    "SF": ["SF", "미래", "과학기술", "우주"],
}

TITLE_KEYWORDS = {
    "범죄도시": ["형사", "마석도", "장첸", "가리봉동", "강력반", "범죄조직", "소탕작전", "맨몸 액션"],
    "범죄도시 2": ["형사", "마석도", "강해상", "베트남", "해외 수사", "강력반", "납치", "소탕작전"],
    "베테랑": ["서도철", "광역수사대", "재벌 3세", "권력형 범죄", "부패", "추격", "통쾌한 액션"],
    "아저씨": ["전직 특수요원", "전당포", "소녀 구출", "납치", "복수", "범죄조직", "감성 액션"],
    "타짜": ["도박", "화투", "사기판", "고니", "평경장", "돈", "승부", "도박판"],
    "신과함께-죄와 벌": ["저승", "지옥", "재판", "환생", "저승차사", "죄와 벌", "웹툰 원작", "가족"],
    "내부자들": ["정치", "재벌", "검찰", "언론", "비자금", "권력", "부패", "복수"],
    "암살": ["일제강점기", "독립운동", "암살단", "저격수", "친일파", "임시정부", "첩보", "추격"],
    "부산행": ["좀비", "기차", "KTX", "재난", "감염", "생존", "부녀", "부산"],
    "파묘": ["무당", "풍수", "묘", "이장", "오컬트", "저주", "굿", "가족의 비밀"],
    "명량": ["이순신", "임진왜란", "해전", "12척", "조선", "왜군", "리더십", "역사 전쟁"],
    "아이언맨": ["토니 스타크", "아이언맨 슈트", "억만장자", "무기기업", "히어로 탄생", "마블", "기술"],
    "퍼스트 어벤져": ["캡틴 아메리카", "스티브 로저스", "슈퍼 솔져", "2차 세계대전", "히드라", "방패", "희생"],
    "스파이더맨: 홈커밍": ["스파이더맨", "피터 파커", "고등학생 히어로", "토니 스타크", "벌처", "성장", "마블"],
    "토르: 천둥의 신": ["토르", "아스가르드", "오딘", "로키", "묠니르", "북유럽 신화", "추방", "왕위 계승"],
    "닥터 스트레인지": ["닥터 스트레인지", "마법사", "멀티버스", "신경외과", "에인션트 원", "시간", "차원"],
    "어벤져스": ["어벤져스", "슈퍼히어로 팀", "쉴드", "로키", "테서랙트", "뉴욕 전투", "마블"],
    "가디언즈 오브 갤럭시": ["스타로드", "가모라", "로켓", "그루트", "인피니티 스톤", "우주 모험", "팀업"],
    "데드풀": ["데드풀", "웨이드 윌슨", "안티히어로", "용병", "재생능력", "복수", "블랙코미디", "메타 유머"],
    "어벤져스: 인피니티 워": ["타노스", "인피니티 스톤", "어벤져스", "가디언즈", "우주 전쟁", "희생", "히어로 대결"],
    "다크 나이트": ["배트맨", "조커", "고담", "하비 덴트", "범죄조직", "정의", "혼돈", "심리전"],
    "조커": ["아서 플렉", "광대", "고담", "사회적 고립", "정신질환", "코미디언", "광기", "범죄 드라마"],
    "수어사이드 스쿼드": ["빌런 팀", "할리 퀸", "데드샷", "아만다 월러", "인챈트리스", "메타휴먼", "DC"],
    "맨 오브 스틸": ["슈퍼맨", "크립톤", "칼엘", "조드 장군", "외계인", "정체성", "히어로 탄생"],
    "원더 우먼": ["원더우먼", "다이애나", "데미스키라", "아마존 전사", "1차 세계대전", "신화", "여성 히어로"],
    "해리 포터와 마법사의 돌": ["해리 포터", "호그와트", "마법학교", "마법사의 돌", "볼드모트", "우정", "성장"],
    "반지의 제왕: 반지 원정대": ["절대반지", "프로도", "간달프", "사우론", "원정대", "중간계", "호빗"],
    "반지의 제왕: 두 개의 탑": ["중간계", "사우론", "간달프", "아라곤", "로한", "헬름협곡", "전쟁"],
    "매트릭스": ["가상현실", "AI", "네오", "모피어스", "시뮬레이션", "해커", "기계 전쟁", "철학적 SF"],
    "인터스텔라": ["우주", "블랙홀", "웜홀", "시간", "부녀", "NASA", "식량난", "인류 생존"],
    "인셉션": ["꿈", "무의식", "인셉션", "코브", "시간 왜곡", "강도 작전", "현실과 환상"],
    "듄": ["아라키스", "스파이스", "폴 아트레이데스", "사막", "예언", "가문 전쟁", "SF 서사", "정치"],
    "오펜하이머": ["맨해튼 프로젝트", "핵개발", "원자폭탄", "과학자", "윤리", "역사 드라마", "전기 영화"],
    "존 윅": ["존 윅", "킬러", "복수", "암살자", "러시아 마피아", "콘티넨탈", "건 액션"],
    "미션 임파서블": ["이단 헌트", "첩보", "CIA", "잠입", "배신", "스파이 액션", "불가능한 임무"],
    "탑건: 매버릭": ["매버릭", "전투기", "파일럿", "해군", "항공 액션", "훈련", "팀워크"],
    "캐리비안의 해적: 블랙펄의 저주": ["잭 스패로우", "해적", "블랙펄", "저주", "보물", "유령선", "바다 모험"],
    "겨울왕국": ["엘사", "안나", "자매", "얼음 마법", "왕국", "저주", "디즈니", "뮤지컬"],
    "슈렉": ["슈렉", "피오나", "동화 패러디", "늪지대", "용", "우정", "가족 코미디"],
    "토이 스토리": ["장난감", "우디", "버즈", "픽사", "우정", "질투", "모험", "가족 애니메이션"],
}

OVERVIEW_KEYWORDS = {
    "강력반": "형사",
    "경찰": "경찰",
    "검사": "검찰",
    "마피아": "마피아",
    "무당": "오컬트",
    "반지": "반지",
    "배트맨": "배트맨",
    "복수": "복수",
    "비밀": "비밀",
    "스파이": "스파이",
    "우주": "우주",
    "전쟁": "전쟁",
    "좀비": "좀비",
    "히어로": "히어로",
}


def unique_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            continue

        key = cleaned.casefold()
        if key in seen:
            continue

        seen.add(key)
        result.append(cleaned)

    return result


def generate_keywords(title: str, genres: list[str] | None, overview: str | None) -> list[str]:
    keywords: list[str] = []

    keywords.extend(TITLE_KEYWORDS.get(title, []))

    for genre in genres or []:
        keywords.append(genre)
        keywords.extend(GENRE_KEYWORDS.get(genre, [])[:2])

    overview_text = overview or ""
    for needle, keyword in OVERVIEW_KEYWORDS.items():
        if needle in overview_text:
            keywords.append(keyword)

    return unique_values(keywords)[:MAX_GENERATED_KEYWORDS]


def validate_local_database(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name().startswith("postgresql") and url.host not in LOCAL_DB_HOSTS:
        raise SystemExit(
            f"Refusing to update non-local database host: {url.host!r}. "
            "Pass a localhost database URL for this backfill."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="movies.keywords 빈 값을 로컬 메타데이터 기반으로 채웁니다.")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="PostgreSQL URL. 기본값은 로컬 CineVerse DB입니다.",
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="이미 keywords가 있는 영화도 생성 키워드를 앞에 합쳐 갱신합니다.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB를 수정하지 않고 갱신 대상만 출력합니다.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    validate_local_database(args.database_url)

    engine = create_engine(args.database_url)
    select_stmt = text(
        """
        SELECT id, title, genres, overview, keywords
        FROM movies
        ORDER BY id ASC
        """
    )
    update_stmt = text(
        """
        UPDATE movies
        SET keywords = :keywords,
            updated_at = now()
        WHERE id = :movie_id
        """
    ).bindparams(bindparam("keywords", type_=ARRAY(String)))

    updates: list[dict[str, Any]] = []

    with engine.begin() as connection:
        rows = connection.execute(select_stmt).mappings().all()

        for row in rows:
            current_keywords = row["keywords"] or []
            generated_keywords = generate_keywords(row["title"], row["genres"], row["overview"])
            if not generated_keywords:
                continue

            if args.merge_existing:
                next_keywords = unique_values([*generated_keywords, *current_keywords])
                should_update = next_keywords != current_keywords
            else:
                next_keywords = generated_keywords
                should_update = not current_keywords

            if not should_update:
                continue

            updates.append(
                {
                    "movie_id": row["id"],
                    "title": row["title"],
                    "keywords": next_keywords,
                }
            )

        if not args.dry_run:
            for update in updates:
                connection.execute(
                    update_stmt,
                    {"movie_id": update["movie_id"], "keywords": update["keywords"]},
                )

    mode = "preview" if args.dry_run else "updated"
    print(f"{mode}={len(updates)}")
    for update in updates:
        print(f"{update['movie_id']} | {update['title']} | {', '.join(update['keywords'][:8])}")


if __name__ == "__main__":
    main()
