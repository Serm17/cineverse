from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
import httpx
from sqlalchemy import text
import uvicorn
from app.api.auth import router as auth_router
from app.api.movies import router as movies_router
from app.api.chat import router as chat_router
from app.api.users import router as users_router
from sqlalchemy.orm import Session
from app.core.dependencies import get_db
from app.core.config import settings
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 개인 정보 캐시 방지 목적
@app.middleware("http")
async def no_store_private_api_cache(request, call_next):
    response = await call_next(request)

    # 브라우저나 중간 캐시 서버 응답을 저장 못하게 설정
    if request.url.path.startswith(("/auth", "/chat", "/user")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response

# 프로필 이미지 url 반환
PROFILE_IMAGE_DIR = Path(__file__).resolve().parent / "profile_images"
app.mount(
    "/profile_images",
    StaticFiles(directory=PROFILE_IMAGE_DIR),
    name="/profile_images"
)


# 프론트 서버
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        # "http://192.168.45.103:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# auth.py의 Router 등록
app.include_router(auth_router)

# movies.py의 Router 등록
app.include_router(movies_router)

# /chat router 등록
app.include_router(chat_router)

# /users router 등록
app.include_router(users_router)

@app.get("/")
def index():
    return {"state": "success", "message": "CineVerse API is running"}

#실행 확인 여부
@app.get("/health")
def root():
    try:
        return {
            "state" : "success",
            "message": "CineVerse"
            }
    except Exception as e:
        return {
            "state" : "error",
            "message": "BE1 Health Check API 호출 실패", 
            "error": str(e)
            }


# PostgreSQL 연결 테스트 API
@app.get("/db-test")
async def db_test(db: Session = Depends(get_db)):
    try:
        # PostgreSQL에 간단한 쿼리 실행
        db.execute(text("SELECT 1"))
        return {
            "state" : "success",
            "message": "PostgreSQL 연결 성공"
        }

    except Exception as e:

        return {
            "status" : "failure",
            "message": "BE2 DB연결 API 호출 실패",
            "error": str(e)
        }
    

@app.get("/ai-health")
async def ai_health_check():
    ai_base_url = settings.AI_BASE_URL.rstrip("/")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ai_base_url}/health",
                timeout=5.0,
            )

        return {
            "state": "success",
            "message": "AI 서버 연결에 성공했습니다.",
            "ai_base_url": ai_base_url,
            "status_code": response.status_code,
        }

    except httpx.TimeoutException:
        return {
            "state": "error",
            "message": "AI 서버 응답 시간이 초과되었습니다.",
            "ai_base_url": ai_base_url,
        }

    except httpx.RequestError as e:
        return {
            "state": "error",
            "message": "AI 서버에 연결할 수 없습니다.",
            "ai_base_url": ai_base_url,
            "error": str(e),
        }

# 수행하면 바로 console창에 main:app 명령 없이 특정 포트로 바로 수행되게 처리..
if __name__ =="__main__":
    # 작성된 파일을 main.py로 저장했을 경우를 가정하고 서버를 실행합니다.
    # 포트를 8080으로 지정하여 localhost:8080에서 확인 가능하도록 설정합니다.
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
    # uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)