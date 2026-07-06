from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.interactions import UserMovieInteraction
from app.models.movies import Movie
from app.models.users import User


preference_type = ("genre", "actor", "keyword")

# 유저 정보 ID 확인 후 반환
def get_user(db: Session, user_id : int) -> User|None:
    return db.query(User).filter(User.id == user_id).first()

# 기본 선호 목록과 새로 추가할 목록 - 중복값 제거
def check_unique_values(current_values, new_values):
    result = []
    check = set()

    for value in (current_values or [])+ (new_values or []):
        # 공백 제거
        value = value.strip()

        if not value:
            continue

        # 중복 - 넘어가기
        if value in check :
            continue

        result.append(value)
        check.add(value)
    
    return result

def movies_like_result(
        db: Session,
        user_id : int,
):
    like_movies = db.scalars(
        select(UserMovieInteraction)
        .where(UserMovieInteraction.user_id == user_id, 
               UserMovieInteraction.action_type=="like")
    ).all()

    return like_movies

# 사용자가 이미 조회,검색,좋아요한 영화 ID 
def get_candidate_movies(db: Session, user_id:int):
    interacted_movie_ids = select(UserMovieInteraction.movie.movie_id).where(UserMovieInteraction.user_id == user_id)

    return list(
        db.scalars(
            select(Movie)
            .where(Movie.poster_path.is_not(None))
            .where(Movie.id.not_in(interacted_movie_ids))
            .order_by(Movie.id.desc())
        ).all()
    )