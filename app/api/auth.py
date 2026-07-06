from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request, Response
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.core.current_user import get_current_user
from app.schemas.users import RegisterRequest
from app.schemas.users import LoginRequest
from app.core.security import create_access_token, create_refresh_token, hash_password, hash_token, verify_password
from app.core.config import settings
from app.core.dependencies import get_db
from app.models.users import User
from app.models.tokens import RefreshToken


# 인증 관련 API들을 묶는 Router /auth/
router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

# 회원가입 API POST /auth/register
@router.post("/register")
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    try :
        # 이메일 중복 확인
        existing_user = (db.query(User).filter(User.email == request.email).first())

        if existing_user :
            return {
                "status" : "failure",
                "message" : "회원가입 실패 - 이메일 중복"
            }

        #비밀번호 hash 
        hashed_pwd = hash_password(request.password)

        new_user = User(
            email = request.email,
            password_hash = hashed_pwd,
            nickname = request.nickname
        )
        
        #DB 저장
        db.add(new_user)
        #실제로 DB 저장
        db.commit()
        #저장 후 생성 id 조회
        db.refresh(new_user)
        # return new_user
        return {
            "status":"success",
            "message":"회원가입 성공",
            "data" : {
                "id" : new_user.id,
                "email" : new_user.email,
                # "password_hashed" : new_user.password_hash,
                "nickname" : new_user.nickname
            }
        }
    except Exception as e:
        # 저장 취소 롤백
        db.rollback()
        return {
            "status":"error",
            "message" : "회원가입 에러",
            "detail" : str(e)
        }

# 로그인 POST /auth/login
@router.post("/login")
async def login(
    request: LoginRequest,
    http_response: Response, 
    user_agent: str | None = Header(default=None),
    db: Session = Depends(get_db)
    ):
    try :
        # 기존 회원인지 아닌지 구분
        user = (db.query(User).filter(User.email == request.email).first())
        
        if not user:
            return {
                "state" : "failure",
                "message" : "해당 이메일은 가입된 회원이 아닙니다."
            }
        
        # 비밀번호 비교
        user_pwd = verify_password(request.password, user.password_hash)
        if not user_pwd :
            return { 
                "state" : "failure",
                "message" : "해당 회원의 비밀번호가 일치하지 않습니다."
            }
        # 로그인 성공 토큰 생성 access_token, refresh_token
        # 토큰에는 사용자 이메일만 저장합니다.
        access_token = create_access_token(
            data ={
                "user_email" : user.email,
                "user_id" : user.id
            }
        )
        # refresh_token 생성 반환, 만료시간 반환
        refresh_token, expires_at = create_refresh_token(
            data = {
                "user_email" : user.email,
                "user_id" : user.id
            }
        )
        expires_at_dt = datetime.fromisoformat(expires_at)

        # DB에 저장할 refresh token을 hash 값으로 저장
        refresh_token_hash = hash_token(refresh_token)
        
        # refresh_tokens 테이블에 직접 저장
        refresh_token_row = RefreshToken(
            user_id=user.id,
            token_hash=refresh_token_hash,
            expires_at=expires_at_dt,
            user_agent=user_agent,
        )

        db.add(refresh_token_row)
        db.commit()

        # HttpOnly Cooki에 refresh token 저장
        http_response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/auth"
        )
        
        return {
            "state" : "success",
            "message": "로그인 성공",
            "data" : {
                "access_token" : access_token,
                # "refresh_token" : refresh_token,
                "token_type" : "bearer", # 토큰 보내는 방식
                "email" : user.email,
                "nickname" : user.nickname
            }
        }

    except Exception as e:
        db.rollback()
        return{
            "state" : "error",
            "message" : "로그인 에러",
            "error" : str(e)
        }


