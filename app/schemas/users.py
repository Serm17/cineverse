# 회원가입 요청(Request) 데이터 형식
from pydantic import BaseModel, EmailStr, Field

class RegisterRequest(BaseModel):
    # 사용자 이메일
    email: EmailStr
    # 사용자 비밀번호
    password: str
    # 사용자 닉네임
    nickname: str

class LoginRequest(BaseModel):
    # 사용자 이메일
    email: EmailStr
    # 사용자 비밀번호
    password: str

class PreferenceRequest(BaseModel):
    # 사용자 선호 장르
    genres: list[str] = Field(default_factory=list)
    # 사용자 선호 배우
    actors: list[str] = Field(default_factory=list)
    # 사용자 선호 키워드
    keywords: list[str] = Field(default_factory=list)
