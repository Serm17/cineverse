from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# PostgreSQL 접속 정보
# 형식:
# postgresql://유저명:비밀번호@호스트:포트/DB명
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:1234@localhost:5432/CineVerse"

# PostgreSQL과 연결할 엔진 생성
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)

# DB 세션 생성 객체
# autocommit=False
# → commit을 직접 실행해야 저장
#
# autoflush=False
# → 쿼리 실행 전 자동 flush 비활성화
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 토큰에서 Authorization 헤더에서 Bearer 토큰 꺼내기
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# FastAPI Dependency
# API 요청마다 DB 세션 생성
# 요청 종료 시 자동으로 세션 종료
def get_db():

    # DB 세션 생성
    db = SessionLocal()

    try:
        # 라우터로 세션 전달
        yield db

    finally:
        # 요청 종료 시 세션 종료
        db.close()

# 
# def get_current_user(token : str = Depends(oauth2_scheme), db:Session = Depends(get_db)):
    