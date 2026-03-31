from __future__ import annotations

from reflebot_telegram_bot.api.schemas import ActionResponse, BackendButton, BackendFile, DialogMessage
from reflebot_telegram_bot.broker.schemas import ReflectionPromptCommand
from reflebot_telegram_bot.core.models import (
    PlatformButton,
    PlatformMedia,
    PlatformMessage,
    PlatformMessageBatch,
)


class ResponsePlanner:
    def from_backend_response(
        self,
        response: ActionResponse,
        *,
        edit_target_message_id: str | None = None,
    ) -> PlatformMessageBatch:
        primary = PlatformMessage(
            text=response.message,
            parse_mode=response.parse_mode,
            buttons=self._map_buttons(response.buttons),
            media=self._map_files(response.files),
            edit_target_message_id=edit_target_message_id,
        )
        follow_up = [
            PlatformMessage(
                text=dialog.message,
                parse_mode=dialog.parse_mode or response.parse_mode,
                buttons=self._map_buttons(dialog.buttons),
                media=self._map_files(dialog.files),
            )
            for dialog in response.dialog_messages
        ]
        return PlatformMessageBatch(primary_message=primary, follow_up_messages=follow_up)

    def from_reflection_prompt(self, command: ReflectionPromptCommand) -> PlatformMessageBatch:
        primary = PlatformMessage(
            text=command.message_text,
            parse_mode=command.parse_mode,
            buttons=self._map_buttons(command.buttons),
        )
        return PlatformMessageBatch(primary_message=primary)

    @staticmethod
    def error_batch(message_text: str) -> PlatformMessageBatch:
        return PlatformMessageBatch(primary_message=PlatformMessage(text=message_text))

    @staticmethod
    def _map_buttons(buttons: list[BackendButton]) -> list[PlatformButton]:
        return [PlatformButton(text=button.text, action=button.action) for button in buttons]

    @staticmethod
    def _map_files(files: list[BackendFile]) -> list[PlatformMedia]:
        return [
            PlatformMedia(
                kind=backend_file.kind,
                platform_file_ref=backend_file.telegram_file_id,
            )
            for backend_file in files
        ]
