from datetime import datetime, timezone
from math import log1p

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai_client.recommend import request_recommend_today_movie
from app.models.movies import Movie, MovieStats
from app.models.users import UserPreferenceScore
from app.services.preference_service import get_user_preference_scores
from app.services.user_service import get_candidate_movies

# 추천 흐름
PREFERENCE_WEIGHT = {
    "genre": 1.2,
    "actor": 1.0,
    "director": 1.1,
    "keyword": 0.9,
    "language": 0.5,
    "character": 1.3,
}

PREFERENCE_SCORE = {
    "view": 0.5,
    "search_click": 0.8,
    "like": 2.0,
}

# 오늘의 ai 영화 추천
async def get_recommend_today_movie_result() :
    
    ai_recommend_result = await request_recommend_today_movie()
    
    # ai의 답변
    answer = ai_recommend_result.get("answer", "")

    # 추천 영화
    movies = ai_recommend_result.get("movies", [])

    return answer, movies

# 사용자 영화 추천 - 기본 추천 기반
def get_user_recommend_movies_result(
        db : Session,
        user_id : int,
        limit : int = 12,
):
    # 기본 추천 리스트
    base_movies = get_recommend_movies_result(db, limit=max(limit*3, 30))

    # 사용자의 취향 점수 목록
    preferences = get_user_preference_scores(db, user_id)
    # 사용자의 취향 점수가 없는 경우 - 기본 영화 추천
    if not preferences:
        return base_movies[:limit]
    
    # movies_id = [movie["movie_id"]]
    result = []
    # for movie in movies:
    #     result.append({
    #         "movie_id": movie.id,
    #         "title": movie.title,
    #         "poster_path": movie.poster_path,
    #         "genres": movie.genres or [],
    #         "vote_average": movie.vote_average,
    #         "recommendation_score": round(score, 3),
    #         "reason": build_user_recommend_reason(matched),
    #         "matched_preferences": matched,
    #     })


# 기본 영화 추천 - 메인 페이지에 보여줄 기본 추천 목록
def get_recommend_movies_result(db : Session, limit : int = 12,):

    candidate_limit = max(limit * 4, 40)

    recommend_result = (
        select(Movie, MovieStats)
        # 통계에 없는 영화도 포함
        .outerjoin(MovieStats, MovieStats.movie_id == Movie.id)
        # 포스터 없는 경우 추천 안함
        .where(Movie.poster_path.is_not(None))
        .order_by(
            func.coalesce(MovieStats.ranking_score, 0).desc(),
            Movie.vote_average.desc().nulls_last(),
            Movie.vote_count.desc().nulls_last(),
            Movie.id.desc(),
        )
        .limit(candidate_limit)
    )

    result_movies = []

    for movie, stats in db.execute(recommend_result).all():
        # 랭킹, 평점, 투표수, 등록 최신성 함께 반영
        score = default_score(movie, stats)

        result_movies.append(
            {
                "movie_id" : movie.id,
                "title" : movie.title,
                "poster_path" : movie.poster_path,
                "genres" : movie.genres or [],
                "vote_average" : movie.vote_average,
                "recommendation_score" : round(score, 3),
                "reson" : build_default_reason(movie, stats),
            }
        )

    # 직접 계산한 추천 점수 기준으로 다시 정령 - 실시간 랭킹이랑 안겹침
    result_movies.sort(key=lambda item:item["recommendation_score"], reverse=True)

    return result_movies

# 기본 영화 - 추천 이유 생성
def build_default_reason(movie: Movie, stats : MovieStats | None):
    
    if stats and stats.ranking_score > 0:
        return "최근 조회수 높은 영화 추천"
    if movie.vote_average and movie.vote_average >=7:
        return "평점 높은 영화 추천"
    if movie.vote_count and movie.vote_count>=1000:
        return "인기 있는 영화 추천"
    return "가볍게 둘러보기 좋은 영화 추천"

# 사용자 기반 - 추천 이유 생성
def build_user_recommend_reason(matched : list[str]):
    if not matched:
        return "인기와 평점 기준으로 추천"
    
    # 가장 먼저 매칭된 취향을 대표 추천 이유로 사용
    preference_type, value = matched[0].split(":", 1)

    label = {
        "genre": "좋아하는 장르",
        "actor": "관심 있는 배우",
        "director": "선호하는 감독",
        "keyword": "관심 키워드",
        "language": "선호 언어",
        "character": "좋아하는 캐릭터",
    }.get(preference_type, "취향")

    return f"{label} '{value}'와 잘 맞는 영화"

# 점수 반영
def default_score(movie : Movie, stats : MovieStats | None) :
    # 랭킹 반영
    ranking_score = (stats.ranking_score if stats else 0) * 0.03

    # 평점
    vote_score = (movie.vote_average or 0) * 0.7

    # 투표 수 - log1p 숫자가 커질수록 증가폭을 완만하게 만들어줌
    vote_count_score = log1p(movie.vote_count or 0) * 0.3

    # 최신성
    recent_score = calculate_created_at_recency_score(movie)
    
    return ranking_score + vote_score + vote_count_score + recent_score

# 최신 점수 반영
def calculate_created_at_recency_score(movie : Movie):
    if movie.created_at is None:
        return 0.0
    
    created_at = movie.created_at

    # timezone 정보가 없는 경우
    if created_at.tzinfo is None:
        # UTC로 맞춰서
        created_at = created_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)

    # 현재 시간과 영화 등록 시간의 차이
    days_since_created = max((now-created_at).days, 0)

    if days_since_created>= 30 :
        return 0.0
    
    result = 1 - (days_since_created/30)

    return result * 0.5
