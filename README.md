# CineVerse Frontend

React/Vite 기반 CineVerse 프론트엔드입니다.

백엔드는 이 저장소 안에서 실행하지 않습니다. 인증, 채팅, 캐릭터 등 API 요청은 외부 백엔드로 전송합니다.

## API Base URL

기본 API 주소:

```txt
http://127.0.0.1:8080
```

환경별로 바꾸려면 `frontend/.env`에 아래 값을 설정합니다.

```env
VITE_API_BASE_URL=http://127.0.0.1:8080
```

## 실행

```bash
cd frontend
npm install
npm run dev
```

프론트 개발 서버:

```txt
http://127.0.0.1:5173
```

## 인증 API

회원가입:

```txt
POST /auth/email-verification/request
POST /auth/register
```

비밀번호 재설정:

```txt
POST /auth/password-reset/request
POST /auth/password-reset/confirm
```

로그인:

```txt
POST /auth/login
```

토큰 재발급:

```txt
POST /auth/refresh
```

로그아웃:

```txt
POST /auth/logout
```

refresh token은 HttpOnly cookie로 관리됩니다. 쿠키 host가 엇갈리지 않도록 프론트도
`http://127.0.0.1:5173`으로 열어 사용하는 것을 권장합니다.
