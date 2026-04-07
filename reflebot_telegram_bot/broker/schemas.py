from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter

from reflebot_telegram_bot.api.schemas import BackendButton


class SendReflectionPromptCommand(BaseModel):
    event_type: Literal["send_reflection_prompt"]
    delivery_id: UUID
    student_id: UUID
    telegram_id: int
    lection_session_id: UUID
    message_text: str
    parse_mode: str | None = "HTML"
    buttons: list[BackendButton] = Field(default_factory=list)
    scheduled_for: datetime | None = None


class UpdateReflectionPromptCommand(BaseModel):
    event_type: Literal["update_reflection_prompt"]
    delivery_id: UUID
    telegram_id: int
    telegram_message_id: int
    message_text: str
    student_id: UUID | None = None
    lection_session_id: UUID | None = None
    parse_mode: str | None = "HTML"
    buttons: list[BackendButton] = Field(default_factory=list)


ReflectionPromptCommand = SendReflectionPromptCommand | UpdateReflectionPromptCommand
reflection_prompt_command_adapter = TypeAdapter(ReflectionPromptCommand)


class ReflectionPromptResultEvent(BaseModel):
    event_type: Literal["reflection_prompt_result"] = "reflection_prompt_result"
    delivery_id: UUID
    success: bool
    sent_at: datetime | None = None
    telegram_message_id: int | None = None
    error: str | None = None
