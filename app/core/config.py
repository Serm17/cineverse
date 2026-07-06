from pydantic_settings import BaseSettings, SettingsConfigDict


# .env 파일에 있는 설정값 가져오기
class Settings(BaseSettings) :
    # JWT 토큰 생성 및 검증 키
    SECRET_KEY : str
    #JWT 서명 알고리즘 - 위조 방지 서명
    ALGORITHM : str = "HS256"
    # access token 만료 시간
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # token 재발급하는 경우 만료 시간 ( 연장 )
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    # BE1이 호출할 BE2 서버 주소
    BE2_BASE_URL: str = "http://127.0.0.1:8001"
    # AI 호출할 서버 주소
    AI_BASE_URL : str = "http://210.109.15.251"

    #프로젝트에 있는 .env파일 읽어오는 설정
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
