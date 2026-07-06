from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user, get_optional_current_user
from app.core.dependencies import get_db
from app.schemas.movies import MovieDetailResponse, RecommendRequest
from app.services.movies.movies_genre_service import genre_movies
from app.services.movies.movies_ranking_service import movie_detail, realtime_movie_ranking_result
from app.services.interaction_service import detail_movie_result, like_movie_result
from app.services.movies.movies_search_service import search_movies_result
from app.services.movies.movies_recommend_service import get_recommend_movies_result, get_recommend_today_movie_result

# 영화 관련 API들을 묶는 Router /movies/
router = APIRouter(
    prefix="/movies",
    tags=["Movies"]
)

# AI 영화 추천 POST /movies/recommend
@router.post("/recommend")
def recommend_movies(
    # request: RecommendRequest,
    limit : int = Query(12, ge=1, le=30),
    db : Session = Depends(get_db),
):
    try:
        recommend_movies = get_recommend_movies_result(db, limit)

        if not recommend_movies:
            return {
                "state" : "failure",
                "message" : "추천하는 영화가 없습니다.",
            }
        return {
            "state" : "success",
            "message": "영화 추천 API입니다.",
            "data" : recommend_movies,
        }
    except Exception as e:
        return {
            "state" : "error",
            "message" : "영화 추천 오류",
            "error" : str(e),
        }


# 영화 검색 GET /movies/search
@router.get("/search")
async def search_movies(
    keyword: str = Query(..., min_length=1),
    page : int = Query(1, ge=1),
    limit : int = Query(20, ge=1, le=50),
    db : Session = Depends(get_db),
):
    try :
        return search_movies_result(db, keyword, page, limit)
    
    except Exception as e :
        return {
            "state":"error",
            "message" : "영화 검색 에러",
            "detail" : str(e)
        }


# 실시간 랭킹 10 GET /movies/ranking
@router.get("/ranking")
async def get_realtime_movie_ranking(
    # 랭킹 조회 개수 제한
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
    ):
    try:
        ranking_result = realtime_movie_ranking_result(db, limit)
        return ranking_result
    except Exception as e:
        return {
            "state" : "error",
            "message" : "영화 랭킹 조회 에러",
            "detail" : str(e)
        }


# 영화 상세 조회 GET /movies/{id}
@router.get("/{movie_id}", response_model= MovieDetailResponse)
async def get_movie_detail(
    movie_id: int,
    source : str = Query("direct"),
    current_user : dict | None = Depends(get_optional_current_user),
    db : Session = Depends(get_db),
):
    try:
        movie_detail_result = movie_detail(db, movie_id)
        if movie_detail_result is None :
            return {
                "state" : "failure",
                "message" : "해당 영화에 대한 정보가 없습니다.",
            }
        
        # 회원일 경우 점수 반영
        if current_user is not None:
            # JWT에서 user_id 가져오기
            user_id = current_user["user_id"]

            # 검색한 경우 action_type 수정
            if source == "search" :
                action_type = "search_click"
            else :
                action_type = "view"

            detail_movie_result(db, user_id, movie_id, action_type)
            
        return {
            "state" : "success",
            "message" : "영화 조회 성공",
            "data" : movie_detail_result,
        }
    except Exception as e:
        return {
            "state" : "error",
            "message" : "영화 상세 조회 에러",
            "error" : str(e)
        }

# 좋아요 POST /movies/{id}/like
@router.post("/{movie_id}/like")
def like_movie(
    movie_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
    ):
    try:
        # JWT 회원 정보에서 user_id를 가져온다.
        user_id = current_user["user_id"]

        if not movie_id :
            return {
                "state" : "failure",
                "message" : "movie_id가 없습니다."
            }
        result = like_movie_result(db, user_id, movie_id)
        return result
    except Exception as e:
        return {
            "state" : "error",
            "message": "좋아요 API 호출 실패",
            "error": str(e)
        }

    
@router.get("/today/recommend")
async def get_today_recommend_movies():
    try:
        result = await get_recommend_today_movie_result()

        if result is None:
            return {
                "state" : "failure",
                "message" : "오늘의 영화 추천은 없습니다.",
            }
        
        return {
            "state" : "success",
            "message" : "오늘의 AI 추천 영화 조회 성공",
            "data" : result,
        }
    
    except Exception as e:
        return {
            "state" : "error",
            "message" : "오늘의 AI 추천 영화 조회 에러",
            "error" : str(e),
        }

@router.get("/genre/{genre}")
def get_genre_movies(
    genre : str,
    page : int = Query(1, ge=1),
    limit : int = Query(20, ge=1, le=50),
    db : Session = Depends(get_db),
):
    try:
        movies_result = genre_movies(db, genre, page, limit)
        if movies_result is None:
            return {
                "state" : "failure",
                "message" : "해당 장르에 관한 영화는 없습니다.",
            }
        
        return {
            "state" : "success",
            "message" : "장르별 영화 성공",
            "data" : [
                {
                    "movie_id" : movie.id,
                    "title" : movie.title,
                    "poster_path": movie.poster_path,
                    "vote_average": movie.vote_average,
                }for movie in movies_result
            ]
        }
    except Exception as e:
        return {
            "state" : "error",
            "message" : "장르별 영화 에러",
            "error" : str(e),
        }