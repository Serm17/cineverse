# 영화 좋아요 결과를 처리하는 함수
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interactions import UserMovieInteraction
from app.models.movies import Movie, MovieStats
from app.services.movies.movies_ranking_service import add_movie_ranking_score
from app.services.preference_service import add_movie_preference_scores, decrease_movie_preference_scores

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

        # user = db.get(User, user_id)
        movie = db.get(Movie, movie_id)
        if movie is None:
            db.rollback()
            return {
                "state" : "failure",
                "message" : "영화 정보를 찾을 수 없습니다."
            }
        add_movie_preference_scores(
            db = db,
            user_id = user_id,
            movie = movie,
            action_type = "like",
        )

        # 영화 랭킹 점수 갱신
        add_movie_ranking_score(db, movie_id, score_delta, "like")

        db.commit()
        db.refresh(interaction)
        
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
    
# 좋아요 영화 삭제 결과
def delete_liked_movie_result(
        db : Session,
        user_id : int,
        movie_id : int
):
    try:
        like_interactions = db.scalars(
            select(UserMovieInteraction)
            .where(
                UserMovieInteraction.user_id == user_id,
                UserMovieInteraction.movie_id == movie_id,
                UserMovieInteraction.action_type == "like"
            )
        ).all()

        # 좋아요 기록이 없으면 삭제할 대상이 없다고 응답
        if not like_interactions:
            return {
                "state" : "failure",
                "message" : "삭제할 좋아요 기록이 없습니다.",
                "data" : {
                    "movie_id" : movie_id
                }
            }
        
        movie = db.get(Movie, movie_id)

        if movie is None:
            return {
                "state" : "failure",
                "message" : "영화 정보를 찾을 수 없습니다."
            }
        
        delete_count = len(like_interactions)

        # 취향 점수 차감하기 위해 영화 정보 조회
        movie = db.get(Movie, movie_id)
        if movie is None:
            return {
                "state" : "failure",
                "message" : "영화 정보를 찾을 수 없습니다.",
            }
        
        # 좋아요로 올라간 장르, 배우, 키워드, 감독, 언어 점수 차감
        decreased_count = decrease_movie_preference_scores(
            db = db,
            user_id = user_id,
            movie = movie,
            action_type = "like",
            action_count =delete_count,
        )

        # 좋아요 행동 삭제
        for like in like_interactions:
            db.delete(like)

        movie_stats = db.get(MovieStats, movie_id)
        if movie_stats:
            movie_stats.like_count = max((movie_stats.like_count or 0) - delete_count, 0)
            ranking_score_delta = sum (max(like.score_delta or 0, 0)for like in like_interactions) # 실제 좋아요 행동에 저장된 점수만큼 랭킹 점수 차감
            movie_stats.ranking_score = max((movie_stats.ranking_score or 0) - ranking_score_delta , 0)

        db.commit()

        return {
            "state" : "success",
            "message" : "좋아요 누른 영화 삭제 성공",
        }
    except Exception as e:
        db.rollback()
        return {
            "state" : "error",
            "message" : "좋아요 누른 영화 삭제 에러",
            "error" : str(e),
        }
    
    
# 회원이 영화 상세 조회 결과 함수 - 점수 반영 +1
def detail_movie_result(db: Session, user_id: int, movie_id: int, action_type: str) ->dict:
    try:
        # 점수
        score_delta = 1
        # 사용자 영화 행동 저장
        source = (
            "search"
            if action_type == "search_click"
            else "direct"
        )
        interaction = user_interaction_result(
            user_id = user_id, 
            movie_id = movie_id, 
            action_type = action_type, 
            source = source, 
            score_delta=score_delta
        )
        db.add(interaction)

        # 행동 대상 영화 조회
        movie = db.get(Movie, movie_id)
        if movie is None:
            db.rollback()
            return {
                "state" : "failure",
                "message" : "영화 정보를 찾을 수 없습니다."
            }
        
        # 영화 장르, 배우, 감독, 키워드, 언어에 반영
        add_movie_preference_scores(
            db = db,
            user_id = user_id,
            movie = movie,
            action_type = action_type,
        )

        # 랭킹 점수 갱신
        add_movie_ranking_score(db, movie_id, score_delta, action_type)

        # 저장
        db.commit()

        return {
            "state" : "success",
            "message" : "사용자 행동 및 취향 점수 반영 성공",
        }
        
    except Exception as e:
        db.rollback()
        return {
            "state" : "error",
            "message" : "상세 조회 에러",
            "error" : str(e)
        }