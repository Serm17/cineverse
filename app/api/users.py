from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.dependencies import get_db
from app.schemas.movies import ShowMovies
from app.services.movies.movies_search_service import get_movie_result
from app.services.user_service import get_recently_viewed_movies_result, get_user, movies_like_result


# 사용자 관련 API들을 묶는 Router /users/
router = APIRouter(
    prefix="/user",
    tags=["User"],
)

# 내 정보 조회 GET /user
@router.get("")
async def get_my_info(
    cureent_user : dict = Depends(get_current_user),
    db : Session = Depends(get_db),
    ):
    try:
        # JWT 검증
        user_id = cureent_user["user_id"]
        # 사용자 정보 가져오기
        user = get_user(db, user_id)
        if not user:
            return {
                "state" : "failure",
                "message" : "DB에서 사용자 정보를 찾을 수 없습니다.",
            }

        return {
            "state" : "success",
            "message" : "정보 조회 성공",
            "data" : {
                "email" : user.email,
                "nickname" : user.nickname,
                # "preferred_genres" : user.preferred_genres,
                # "preferred_actors" : user.preferred_actors,
                # "preferred_keywords" : user.preferred_keywords,
            }
        }
    
    except Exception as e:
        return {
            "state": "error",
            "message": "정보 조회 실패",
            "error": str(e)
        }
    
# 취향 GET /user/preferences
@router.get("/preferences")
async def get_my_preferences(
    cureent_user : dict = Depends(get_current_user),
    db : Session = Depends(get_db),
) :
    try:
        # JWT 검증
        user_id = cureent_user["user_id"]
        user = get_user(db, user_id)

        return {
            "state" : "success",
            "message" : "취향 조회 성공",
            "data" : {
                "preferred_genres" : user.preferred_genres,
                "preferred_actors" : user.preferred_actors,
                "preferred_keywords" : user.preferred_keywords,
            }
        }
    except Exception as e:
        return {
            "state" : "error",
            "message" : "취향 조회 실패",
            "error" : str(e),
        }

# 좋아요 누른 영화 - 조회 /user/movies-like
@router.get("/movies-like")
async def get_my_like(
    current_user : dict = Depends(get_current_user),
    db : Session = Depends(get_db),
):
    try:
        # JWT 검증
        user_id = current_user["user_id"]

        # 사용자가 좋아요 누른 영화
        movies_result = movies_like_result(db, user_id)

        if not movies_result:
            return {
                "state" : "failure",
                "message" : "좋아요 누른 영화가 없습니다.",
            }
        
        return {
            "state" : "success",
            "message" : "좋아요 누른 영화 조회 성공",
            "data" : [
                get_movie_result(like.movie)
                for like in movies_result
            ],
        }

    except Exception as e:
        return {
            "state" : "error",
            "message" : "좋아요 조회 에러",
            "error" : str(e),
        }

# 최근에 상세 조회한 영화 조회
@router.get("/recently-viewed", response_model=ShowMovies)
async def get_recently_movies(
    current_user : dict = Depends(get_current_user),
    limit : int = Query(5, ge=1, le=50),
    db : Session = Depends(get_db)
):
    try:
        # JWT 검증
        user_id = current_user["user_id"]

        movies_viewed_result = get_recently_viewed_movies_result(db, user_id, limit)

        if not movies_viewed_result:
            return {
                "state" : "failure",
                "message" : "최근 조회한 영화가 없습니다.",
                "data" : [],
            }
        return {
            "state" : "success",
            "message" : "최근 조회한 영화 조회 성공",
            "data" : [
                get_movie_result(viewed.movie)
                for viewed in movies_viewed_result
            ]

        }
    except Exception as e:
        return {
            "state" : "error",
            "message" : "최근 본 영화 조회 에러",
            "data" : [],
            "error" : str(e),
        }
