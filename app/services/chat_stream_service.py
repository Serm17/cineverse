import json

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai_client.chat import stream_character_chat
from app.repsitories.chat_repository import create_message, create_room, get_room_messages, get_room_user, make_ai_history
from app.schemas.chat import CharacterChatRequest, SendChatMessageRequest
from app.services.character_service import get_active_character


# stream 끝난 캐릭터 답변 저장
async def stream_and_save_character_answer(
        db:Session,
        room_id : int,
        message : str,
        history : list[dict],
        character : str,
):
    answer_parts = []
    try:
        async for chunk in stream_character_chat(message, history, character):
            yield chunk

            if chunk.startswith("data: "):
                data = chunk.removeprefix("data: ").strip()

                if data == "[DONE]":
                    continue

                try:
                    parsed = json.loads(data)

                    if isinstance(parsed, str):
                        answer_parts.append(parsed)
                    elif isinstance(parsed, dict) and "error" not in parsed:
                        answer_parts.append(parsed.get("answer", ""))
                except json.JSONDecodeError:
                    answer_parts.append(data)
    finally :
        # 스트림 정상 종료시 모아둔 답변 assistant 메시지로 저장
        answer = "".join(answer_parts).strip()
        if answer:
            create_message(db, room_id, "assistant", answer, character)
            db.commit()

def make_streaming_response(generator):
    return StreamingResponse(
        generator,
        media_type = "text/event-stream",
        headers ={
            "Cache-Control" : "no-cache",
            "X-Accel-Buffering" : "no",
        },
    )

async def start_character_chat_stream(db: Session, user_id: int, request: CharacterChatRequest):
    # 새 1대1 캐릭터 스트림 채팅방 생성
    message = request.message.strip()

    if not message:
        return {
            "state": "failure",
            "message": "내용을 입력해주세요.",
        }

    # 별칭을 정식 캐릭터명으로 변환
    character = get_active_character(db, request.character)

    if character is None:
        return {
            "state": "failure",
            "message": "지원하지 않는 캐릭터입니다.",
            "data": {
                "character": request.character,
            },
        }

    # 스트림은 캐릭터 대화 전용이므로 character 방으로 생성
    room = create_room(db, user_id, character)

    # 새 방이라 이전 히스토리는 없음
    history = []

    # 사용자 메시지는 먼저 저장
    create_message(
        db=db,
        room_id=room.id,
        role="user",
        content=message,
    )
    db.commit()

    return make_streaming_response(
        stream_and_save_character_answer(
            db=db,
            room_id=room.id,
            message=message,
            history=history,
            character=character,
        )
    )

async def continue_chat_stream(db: Session, user_id: int, room_id: int, request: SendChatMessageRequest):
    # 기존 채팅방에서 스트림으로 이어서 대화
    message = request.content.strip()

    if not message:
        return {
            "state": "failure",
            "message": "내용을 입력해주세요.",
        }

    room = get_room_user(db, room_id, user_id)

    if not room:
        return {
            "state": "failure",
            "message": "채팅방을 찾을 수 없습니다.",
        }

    # AI /chat/stream은 그룹 채팅 미지원
    if room.room_type == "group":
        return {
            "state": "failure",
            "message": "그룹 채팅은 스트리밍을 지원하지 않습니다.",
        }

    # 요청에 캐릭터가 있으면 그 캐릭터로 변경
    if request.character:
        character = get_active_character(db, request.character)

        if character is None:
            return {
                "state": "failure",
                "message": "지원하지 않는 캐릭터입니다.",
                "data": {
                    "character": request.character,
                },
            }

        current_character = room.characters[0] if room.characters else None

        if character != current_character:
            room.characters = [character]
    else:
        character = room.characters[0] if room.characters else None

    # 스트림은 character 필수
    if not character:
        return {
            "state": "failure",
            "message": "스트리밍 채팅은 캐릭터가 필요합니다.",
        }

    previous_messages = get_room_messages(db, room.id)
    history = make_ai_history(previous_messages)

    create_message(
        db=db,
        room_id=room.id,
        role="user",
        content=message,
    )
    db.commit()

    return make_streaming_response(
        stream_and_save_character_answer(
            db=db,
            room_id=room.id,
            message=message,
            history=history,
            character=character,
        )
    )
