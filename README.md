# CineVerse
# 관리자 콘텐츠 API 화면

`/admin`에서 BE2 관리자 API 명세에 맞춘 콘텐츠 운영 화면을 사용할 수 있습니다.

- `POST /admin/movies`: 영화 등록
- `PUT /admin/movies/{id}`: 영화 수정
- `DELETE /admin/movies/{id}`: 영화 삭제
- `POST /admin/characters`: 캐릭터 등록
- `PUT /admin/characters/{id}`: 캐릭터/프롬프트 수정
- `GET /admin/stats`: 사용자·추천·인기 영화 등 서비스 통계

기존 로그인에서 저장한 access token과 refresh 흐름을 재사용합니다. 관리자 역할이 토큰에 포함되어 있으면 프론트에서 먼저 확인하며, 최종 권한 검사는 백엔드의 HTTP 401/403 응답을 따릅니다. 이 저장소에는 BE2 백엔드 소스가 없으므로 위 엔드포인트의 서버 구현 및 관리자 역할 발급은 백엔드 저장소에서 제공되어야 합니다.
