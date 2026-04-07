from __future__ import annotations

from pydantic import BaseModel, Field


class BackendButton(BaseModel):
    text: str
    action: str | None = None
    url: str | None = None


class BackendFile(BaseModel):
    telegram_file_id: str
    kind: str


class DialogMessage(BaseModel):
    message: str | None = None
    parse_mode: str | None = None
    buttons: list[BackendButton] = Field(default_factory=list)
    files: list[BackendFile] = Field(default_factory=list)


class MessageTracking(BaseModel):
    tracking_key: str


class ActionResponse(BaseModel):
    message: str | None = None
    parse_mode: str | None = None
    buttons: list[BackendButton] = Field(default_factory=list)
    files: list[BackendFile] = Field(default_factory=list)
    dialog_messages: list[DialogMessage] = Field(default_factory=list)
    awaiting_input: bool = False
    message_tracking: MessageTracking | None = None


class LoginRequest(BaseModel):
    telegram_id: int
    invite_token: str | None = None


class LoginResponse(ActionResponse):
    full_name: str | None = None
    telegram_username: str | None = None
    telegram_id: int | None = None
    is_active: bool = True
    is_admin: bool = False
    is_teacher: bool = False
    is_student: bool = False


class TextActionRequest(BaseModel):
    text: str


class MessageDeliveredRequest(BaseModel):
    tracking_key: str
    telegram_message_id: int


class BackendError(BaseModel):
    detail: str
    error_code: str | None = None
