# 영화 좋아요 결과를 처리하는 함수
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interactions import UserMovieInteraction
from app.models.movies import Movie
from app.models.users import User
from app.services.movies.movies_ranking_service import add_movie_ranking_score
from app.services.preference_service import movie_genre_add_preferences_user

def user_interaction_result(user_id: int, movie_id:int, action_type:str, source:str, score_delta:int):
    return UserMovieInteraction(
        user_id=user_id,
        movie_id=movie_id,
        action_type=action_type,
        source=source,
        score_delta=score_delta,
    )

# 회원이 영화 좋아요 누른 결과 함수
def like_movie_result(db: Session, user_id: int, movie_id: int) -> dict:
    try:
        # 이미 좋아요를 누른 영화인지 확인
        already_liked = db.scalar(select(UserMovieInteraction)
                        .where(
                            UserMovieInteraction.movie_id == movie_id,
                            UserMovieInteraction.user_id == user_id,
                            UserMovieInteraction.action_type == "like"
                        ))
        if already_liked:
            return {
                "state": "failure",
                "message": "이미 좋아요를 누른 영화입니다.",
                "user_id": user_id,
                "movie_id": movie_id
            }
        score_delta = 2  # 좋아요 점수

        # 사용자 영화 행동을 저장
        interaction = user_interaction_result(user_id, movie_id, "like", "direct", score_delta)
        
        db.add(interaction)

        user = db.get(User, user_id)
        movie = db.get(Movie, movie_id)
        movie_genre_add_preferences_user(user, movie)

        # 영화 랭킹 점수 갱신
        add_movie_ranking_score(db, movie_id, score_delta, "like")
        
        return {
            "state": "success",
            "message": "좋아요 API 성공했습니다.",
            "user_id": user_id,
            "movie_id": movie_id,
            "interaction_id": interaction.id,
        }
    except Exception as e:
        db.rollback()
        return {
            "state": "error",
            "message": "좋아요 API 실패",
            "error": str(e)
        }

# 회원이 영화 상세 조회 결과 함수 - 점수 반영 +1
def detail_movie_result(db: Session, user_id: int, movie_id: int, action_type: str) ->dict:
    try:
        score_delta = 1
        interaction = user_interaction_result(user_id, movie_id, action_type, "direct", score_delta)
        db.add(interaction)

        # 랭킹 점수 갱신
        add_movie_ranking_score(db, movie_id, score_delta, "view")

        # 저장
        db.commit()
        
    except Exception as e:
        db.rollback()
        return {
            "state" : "error",
            "message" : "상세 조회 에러",
            "error" : str(e)
        }