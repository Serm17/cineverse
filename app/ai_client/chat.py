from app.ai_client.base import post_ai


# AI 서버의 POST /chat/auto API 호출
# 기본 AI 채팅, 캐릭터 AI 채팅, 그룹 AI 채팅 모두 자동 분류용
async def request_ai_chat(
    message: str,
    history: list[dict],
    character: str | None = None,
) -> dict:
    payload = {
        "message" : message,
        "history" : history
    }
    # 캐릭터가 있는 경우
    if character: payload["character"] = character
    return await post_ai("/chat/auto", payload)

# 특정 캐릭터와 1:1 대화용
async def request_character_chat(
    message: str,
    history: list[dict],
    character: str,
) -> dict:
    payload = {
        "message" : message,
        "history" : history,
        "character" : character
    }
    return await post_ai("/chat", payload)

# 그룹 채팅용
async def request_group_chat(
    characters: list[str],
    message: str,
    history: list[dict],
) -> dict:
    payload = {
        "characters": characters,
        "message": message,
        "history": history,
    }
    return await post_ai("/chat/group", payload)