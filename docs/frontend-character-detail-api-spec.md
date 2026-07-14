# CineVerse 캐릭터 정보 조회 API 명세서

작성 기준: 2026-07-09  
기준 코드: `app/api/chat.py`, `app/services/character_service.py`  
Base URL: `http://127.0.0.1:8080`

## 1. API 요약

| 항목 | 값 |
| --- | --- |
| Method | `GET` |
| 현재 실제 Path | `/chatcharcter/{character_name}` |
| 인증 | 없음 |
| Content-Type | `application/json` |
| 설명 | 캐릭터 이름 또는 별칭으로 활성화된 캐릭터 단건 정보를 조회 |

주의: 현재 코드가 `@router.get("charcter/{character_name}")`로 작성되어 있어서 실제 OpenAPI 경로는 `/chatcharcter/{character_name}`입니다. 백엔드에서 라우트를 고치면 권장 경로는 `/chat/character/{character_name}`입니다.

## 2. 요청

### Path Parameter

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `character_name` | string | 예 | 캐릭터 이름 또는 등록된 별칭 |

요청 예시:

```http
GET /chatcharcter/토니%20스타크
```

프론트 예시:

```ts
const characterName = encodeURIComponent("토니 스타크");

const res = await fetch(
  `http://127.0.0.1:8080/chatcharcter/${characterName}`
);

const data = await res.json();
```

## 3. 성공 응답

```json
{
  "state": "success",
  "message": "캐릭터 정보 조회 성공",
  "data": {
    "id": 1,
    "name": "토니 스타크",
    "profile_image": "https://example.com/profile.jpg"
  }
}
```

### Response Data

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | number | 캐릭터 ID |
| `name` | string | 정식 캐릭터 이름 |
| `profile_image` | string \| null | 캐릭터 프로필 이미지 URL 또는 경로 |

참고: 단건 조회 API는 현재 `movie_title`을 반환하지 않습니다. `movie_title`이 필요하면 `GET /chat/characters` 목록 API에는 포함되어 있습니다.

## 4. 실패 응답

캐릭터 이름/별칭을 찾지 못한 경우:

```json
{
  "state": "failure",
  "message": "관련 캐릭터 정보가 없습니다."
}
```

별칭 변환은 됐지만 DB에서 활성 캐릭터 row를 찾지 못한 경우:

```json
{
  "state": "failure",
  "message": "DB에 캐릭터 관련 정보가 없습니다."
}
```

서버 처리 중 예외:

```json
{
  "state": "error",
  "message": "캐릭터 정보 조회 에러",
  "error": "..."
}
```

## 5. 프론트 연동 메모

| 상황 | 처리 |
| --- | --- |
| 현재 서버 호출 | `/chatcharcter/{encodeURIComponent(characterName)}` 사용 |
| 이름에 공백/한글 포함 | 반드시 `encodeURIComponent` 적용 |
| 성공 여부 판단 | `response.state === "success"` |
| 결과 없음 | `state: "failure"`이면 빈 상태 UI 처리 |
| 이미지 없음 | `profile_image === null` 가능성 방어 |