# 토큰 재발급 POST /auth/refresh - access_token이 만료되었을 때 refresh token 검증 후 재발급
@router.post("/refresh")
async def refresh_token(http_request : Request, db:Session = Depends(get_db)):
    try:
        
        # 브라우저 내에 있는 refresh_token 꺼내기
        refresh_token = http_request.cookies.get("refresh_token")
        if not refresh_token:
            return {
                "state" : "failure",
                "message" : "refresh_token이 브라우저 내 쿠기에 없습니다."
            }
        
        # refresh token JWT 자체 검증
        payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        if payload.get("type") != "refresh":
            return {
                "state" : "failure",
                "message" : "refresh_token이 아닙니다."
            }

        # 토큰 내 사용자 정보 꺼내기
        user_email = payload.get("user_email")
        user_id = payload.get("user_id")

        if not user_email or not user_id:
            return{
                "state" : "failure",
                "message" : "refresh_token 내 회원 정보가 올바르지 않습니다."
            }
        
        # DB에 있는 refresh_token_hash랑 비교 및 검증
        refresh_token_hash = hash_token(refresh_token)

        saved_refresh_token = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == refresh_token_hash)
            .first()
        )
        if saved_refresh_token is None:
            return {
                "state" : "failure",
                "message" : "유효하지 않은 refresh_token",
            }
        # 로그아웃된 경우
        elif saved_refresh_token.revoked_at is not None:
            return {
                "state": "failure",
                "message": "이미 로그아웃 처리된 refresh_token입니다."
            }
        
        # 만료된 토큰인지 검증
        now = datetime.now(timezone.utc)
        expires_at = saved_refresh_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            return {
                "state": "failure",
                "message": "DB에 저장된 refresh_token이 만료되었습니다."
            }
        # 다른 유저의 토큰인 경우
        if saved_refresh_token.user_id != user_id:
            return {
                "state": "failure",
                "message": "해당 DB내 토큰이 브라우저 토큰과 다른 토큰입니다."
            }
        # 토큰 재발급 해서 사용한거 last_used_at 저장
        saved_refresh_token.last_used_at = now
        db.commit()
        new_access_token = create_access_token(
            data = {
                "user_email" : user_email,
                "user_id" : user_id
            }
        )
        return {
            "state" : "success",
            "message": "토큰 재발급 성공",
            "data" : {
                "access_token": new_access_token,
                "token_type": "bearer",
                "email": user_email
            }
        }
    #refresh_token 만료
    except JWTError:
        db.rollback()
        return {
            "state" : "failure",
            "message" : "refresh_token 만료 or 오류"
        }
    
    except Exception as e:
        db.rollback()
        return {
            "state" : "error",
            "message" : "토큰 재발급 실패",
            "error" : str(e)
        }


# 로그아웃 POST /auth/logout
@router.post("/logout")
async def logout(http_request : Request, http_response: Response, db:Session = Depends(get_db)):
    try :
        
        # 클라이언트 브라우저가 보낸 쿠키 - refresh 토큰
        refresh_token = http_request.cookies.get("refresh_token")

        if refresh_token :
            refresh_token_hash = hash_token(refresh_token)

            saved_refresh_token = (
                db.query(RefreshToken)
                .filter(RefreshToken.token_hash == refresh_token_hash)
                .first()
            )
            # DB에 토큰이 있고, 아직 폐기되지 않은 토큰이면 revoked_at 기록
            if saved_refresh_token and saved_refresh_token.revoked_at is None:
                saved_refresh_token.revoked_at = datetime.now(timezone.utc)
                db.commit()

        # 브라우저 쿠키 삭제
        http_response.delete_cookie(
            key="refresh_token",
            path="/auth",
            samesite="lax",
            secure=False,
            httponly=True,
        )
        return {
            "state" : "success",
            "message": "로그아웃 성공",
            "data" : {
                "detail" : "클라이언트 쪽에서 access_token, refresh_token 삭제"
            }
        }
    except Exception as e:
        db.rollback()
        return {
            "state" : "error",
            "message" : "로그아웃 에러",
            "error" : str(e)
        }
