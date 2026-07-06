from app.ai_client.base import post_ai
from app.schemas.movies import RecommendRequest


# ai - 날마다 추천하는 영화 리스트
async def request_recommend_today_movie():
    payload = {
        "message" : "오늘 메인 페이지에 보여줄 영화 추천 리스트 만들어줘",
        "history" : [],
    }
    
    return await post_ai("/recommend", payload)