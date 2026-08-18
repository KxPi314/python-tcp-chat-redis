import json
from pydantic import BaseModel, Field, ValidationError
from typing import Any

chat_name_regex = r'^[^\s]+$'
username_regex = r'^[A-Za-z0-9_-]{1,16}$'
password_regex = r'^[^\s]{8,64}$'

class LoginArgs(BaseModel):
    username: str = Field(..., pattern=username_regex)
    password: str = Field(..., pattern=password_regex)

class RegisterArgs(BaseModel):
    username: str = Field(..., pattern=username_regex)
    password: str = Field(..., pattern=password_regex)

class MsgArgs(BaseModel):
    text: str
    to_chat: str  = Field(..., pattern=chat_name_regex)

class NewChatArgs(BaseModel):
    chat_name: str = Field(..., pattern=chat_name_regex)
    members: list[str] = Field(..., max_length=50)

class DelAccountArgs(BaseModel):
    reason: str

class AddToChatArgs(BaseModel):
    chat_name: str = Field(..., pattern=chat_name_regex)
    user_name: str = Field(..., pattern=username_regex)

class DelFromChatArgs(BaseModel):
    chat_name: str = Field(..., pattern=chat_name_regex)
    user_name: str = Field(..., pattern=username_regex)

class ChatSyncArgs(BaseModel):
    chat_name: str = Field(..., pattern=chat_name_regex)
    limit: int = Field(20, ge=1, le=100)
    newest_message_id_known: str

class ChatHistoryArgs(BaseModel):
    chat_name: str = Field(..., pattern=chat_name_regex)
    limit: int = Field(20, ge=1, le=100)
    last_message_id_seen: str

class ChatMembersListArgs(BaseModel):
    chat_name: str

class EmptyArgs(BaseModel):
    pass

class Request(BaseModel):
    token: str | None = None
    action: str
    payload: Any
    
MODELS = {
    'msg': MsgArgs,
    'login': LoginArgs,
    'register' : RegisterArgs,
    'new_chat': NewChatArgs,
    'delete_account': DelAccountArgs,
    'add_to_chat' : AddToChatArgs,
    'del_from_chat' : DelFromChatArgs,
    'sync_chat' : ChatSyncArgs,
    'chat_history': ChatHistoryArgs,
    'chat_members_list': ChatMembersListArgs,
    'users_list': EmptyArgs,
    'chats_list': EmptyArgs
}


def check_request(size: int, request: str):
    if len(request.encode('utf-8')) != size:
        return False, "request length Error"
    try:
        envelope = Request.model_validate_json(request)
        model = MODELS.get(envelope.action)
        if not model:
            return False, "unknown action Error"
        validated_payload = model.model_validate(envelope.payload)
        envelope.payload = validated_payload
        return True, envelope
    except ValidationError as e:
        return False, f"validation Error: {e.json()}"
    except json.JSONDecodeError:
        return False, "JSON format Error"