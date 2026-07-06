from datetime import datetime, timedelta, timezone
import hashlib

from passlib.context import CryptContext
from jose import jwt
from app.core.config import settings

# bcrypt 방식으로 비밀번호를 해시하기 위한 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#비밀번호 hash함수
def hash_password(password:str) :
    #입력받은 비밀번호 bcrypt 해시값으로 반환
    return pwd_context.hash(password)

# 토큰 hash함수
def hash_token(token : str) :
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

# 로그인할 때 사용
def verify_password(plain_password: str, hashed_password: str) -> bool:
    # plain_password: 사용자가 로그인할 때 입력한 비밀번호
    # hashed_password: DB에 저장된 암호화된 비밀번호
    # bcrypt는 같은 비밀번호라도 매번 다른 해시가 나오기 때문에 verify()를 써야 함
    return pwd_context.verify(plain_password, hashed_password)

# 로그인 성공시 access token 생성 - JWT
def create_access_token(data : dict):
    # 원본 data를 직접 수정하지 않기 위해 복사
    to_encode = data.copy()
    # access token 만료 시간 설정
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # access token임을 구분할 수 있도록 type을 넣습니다.
    to_encode.update({
        "exp": expire,
        "type": "access"
    })

    # 토큰 생성
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm = settings.ALGORITHM
    )

# refresh token 생성
def create_refresh_token(data : dict):
    # 원본 data를 직접 수정하지 않기 위해 복사
    to_encode = data.copy()
    # refresh token 만료 시간 설정
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # refresh token임을 구분할 수 있도록 type을 넣습니다.
    to_encode.update({
        "exp":expire,
        "type" : "refresh"
    })
    #토큰 반환
    refresh_token = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return refresh_token, expire.isoformat()
